"""
CSV-to-JSON Converter for Control Rig Pipeline
================================================
Converts the flat CSV exported by ddc_blendshape_input_trace.py into a
structured JSON file suitable for the Unreal Control Rig builder.

The CSV is human-editable (fix classifications, add/remove rows) before
conversion. This module parses pipe-delimited lists, embedded keyframe
data, and string-encoded details into typed Python dicts.

Usage (CLI):
    python csv_to_control_rig_json.py input.csv [output.json]

Usage (import):
    from MindOverMind.pipeline.csv_to_control_rig_json import convert_csv_to_control_rig_json
    convert_csv_to_control_rig_json("schema.csv", "schema.json")
"""

import csv
import json
import os
import re
import sys
from datetime import datetime


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EXPECTED_FIELDNAMES = [
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


# ---------------------------------------------------------------------------
# Row validation
# ---------------------------------------------------------------------------

def validate_csv_row(csv_row, row_number):
    """
    Check that a CSV row has the minimum required fields for conversion.

    Args:
        csv_row: A dict from csv.DictReader representing one CSV row.
        row_number: The 1-based row number in the CSV (for warning messages).

    Returns:
        bool: True if the row is usable, False if it should be skipped.
    """
    required_fields = ["blendshape_node", "target_name", "driving_method"]
    for field in required_fields:
        if not csv_row.get(field, "").strip():
            print("WARNING: validate_csv_row - missing '{}' on row {}".format(
                field, row_number
            ))
            return False
    return True


# ---------------------------------------------------------------------------
# Detail parsers (one per driving_method)
# ---------------------------------------------------------------------------

def parse_sdk_details(details_string):
    """
    Parse setDrivenKey details into structured data.

    Expects format: "SDK input: ctrl.attr | keys: (0.0 -> 0.0), (1.0 -> 1.0)"

    Args:
        details_string: The raw details string from the CSV.

    Returns:
        dict: {"sdk_input": str, "keyframes": [{"input": float, "output": float}, ...]}
    """
    parsed = {}

    # Extract SDK input attribute
    sdk_input_match = re.search(r"SDK input:\s*(\S+)", details_string)
    parsed["sdk_input"] = sdk_input_match.group(1) if sdk_input_match else ""

    # Extract keyframe pairs: (float -> float)
    keyframe_matches = re.findall(
        r"\(([+-]?\d+(?:\.\d+)?)\s*->\s*([+-]?\d+(?:\.\d+)?)\)",
        details_string,
    )
    parsed["keyframes"] = [
        {"input": float(input_val), "output": float(output_val)}
        for input_val, output_val in keyframe_matches
    ]

    return parsed


def parse_psd_details(details_string):
    """
    Parse poseInterpolator details into driver list and pose names.

    Expects format: "PSD drivers: joint1, joint2 | Poses: rest, poseA, poseB"

    Args:
        details_string: The raw details string from the CSV.

    Returns:
        dict: {"psd_drivers": [str, ...], "poses": [str, ...]}
    """
    parsed = {"psd_drivers": [], "poses": []}

    driver_match = re.search(r"PSD drivers:\s*(.+?)(?:\s*\||$)", details_string)
    if driver_match:
        parsed["psd_drivers"] = [
            driver.strip() for driver in driver_match.group(1).split(",")
            if driver.strip()
        ]

    pose_match = re.search(r"Poses:\s*(.+)", details_string)
    if pose_match:
        parsed["poses"] = [
            pose.strip() for pose in pose_match.group(1).split(",")
            if pose.strip()
        ]

    return parsed


def parse_combo_details(details_string):
    """
    Parse combinationShape details into combo mode and input shapes.

    Expects format: "Combo mode: multiply, inputs: nodeA.attr, nodeB.attr"

    Args:
        details_string: The raw details string from the CSV.

    Returns:
        dict: {"combo_mode": str, "combo_inputs": [str, ...]}
    """
    parsed = {"combo_mode": "", "combo_inputs": []}

    mode_match = re.search(r"Combo mode:\s*(\w+)", details_string)
    if mode_match:
        parsed["combo_mode"] = mode_match.group(1)

    inputs_match = re.search(r"inputs:\s*(.+)", details_string)
    if inputs_match:
        parsed["combo_inputs"] = [
            combo_input.strip()
            for combo_input in inputs_match.group(1).split(",")
            if combo_input.strip()
        ]

    return parsed


def parse_remap_details(details_string):
    """
    Parse remapValue details into source attribute and remap range.

    Expects format: "Remap from: ctrl.attr | range: [0,1] -> [0,1]"

    Args:
        details_string: The raw details string from the CSV.

    Returns:
        dict: {"remap_source": str, "input_min": float, "input_max": float,
               "output_min": float, "output_max": float}
    """
    parsed: dict[str, str | float] = {"remap_source": ""}

    source_match = re.search(r"Remap from:\s*(\S+)", details_string)
    if source_match:
        parsed["remap_source"] = source_match.group(1)

    range_match = re.search(
        r"range:\s*\[([+-]?\d+(?:\.\d+)?),\s*([+-]?\d+(?:\.\d+)?)\]"
        r"\s*->\s*\[([+-]?\d+(?:\.\d+)?),\s*([+-]?\d+(?:\.\d+)?)\]",
        details_string,
    )
    if range_match:
        parsed["input_min"] = float(range_match.group(1))
        parsed["input_max"] = float(range_match.group(2))
        parsed["output_min"] = float(range_match.group(3))
        parsed["output_max"] = float(range_match.group(4))

    return parsed


def parse_math_node_details(details_string):
    """
    Shared parser for clamp, multiplyDivide, and plusMinusAverage details.

    Expects format: "Op: multiply, inputs: nodeA.attr, nodeB.attr"
    or for clamp:   "Inputs: nodeA.attr | clamp: [[0,0,0], [1,1,1]]"

    Args:
        details_string: The raw details string from the CSV.

    Returns:
        dict: {"operation": str, "math_inputs": [str, ...]}
              For clamp: {"clamp_inputs": [str, ...], "clamp_range": [str, ...]}
    """
    # Clamp has a different format
    if "clamp:" in details_string.lower():
        parsed = {"clamp_inputs": [], "clamp_range": []}

        inputs_match = re.search(r"Inputs:\s*(.+?)(?:\s*\||$)", details_string)
        if inputs_match:
            parsed["clamp_inputs"] = [
                clamp_input.strip()
                for clamp_input in inputs_match.group(1).split(",")
                if clamp_input.strip()
            ]

        clamp_match = re.search(r"clamp:\s*(.+)", details_string)
        if clamp_match:
            clamp_values = re.findall(
                r"[+-]?\d+(?:\.\d+)?", clamp_match.group(1)
            )
            parsed["clamp_range"] = [float(val) for val in clamp_values]

        return parsed

    # multiplyDivide / plusMinusAverage
    parsed = {"operation": "", "math_inputs": []}

    op_match = re.search(r"Op:\s*(\w+)", details_string)
    if op_match:
        parsed["operation"] = op_match.group(1)

    inputs_match = re.search(r"inputs:\s*(.+)", details_string)
    if inputs_match:
        parsed["math_inputs"] = [
            math_input.strip()
            for math_input in inputs_match.group(1).split(",")
            if math_input.strip()
        ]

    return parsed


def parse_condition_details(details_string):
    """
    Parse condition node details into operation and inputs.

    Expects format: "Condition: greaterThan, inputs: nodeA.attr, nodeB.attr"

    Args:
        details_string: The raw details string from the CSV.

    Returns:
        dict: {"condition_operation": str, "condition_inputs": [str, ...]}
    """
    parsed = {"condition_operation": "", "condition_inputs": []}

    op_match = re.search(r"Condition:\s*(\w+)", details_string)
    if op_match:
        parsed["condition_operation"] = op_match.group(1)

    inputs_match = re.search(r"inputs:\s*(.+)", details_string)
    if inputs_match:
        parsed["condition_inputs"] = [
            condition_input.strip()
            for condition_input in inputs_match.group(1).split(",")
            if condition_input.strip()
        ]

    return parsed


def parse_details_by_method(driving_method, details_string):
    """
    Dispatch to the correct detail parser based on driving_method.

    Args:
        driving_method: The driving method string from the CSV row.
        details_string: The raw details string from the CSV row.

    Returns:
        dict: Parsed details with typed fields, or {"raw": details_string} as fallback.
    """
    if not details_string or not details_string.strip():
        return {}

    parser_dispatch = {
        "setDrivenKey": parse_sdk_details,
        "animCurve": lambda d: {"anim_curve_node": d.replace("Timeline anim curve: ", "").strip()},
        "expression": lambda d: {"expression_code": d.replace("Expression: ", "").strip()},
        "poseInterpolator": parse_psd_details,
        "combinationShape": parse_combo_details,
        "remapValue": parse_remap_details,
        "clamp": parse_math_node_details,
        "multiplyDivide": parse_math_node_details,
        "plusMinusAverage": parse_math_node_details,
        "condition": parse_condition_details,
        "directConnection": lambda d: {"controller_attr": d.replace("Controller attr: ", "").strip()},
        "none": lambda d: {"reason": d},
    }

    parser = parser_dispatch.get(driving_method)
    if parser is None:
        return {"raw": details_string}

    try:
        return parser(details_string)
    except Exception:
        print("WARNING: parse_details_by_method - failed to parse '{}' details: {}".format(
            driving_method, details_string
        ))
        return {"raw": details_string}


# ---------------------------------------------------------------------------
# Row → driver record conversion
# ---------------------------------------------------------------------------

def build_driver_record(csv_row):
    """
    Convert one CSV row into a structured driver dict.

    Parses numeric fields to proper types and splits pipe-delimited
    controller attrs into a list.

    Args:
        csv_row: A dict from csv.DictReader representing one CSV row.

    Returns:
        dict: A driver record with typed fields and parsed details.
    """
    driving_method = csv_row.get("driving_method", "").strip()
    details_string = csv_row.get("details", "").strip()

    # Split pipe-delimited ultimate_controller_attrs into a list
    raw_controllers = csv_row.get("ultimate_controller_attrs", "").strip()
    if raw_controllers:
        controller_attr_list = [
            controller.strip()
            for controller in raw_controllers.split("|")
            if controller.strip()
        ]
    else:
        controller_attr_list = []

    return {
        "driving_method": driving_method,
        "immediate_driver_node": csv_row.get("immediate_driver_node", "").strip(),
        "immediate_driver_attr": csv_row.get("immediate_driver_attr", "").strip(),
        "immediate_driver_type": csv_row.get("immediate_driver_type", "").strip(),
        "ultimate_controller_attrs": controller_attr_list,
        "parsed_details": parse_details_by_method(driving_method, details_string),
    }


# ---------------------------------------------------------------------------
# Grouping rows by node and target
# ---------------------------------------------------------------------------

def group_rows_by_node_and_target(csv_rows):
    """
    Group validated CSV rows into a nested structure by blendshape node and target.

    Multiple CSV rows for the same target (different drivers) become entries
    in that target's drivers list.

    Args:
        csv_rows: A list of dicts from csv.DictReader.

    Returns:
        dict: Nested structure {node_name: {target_name: {"target_index": int,
              "shape_classification": str, "current_weight": float,
              "drivers": [driver_record, ...]}}}
    """
    grouped = {}

    for row_number, csv_row in enumerate(csv_rows, start=2):  # row 1 is header
        if not validate_csv_row(csv_row, row_number):
            continue

        blendshape_node = csv_row["blendshape_node"].strip()
        target_name = csv_row["target_name"].strip()

        # Initialize node dict if first time seeing this node
        if blendshape_node not in grouped:
            grouped[blendshape_node] = {}

        node_targets = grouped[blendshape_node]

        # Initialize target dict if first time seeing this target
        if target_name not in node_targets:
            # Parse numeric fields with safe defaults
            try:
                target_index = int(csv_row.get("target_index", 0))
            except (ValueError, TypeError):
                print("WARNING: group_rows_by_node_and_target - invalid target_index on row {}".format(
                    row_number
                ))
                target_index = 0

            try:
                current_weight = float(csv_row.get("current_weight", 0.0))
            except (ValueError, TypeError):
                print("WARNING: group_rows_by_node_and_target - invalid current_weight on row {}".format(
                    row_number
                ))
                current_weight = 0.0

            node_targets[target_name] = {
                "target_index": target_index,
                "shape_classification": csv_row.get("shape_classification", "").strip(),
                "current_weight": current_weight,
                "drivers": [],
            }

        # Append driver record for this row
        driver_record = build_driver_record(csv_row)
        node_targets[target_name]["drivers"].append(driver_record)

    for node_name in grouped:
        unsorted_targets = grouped[node_name]
        grouped[node_name] = dict(
            sorted(unsorted_targets.items(), key=lambda item: item[1]["target_index"])
        )
    return grouped


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def convert_csv_to_control_rig_json(csv_path, json_output_path=None):
    """
    Read a blendshape schema CSV and write a structured JSON file for the
    Control Rig builder.

    If json_output_path is None, writes to the same directory as the CSV
    with a .json extension.

    Args:
        csv_path: Path to the input CSV file.
        json_output_path: Optional path for the output JSON file.

    Returns:
        str: Path to the written JSON file, or empty string on failure.
    """
    # Guard: CSV must exist
    if not os.path.isfile(csv_path):
        print("WARNING: convert_csv_to_control_rig_json - CSV file not found: {}".format(
            csv_path
        ))
        return ""

    # Default output path: same name with .json extension
    if json_output_path is None:
        json_output_path = os.path.splitext(csv_path)[0] + ".json"

    # Read CSV rows
    csv_rows = []
    try:
        with open(csv_path, "r", newline="") as csv_file:
            reader = csv.DictReader(csv_file)

            # Validate fieldnames
            actual_fieldnames = reader.fieldnames or []
            missing_fieldnames = [
                field for field in EXPECTED_FIELDNAMES
                if field not in actual_fieldnames
            ]
            if missing_fieldnames:
                print("WARNING: convert_csv_to_control_rig_json - CSV missing columns: {}".format(
                    ", ".join(missing_fieldnames)
                ))
                print("  Continuing with empty defaults for missing columns.")

            csv_rows = list(reader)
    except Exception:
        print("WARNING: convert_csv_to_control_rig_json - failed to read CSV: {}".format(
            csv_path
        ))
        return ""

    if not csv_rows:
        print("WARNING: convert_csv_to_control_rig_json - CSV is empty: {}".format(
            csv_path
        ))
        return ""

    # Group rows into nested structure
    blendshape_nodes = group_rows_by_node_and_target(csv_rows)

    # Count totals for metadata
    total_targets = sum(
        len(targets) for targets in blendshape_nodes.values()
    )

    # Build final JSON structure
    output_data = {
        "metadata": {
            "source_csv": os.path.basename(csv_path),
            "export_date": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "total_targets": total_targets,
            "total_blendshape_nodes": len(blendshape_nodes),
        },
        "blendshape_nodes": {
            node_name: {"targets": targets}
            for node_name, targets in blendshape_nodes.items()
        },
    }

    # Write JSON
    try:
        with open(json_output_path, "w") as json_file:
            json.dump(output_data, json_file, indent=4)
    except Exception:
        print("WARNING: convert_csv_to_control_rig_json - failed to write JSON: {}".format(
            json_output_path
        ))
        return ""

    print("Converted {} CSV rows -> {} targets across {} blendshape node(s)".format(
        len(csv_rows), total_targets, len(blendshape_nodes)
    ))
    print("JSON written to: {}".format(json_output_path))

    return json_output_path


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python csv_to_control_rig_json.py <input.csv> [output.json]")
        sys.exit(1)

    input_csv_path = sys.argv[1]
    output_json_path = sys.argv[2] if len(sys.argv) > 2 else None

    result_path = convert_csv_to_control_rig_json(input_csv_path, output_json_path)
    if not result_path:
        sys.exit(1)
