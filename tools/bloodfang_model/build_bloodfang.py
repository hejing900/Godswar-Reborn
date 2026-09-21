"""Run with Blender --background --python this_file.py -- --output DIRECTORY.

Creates original authored 3D geometry, rig, animation, source .blend, GLB,
documented JSON interchange and beauty/motion renders. Never reads client assets.
"""
import argparse
import json
import math
from pathlib import Path
import sys
import bpy
from mathutils import Vector

sys.path.insert(0,str(Path(__file__).resolve().parent))
from geometry import PALETTE
from dragon_geometry import create_dragon as create_bloodfang
from dragon_rig import create_dragon_rig as create_rig, build_dragon_actions as build_actions


def matrix_values(matrix):
    return [float(value) for row in matrix for value in row]


def export_interchange(mesh,rig,clips,path):
    """Matrices are row-major storage, Blender column-vector multiplication."""
    data=mesh.data
    data.calc_loop_triangles()
    materials=[{"name":name,"base_color":list(color)} for name,color in PALETTE]
    vertices=[]; triangles=[]
    groups={g.index:g.name for g in mesh.vertex_groups}
    # Dedup equal position/normal/material UV corners to retain hard surfaces.
    lookup={}
    for tri in data.loop_triangles:
        indexes=[]
        material=data.polygons[tri.polygon_index].material_index
        for loop_id in tri.loops:
            loop=data.loops[loop_id]
            source=data.vertices[loop.vertex_index]
            normal=tuple(data.corner_normals[loop_id].vector)
            uv=tuple(data.uv_layers.active.data[loop_id].uv)
            key=(source.index,normal,uv)
            if key not in lookup:
                lookup[key]=len(vertices)
                vertices.append({"position":list(source.co),"normal":list(normal),
                                 "uv":list(uv),"source_vertex":source.index,
                                 "weights":[{"bone":groups[g.group],"weight":g.weight}
                                            for g in source.groups if g.weight>0]})
            indexes.append(lookup[key])
        triangles.append({"vertices":indexes,"material":material})
    bones=[]
    for bone in rig.data.bones:
        local=bone.parent.matrix_local.inverted()@bone.matrix_local if bone.parent else bone.matrix_local
        bones.append({"name":bone.name,"parent":bone.parent.name if bone.parent else None,
                      "head":list(bone.head_local),"tail":list(bone.tail_local),
                      "matrix_local":matrix_values(local),
                      "matrix_world":matrix_values(bone.matrix_local),
                      "bind_matrix":matrix_values(bone.matrix_local),
                      "inverse_bind_matrix":matrix_values(bone.matrix_local.inverted()),
                      "local_rest_matrix":matrix_values(local)})
    actions=[]
    scene=bpy.context.scene
    for name,action,last in clips:
        rig.animation_data.action=action
        keyframes=[]
        for frame in range(1,last+1):
            scene.frame_set(frame)
            bpy.context.view_layer.update()
            poses={}
            for bone in rig.pose.bones:
                matrix=bone.parent.matrix.inverted()@bone.matrix if bone.parent else bone.matrix
                loc,rot,scale=bone.matrix_basis.decompose()
                poses[bone.name]={"location":list(loc),"rotation_quaternion":list(rot),
                                  "scale":list(scale),"matrix_basis":matrix_values(bone.matrix_basis),
                                  "local_pose_matrix":matrix_values(matrix),
                                  "matrix_local":matrix_values(matrix),
                                  "world_pose_matrix":matrix_values(bone.matrix)}
            keyframes.append({"frame":frame,"bones":poses})
        actions.append({"name":name,"fps":24,"frame_start":1,"frame_end":last,
                        "loop":name in ("Idle","Move"),"keyframes":keyframes})
    payload={"schema":"bloodfang_original_mesh_v1","authoring":"Original procedural mesh and authored rig; no imported assets",
             "units":"model","coordinate_system":"RH_Z_UP_FRONT_MINUS_Y",
             "matrix_convention":"row-major storage; column-vector multiplication",
             "texture_uv":"12 horizontal solid-color swatches, RGB from material base_color",
             "materials":materials,"vertices":vertices,"triangles":triangles,
             "bones":bones,"actions":actions}
    path.write_text(json.dumps(payload,separators=(",",":")),encoding="utf-8")
    return {"source_vertices":len(data.vertices),"export_vertices":len(vertices),
            "triangles":len(triangles),"bones":len(bones),
            "actions":{name:last for name,_,last in clips}}


def point_at(obj,target):
    obj.rotation_euler=(Vector(target)-obj.location).to_track_quat("-Z","Y").to_euler()


def configure_studio():
    scene=bpy.context.scene
    scene.render.engine="CYCLES"
    scene.cycles.samples=40
    scene.cycles.use_denoising=True
    scene.render.resolution_x=1200;scene.render.resolution_y=1200
    scene.render.resolution_percentage=100
    scene.render.image_settings.file_format="PNG"
    scene.render.film_transparent=False
    scene.world.color=(.15,.15,.15)
    scene.world.use_nodes=True
    scene.world.node_tree.nodes["Background"].inputs["Color"].default_value=(.36,.38,.43,1)
    scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value=.40
    scene.view_settings.view_transform="AgX"
    scene.view_settings.look="AgX - Medium High Contrast"
    bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.08))
    ground=bpy.context.object;ground.name="Studio ground (presentation only)"
    mat=bpy.data.materials.new("Warm neutral studio")
    mat.diffuse_color=(.53,.50,.47,1);mat.use_nodes=True
    mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value=(.53,.50,.47,1)
    mat.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value=.87
    ground.data.materials.append(mat)
    for name,location,power,color,size in [
        ("Large warm key",(-3.5,-5,7),900,(1,.87,.76),5),
        ("Cool face fill",(5,-3,4),600,(.74,.84,1),4),
        ("Soft ruby rim",(1.8,3,6),1200,(1,.46,.38),3),
    ]:
        light=bpy.data.lights.new(name,"AREA");light.energy=power;light.color=color;light.shape="DISK";light.size=size
        obj=bpy.data.objects.new(name,light);bpy.context.collection.objects.link(obj);obj.location=location
        point_at(obj,(0,0,2))
    camera_data=bpy.data.cameras.new("Presentation camera")
    camera=bpy.data.objects.new("Presentation camera",camera_data)
    bpy.context.collection.objects.link(camera)
    camera_data.type="ORTHO";camera_data.ortho_scale=6.7
    camera.location=(7,-12,6.7);point_at(camera,(0,.20,1.72))
    scene.camera=camera
    return camera


def render_views(rig,clips,camera,out):
    scene=bpy.context.scene
    actions={name:(action,last) for name,action,last in clips}
    rig.animation_data.action=actions["Idle"][0]
    scene.frame_set(1)
    for name,location in [("bloodfang-hero",(7,-12,6.2)),
                           ("bloodfang-rear",(-7,12,6.0))]:
        camera.location=location;point_at(camera,(0,.20,1.72))
        scene.render.filepath=str(out/(name+".png"))
        bpy.ops.render.render(write_still=True)
    camera.location=(4,-13,5.7);point_at(camera,(0,.20,1.72))
    scene.render.resolution_x=520;scene.render.resolution_y=520
    scene.cycles.samples=20
    motion=out/"motion"
    motion.mkdir(exist_ok=True)
    for name,frames in [("Idle",[1,19]),("Move",[4,10]),("Attack",[1,16]),
                        ("Death",[1,42]),("Angry",[1,19]),("Happy",[4,10])]:
        rig.animation_data.action=actions[name][0]
        for frame in frames:
            scene.frame_set(frame)
            scene.render.filepath=str(motion/(f"{name.lower()}-{frame:02}.png"))
            bpy.ops.render.render(write_still=True)
    scene.render.resolution_x=1200;scene.render.resolution_y=1200
    scene.cycles.samples=40
    rig.animation_data.action=actions["Idle"][0];scene.frame_set(1)
    camera.location=(7,-12,6.2);point_at(camera,(0,.20,1.72))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",required=True)
    parser.add_argument("--skip-renders",action="store_true")
    args=parser.parse_args(sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else [])
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    bpy.ops.object.select_all(action="SELECT");bpy.ops.object.delete(use_global=False)
    mesh=create_bloodfang()
    rig=create_rig(mesh)
    clips=build_actions(rig)
    stats=export_interchange(mesh,rig,clips,out/"bloodfang-original.mesh.json")
    print("BLOODFANG_STATS "+json.dumps(stats),flush=True)
    rig.animation_data.action=clips[0][1];bpy.context.scene.frame_set(1)
    bpy.ops.object.select_all(action="DESELECT")
    mesh.select_set(True);rig.select_set(True)
    bpy.context.view_layer.objects.active=rig
    bpy.ops.export_scene.gltf(filepath=str(out/"bloodfang-original.glb"),export_format="GLB",
                             use_selection=True,export_animations=True,export_animation_mode="ACTIONS",
                             export_skins=True,export_all_influences=True)
    camera=configure_studio()
    if not args.skip_renders:render_views(rig,clips,camera,out)
    # Opening the source file starts with the character and rig selected.
    bpy.ops.object.select_all(action="DESELECT")
    mesh.select_set(True);rig.select_set(True);bpy.context.view_layer.objects.active=rig
    bpy.ops.wm.save_as_mainfile(filepath=str(out/"bloodfang-original.blend"))
    stats["source"]=str(Path(__file__).resolve())
    (out/"model-summary.json").write_text(json.dumps(stats,indent=2),encoding="utf-8")
    print("BLOODFANG_COMPLETE",flush=True)


if __name__=="__main__":main()
