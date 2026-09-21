"""Original scale and membrane painting, baked to one portable sRGB UV atlas."""
from pathlib import Path
import bpy
import numpy as np


def ramp(nodes, values):
    node=nodes.new('ShaderNodeValToRGB')
    elements=node.color_ramp.elements
    for element in list(elements)[2:]:elements.remove(element)
    for index,(position,color) in enumerate(values):
        element=elements[index] if index<2 else elements.new(position)
        element.position=position;element.color=(*color,1)
    return node


def paint_materials(mesh):
    """Object-space cells stay continuous over seams; original procedural pigment."""
    for index,mat in enumerate(mesh.data.materials):
        if index not in (0,1,2,3,4,5,6,10):continue
        nodes=mat.node_tree.nodes;links=mat.node_tree.links
        shader=nodes.get('Principled BSDF')
        coordinate=nodes.new('ShaderNodeTexCoord')
        vector=nodes.new('ShaderNodeVectorMath');vector.operation='MULTIPLY'
        vector.inputs[1].default_value=(1,1,1.5 if index in (0,1,10) else 1)
        links.new(coordinate.outputs['Object'],vector.inputs[0])
        noise=nodes.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=3.2
        noise.inputs['Detail'].default_value=3
        links.new(vector.outputs['Vector'],noise.inputs['Vector'])
        mottling=ramp(nodes,[(.15,(.57,.60,.63)),(.85,(1.35,1.28,1.20))])
        links.new(noise.outputs['Fac'],mottling.inputs[0])
        pigment=nodes.new('ShaderNodeMixRGB');pigment.blend_type='MULTIPLY'
        pigment.inputs[0].default_value=1
        color=list(mat.diffuse_color)
        if index in (0,10):color=[v*1.5 for v in color[:3]]+[1]
        pigment.inputs[1].default_value=color
        links.new(mottling.outputs[0],pigment.inputs[2])
        result=pigment.outputs[0]
        if index in (0,1,2,3,10):
            cells=nodes.new('ShaderNodeTexVoronoi');cells.feature='DISTANCE_TO_EDGE'
            cells.inputs['Scale'].default_value=13 if index in (0,1,10) else 6
            cells.inputs['Randomness'].default_value=.76
            links.new(vector.outputs['Vector'],cells.inputs['Vector'])
            values=[(0,(.54,.57,.59)),(.032,(.72,.76,.80)),(.09,(1.09,1.12,1.14)),(.32,(.93,.96,1))]
            if index in (2,3):values=[(0,(.83,.81,.82)),(.014,(.88,.86,.87)),(.045,(1,1,1)),(.30,(1.045,1.012,1))]
            scales=ramp(nodes,values);links.new(cells.outputs['Distance'],scales.inputs[0])
            layer=nodes.new('ShaderNodeMixRGB');layer.blend_type='MULTIPLY'
            layer.inputs[0].default_value=1
            links.new(result,layer.inputs[1]);links.new(scales.outputs[0],layer.inputs[2])
            result=layer.outputs[0]
        links.new(result,shader.inputs['Base Color'])


def bake_atlas(mesh,path,size=1024):
    scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=24
    scene.render.bake.margin=12;scene.render.bake.use_clear=True
    scene.render.bake.use_pass_direct=False;scene.render.bake.use_pass_indirect=False
    scene.render.bake.use_pass_color=True
    bpy.ops.object.select_all(action='DESELECT')
    mesh.select_set(True);bpy.context.view_layer.objects.active=mesh
    facial_uvs(mesh,spread=True)
    paint_materials(mesh)
    images=[]
    for name,kind in [('Bloodfang original scale pigment','DIFFUSE'),('Bloodfang original crevice AO','AO')]:
        image=bpy.data.images.new(name,width=size,height=size,alpha=True,float_buffer=True)
        image.colorspace_settings.name='Linear Rec.709'
        for mat in mesh.data.materials:
            node=mat.node_tree.nodes.new('ShaderNodeTexImage');node.image=image
            mat.node_tree.nodes.active=node
        print('BAKE_START '+kind,flush=True)
        bpy.ops.object.bake(type=kind)
        values=np.empty(size*size*4,dtype=np.float32);image.pixels.foreach_get(values)
        images.append(values.reshape((-1,4)))
    pigment,occlusion=images
    pigment[:,:3]*=.48+.52*np.clip(occlusion[:,:3],0,1)
    linear=np.clip(pigment[:,:3],0,1)
    pigment[:,:3]=np.where(linear<=.0031308,linear*12.92,1.055*np.power(linear,1/2.4)-.055)
    pigment[:,3]=1
    atlas=bpy.data.images.new('Bloodfang original painted atlas',width=size,height=size,alpha=True)
    atlas.colorspace_settings.name='sRGB'
    atlas.pixels.foreach_set(pigment.ravel());atlas.update()
    atlas.filepath_raw=str(path);atlas.file_format='PNG';atlas.save();atlas.pack()
    facial_uvs(mesh,spread=False)
    apply_atlas(mesh,atlas)
    print('BAKE_COMPLETE '+str(path),flush=True)
    return {'path':Path(path).name,'uv_origin':'bottom_left','color_space':'sRGB'}


def apply_atlas(mesh,atlas):
    """The source renders the same portable diffuse texture used in-game."""
    for mat in mesh.data.materials:
        nodes=mat.node_tree.nodes;links=mat.node_tree.links
        nodes.clear();output=nodes.new('ShaderNodeOutputMaterial')
        shader=nodes.new('ShaderNodeBsdfPrincipled');shader.inputs['Roughness'].default_value=.78
        texture=nodes.new('ShaderNodeTexImage');texture.image=atlas
        links.new(texture.outputs['Color'],shader.inputs['Base Color'])
        links.new(shader.outputs[0],output.inputs['Surface'])


def facial_uvs(mesh,spread=False):
    """Rasterize flat pigment tiles only while baking; render their stable centers."""
    for face in mesh.data.polygons:
        if face.material_index not in (7,8,9):continue
        left=.03+(face.material_index-7)*.31
        for index,loop in enumerate(face.loop_indices):
            corner=[(0,0),(1,0),(1,1),(0,1)][index%4] if spread else (.5,.5)
            mesh.data.uv_layers.active.data[loop].uv=(left+.23*corner[0],.945+.040*corner[1])


def reuse_atlas(mesh,directory,path):
    """Keep reviewed UVs and pixels during the bounded eye-rim topology repair."""
    with bpy.data.libraries.load(str(directory/'bloodfang-refined.blend'),link=False) as (source,target):
        target.meshes=['Bloodfang_RefinedOriginalMesh']
    reference=target.meshes[0]
    def coordinate(value):return tuple(round(x,6) for x in value)
    def key(data,face):return (face.material_index,tuple(sorted(coordinate(data.vertices[i].co) for i in face.vertices)))
    lookup={key(reference,face):{coordinate(reference.vertices[reference.loops[i].vertex_index].co):
                                tuple(reference.uv_layers.active.data[i].uv) for i in face.loop_indices}
            for face in reference.polygons}
    replaced=0
    for face in mesh.data.polygons:
        if face.material_index in (7,8,9):continue
        old=lookup.get(key(mesh.data,face))
        if old is None:
            if face.material_index!=8:raise ValueError('Unexpected changed surface during eye-only repair')
            continue
        for index in face.loop_indices:
            mesh.data.uv_layers.active.data[index].uv=old[coordinate(mesh.data.vertices[mesh.data.loops[index].vertex_index].co)]
        replaced+=1
    atlas=bpy.data.images.load(str(directory/'bloodfang-refined-atlas.png'),check_existing=False)
    atlas.name='Bloodfang original painted atlas';atlas.colorspace_settings.name='sRGB'
    atlas.pack();facial_uvs(mesh,spread=False);apply_atlas(mesh,atlas)
    if Path(path).read_bytes()!=(directory/'bloodfang-refined-atlas.png').read_bytes():
        raise ValueError('Reviewed atlas changed during eye-only repair')
    bpy.data.meshes.remove(reference)
    print(f'ATLAS_REUSED unchanged detailed polygon UVs={replaced}; facial pigments use tile centers',flush=True)
    return {'path':Path(path).name,'uv_origin':'bottom_left','color_space':'sRGB'}
