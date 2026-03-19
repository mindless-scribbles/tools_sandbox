# Unreal Python Style Reference

Reference implementation: `HomeProjects/duplicator.py`

## Asset Paths

Always use full Unreal asset paths (`/Game/Characters/MyAsset`), never OS file paths for assets.

## Transactions

Wrap asset-modifying operations in a scoped transaction for single-undo:

```python
with unreal.ScopedEditorTransaction("description of operation"):
    # do work
```

## Logging

Use `unreal.log()`, `unreal.log_warning()`, `unreal.log_error()` instead of `print()`. These route to the Output Log with proper severity. Warning and error variants auto-open the Output Log.

## Slow Tasks

Wrap long-running loops in a slow task to show a progress bar:

```python
with unreal.ScopedSlowTask(total_steps, "Description") as slow_task:
    slow_task.make_dialog(True)
    for item in items:
        slow_task.enter_progress_frame(1)
        # do work
```

## Editor vs Runtime

Note which functions are editor-only (`unreal.EditorAssetLibrary`, etc.) so they aren't accidentally called at runtime.
