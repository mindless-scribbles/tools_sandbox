# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Python toolkit for automating DCC pipelines between Autodesk Maya and Unreal Engine 5.

## Setup

```bash
uv sync       # install dependencies
pyright .     # type check
```

Python 3.10 (`.python-version`). Dependencies: `maya-stubs`, `pymel`, `future`.

## Architecture

Scripts run inside their host DCC interpreters (Maya Script Editor or UE5 Python console), not as standalone CLI tools.

**Maya → Unreal pipeline:**
1. `MindOverMind/maya_scripts/maya_blendshape_schema.py` — traces full driver chains (SDKs, PSD, combinationShape, expressions, etc.) for every blendshape target via recursive graph traversal with cycle detection. Exports CSV with shape classification and wiring details.
2. `MindOverMind/unreal_scripts/build_facial_control_rig.py` — consumes CSV to build a Control Rig. Currently a placeholder.

**Standalone:** `HomeProjects/duplicator.py` — UE5 editor utility for duplicating actors with spacing/layout options.

## Key Details

- `MindOverMind/unreal_scripts/` is missing `__init__.py`.
- New Maya node types go in `trace_driver_chain` as additional `elif` branches.
- No test suite exists yet.

## Code Style

### Naming

Variable names describe what the data represents, not its type. Loop variables equally descriptive.
- Bad: `indices`, `float_values`, `conns`, `idx`, `fv`
- Good: `driver_slot_indices`, `driver_values`, `driver_matrix_conns`, `driver_slot_idx`, `driver_val`

Known violations in `maya_blendshape_schema.py:67-75` (`float_values`, `value_values`, `fv`, `vv`) — fix when touched.

### Docstrings

Every function gets a docstring: what it does, inputs, return value with type. One-liners only for trivial helpers.

### Error Handling

- No bare `except Exception: pass`. Every failure gets an explicit check with: `"WARNING: function_name - description on {node}"`
- `continue` for non-fatal loop failures, `return []`/`return ""`/`return {}` for bail-outs after a warning.
- Known violations in `maya_blendshape_schema.py:78-79` and `118-119` — fix when touched.

### Defensive Coding

Guard None returns with `or []` / `or 0` / `or {}`. Critical for Maya `cmds` functions — see `docs/maya_style_reference.md`.

### Deduplication

`dict.fromkeys()` when order matters. Never `list(set(...))` on ordered data. See `maya_blendshape_schema.py:94`.

### Guard Clauses

Early exits at function top for invalid data. Always warn before returning early. No silent `break` without a comment.

### List Comprehensions

Use for simple transforms. If logic gets complex, use a regular for loop.

### File Output

- **CSV** — tabular data for human review. `csv.DictWriter` with explicit `fieldnames`.
- **JSON** — pipeline data exchange. Always `indent=4`. Preferred for inter-tool data.

## DCC-Specific Conventions

- **Maya:** `docs/maya_style_reference.md`
- **Unreal:** `docs/unreal_style_reference.md`
