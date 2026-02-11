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
    decimate_meshes(args.decimate)
    apply_transforms()
    export_fbx(args.output)
    print("Done")


if __name__ == "__main__":
    main()
