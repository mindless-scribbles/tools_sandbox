# Plan: CSV-to-JSON Converter for Control Rig Pipeline

## Context

The pipeline currently flows: **Maya trace → CSV → Unreal Control Rig builder**. The CSV is flat and string-heavy (pipe-delimited lists, embedded keyframe data in a `details` column). A new intermediate module will convert CSV → structured JSON so the Unreal-side script gets clean, typed data. The user also wants to be able to hand-edit the CSV before conversion (fix classifications, add/remove rows, etc.).

## New File

**`MindOverMind/pipeline/csv_to_control_rig_json.py`** — standalone Python 3.10 module, no DCC dependencies (only `csv`, `json`, `re`, `os`, `sys`, `datetime`).

Also create empty `MindOverMind/pipeline/__init__.py`.

## JSON Output Schema

```json
{
    "metadata": {
        "source_csv": "path/to/file.csv",
        "export_date": "2026-03-19T14:30:00",
        "total_targets": 97,
        "total_blendshape_nodes": 1
    },
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
                            "ultimate_controller_attrs": ["ctrlBrow_R.translateX"],
                            "parsed_details": {
                                "sdk_input": "ctrlBrow_R.translateX",
                                "keyframes": [
                                    {"input": 0.0, "output": 0.0},
                                    {"input": 1.0, "output": 1.0}
                                ]
                            }
                        }
                    ]
                }
            }
        }
    }
}
```

- Targets grouped under their `blendshape_node`
- Multiple drivers per target supported (multiple CSV rows → `drivers` array)
- `ultimate_controller_attrs` split from pipe-delimited string into list
- Numeric fields converted to proper types (`target_index` → int, `current_weight` → float)

## Details Parsing (per driving_method)

Each method's `details` string gets parsed into a typed `parsed_details` dict:

| driving_method | Parsed fields |
|---|---|
| `setDrivenKey` | `sdk_input` (str), `keyframes` (list of `{input, output}` floats) |
| `animCurve` | `anim_curve_node` (str) |
| `expression` | `expression_code` (str) |
| `poseInterpolator` | `psd_drivers` (list), `poses` (list) |
| `combinationShape` | `combo_mode` (str), `combo_inputs` (list) |
| `remapValue` | `remap_source` (str), remap range info |
| `clamp` | `clamp_inputs` (list), `clamp_range` (list of floats) |
| `multiplyDivide` | `operation` (str), `math_inputs` (list) |
| `plusMinusAverage` | `operation` (str), `math_inputs` (list) |
| `condition` | `condition_operation` (str), `condition_inputs` (list) |
| `directConnection` | `controller_attr` (str) |
| `none` | `reason` (str) |
| unrecognized | `raw` (str) — fallback preserves the original string |

## Module Functions

1. **`validate_csv_row(csv_row, row_number)`** — checks required fields, warns and returns False for bad rows
2. **`parse_sdk_details(details_string)`** — regex extracts keyframe pairs from `"keys: (0.0 -> 0.0), (1.0 -> 1.0)"`
3. **`parse_psd_details(details_string)`** — splits PSD drivers and pose names
4. **`parse_combo_details(details_string)`** — extracts combo mode and input shapes
5. **`parse_remap_details(details_string)`** — extracts remap source and range
6. **`parse_math_node_details(details_string)`** — shared parser for clamp/multiplyDivide/plusMinusAverage
7. **`parse_condition_details(details_string)`** — extracts condition op and inputs
8. **`parse_details_by_method(driving_method, details_string)`** — dispatch function routing to the correct parser
9. **`build_driver_record(csv_row)`** — converts one CSV row into a structured driver dict
10. **`group_rows_by_node_and_target(csv_rows)`** — groups rows into nested `{node: {target: {drivers: [...]}}}` structure
11. **`convert_csv_to_control_rig_json(csv_path, json_output_path=None)`** — main entry point: read CSV, validate, group, write JSON

Plus `if __name__ == "__main__"` block for CLI usage: `python csv_to_control_rig_json.py input.csv [output.json]`

## Files to Modify

- **Create:** `MindOverMind/pipeline/__init__.py` (empty)
- **Create:** `MindOverMind/pipeline/csv_to_control_rig_json.py` (the converter)
- **Update:** `MindOverMind/unreal_scripts/build_facial_control_rig.py` — change signature from `csv_path` to `json_path`
- **Update:** `CLAUDE.md` — add pipeline module to Architecture section

## Error Handling

- Guard clause: bail early if CSV file doesn't exist
- Validate CSV fieldnames against expected columns (warn on missing, continue with empty defaults)
- Each parser wraps in try/except → falls back to `{"raw": details_string}` with a WARNING
- Skips invalid rows with warning, never stops the pipeline

## Verification

1. Run the converter against `MindOverMind/maya_scripts/Wendall_Blendhsape_Schema.csv`
2. Inspect the output JSON for correct structure, types, and parsed keyframes
3. Verify all 97 rows produce valid target entries with parsed SDK details
4. Run `pyright .` to type-check
