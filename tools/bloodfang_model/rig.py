"""Original deformation rig and authored animation cycles for Bloodfang."""
import math
import bpy
from mathutils import Vector


def create_rig(mesh):
    data=bpy.data.armatures.new("Bloodfang_Skeleton")
    rig=bpy.data.objects.new("Bloodfang_Rig",data)
    bpy.context.collection.objects.link(rig)
    bpy.context.view_layer.objects.active=rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    layout=[
        # Identity rest orientation makes root translation/rotation world-aligned.
        ("root",None,(0,0,0),(0,.5,0)),
        ("spine","root",(0,0,.75),(0,0,1.95)),
        ("head","spine",(0,0,1.97),(0,0,2.95)),
        ("tail","spine",(0,.23,.83),(0,.42,.20)),
    ]
    for s,suffix in ((1,"L"),(-1,"R")):
        layout.extend([
            ("ear."+suffix,"head",(s*.50,0,2.92),(s*.83,.04,3.99)),
            ("wing."+suffix,"spine",(s*.52,.07,1.80),(s*1.76,.03,2.50)),
            ("wingtip."+suffix,"wing."+suffix,(s*1.76,.03,2.50),(s*3,.10,2.19)),
            ("foot."+suffix,"spine",(s*.27,.04,.82),(s*.36,-.15,.29)),
        ])
    for name,parent,head,tail in layout:
        bone=data.edit_bones.new(name)
        bone.head=head;bone.tail=tail
        if parent:bone.parent=data.edit_bones[parent]
        # Consistent roll for deterministic interchange transforms.
        if name!="root":bone.align_roll(Vector((0,-1,0)))
    bpy.ops.object.mode_set(mode="OBJECT")
    mesh.parent=rig
    modifier=mesh.modifiers.new("Bloodfang deformation","ARMATURE")
    modifier.object=rig
    rig.show_in_front=True
    rig.data.display_type="STICK"
    for bone in rig.pose.bones:
        bone.rotation_mode="XYZ"
    return rig


def build_actions(rig):
    """24 fps: subtle hover, brisk flying travel, bite lunge, defeated fall."""
    scene=bpy.context.scene
    scene.render.fps=24
    clips=[]
    specs=[("Idle",48), ("Move",24), ("Attack",30), ("Death",42),
           ("Angry",36),("Happy",36)]
    for name,last in specs:
        rig.animation_data_create()
        action=bpy.data.actions.new("Bloodfang_"+name)
        action.use_fake_user=True
        rig.animation_data.action=action
        frames=sorted(set([1,last]+list(range(1,last+1,3))))
        for frame in frames:
            scene.frame_set(frame)
            t=(frame-1)/(last-1)
            phase=t*math.tau
            for bone in rig.pose.bones:
                bone.location=(0,0,0);bone.rotation_euler=(0,0,0);bone.scale=(1,1,1)
            root=rig.pose.bones["root"]
            spine=rig.pose.bones["spine"]
            head=rig.pose.bones["head"]
            if name=="Idle":
                flap=math.sin(phase*2)*.14
                root.location.z=.10+.055*math.sin(phase*2-.4)
                spine.rotation_euler.x=.025*math.sin(phase)
                head.rotation_euler.z=.035*math.sin(phase)
                ear=.055*math.sin(phase+.5)
                tip=.06*math.sin(phase*2-.5)
            elif name=="Move":
                flap=math.sin(phase*2)*.37
                root.location.z=.24+.13*math.sin(phase*2-.5)
                spine.rotation_euler.x=.13
                head.rotation_euler.x=-.10
                ear=-.11
                tip=.16*math.sin(phase*2-.65)
            elif name=="Attack":
                strike=max(0,math.sin(math.pi*min(1,max(0,(t-.18)/.62))))
                root.location.y=-.75*strike
                root.location.z=.10+.13*strike
                spine.rotation_euler.x=.25*strike
                head.rotation_euler.x=-.18*strike
                flap=.22*math.sin(phase)-.30*strike
                ear=-.16*strike
                tip=-.15*strike
            elif name=="Angry":
                bristle=math.sin(math.pi*t)
                root.location.z=.10+.025*math.sin(phase*4)
                spine.rotation_euler.x=.13*bristle
                head.rotation_euler.x=-.16*bristle
                head.rotation_euler.z=.08*math.sin(phase*3)*bristle
                flap=-.20*bristle+.07*math.sin(phase*4)
                tip=-.18*bristle
                ear=.26*bristle
            elif name=="Happy":
                root.location.z=.12+.19*(1-math.cos(phase*2))*.5
                spine.rotation_euler.z=.075*math.sin(phase*2)
                head.rotation_euler.z=-.12*math.sin(phase*2)
                flap=.25*math.sin(phase*3)
                tip=.14*math.sin(phase*3-.5)
                ear=-.10+.08*math.sin(phase*2)
            else:
                fall=min(1,max(0,(t-.12)/.6))
                smooth=fall*fall*(3-2*fall)
                root.location.y=-.20*smooth
                root.rotation_euler.x=1.36*smooth
                root.location.z=.10+.34*smooth
                spine.rotation_euler.x=.22*smooth
                head.rotation_euler.z=-.16*smooth
                flap=-.65*smooth
                tip=-.5*smooth
                ear=-.34*smooth
            for sign,suffix in ((1,"L"),(-1,"R")):
                # Local X bends through wing's screen-plane; local Z is flap axis.
                rig.pose.bones["wing."+suffix].rotation_euler.z=sign*flap
                rig.pose.bones["wingtip."+suffix].rotation_euler.z=sign*tip
                rig.pose.bones["ear."+suffix].rotation_euler.x=ear
                rig.pose.bones["foot."+suffix].rotation_euler.x=.10 if name=="Move" else 0
            rig.pose.bones["tail"].rotation_euler.x=.10*math.sin(phase)
            if name=="Death":
                bpy.context.view_layer.update()
                evaluated=rig.children[0].evaluated_get(bpy.context.evaluated_depsgraph_get())
                deformed=evaluated.to_mesh()
                minimum=min((evaluated.matrix_world@v.co).z for v in deformed.vertices)
                evaluated.to_mesh_clear()
                # Authored landing remains on the presentation floor at every key.
                if minimum<.075:root.location.z+=.075-minimum
            for bone in rig.pose.bones:
                bone.keyframe_insert("location",frame=frame,group=bone.name)
                bone.keyframe_insert("rotation_euler",frame=frame,group=bone.name)
                bone.keyframe_insert("scale",frame=frame,group=bone.name)
        clips.append((name,action,last))
    rig.animation_data.action=clips[0][1]
    scene.frame_start=1;scene.frame_end=48;scene.frame_set(1)
    return clips
