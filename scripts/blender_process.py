"""Headless Blender script: import GLB, decimate meshes, export FBX for UE5.

Usage:
    blender --background --python blender_process.py -- --input model.glb --output model.fbx --decimate 0.5
"""

import argparse
import sys

import bpy


def parse_args():
    # Blender passes everything after '--' to the script
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description="GLB to FBX converter")
    parser.add_argument("--input", required=True, help="Input GLB file path")
    parser.add_argument("--output", required=True, help="Output FBX file path")
    parser.add_argument(
        "--decimate",
        type=float,
        default=0.5,
        help="Decimate ratio (0.0-1.0, default 0.5)",
    )
    parser.add_argument(
        "--merge-children",
        action="store_true",
        help="Merge child meshes under EMPTY parents into single meshes",
    )
    return parser.parse_args(argv)


def clean_scene():
    """Remove all default objects."""
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    # Remove orphan data
    for block in bpy.data.meshes:
        if block.users == 0:
            bpy.data.meshes.remove(block)
    for block in bpy.data.materials:
        if block.users == 0:
            bpy.data.materials.remove(block)
    for block in bpy.data.cameras:
        if block.users == 0:
            bpy.data.cameras.remove(block)
    for block in bpy.data.lights:
        if block.users == 0:
            bpy.data.lights.remove(block)


def import_glb(filepath):
    """Import a GLB/GLTF file."""
    print(f"Importing: {filepath}")
    bpy.ops.import_scene.gltf(filepath=filepath)
    print(f"Imported {len(bpy.context.selected_objects)} objects")


def merge_mesh_groups():
    """Merge mesh children under EMPTY parents into single meshes.

    GLB files import with EMPTY parent objects containing MESH children.
    This merges each group into a single mesh with the parent's name.
    """
    # Find all EMPTY objects that have MESH children
    empty_parents = []
    for obj in bpy.data.objects:
        if obj.type == "EMPTY":
            mesh_children = [c for c in obj.children if c.type == "MESH"]
            if mesh_children:
                empty_parents.append((obj, mesh_children))

    print(f"Found {len(empty_parents)} parent groups with meshes")

    for parent, mesh_children in empty_parents:
        parent_name = parent.name

        # Clear parent on mesh children (keep world transforms)
        bpy.ops.object.select_all(action="DESELECT")
        for child in mesh_children:
            child.select_set(True)
        bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")

        # Rename parent to free up the name for the merged mesh
        parent.name = parent_name + "__to_delete"

        if len(mesh_children) == 1:
            print(f"Reparenting single mesh under '{parent_name}'")
            mesh_children[0].name = parent_name
        else:
            print(f"Merging {len(mesh_children)} meshes under '{parent_name}'")
            bpy.ops.object.select_all(action="DESELECT")
            for child in mesh_children:
                child.select_set(True)
            bpy.context.view_layer.objects.active = mesh_children[0]
            bpy.ops.object.join()
            bpy.context.active_object.name = parent_name

    # Delete processed empty parents
    bpy.ops.object.select_all(action="DESELECT")
    for parent, _ in empty_parents:
        if parent.name in bpy.data.objects:
            bpy.data.objects[parent.name].select_set(True)
    if bpy.context.selected_objects:
        bpy.ops.object.delete()

    # Clean up any remaining childless empties (e.g., root nodes from GLB)
    bpy.ops.object.select_all(action="DESELECT")
    for obj in bpy.data.objects:
        if obj.type == "EMPTY" and len(obj.children) == 0:
            obj.select_set(True)
    if bpy.context.selected_objects:
        print(f"Cleaning up {len(bpy.context.selected_objects)} childless empties")
        bpy.ops.object.delete()

    remaining = [obj for obj in bpy.data.objects if obj.type == "MESH"]
    print(f"Total meshes after merging: {len(remaining)}")


def decimate_meshes(ratio):
    """Apply decimation to all mesh objects."""
    if ratio >= 1.0:
        print("Decimate ratio is 1.0, skipping decimation")
        return

    mesh_objects = [obj for obj in bpy.data.objects if obj.type == "MESH"]
    print(f"Decimating {len(mesh_objects)} meshes with ratio {ratio}")

    for obj in mesh_objects:
        bpy.context.view_layer.objects.active = obj
        modifier = obj.modifiers.new(name="Decimate", type="DECIMATE")
        modifier.decimate_type = "COLLAPSE"
        modifier.ratio = ratio
        bpy.ops.object.modifier_apply(modifier=modifier.name)
        print(f"  Decimated '{obj.name}': {len(obj.data.polygons)} polys remaining")


def apply_transforms():
    """Apply all transforms to objects."""
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)


def export_fbx(filepath):
    """Export scene as FBX with UE5-compatible settings."""
    print(f"Exporting FBX: {filepath}")
    bpy.ops.export_scene.fbx(
        filepath=filepath,
        axis_forward="-Z",
        axis_up="Y",
        use_selection=False,
        global_scale=1.0,
        apply_unit_scale=True,
        apply_scale_options="FBX_SCALE_ALL",
        use_mesh_modifiers=True,
        mesh_smooth_type="FACE",
        use_triangles=True,
        use_tspace=True,
        embed_textures=True,
        path_mode="COPY",
        bake_anim=False,
    )
    print("Export complete")


def main():
    args = parse_args()
    clean_scene()
    import_glb(args.input)
    if args.merge_children:
        merge_mesh_groups()
    decimate_meshes(args.decimate)
    apply_transforms()
    export_fbx(args.output)
    print("Done")


if __name__ == "__main__":
    main()
