# Blendshape Schema — Before/After Code Examples

Reference examples showing coding convention violations that were fixed in `ddc_blendshape_input_trace.py`.

## Naming

Variable names describe what the data represents, not its type.

**Before** (`get_sdk_keyframe_data`):
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

## Error Handling

No bare `except Exception: pass`. Every failure gets an explicit warning.

**Before** (`get_sdk_keyframe_data`):
```python
except Exception:
    pass
```

**After:**
```python
except Exception:
    cmds.warning("WARNING: get_sdk_keyframe_data - failed to read keyframes on {}".format(curve_node))
```

## Deduplication

`dict.fromkeys()` when order matters. Never `list(set(...))` on ordered data.

```python
# Correct — preserves insertion order
return list(dict.fromkeys(drivers))

# Wrong — destroys order
return list(set(drivers))
```

## Defensive Coding

Always guard `cmds` calls that return None.

```python
# Always guard cmds calls that return None
history = cmds.listHistory(mesh) or []
num_keys = cmds.keyframe(curve, query=True, keyframeCount=True) or 0
conns = cmds.listConnections(plug, source=True) or []
```
