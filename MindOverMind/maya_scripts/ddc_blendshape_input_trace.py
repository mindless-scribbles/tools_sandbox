"""
Export Blendshape Control Schema to CSV
========================================
Given a mesh with blendshapes, traces the full control wiring for each target:
  - Which controller attribute drives each shape
  - Whether the shape is a corrective (driven by multiple inputs)
  - The driving method (direct connection, SDK, expression, etc.)
  - For correctives: the input driver shapes/attributes and combination logic
  - For SDKs: the actual keyframe mapping values for reconstruction

Output CSV is structured for rebuilding the control schema in Unreal Control Rig.

Usage:
    1. Select a mesh that has blendshape deformers
    2. Run this script in Maya's Script Editor (Python tab)
    3. A file dialog will prompt for the CSV save location

Alternatively, call from code:
    from export_blendshape_schema import export_blendshape_schema
    export_blendshape_schema("myMesh")
"""

import maya.cmds as cmds
import csv
import os


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def get_blendshape_nodes(mesh):
    """Return all blendShape nodes connected to a mesh's deformation chain."""
    history = cmds.listHistory(mesh, pruneDagObjects=True) or []
    return [n for n in history if cmds.nodeType(n) == "blendShape"]


def get_target_info(bs_node):
    """
    Return a list of dicts for each blendshape target:
      { 'index': int, 'name': str, 'weight_attr': str }
    """
    aliases = cmds.aliasAttr(bs_node, query=True) or []
    targets = []
    for i in range(0, len(aliases), 2):
        alias_name = aliases[i]
        weight_attr = aliases[i + 1]  # e.g. "weight[3]"
        idx = int(weight_attr.split("[")[1].rstrip("]"))
        targets.append({
            "index": idx,
            "name": alias_name,
            "weight_attr": "{}.{}".format(bs_node, alias_name),
        })
    return targets


def get_sdk_keyframe_data(curve_node):
    """
    Extract keyframe values from a set driven key curve.
    Returns a string like: "keys: (0.0 -> 0.0), (1.0 -> 1.0)"
    This is the critical mapping data needed to recreate the SDK in Control Rig.
    """
    try:
        num_keys = cmds.keyframe(curve_node, query=True, keyframeCount=True) or 0
        if num_keys == 0:
            return ""
        sdk_input_values = cmds.keyframe(
            curve_node, query=True, floatChange=True
        ) or []
        sdk_output_values = cmds.keyframe(
            curve_node, query=True, valueChange=True
        ) or []
        if sdk_input_values and sdk_output_values:
            pairs = []
            for input_val, output_val in zip(sdk_input_values, sdk_output_values):
                pairs.append("({} -> {})".format(round(input_val, 4), round(output_val, 4)))
            return "keys: {}".format(", ".join(pairs))
    except Exception:
        cmds.warning("WARNING: get_sdk_keyframe_data - failed to read keyframes on {}".format(curve_node))
    return ""


def get_pose_interpolator_drivers(psi_node):
    """Extract the driver transforms/joints feeding a poseInterpolator."""
    drivers = []
    driver_slot_indices = cmds.getAttr(psi_node + ".driver", multiIndices=True) or []
    for driver_slot_idx in driver_slot_indices:
        driver_matrix_conns = cmds.listConnections(
            "{}.driver[{}].driverMatrix".format(psi_node, driver_slot_idx),
            source=True, destination=False, plugs=True
        ) or []
        if driver_matrix_conns:
            drivers.append(driver_matrix_conns[0].split(".")[0])
    return list(dict.fromkeys(drivers))


def get_pose_interpolator_poses(psi_node):
    """
    Extract pose names and their driver values from a poseInterpolator.
    Returns a summary string describing each stored pose.
    """
    try:
        pose_slot_indices = cmds.getAttr(
            psi_node + ".pose", multiIndices=True
        ) or []
        pose_info = []
        for pose_slot_idx in pose_slot_indices:
            # Try to get the pose name
            try:
                pose_name = cmds.getAttr(
                    "{}.pose[{}].poseName".format(psi_node, pose_slot_idx)
                ) or "pose_{}".format(pose_slot_idx)
            except Exception:
                cmds.warning("WARNING: get_pose_interpolator_poses - could not read poseName for pose {} on {}".format(pose_slot_idx, psi_node))
                pose_name = "pose_{}".format(pose_slot_idx)
            pose_info.append(pose_name)
        if pose_info:
            return "Poses: {}".format(", ".join(pose_info))
    except Exception:
        cmds.warning("WARNING: get_pose_interpolator_poses - failed to read poses on {}".format(psi_node))
    return ""


def get_combination_shape_inputs(combo_node):
    """Extract the input weight attributes feeding a combinationShape node."""
    inputs = []
    input_weight_indices = cmds.getAttr(
        combo_node + ".inputWeight", multiIndices=True
    ) or []
    for input_weight_idx in input_weight_indices:
        input_weight_conns = cmds.listConnections(
            "{}.inputWeight[{}]".format(combo_node, input_weight_idx),
            source=True, destination=False, plugs=True,
            skipConversionNodes=True
        ) or []
        inputs.extend(input_weight_conns)
    return inputs


def trace_driver_chain(attr, depth=0, max_depth=20, visited=None):
    """
    Recursively trace upstream connections from a blendshape weight attribute.

    Walks the dependency graph upstream via recursive calls, using a visited
    set for cycle detection to avoid infinite loops in circular wiring.

    Args:
        attr: The Maya attribute plug string to trace (e.g. "blendShape1.jawOpen").
        depth: Current recursion depth (used internally).
        max_depth: Maximum recursion depth before bailing out. Defaults to 20.
        visited: Set of already-visited attributes for cycle detection (used internally).

    Returns:
        list[dict]: Driver records, each containing: driver_node, driver_attr,
        driver_type, method, details, upstream_controllers.
    """
    if visited is None:
        visited = set()
    if attr in visited or depth > max_depth:
        return []
    visited.add(attr)

    records = []
    connections = cmds.listConnections(
        attr, source=True, destination=False,
        plugs=True, skipConversionNodes=True
    ) or []

    if not connections:
        return []

    for src_plug in connections:
        src_node = src_plug.split(".")[0]
        src_type = cmds.nodeType(src_node)

        record = {
            "driver_node": src_node,
            "driver_attr": src_plug,
            "driver_type": src_type,
            "method": "directConnection",
            "details": "",
            "upstream_controllers": [],
        }

        # ----- Set Driven Key (animCurveU*) -----
        if src_type.startswith("animCurveU"):
            record["method"] = "setDrivenKey"
            sdk_inputs = cmds.listConnections(
                src_node + ".input", source=True,
                destination=False, plugs=True,
                skipConversionNodes=True
            ) or []
            if sdk_inputs:
                record["details"] = "SDK input: {}".format(sdk_inputs[0])
                record["upstream_controllers"] = [sdk_inputs[0]]
                for inp in sdk_inputs:
                    upstream = trace_driver_chain(
                        inp, depth + 1, max_depth, visited
                    )
                    for u in upstream:
                        record["upstream_controllers"].extend(
                            u.get("upstream_controllers", [])
                        )
            else:
                record["details"] = (
                    "SDK curve, no connected input (possibly baked)"
                )
            # Append the actual key data for SDK reconstruction
            sdk_keys = get_sdk_keyframe_data(src_node)
            if sdk_keys:
                record["details"] += " | " + sdk_keys

        # ----- Regular animCurve (timeline animation) -----
        elif src_type.startswith("animCurve"):
            record["method"] = "animCurve"
            record["details"] = "Timeline anim curve: {}".format(src_node)

        # ----- Expression -----
        elif src_type == "expression":
            expr_string = cmds.getAttr(src_node + ".expression") or ""
            short_expr = expr_string.replace("\n", " ").strip()
            if len(short_expr) > 200:
                short_expr = short_expr[:200] + "..."
            record["method"] = "expression"
            record["details"] = "Expression: {}".format(short_expr)

        # ----- Pose Interpolator (PSD corrective system) -----
        elif src_type == "poseInterpolator":
            record["method"] = "poseInterpolator"
            pose_drivers = get_pose_interpolator_drivers(src_node)
            pose_info = get_pose_interpolator_poses(src_node)
            details_parts = []
            if pose_drivers:
                details_parts.append(
                    "PSD drivers: {}".format(", ".join(pose_drivers))
                )
            if pose_info:
                details_parts.append(pose_info)
            record["details"] = " | ".join(details_parts) if details_parts else "unknown"
            record["upstream_controllers"] = pose_drivers

        # ----- combinationShape node -----
        elif src_type == "combinationShape":
            record["method"] = "combinationShape"
            combo_inputs = get_combination_shape_inputs(src_node)
            # Also get the combination mode (multiply vs. lowest)
            try:
                combo_type = cmds.getAttr(src_node + ".combinationType")
                combo_type_name = {0: "lowest", 1: "multiply"}.get(
                    combo_type, str(combo_type)
                )
            except Exception:
                combo_type_name = "unknown"
            record["details"] = "Combo mode: {}, inputs: {}".format(
                combo_type_name,
                ", ".join(combo_inputs) if combo_inputs else "unknown",
            )
            record["upstream_controllers"] = combo_inputs

        # ----- remapValue -----
        elif src_type == "remapValue":
            record["method"] = "remapValue"
            remap_inputs = cmds.listConnections(
                src_node + ".inputValue", source=True,
                destination=False, plugs=True,
                skipConversionNodes=True
            ) or []
            # Get the input/output min/max for reconstruction
            try:
                in_min = cmds.getAttr(src_node + ".inputMin")
                in_max = cmds.getAttr(src_node + ".inputMax")
                out_min = cmds.getAttr(src_node + ".outputMin")
                out_max = cmds.getAttr(src_node + ".outputMax")
                remap_range = "range: [{},{}] -> [{},{}]".format(
                    round(in_min, 4), round(in_max, 4),
                    round(out_min, 4), round(out_max, 4),
                )
            except Exception:
                remap_range = ""
            record["details"] = "Remap from: {} | {}".format(
                remap_inputs[0] if remap_inputs else "unknown",
                remap_range,
            )
            if remap_inputs:
                record["upstream_controllers"] = [remap_inputs[0]]
                upstream = trace_driver_chain(
                    remap_inputs[0], depth + 1, max_depth, visited
                )
                for u in upstream:
                    record["upstream_controllers"].extend(
                        u.get("upstream_controllers", [])
                    )

        # ----- clamp -----
        elif src_type == "clamp":
            record["method"] = "clamp"
            clamp_inputs = cmds.listConnections(
                src_node, source=True,
                destination=False, plugs=True,
                skipConversionNodes=True
            ) or []
            try:
                clamp_min = cmds.getAttr(src_node + ".min")
                clamp_max = cmds.getAttr(src_node + ".max")
                clamp_range = "clamp: [{}, {}]".format(clamp_min, clamp_max)
            except Exception:
                clamp_range = ""
            record["details"] = "Inputs: {} | {}".format(
                ", ".join(clamp_inputs), clamp_range
            )
            record["upstream_controllers"] = clamp_inputs

        # ----- multiplyDivide -----
        elif src_type == "multiplyDivide":
            record["method"] = "multiplyDivide"
            md_inputs = cmds.listConnections(
                src_node, source=True,
                destination=False, plugs=True,
                skipConversionNodes=True
            ) or []
            try:
                op = cmds.getAttr(src_node + ".operation")
                op_name = {
                    1: "multiply", 2: "divide", 3: "power"
                }.get(op, str(op))
            except Exception:
                op_name = "unknown"
            record["details"] = "Op: {}, inputs: {}".format(
                op_name, ", ".join(md_inputs)
            )
            record["upstream_controllers"] = md_inputs
            for inp in md_inputs:
                upstream = trace_driver_chain(
                    inp, depth + 1, max_depth, visited
                )
                for u in upstream:
                    record["upstream_controllers"].extend(
                        u.get("upstream_controllers", [])
                    )

        # ----- plusMinusAverage -----
        elif src_type == "plusMinusAverage":
            record["method"] = "plusMinusAverage"
            pma_inputs = cmds.listConnections(
                src_node, source=True,
                destination=False, plugs=True,
                skipConversionNodes=True
            ) or []
            op = cmds.getAttr(src_node + ".operation")
            op_names = {1: "sum", 2: "subtract", 3: "average"}
            record["details"] = "Op: {}, inputs: {}".format(
                op_names.get(op, str(op)), ", ".join(pma_inputs)
            )
            record["upstream_controllers"] = pma_inputs
            for inp in pma_inputs:
                upstream = trace_driver_chain(
                    inp, depth + 1, max_depth, visited
                )
                for u in upstream:
                    record["upstream_controllers"].extend(
                        u.get("upstream_controllers", [])
                    )

        # ----- condition -----
        elif src_type == "condition":
            record["method"] = "condition"
            cond_inputs = cmds.listConnections(
                src_node, source=True,
                destination=False, plugs=True,
                skipConversionNodes=True
            ) or []
            try:
                cond_op = cmds.getAttr(src_node + ".operation")
                cond_op_name = {
                    0: "equal", 1: "notEqual", 2: "greaterThan",
                    3: "greaterOrEqual", 4: "lessThan", 5: "lessOrEqual",
                }.get(cond_op, str(cond_op))
            except Exception:
                cond_op_name = "unknown"
            record["details"] = "Condition: {}, inputs: {}".format(
                cond_op_name, ", ".join(cond_inputs)
            )
            record["upstream_controllers"] = cond_inputs

        # ----- transform / joint (direct controller attr) -----
        elif src_type in ("transform", "joint", "nurbsCurve"):
            record["method"] = "directConnection"
            record["details"] = "Controller attr: {}".format(src_plug)
            record["upstream_controllers"] = [src_plug]

        # ----- Fallback: any other utility node, keep tracing -----
        else:
            record["method"] = src_type
            generic_inputs = cmds.listConnections(
                src_node, source=True,
                destination=False, plugs=True,
                skipConversionNodes=True
            ) or []
            record["details"] = "Type: {}, inputs: {}".format(
                src_type, ", ".join(generic_inputs)
            )
            record["upstream_controllers"] = generic_inputs
            for inp in generic_inputs:
                upstream = trace_driver_chain(
                    inp, depth + 1, max_depth, visited
                )
                for u in upstream:
                    record["upstream_controllers"].extend(
                        u.get("upstream_controllers", [])
                    )

        # Deduplicate upstream controllers while preserving order
        record["upstream_controllers"] = list(
            dict.fromkeys(record["upstream_controllers"])
        )
        records.append(record)

    return records


def classify_shape(target_name, driver_records):
    """
    Classify a shape based on its drivers:
      primary, combo_corrective, psd_corrective,
      likely_corrective, named_corrective, undriven
    """
    methods = {r["method"] for r in driver_records}

    if "combinationShape" in methods:
        return "combo_corrective"
    if "poseInterpolator" in methods:
        return "psd_corrective"

    corrective_hints = [
        "_combo", "_corrective", "_fix", "Combo", "Corrective",
        "_psd", "_PSD", "_corr", "_crt",
    ]
    for hint in corrective_hints:
        if hint in target_name:
            all_upstream = []
            for r in driver_records:
                all_upstream.extend(r.get("upstream_controllers", []))
            if len(set(all_upstream)) > 1:
                return "likely_corrective"
            return "named_corrective"

    return "primary"


# ---------------------------------------------------------------------------
# Main export function
# ---------------------------------------------------------------------------

def export_blendshape_schema(mesh=None, output_path=None):
    """
    Export the complete blendshape control schema for a mesh to CSV.

    Parameters:
        mesh (str): The mesh transform name. If None, uses current selection.
        output_path (str): CSV file path. If None, opens a file dialog.

    Returns:
        str: Path to the written CSV file.
    """
    # Resolve mesh
    if mesh is None:
        sel = cmds.ls(selection=True, long=False)
        if not sel:
            cmds.warning(
                "No mesh selected. Select a mesh with blendshapes."
            )
            return None
        mesh = sel[0]

    # Get blendshape nodes
    bs_nodes = get_blendshape_nodes(mesh)
    if not bs_nodes:
        cmds.warning("No blendShape nodes found on '{}'.".format(mesh))
        return None

    print("Found blendShape nodes: {}".format(", ".join(bs_nodes)))

    # Resolve output path
    if output_path is None:
        output_path = cmds.fileDialog2(
            fileFilter="CSV Files (*.csv)",
            dialogStyle=2,
            caption="Save Blendshape Schema CSV",
            fileMode=0,
        )
        if not output_path:
            print("Export cancelled.")
            return None
        output_path = output_path[0]

    # Collect all rows
    rows = []

    for bs_node in bs_nodes:
        targets = get_target_info(bs_node)
        print("Processing '{}': {} targets".format(bs_node, len(targets)))

        for target in targets:
            t_name = target["name"]
            t_attr = target["weight_attr"]
            t_idx = target["index"]

            try:
                current_val = cmds.getAttr(t_attr)
            except Exception:
                current_val = 0.0

            driver_records = trace_driver_chain(t_attr)
            shape_class = classify_shape(t_name, driver_records)

            if driver_records:
                for dr in driver_records:
                    controllers = dr.get("upstream_controllers", [])
                    controllers_str = (
                        " | ".join(controllers) if controllers
                        else dr["driver_attr"]
                    )
                    rows.append({
                        "blendshape_node": bs_node,
                        "target_name": t_name,
                        "target_index": t_idx,
                        "shape_classification": shape_class,
                        "driving_method": dr["method"],
                        "immediate_driver_node": dr["driver_node"],
                        "immediate_driver_attr": dr["driver_attr"],
                        "immediate_driver_type": dr["driver_type"],
                        "ultimate_controller_attrs": controllers_str,
                        "details": dr["details"],
                        "current_weight": round(current_val, 4),
                    })
            else:
                rows.append({
                    "blendshape_node": bs_node,
                    "target_name": t_name,
                    "target_index": t_idx,
                    "shape_classification": "undriven",
                    "driving_method": "none",
                    "immediate_driver_node": "",
                    "immediate_driver_attr": "",
                    "immediate_driver_type": "",
                    "ultimate_controller_attrs": "",
                    "details": "No incoming connections found",
                    "current_weight": round(current_val, 4),
                })

    # Write CSV
    fieldnames = [
        "blendshape_node",
        "target_name",
        "target_index",
        "shape_classification",
        "driving_method",
        "immediate_driver_node",
        "immediate_driver_attr",
        "immediate_driver_type",
        "ultimate_controller_attrs",
        "details",
        "current_weight",
    ]

    with open(output_path, "w") as f:
        writer = csv.DictWriter(
            f, fieldnames=fieldnames, lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)

    print("=" * 60)
    print("Exported {} rows to: {}".format(len(rows), output_path))
    print("=" * 60)

    # Summary
    classifications = {}
    for r in rows:
        c = r["shape_classification"]
        classifications[c] = classifications.get(c, 0) + 1
    print("\nShape classification summary:")
    for cls, count in sorted(classifications.items()):
        print("  {}: {}".format(cls, count))

    methods = {}
    for r in rows:
        m = r["driving_method"]
        methods[m] = methods.get(m, 0) + 1
    print("\nDriving method summary:")
    for m, count in sorted(methods.items()):
        print("  {}: {}".format(m, count))

    return output_path


# ---------------------------------------------------------------------------
# Run on execute
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    export_blendshape_schema()
