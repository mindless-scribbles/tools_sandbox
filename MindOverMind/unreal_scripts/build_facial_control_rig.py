import build_facial_control_rig
build_facial_control_rig.build_facial_rig(
    csv_path=r"D:/Export/blendshape_schema.csv",
    rig_path="/Game/Characters/MyChar/CR_Facial_CtrlRig"
)
```

That works from the Output Log (set to Python), from the Python console, or from any other script.

**If you want subdirectories** for organization (which you probably will as you build more tools), add an `__init__.py` to make them proper packages:
```
YourProject/
  Content/
    Python/
      __init__.py                          (can be empty)
      build_facial_control_rig.py
      maya_export/
        __init__.py
        export_blendshape_schema.py
      facial_rig/
        __init__.py
        build_facial_control_rig.py
