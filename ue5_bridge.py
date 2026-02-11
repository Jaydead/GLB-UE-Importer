"""UE5 remote execution wrapper for FBX import."""

import time
from pathlib import PureWindowsPath

from remote_execution import RemoteExecution, RemoteExecutionConfig


def import_fbx(fbx_path: str, ue5_content_folder: str = "/Game/Imports", discovery_timeout: float = 10.0, import_materials: bool = True) -> dict:
    """Import an FBX file into UE5 via remote execution.

    Args:
        fbx_path: Absolute path to the .fbx file on disk.
        ue5_content_folder: UE5 content browser destination (e.g. '/Game/Imports').
        discovery_timeout: Seconds to wait for UE5 node discovery.
        import_materials: Whether to import materials and textures.

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
        command = _build_import_command(fbx_path_escaped, ue5_content_folder, import_materials)
        result = remote.run_command(command, raise_on_failure=True)

        return result
    finally:
        remote.stop()


def _build_import_command(fbx_path: str, content_folder: str, import_materials: bool = True) -> str:
    """Build the Python command string to execute inside UE5."""
    # Derive asset name from filename
    asset_name = PureWindowsPath(fbx_path).stem

    return f'''
import unreal

def do_import():
    import uuid as _uuid

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

    if asset_exists:
        # REIMPORT: Import directly to preserve references
        task = unreal.AssetImportTask()
        task.set_editor_property("filename", r"{fbx_path}")
        task.set_editor_property("destination_path", r"{content_folder}")
        task.set_editor_property("destination_name", asset_name)
        task.set_editor_property("replace_existing", True)
        task.set_editor_property("automated", True)
        task.set_editor_property("save", True)

        options = unreal.FbxImportUI()
        options.set_editor_property("import_mesh", True)
        options.set_editor_property("import_textures", {import_materials})
        options.set_editor_property("import_materials", {import_materials})
        options.set_editor_property("import_as_skeletal", False)
        options.static_mesh_import_data.set_editor_property("combine_meshes", True)
        options.static_mesh_import_data.set_editor_property("auto_generate_collision", True)
        options.static_mesh_import_data.set_editor_property("generate_lightmap_u_vs", True)
        options.set_editor_property("import_animations", False)
        task.set_editor_property("options", options)

        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])

        if task.get_editor_property("imported_object_paths"):
            paths = task.get_editor_property("imported_object_paths")
            print(f"Reimported: {{list(paths)}}")
        else:
            print("Reimport completed but no assets were reported")

        print(f"Successfully reimported to {content_folder}")

    else:
        # FRESH IMPORT: Use temp folder to work around Interchange rename issue
        temp_folder = r"{content_folder}/_temp_import_" + _uuid.uuid4().hex[:8]

        task = unreal.AssetImportTask()
        task.set_editor_property("filename", r"{fbx_path}")
        task.set_editor_property("destination_path", temp_folder)
        task.set_editor_property("replace_existing", True)
        task.set_editor_property("automated", True)
        task.set_editor_property("save", True)

        options = unreal.FbxImportUI()
        options.set_editor_property("import_mesh", True)
        options.set_editor_property("import_textures", {import_materials})
        options.set_editor_property("import_materials", {import_materials})
        options.set_editor_property("import_as_skeletal", False)
        options.static_mesh_import_data.set_editor_property("combine_meshes", True)
        options.static_mesh_import_data.set_editor_property("auto_generate_collision", True)
        options.static_mesh_import_data.set_editor_property("generate_lightmap_u_vs", True)
        options.set_editor_property("import_animations", False)
        task.set_editor_property("options", options)

        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])

        if task.get_editor_property("imported_object_paths"):
            paths = task.get_editor_property("imported_object_paths")
            print(f"Imported: {{list(paths)}}")
        else:
            print("Import completed but no assets were reported")
            return

        # Move assets from temp folder to final destination
        temp_assets = unreal.EditorAssetLibrary.list_assets(temp_folder, recursive=False)
        for asset_path in temp_assets:
            asset_path = str(asset_path)
            name = asset_path.split("/")[-1].split(".")[0]
            # Fix Interchange renaming: strip numeric suffix added to mesh name
            if name != asset_name and name.startswith(asset_name):
                suffix = name[len(asset_name):]
                if suffix.isdigit():
                    name = asset_name
            dest = r"{content_folder}/" + name
            if unreal.EditorAssetLibrary.does_asset_exist(dest):
                unreal.EditorAssetLibrary.delete_asset(dest)
                unreal.SystemLibrary.collect_garbage()
            unreal.EditorAssetLibrary.rename_asset(asset_path, dest)

        unreal.EditorAssetLibrary.delete_directory(temp_folder)

        # Physically delete the temp folder from disk
        content_dir = unreal.Paths.project_content_dir()
        rel_path = temp_folder.replace("/Game/", "", 1)
        disk_path = os.path.join(content_dir, rel_path)
        if os.path.isdir(disk_path):
            shutil.rmtree(disk_path)

        print(f"Successfully imported to {content_folder}")

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
