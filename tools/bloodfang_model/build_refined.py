"""Build the original refined dragon; outputs remain staged for visual review."""
import argparse
import json
from pathlib import Path
import sys
import bpy

sys.path.insert(0,str(Path(__file__).resolve().parent))
from refined_geometry import create_refined
from build_bloodfang import configure_studio, point_at
from refined_texture import bake_atlas, reuse_atlas
from refined_rig import create_dragon_rig, build_dragon_actions
from refined_export import export_refined


def render_views(rig,clips,camera,out):
    scene=bpy.context.scene;actions={name:action for name,action,last in clips}
    rig.animation_data.action=actions['Idle'];scene.frame_set(1)
    camera.data.ortho_scale=6.45
    scene.render.resolution_x=1280;scene.render.resolution_y=1100;scene.cycles.samples=48
    for name,location in [('hero',(6,-12,5.5)),('rear',(-7,12,5.5))]:
        camera.location=location;point_at(camera,(0,.08,1.60))
        scene.render.filepath=str(out/f'bloodfang-refined-{name}.png')
        bpy.ops.render.render(write_still=True)
    camera.location=(4,-13,5.7);point_at(camera,(0,.08,1.55))
    scene.render.resolution_x=520;scene.render.resolution_y=520;scene.cycles.samples=20
    motion=out/'motion';motion.mkdir(exist_ok=True)
    for name,frames in [('Idle',[1,19]),('Move',[4,10]),('Attack',[1,16]),
                         ('Death',[1,42]),('Angry',[1,19]),('Happy',[4,10])]:
        rig.animation_data.action=actions[name]
        for frame in frames:
            scene.frame_set(frame);scene.render.filepath=str(motion/f'{name.lower()}-{frame:02}.png')
            bpy.ops.render.render(write_still=True)
    rig.animation_data.action=actions['Idle'];scene.frame_set(1)
    camera.location=(6,-12,5.5);point_at(camera,(0,.08,1.60))
    scene.render.resolution_x=1280;scene.render.resolution_y=1100;scene.cycles.samples=48


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--preview',action='store_true')
    parser.add_argument('--skip-renders',action='store_true')
    parser.add_argument('--reuse-atlas-from',type=Path)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    args.output.mkdir(parents=True,exist_ok=True)
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    mesh=create_refined()
    mesh.data.calc_loop_triangles()
    print(f'REFINED_GEOMETRY vertices={len(mesh.data.vertices)} triangles={len(mesh.data.loop_triangles)}',flush=True)
    if not args.preview:
        atlas_path=args.output/'bloodfang-refined-atlas.png'
        texture=(reuse_atlas(mesh,args.reuse_atlas_from,atlas_path) if args.reuse_atlas_from
                 else bake_atlas(mesh,atlas_path))
        rig=create_dragon_rig(mesh);clips=build_dragon_actions(rig)
        stats=export_refined(mesh,rig,clips,args.output/'bloodfang-refined.mesh.json',texture)
        (args.output/'model-summary.json').write_text(json.dumps(stats,indent=2),encoding='utf-8')
        print('REFINED_EXPORT_COMPLETE '+json.dumps(stats),flush=True)
        rig.animation_data.action=clips[0][1];bpy.context.scene.frame_set(1)
        bpy.ops.object.select_all(action='DESELECT');mesh.select_set(True);rig.select_set(True)
        bpy.context.view_layer.objects.active=rig
        bpy.ops.export_scene.gltf(filepath=str(args.output/'bloodfang-refined.glb'),export_format='GLB',
                                 use_selection=True,export_animations=True,export_animation_mode='ACTIONS',
                                 export_skins=True,export_all_influences=True)
        camera=configure_studio()
        if not args.skip_renders:render_views(rig,clips,camera,args.output)
        bpy.ops.object.select_all(action='DESELECT');mesh.select_set(True);rig.select_set(True)
        bpy.context.view_layer.objects.active=rig
        bpy.ops.wm.save_as_mainfile(filepath=str(args.output/'bloodfang-refined.blend'))
        print('REFINED_COMPLETE',flush=True)
        return
    camera=configure_studio();camera.data.ortho_scale=6.45
    camera.location=(6,-12,5.5);point_at(camera,(0,.13,1.52))
    scene=bpy.context.scene;scene.cycles.samples=48
    scene.render.resolution_x=1280;scene.render.resolution_y=1100
    scene.render.filepath=str(args.output/'bloodfang-refined-hero.png')
    bpy.ops.render.render(write_still=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output/'bloodfang-refined-preview.blend'))
    print('REFINED_PREVIEW_COMPLETE',flush=True)


if __name__=='__main__':main()
