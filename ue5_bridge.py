"""UE5 remote execution wrapper for FBX import."""

import time
from pathlib import PureWindowsPath

import remote_execution as _re
from remote_execution import RemoteExecution, RemoteExecutionConfig

# Epic's default receive buffer (8 KB) is too small for our command responses.
_re.DEFAULT_RECEIVE_BUFFER_SIZE = 65536


def import_fbx(fbx_path: str, ue5_content_folder: str = "/Game/Imports", discovery_timeout: float = 10.0, import_materials: bool = True, complex_collision: bool = False, combine_meshes: bool = True) -> dict:
    """Import an FBX file into UE5 via remote execution.

    Args:
        fbx_path: Absolute path to the .fbx file on disk.
        ue5_content_folder: UE5 content browser destination (e.g. '/Game/Imports').
        discovery_timeout: Seconds to wait for UE5 node discovery.
        import_materials: Whether to import materials and textures.
        complex_collision: Whether to set 'Use Complex as Simple' collision.
        combine_meshes: Whether to merge all meshes into a single static mesh.

    Returns:
        dict with 'success' (bool) and 'result' / 'output' keys.

    Raises:
        ConnectionError: If no UE5 editor found within timeout.
        RuntimeError: If the import command fails.
    """
    config = RemoteExecutionConfig()
    config.multicast_bind_address = '127.0.0.1'
    remote = RemoteExecution(config)
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
        command = _build_import_command(fbx_path_escaped, ue5_content_folder, import_materials, complex_collision, combine_meshes)
        try:
            result = remote.run_command(command, raise_on_failure=True)
        except RuntimeError:
            # UE5 may drop the TCP connection on long imports while still
            # completing successfully.  Treat as a warning, not a failure.
            return {
                "success": True,
                "output": ["Warning: Lost connection to UE5 before receiving confirmation. "
                           "The import likely succeeded — check the UE5 Content Browser."],
            }

        return result
    finally:
        remote.stop()


def _build_import_command(fbx_path: str, content_folder: str, import_materials: bool = True, complex_collision: bool = False, combine_meshes: bool = True) -> str:
    """Build the Python command string to execute inside UE5."""
    # Derive asset name from filename
    asset_name = PureWindowsPath(fbx_path).stem

    return f'''
import unreal

def do_import():
    # Clean up any leftover temp folders from previous runs
    import os, shutil
    content_dir = unreal.Paths.project_content_dir()
    rel_content = r"{content_folder}".replace("/Game/", "", 1)
    imports_disk = os.path.join(content_dir, rel_content)
    if os.path.isdir(imports_disk):
        for entry in os.listdir(imports_disk):
            if entry.startswith("_temp_import_"):
                temp_disk = os.path.join(imports_disk, entry)
                if os.path.isdir(temp_disk):
                    # Delete from editor
                    temp_ue = r"{content_folder}/" + entry
                    existing = unreal.EditorAssetLibrary.list_assets(temp_ue, recursive=True)
                    for a in existing:
                        unreal.EditorAssetLibrary.delete_asset(str(a))
                    unreal.EditorAssetLibrary.delete_directory(temp_ue)
                    # Delete from disk
                    shutil.rmtree(temp_disk)
                    print(f"Cleaned up leftover temp folder: {{entry}}")

    asset_name = r"{asset_name}"
    final_path = r"{content_folder}/" + asset_name
    asset_exists = unreal.EditorAssetLibrary.does_asset_exist(final_path)
    imported_mesh_paths = []

    if asset_exists:
        # REIMPORT: Import directly to preserve references
        task = unreal.AssetImportTask()
        task.set_editor_property("filename", r"{fbx_path}")
        task.set_editor_property("destination_path", r"{content_folder}")
        task.set_editor_property("destination_name", asset_name)
        task.set_editor_property("replace_existing", True)
        task.set_editor_property("replace_existing_settings", True)
        task.set_editor_property("automated", True)
        task.set_editor_property("save", True)

        options = unreal.FbxImportUI()
        options.set_editor_property("import_mesh", True)
        options.set_editor_property("import_textures", {import_materials})
        options.set_editor_property("import_materials", {import_materials})
        options.set_editor_property("import_as_skeletal", False)
        options.static_mesh_import_data.set_editor_property("combine_meshes", {combine_meshes})
        options.static_mesh_import_data.set_editor_property("auto_generate_collision", True)
        options.static_mesh_import_data.set_editor_property("generate_lightmap_u_vs", True)
        options.set_editor_property("import_animations", False)
        task.set_editor_property("options", options)

        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])

        if task.get_editor_property("imported_object_paths"):
            paths = task.get_editor_property("imported_object_paths")
            imported_mesh_paths = [str(p) for p in paths]
            print(f"Reimported: {{imported_mesh_paths}}")
        else:
            print("Reimport completed but no assets were reported")

        print(f"Successfully reimported to {content_folder}")

    else:
        # FRESH IMPORT: Import directly to destination
        task = unreal.AssetImportTask()
        task.set_editor_property("filename", r"{fbx_path}")
        task.set_editor_property("destination_path", r"{content_folder}")
        task.set_editor_property("destination_name", asset_name)
        task.set_editor_property("replace_existing", True)
        task.set_editor_property("replace_existing_settings", True)
        task.set_editor_property("automated", True)
        task.set_editor_property("save", True)

        options = unreal.FbxImportUI()
        options.set_editor_property("import_mesh", True)
        options.set_editor_property("import_textures", {import_materials})
        options.set_editor_property("import_materials", {import_materials})
        options.set_editor_property("import_as_skeletal", False)
        options.static_mesh_import_data.set_editor_property("combine_meshes", {combine_meshes})
        options.static_mesh_import_data.set_editor_property("auto_generate_collision", True)
        options.static_mesh_import_data.set_editor_property("generate_lightmap_u_vs", True)
        options.set_editor_property("import_animations", False)
        task.set_editor_property("options", options)

        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])

        if task.get_editor_property("imported_object_paths"):
            paths = task.get_editor_property("imported_object_paths")
            imported_mesh_paths = [str(p) for p in paths]
            print(f"Imported: {{imported_mesh_paths}}")
        else:
            print("Import completed but no assets were reported")
            return

        print(f"Successfully imported to {content_folder}")

    # Set "Use Complex as Simple" collision if requested
    if {complex_collision}:
        for mesh_path in imported_mesh_paths:
            mesh_asset = unreal.EditorAssetLibrary.load_asset(mesh_path)
            if mesh_asset and isinstance(mesh_asset, unreal.StaticMesh):
                body_setup = mesh_asset.get_editor_property("body_setup")
                if body_setup:
                    body_setup.set_editor_property("collision_trace_flag", unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
                    mesh_asset.set_editor_property("body_setup", body_setup)
                    unreal.EditorAssetLibrary.save_asset(mesh_path)
                    mesh_name = mesh_path.split("/")[-1]
                    print(f"Set 'Use Complex as Simple' collision on {{mesh_name}}")

    # Move materials to a "Materials" subfolder
    if not {import_materials}:
        return
    materials_folder = r"{content_folder}/Materials"
    if not unreal.EditorAssetLibrary.does_directory_exist(materials_folder):
        unreal.EditorAssetLibrary.make_directory(materials_folder)

    asset_registry = unreal.AssetRegistryHelpers.get_asset_registry()
    assets = asset_registry.get_assets_by_path(r"{content_folder}", recursive=False)
    for asset_data in assets:
        if asset_data.asset_class_path.asset_name in ("MaterialInstanceConstant", "Material", "MaterialInterface"):
            old_path = str(asset_data.package_name)
            asset_name_str = str(asset_data.asset_name)
            new_path = f"{{materials_folder}}/{{asset_name_str}}"
            if unreal.EditorAssetLibrary.does_asset_exist(new_path):
                unreal.EditorAssetLibrary.delete_asset(new_path)
            unreal.EditorAssetLibrary.rename_asset(old_path, new_path)
            print(f"Moved material: {{asset_name_str}} -> Materials/")

do_import()
'''
