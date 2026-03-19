# Plan: CSV-to-JSON Converter Module + Rename build_facial_control_rig

## Context

The Maya→Unreal pipeline currently exports blendshape wiring data as CSV (`ddc_blendshape_input_trace.py`). The Unreal-side placeholder (`build_facial_control_rig.py`) references a CSV path. Per CLAUDE.md, JSON with `indent=4` is the preferred format for inter-tool data exchange. The user wants a converter module that sits between the Maya export and the Unreal consumer, and the ability to re-convert edited CSVs into fresh JSON.

---

## Files Involved

| File | Action |
|------|--------|
| `MindOverMind/maya_scripts/csv_to_json_converter.py` | **New** — converter module |
| `MindOverMind/unreal_scripts/build_facial_control_rig.py` | **Rename** → `ddc_build_facial_control_rig.py`, update to reference JSON |
| `CLAUDE.md` | Update filename reference and architecture description |

---

## Step 1: Create `MindOverMind/maya_scripts/csv_to_json_converter.py`

A standalone module that reads a blendshape schema CSV and writes a structured JSON file.

### Design

- Read CSV with `csv.DictReader`
- Group rows by `blendshape_node` → `target_name` for a hierarchical JSON structure rather than flat row duplication
- Cast numeric fields (`target_index` → int, `current_weight` → float)
- Write JSON with `indent=4` per CLAUDE.md convention
- Provide a `convert_csv_to_json(csv_path, json_path=None)` function:
  - If `json_path` is None, derive it from `csv_path` by replacing `.csv` with `.json`
  - Returns the output path
- Include `if __name__ == "__main__":` block that accepts paths as arguments for standalone use

### JSON Structure

```json
{
    "blendshape_nodes": {
        "asFaceBS": {
            "targets": {
                "brow_innerRaiser_R": {
                    "target_index": 0,
                    "shape_classification": "primary",
                    "current_weight": 0.0,
                    "drivers": [
                        {
                            "driving_method": "setDrivenKey",
                            "immediate_driver_node": "asFaceBS_brow_innerRaiser_R",
                            "immediate_driver_attr": "asFaceBS_brow_innerRaiser_R.output",
                            "immediate_driver_type": "animCurveUU",
                            "ultimate_controller_attrs": "ctrlBrow_R.translateX",
                            "details": "SDK input: ctrlBrow_R.translateX | keys: (0.0 -> 0.0), (1.0 -> 1.0)"
                        }
                    ]
                }
            }
        }
    }
}
```

This groups by blendshape node and target name, hoisting shared fields (`target_index`, `shape_classification`, `current_weight`) to the target level, with per-driver records in a `drivers` list. This eliminates the row duplication present in the CSV when a target has multiple drivers.

### Conventions to follow
- Descriptive variable names (not `row`, `r`, `d` — use `csv_row`, `target_record`, etc.)
- Docstrings on all functions
- Defensive guards: file existence check before reading
- Error handling: `cmds` is NOT available here (this runs standalone, not in Maya) — use `print()` for warnings
- `json.dump()` with `indent=4`

---

## Step 2: Rename `build_facial_control_rig.py` → `ddc_build_facial_control_rig.py`

```bash
git mv MindOverMind/unreal_scripts/build_facial_control_rig.py MindOverMind/unreal_scripts/ddc_build_facial_control_rig.py
```

Update the placeholder content to reference JSON instead of CSV:
- Change `csv_path` parameter to `json_path`
- Update the example path from `.csv` to `.json`

---

## Step 3: Update `CLAUDE.md`

### Architecture section
Change:
```
2. `MindOverMind/unreal_scripts/build_facial_control_rig.py` — consumes CSV to build a Control Rig. Currently a placeholder.
```
To:
```
2. `MindOverMind/maya_scripts/csv_to_json_converter.py` — converts the CSV export to structured JSON for pipeline consumption.
3. `MindOverMind/unreal_scripts/ddc_build_facial_control_rig.py` — consumes JSON to build a Control Rig. Currently a placeholder.
```

---

## Verification

1. Run the converter against the existing CSV:
   ```bash
   uv run python MindOverMind/maya_scripts/csv_to_json_converter.py MindOverMind/maya_scripts/Wendall_Blendhsape_Schema.csv
   ```
2. Inspect the output JSON for correct structure, proper nesting, and `indent=4`
3. Confirm `pyright` passes (or only shows pre-existing stub errors)

---

## Post-approval

This plan will be saved to `docs/csv_to_json_converter_plan.md` before implementation begins.
