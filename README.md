# GLB to UE5 Importer

A one-click desktop tool that imports `.glb` files into Unreal Engine 5. It processes the model through Blender (headless) for mesh merging, decimation, and FBX conversion, then pushes the result straight into UE5 via remote execution — no manual export/import steps needed.

## How It Works

```
GLB file → Blender (merge child meshes → decimate → FBX export) → UE5 (remote import)
```

Drop a `.glb` file into the GUI, tweak settings if needed, and hit **Import to UE5**. The tool handles the rest while UE5 Editor is running.

## Features

- **Drag & drop** GLB files or browse to select
- **Merge child meshes** — joins mesh children under empty parent objects into single meshes (cleans up GLB hierarchy)
- **Mesh decimation** — adjustable ratio (1.0 = keep original, lower = fewer polygons)
- **Merge meshes** — combine all meshes into a single static mesh in UE5
- **Material import** — brings materials along and organizes them into a `Materials/` subfolder
- **Complex as simple collision** — use mesh geometry directly as collision
- **Reimport-safe** — updates existing assets in-place without breaking level references
- **FBX output folder** — optionally keep the intermediate FBX files on disk
- **Persistent settings** — all options and window layout saved between sessions

## Prerequisites

- **Python 3.10+**
- **Blender** installed (standard path, or set `BLENDER_PATH` environment variable)
- **Unreal Engine 5** with:
  - Python Editor Script Plugin enabled
  - Remote Execution enabled (Edit > Project Settings > Python > Remote Execution)
  - UE5 Editor running when you import

## Setup

```bash
pip install -r requirements.txt
python main.py
```

## Usage

1. Start UE5 Editor with your project open
2. Run `python main.py`
3. Select a `.glb` file (drag & drop or browse)
4. Set the UE5 destination folder (default: `/Game/Imports`)
5. Adjust options as needed
6. Click **Import to UE5**
