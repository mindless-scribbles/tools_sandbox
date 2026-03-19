"""
duplicate_with_spacing.py
Unreal Engine 5 Editor Utility Script

Duplicates the selected actor(s) in the viewport with user-defined spacing,
count, axis, and layout mode (left-to-right or center-out).

Usage:
    Run from the UE5 Python console or as an Editor Utility Script.
    A dialog will prompt for all parameters.
"""

import unreal


# ---------------------------------------------------------------------------
# Dialog helpers
# ---------------------------------------------------------------------------

def show_dialog():
    """
    Present a multi-field input dialog and return a dict of parameters,
    or None if the user cancelled.
    """

    # Build dialog fields
    fields = [
        unreal.AppInputDialogField("Count (copies, not including original)"),
        unreal.AppInputDialogField("Spacing (cm)"),
        unreal.AppInputDialogField("Axis  [X / Y / Z]"),
        unreal.AppInputDialogField("Layout  [LR = left-to-right / CO = center-out]"),
    ]

    results = unreal.AppDialog.show_input_dialog(
        title="Duplicate With Spacing",
        message="Enter duplication parameters:",
        fields=fields,
    )

    # User hit Cancel or closed the window
    if not results:
        return None

    # Validate and parse
    try:
        count = int(results[0].strip())
        if count < 1:
            raise ValueError("Count must be >= 1")
    except ValueError as exc:
        unreal.log_error(f"[DuplicateWithSpacing] Invalid count: {exc}")
        return None

    try:
        spacing = float(results[1].strip())
    except ValueError:
        unreal.log_error("[DuplicateWithSpacing] Invalid spacing value.")
        return None

    axis_raw = results[2].strip().upper()
    if axis_raw not in ("X", "Y", "Z"):
        unreal.log_error("[DuplicateWithSpacing] Axis must be X, Y, or Z.")
        return None

    layout_raw = results[3].strip().upper()
    if layout_raw not in ("LR", "CO"):
        unreal.log_error("[DuplicateWithSpacing] Layout must be LR or CO.")
        return None

    return {
        "count":   count,
        "spacing": spacing,
        "axis":    axis_raw,       # "X", "Y", or "Z"
        "layout":  layout_raw,     # "LR" or "CO"
    }


# ---------------------------------------------------------------------------
# Offset calculation
# ---------------------------------------------------------------------------

AXIS_MAP = {
    "X": unreal.Vector(1.0, 0.0, 0.0),
    "Y": unreal.Vector(0.0, 1.0, 0.0),
    "Z": unreal.Vector(0.0, 0.0, 1.0),
}


def compute_offsets(count, spacing, axis_key, layout):
    """
    Return a list of unreal.Vector offsets (one per copy) relative to the
    original actor's location.

    Left-to-right (LR):
        Copies are placed at +1*spacing, +2*spacing, ... along the axis.
        The original stays at index 0 (no offset).

    Center-out (CO):
        The entire array (original + copies) is centered on the original's
        position.  The original is shifted so the group is balanced.
        offsets[0] is the correction for the original itself; offsets[1:]
        are for each copy.
    """
    direction = AXIS_MAP[axis_key]
    total = count + 1  # original + copies

    if layout == "LR":
        # Original stays put; copies fan out in the positive direction.
        offsets = []
        for i in range(1, count + 1):
            offsets.append(direction * (spacing * i))
        return offsets, unreal.Vector(0.0, 0.0, 0.0)  # (copy_offsets, origin_correction)

    else:  # CO  (center-out)
        # Total span = (total - 1) * spacing
        # Center offset of the whole array relative to original position = -span/2
        span = (total - 1) * spacing
        start_offset = direction * (-span / 2.0)  # move original to array start

        copy_offsets = []
        for i in range(1, count + 1):
            copy_offsets.append(start_offset + direction * (spacing * i))

        return copy_offsets, start_offset  # origin_correction moves the original


# ---------------------------------------------------------------------------
# Main duplication routine
# ---------------------------------------------------------------------------

def duplicate_selected_actors():
    editor_subsystem  = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    level_editor      = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)

    selected = editor_subsystem.get_selected_level_actors()

    if not selected:
        unreal.log_warning("[DuplicateWithSpacing] No actors selected in the viewport.")
        return

    params = show_dialog()
    if params is None:
        unreal.log("[DuplicateWithSpacing] Cancelled.")
        return

    count   = params["count"]
    spacing = params["spacing"]
    axis    = params["axis"]
    layout  = params["layout"]

    unreal.log(
        f"[DuplicateWithSpacing] count={count}, spacing={spacing}cm, "
        f"axis={axis}, layout={layout}"
    )

    # Begin an undo transaction so the entire operation is one Ctrl+Z step.
    with unreal.ScopedEditorTransaction("Duplicate With Spacing") as trans:

        for source_actor in selected:
            origin_loc = source_actor.get_actor_location()

            copy_offsets, origin_correction = compute_offsets(
                count, spacing, axis, layout
            )

            # If center-out, reposition the original first.
            if layout == "CO":
                new_origin = unreal.Vector(
                    origin_loc.x + origin_correction.x,
                    origin_loc.y + origin_correction.y,
                    origin_loc.z + origin_correction.z,
                )
                source_actor.set_actor_location(new_origin, sweep=False, teleport=True)
                origin_loc = new_origin  # use updated position for copy math

            # Duplicate and position each copy.
            for offset in copy_offsets:
                # duplicate_actor returns a list; grab the first element.
                duplicated = editor_subsystem.duplicate_actor(
                    source_actor,
                    source_actor.get_actor_label() + "_dup",
                    offset=unreal.Vector(0, 0, 0),  # we set location manually
                )

                if duplicated is None:
                    unreal.log_error(
                        f"[DuplicateWithSpacing] Failed to duplicate {source_actor.get_actor_label()}"
                    )
                    continue

                target_loc = unreal.Vector(
                    origin_loc.x + offset.x,
                    origin_loc.y + offset.y,
                    origin_loc.z + offset.z,
                )
                duplicated.set_actor_location(target_loc, sweep=False, teleport=True)

    unreal.log("[DuplicateWithSpacing] Done.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    duplicate_selected_actors()
