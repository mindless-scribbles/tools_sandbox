# Plan: Refactor and Rename `maya_blendshape_schema.py`

## Goal

Refactor `MindOverMind/maya_scripts/maya_blendshape_schema.py` to comply with the project's coding conventions defined in `CLAUDE.md`, rename the file to `dcc_blendshape_input_trace.py`, and decouple `CLAUDE.md` from line-number references that go stale after edits.

## Why

`CLAUDE.md` explicitly flags known violations at specific lines with "fix when touched." The user is now touching this file. Additionally, `CLAUDE.md` and `docs/maya_style_reference.md` both reference `maya_blendshape_schema.py` by filename and line number — those references will break after renaming and refactoring.

---

## Files Involved

| File | Action |
|------|--------|
| `MindOverMind/maya_scripts/maya_blendshape_schema.py` | Rename to `dcc_blendshape_input_trace.py`, then refactor |
| `CLAUDE.md` | Update filename references, remove line-number citations, remove stale note about missing `__init__.py` |
| `docs/maya_style_reference.md` | Update filename reference on line 16, remove line-number citations |
| `docs/blendshape_schema_examples.md` | **New file** — before/after code snippets extracted from the violations |

No Python files import `maya_blendshape_schema` — the rename is safe.

---

## Step 1: Create `docs/blendshape_schema_examples.md`

A before/after reference file showing the violations that existed and how they were fixed. Covers three categories:

### Naming (from `get_sdk_keyframe_data`, lines 67-76)

**Before:**
```python
float_values = cmds.keyframe(curve_node, query=True, floatChange=True) or []
value_values = cmds.keyframe(curve_node, query=True, valueChange=True) or []
if float_values and value_values:
    pairs = []
    for fv, vv in zip(float_values, value_values):
        pairs.append("({} -> {})".format(round(fv, 4), round(vv, 4)))
```

**After:**
```python
sdk_input_values = cmds.keyframe(curve_node, query=True, floatChange=True) or []
sdk_output_values = cmds.keyframe(curve_node, query=True, valueChange=True) or []
if sdk_input_values and sdk_output_values:
    pairs = []
    for input_val, output_val in zip(sdk_input_values, sdk_output_values):
        pairs.append("({} -> {})".format(round(input_val, 4), round(output_val, 4)))
```

### Error Handling (from `get_sdk_keyframe_data`, lines 78-79)

**Before:**
```python
except Exception:
    pass
```

**After:**
```python
except Exception:
    cmds.warning("WARNING: get_sdk_keyframe_data - failed to read keyframes on {}".format(curve_node))
```

### Deduplication (from `get_pose_interpolator_drivers`, line 94)

```python
# Correct — preserves insertion order
return list(dict.fromkeys(drivers))

# Wrong — destroys order
return list(set(drivers))
```

### Defensive Coding (from multiple functions)

```python
# Always guard cmds calls that return None
history = cmds.listHistory(mesh) or []
num_keys = cmds.keyframe(curve, query=True, keyframeCount=True) or 0
conns = cmds.listConnections(plug, source=True) or []
```

---

## Step 2: Update `CLAUDE.md`

### Line 23 — Architecture section
Change:
```
`MindOverMind/maya_scripts/maya_blendshape_schema.py` — traces full driver chains...
```
To:
```
`MindOverMind/maya_scripts/dcc_blendshape_input_trace.py` — traces full driver chains...
```

### Line 30 — Key Details
Remove:
```
- `MindOverMind/unreal_scripts/` is missing `__init__.py`.
```
(This was fixed in commit `ee658e5`.)

### Line 42 — Naming section
Remove:
```
Known violations in `maya_blendshape_schema.py:67-75` (`float_values`, `value_values`, `fv`, `vv`) — fix when touched.
```
Replace with:
```
See `docs/blendshape_schema_examples.md` for before/after naming examples.
```

### Line 52 — Error Handling section
Remove:
```
- Known violations in `maya_blendshape_schema.py:78-79` and `118-119` — fix when touched.
```
Replace with:
```
- See `docs/blendshape_schema_examples.md` for before/after error handling examples.
```

### Line 60 — Deduplication section
Change:
```
`dict.fromkeys()` when order matters. Never `list(set(...))` on ordered data. See `maya_blendshape_schema.py:94`.
```
To:
```
`dict.fromkeys()` when order matters. Never `list(set(...))` on ordered data. See `docs/blendshape_schema_examples.md`.
```

---

## Step 3: Update `docs/maya_style_reference.md`

### Line 16
Change:
```
See `MindOverMind/maya_scripts/maya_blendshape_schema.py` lines 34, 43, 64, 86, 91 for consistent application.
```
To:
```
See `docs/blendshape_schema_examples.md` for examples of defensive guards applied consistently.
```

---

## Step 4: Rename the file

```bash
git mv MindOverMind/maya_scripts/maya_blendshape_schema.py MindOverMind/maya_scripts/dcc_blendshape_input_trace.py
```

---

## Step 5: Refactor `dcc_blendshape_input_trace.py`

All changes are mechanical renames and warning additions. Zero logic changes. Zero new imports.

### 5a. `get_sdk_keyframe_data()` (lines 67-79)

**Renames:**
- `float_values` → `sdk_input_values` (lines 67, 73)
- `value_values` → `sdk_output_values` (lines 70, 73)
- `fv` → `input_val` (lines 75, 76)
- `vv` → `output_val` (lines 75, 76)

**Error handling (lines 78-79):**
```python
# Before
except Exception:
    pass

# After
except Exception:
    cmds.warning("WARNING: get_sdk_keyframe_data - failed to read keyframes on {}".format(curve_node))
```

### 5b. `get_pose_interpolator_drivers()` (lines 86-93)

**Renames:**
- `indices` → `driver_slot_indices` (lines 86, 87)
- `idx` → `driver_slot_idx` (lines 87, 89)
- `conns` → `driver_matrix_conns` (lines 88, 92, 93)

### 5c. `get_pose_interpolator_poses()` (lines 103-119)

**Renames:**
- `pose_indices` → `pose_slot_indices` (lines 103, 107)
- `idx` → `pose_slot_idx` (lines 107, 111, 114)

**Error handling — inner except (lines 113-114):**
```python
# Before
except Exception:
    pose_name = "pose_{}".format(idx)

# After
except Exception:
    cmds.warning("WARNING: get_pose_interpolator_poses - could not read poseName for pose {} on {}".format(pose_slot_idx, psi_node))
    pose_name = "pose_{}".format(pose_slot_idx)
```

**Error handling — outer except (lines 118-119):**
```python
# Before
except Exception:
    pass

# After
except Exception:
    cmds.warning("WARNING: get_pose_interpolator_poses - failed to read poses on {}".format(psi_node))
```

### 5d. `get_combination_shape_inputs()` (lines 126-135)

**Renames:**
- `indices` → `input_weight_indices` (lines 126, 129)
- `idx` → `input_weight_idx` (lines 129, 131)
- `conns` → `input_weight_conns` (lines 130, 135)

### 5e. `trace_driver_chain()` docstring (lines 140-146)

**Expand to:**
```python
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
```

---

## Verification

```bash
uv run pyright MindOverMind/maya_scripts/dcc_blendshape_input_trace.py
```

No test suite exists. Full runtime validation requires Maya Script Editor.
