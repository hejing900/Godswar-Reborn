"""Refined true-UV interchange using the established authored rig matrix contract."""
import json
import bpy
from build_bloodfang import export_interchange
from refined_geometry import PALETTE


def export_refined(mesh,rig,clips,path,texture):
    stats=export_interchange(mesh,rig,clips,path)
    document=json.loads(path.read_text(encoding='utf-8'))
    document['materials']=[{'name':name,'base_color':list(color)} for name,color in PALETTE]
    document['texture']=texture
    document['texture_uv']='Original unwrapped UV islands with baked scale pigment and crevice AO'
    path.write_text(json.dumps(document,separators=(',',':')),encoding='utf-8')
    low=[float('inf')]*3;high=[float('-inf')]*3;bounds={}
    for name,action,last in clips:
        rig.animation_data.action=action;clip_low=[float('inf')]*3;clip_high=[float('-inf')]*3
        for frame in range(1,last+1):
            bpy.context.scene.frame_set(frame);bpy.context.view_layer.update()
            evaluated=mesh.evaluated_get(bpy.context.evaluated_depsgraph_get());data=evaluated.to_mesh()
            for vertex in data.vertices:
                x,y,z=evaluated.matrix_world@vertex.co
                native=(-x,z,y)
                for axis,value in enumerate(native):
                    clip_low[axis]=min(clip_low[axis],value);clip_high[axis]=max(clip_high[axis],value)
            evaluated.to_mesh_clear()
        bounds[name]={'minimum':clip_low,'maximum':clip_high}
        low=[min(a,b) for a,b in zip(low,clip_low)];high=[max(a,b) for a,b in zip(high,clip_high)]
    stats['native_coordinate_transform']='(-X,Z,Y), front -Z'
    stats['native_animation_bounds']=bounds
    stats['native_conservative_bounds']={'minimum':[v-.06 for v in low],'maximum':[v+.06 for v in high]}
    stats['texture']=texture
    return stats
