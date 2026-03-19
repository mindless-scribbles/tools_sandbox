# Maya Python Style Reference

## cmds, Not pymel

Use `cmds` for all Maya commands. pymel has significant performance overhead. If encountered in legacy code, note it but do not refactor unless asked.

## cmds Returns None, Not Empty Collections

`listConnections`, `listRelatives`, `ls`, `keyframe`, `getAttr`, `listAttr` all return None on failure. Always guard:

```python
history = cmds.listHistory(mesh) or []
num_keys = cmds.keyframe(curve, query=True, keyframeCount=True) or 0
```

See `MindOverMind/maya_scripts/maya_blendshape_schema.py` lines 34, 43, 64, 86, 91 for consistent application.

## Validate Before Querying

Always `cmds.objExists(node)` before querying a node. Always `cmds.attributeQuery(attr, node=node, exists=True)` before querying an attribute. Never assume a node or attribute exists just because it was returned earlier in the same script.

## Selection State

Never rely on Maya's current selection inside a function — pass node names as arguments. Functions that change selection must restore it before returning.

## Undo Chunks

Wrap scene-modifying functions in undo chunks with try/finally:

```python
cmds.undoInfo(openChunk=True)
try:
    # do work
finally:
    cmds.undoInfo(closeChunk=True)
```

## Feedback

- `print()` for warnings and progress reporting
- `cmds.warning()` for user-facing messages (prints in orange, more visible)
- `cmds.confirmDialog()` for tools with UIs that require user acknowledgment
