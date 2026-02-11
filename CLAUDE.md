# GLB to UE5 Importer

## Project Overview
Desktop tool that takes a `.glb` file, processes it through Blender (headless), and imports the result into UE5 via Python remote execution. One-click pipeline: GLB → Decimate → FBX → UE5.

## Architecture
- `main.py` → `gui.py` (PySide6 UI) → `blender_bridge.py` → `scripts/blender_process.py` (runs inside Blender)
- `gui.py` → `ue5_bridge.py` → `remote_execution.py` (UE5 remote exec protocol)

## Key Files
- `scripts/blender_process.py` — Runs inside Blender's Python environment (uses `bpy`), not standard Python
- `remote_execution.py` — Vendored from Epic Games (PythonScriptPlugin). Do not modify.
- `blender_bridge.py` — Finds Blender install, runs it as subprocess
- `ue5_bridge.py` — Wraps remote_execution for FBX import into UE5
- `gui.py` — PySide6 GUI with worker thread for async pipeline execution

## Technical Details
- `blender_process.py` uses `--` separator for argparse args after Blender's own args
- FBX export uses UE5-compatible axis settings: `forward=-Z`, `up=Y`
- GUI uses `QThread` + `QObject.moveToThread` pattern for async work
- Blender detection order: `BLENDER_PATH` env → standard Windows path → `which` → Steam
- UE5 remote execution: UDP multicast `239.0.0.1:6766` for discovery, TCP for commands
- The client listens on TCP and UE5 connects to it (not the other way around)

## Prerequisites
- Python 3.10+, PySide6
- Blender installed (standard path or set `BLENDER_PATH`)
- UE5 with Python Editor Script Plugin enabled + Remote Execution enabled
- UE5 Editor must be running when importing

## Running
```
pip install -r requirements.txt
python main.py
```
