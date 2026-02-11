"""UE5 remote execution wrapper for FBX import."""

import time
from pathlib import PureWindowsPath

from remote_execution import RemoteExecution


def import_fbx(fbx_path: str, ue5_content_folder: str = "/Game/Imports", discovery_timeout: float = 10.0) -> dict:
    """Import an FBX file into UE5 via remote execution.

    Args:
        fbx_path: Absolute path to the .fbx file on disk.
        ue5_content_folder: UE5 content browser destination (e.g. '/Game/Imports').
        discovery_timeout: Seconds to wait for UE5 node discovery.

    Returns:
        dict with 'success' (bool) and 'result' / 'output' (str) keys.

    Raises:
        ConnectionError: If no UE5 editor found within timeout.
        RuntimeError: If the import command fails.
    """
    remote = RemoteExecution()
    remote.start()

    try:
        # Wait for UE5 node discovery
        deadline = time.time() + discovery_timeout
        while not remote.remote_nodes and time.time() < deadline:
            time.sleep(0.5)

        if not remote.remote_nodes:
            raise ConnectionError(
                "No UE5 Editor found. Ensure:\n"
                "  1. UE5 Editor is running\n"
                "  2. Python Editor Script Plugin is enabled\n"
                "  3. Remote Execution is enabled in Project Settings > Plugins > Python"
            )

        # remote_nodes is a list of dicts with 'node_id' key
        node = remote.remote_nodes[0]
        node_id = node["node_id"]

        # Open TCP command connection to the node
        remote.open_command_connection(node_id)

        # Normalize path for Python string embedding (forward slashes)
        fbx_path_escaped = fbx_path.replace("\\", "/")

        # Build and execute the import command
        command = _build_import_command(fbx_path_escaped, ue5_content_folder)
        result = remote.run_command(command, raise_on_failure=True)

        return result
    finally:
        remote.stop()


def _build_import_command(fbx_path: str, content_folder: str) -> str:
    """Build the Python command string to execute inside UE5."""
    # Derive asset name from filename
    asset_name = PureWindowsPath(fbx_path).stem

    return f'''
import unreal

def do_import():
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", r"{fbx_path}")
    task.set_editor_property("destination_path", r"{content_folder}")
    task.set_editor_property("destination_name", r"{asset_name}")
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("automated", True)
    task.set_editor_property("save", True)

    options = unreal.FbxImportUI()
    options.set_editor_property("import_mesh", True)
    options.set_editor_property("import_textures", True)
    options.set_editor_property("import_materials", True)
    options.set_editor_property("import_as_skeletal", False)

    options.static_mesh_import_data.set_editor_property("combine_meshes", True)
    options.static_mesh_import_data.set_editor_property("auto_generate_collision", True)
    options.static_mesh_import_data.set_editor_property("generate_lightmap_u_vs", True)

    options.set_editor_property("import_animations", False)

    task.set_editor_property("options", options)

    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])

    if task.get_editor_property("imported_object_paths"):
        paths = task.get_editor_property("imported_object_paths")
        print(f"Successfully imported: {{list(paths)}}")
    else:
        print("Import completed but no assets were reported")

do_import()
'''
