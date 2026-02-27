# GLB to UE5 Importer

## Project Overview
Desktop tool that takes a `.glb` file, processes it through Blender (headless), and imports the result into UE5 via Python remote execution. One-click pipeline: GLB → Merge Child Meshes → Decimate → FBX → UE5.

## Architecture
- `main.py` → `gui.py` (PySide6 UI) → `blender_bridge.py` → `scripts/blender_process.py` (runs inside Blender)
- `gui.py` → `ue5_bridge.py` → `remote_execution.py` (UE5 remote exec protocol)

## Key Files
- `scripts/blender_process.py` — Runs inside Blender's Python environment (uses `bpy`), not standard Python
- `remote_execution.py` — Vendored from Epic Games (PythonScriptPlugin). Do not modify.
- `blender_bridge.py` — Finds Blender install, runs it as subprocess
- `ue5_bridge.py` — Wraps remote_execution for FBX import into UE5
- `gui.py` — PySide6 GUI with worker thread for async pipeline execution

## Blender Processing
- Optional "Merge Child Meshes" (default on): merges mesh children under EMPTY parents into single meshes
  - Single child mesh: reparented to world, renamed to parent's name
  - Multiple child meshes: joined into one mesh, renamed to parent's name
  - Childless empties cleaned up after merge
- Decimation applied after merge via `--decimate` ratio

## UE5 Import Logic
- Both reimport and fresh import use `replace_existing=True` + `replace_existing_settings=True` to ensure new options are applied
- **Reimport** (asset exists): Import directly to preserve level references
- **Fresh import** (asset new): Import directly to destination folder
- Optional "Merge Meshes" (default on): controls `combine_meshes` on `FbxStaticMeshImportData`
- Optional "Complex as Simple" collision: applied to all imported static meshes via `imported_object_paths`
- Materials auto-moved to `Materials/` subfolder
- Optional "FBX Output" folder keeps source FBX files permanently on disk

## Technical Details
- `blender_process.py` uses `--` separator for argparse args after Blender's own args
- FBX export uses UE5-compatible axis settings: `forward=-Z`, `up=Y`
- GUI uses `QThread` + `QObject.moveToThread` pattern for async work
- GUI settings persisted to `settings.ini` (INI format via `QSettings`, gitignored) — restores all options and window geometry on launch
- GUI organized into Blender settings row, UE5 settings row, and folder paths row
- Blender detection order: `BLENDER_PATH` env → standard Windows path → `which` → Steam
- UE5 remote execution: UDP multicast `239.0.0.1:6766` for discovery, TCP port `6776` for commands
- Multicast bind address must match UE5's setting (currently `127.0.0.1`, configured in `ue5_bridge.py`)
- The client listens on TCP and UE5 connects to it (not the other way around)

## UE5 5.6 Gotchas
- `EditorAssetLibrary.fixup_redirectors_in_folder()` does NOT exist
- `FbxImportUI` has no `is_reimport` property
- `AssetImportTask.replace_existing_settings` must be `True` to override stored import options on reimport
- Interchange aggressively renames assets even after deletion + GC
- `EditorAssetLibrary.delete_directory()` only marks deleted in registry — must also delete physical folder
- `run_command()` output is a **list** of log lines, not a string
- Deleting + recreating an asset breaks level references — always reimport when asset exists
- Epic's `DEFAULT_RECEIVE_BUFFER_SIZE` is only 8 KB — overridden to 64 KB in `ue5_bridge.py` to avoid JSON truncation
- `run_command()` can raise `RuntimeError` on long imports even when UE5 completes successfully — caught as warning

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
