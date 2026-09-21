"""Refined original juvenile dragon rig with six hovering flight actions."""
import math
import bpy
from mathutils import Vector, Quaternion
from refined_geometry import TAIL


def create_dragon_rig(mesh):
    data=bpy.data.armatures.new("Bloodfang_RefinedSkeleton")
    rig=bpy.data.objects.new("Bloodfang_RefinedRig",data)
    bpy.context.collection.objects.link(rig)
    bpy.context.view_layer.objects.active=rig;rig.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    layout=[("root",None,(0,0,0),(0,.5,0)),
            ("spine","root",(0,0,.66),(0,-.02,1.58)),
            ("neck","spine",(0,-.02,1.58),(0,-.25,2.20)),
            ("head","neck",(0,-.25,2.20),(0,-.25,2.65)),
            ("jaw","head",(0,-.43,2.17),(0,-.98,2.16)),
            ("tail.01","spine",TAIL[0],TAIL[2]),
            ("tail.02","tail.01",TAIL[2],TAIL[4]),
            ("tail.03","tail.02",TAIL[4],TAIL[7]),
            ("tail.04","tail.03",TAIL[7],TAIL[9])]
    for s,suffix in ((1,"L"),(-1,"R")):
        layout.extend([
            ("wing."+suffix,"spine",(s*.16,.05,1.57),(s*1.58,.27,2.43)),
            ("wingtip."+suffix,"wing."+suffix,(s*1.58,.27,2.43),(s*2.78,.43,2.24)),
            ("arm."+suffix,"spine",(s*.31,-.02,1.47),(s*.52,-.54,.97)),
            ("foot."+suffix,"spine",(s*.28,.13,.82),(s*.46,-.26,.18)),
        ])
    for name,parent,head,tail in layout:
        bone=data.edit_bones.new(name);bone.head=head;bone.tail=tail
        if parent:bone.parent=data.edit_bones[parent]
        if name!="root":bone.align_roll(Vector((0,-1,0)))
    bpy.ops.object.mode_set(mode="OBJECT")
    mesh.parent=rig;modifier=mesh.modifiers.new("Original dragon deformation","ARMATURE");modifier.object=rig
    rig.show_in_front=True;rig.data.display_type="STICK"
    for bone in rig.pose.bones:bone.rotation_mode="XYZ"
    return rig


def build_dragon_actions(rig):
    scene=bpy.context.scene;scene.render.fps=24
    clips=[]
    for name,last in [("Idle",48),("Move",24),("Attack",30),("Death",42),("Angry",36),("Happy",36)]:
        rig.animation_data_create();action=bpy.data.actions.new("Bloodfang_Refined_"+name)
        action.use_fake_user=True;rig.animation_data.action=action
        for frame in sorted(set([1,last]+list(range(1,last+1,3)))):
            scene.frame_set(frame);t=(frame-1)/(last-1);phase=t*math.tau
            for bone in rig.pose.bones:
                bone.location=(0,0,0);bone.rotation_euler=(0,0,0);bone.scale=(1,1,1)
            root=rig.pose.bones["root"];spine=rig.pose.bones["spine"]
            neck=rig.pose.bones["neck"];head=rig.pose.bones["head"];jaw=rig.pose.bones["jaw"]
            tail=.055*math.sin(phase);arms=.0;feet=.0
            if name=="Idle":
                root.location.z=.25+.045*math.sin(phase*2-.5)
                spine.rotation_euler.x=.13
                flap=.17*math.sin(phase*2);tip=.075*math.sin(phase*2-.55)
                neck.rotation_euler.x=-.09+.025*math.sin(phase)
                head.rotation_euler.z=.025*math.sin(phase)
                arms=-.19+.025*math.sin(phase);feet=.28
            elif name=="Move":
                root.location.z=.34+.085*math.sin(phase*2-.5)
                spine.rotation_euler.x=.32;neck.rotation_euler.x=-.22
                flap=.39*math.sin(phase*2);tip=.17*math.sin(phase*2-.55)
                arms=-.35;feet=.48;tail=.10*math.sin(phase-.5)
            elif name=="Attack":
                strike=max(0,math.sin(math.pi*min(1,max(0,(t-.15)/.68))))
                root.location.y=-.50*strike;root.location.z=.23+.08*strike
                spine.rotation_euler.x=.13+.20*strike;neck.rotation_euler.x=-.09+.17*strike
                head.rotation_euler.x=-.12*strike
                # The jaw's local X runs toward -X: negative rotation opens it.
                jaw.rotation_euler.x=-.52*strike
                flap=-.24*strike;tip=-.10*strike;arms=-.19-.24*strike;feet=.28
                tail=-.13*strike
            elif name=="Angry":
                bristle=math.sin(math.pi*t)
                root.location.z=.25+.025*math.sin(phase*4)
                spine.rotation_euler.x=.10;feet=.28
                neck.rotation_euler.x=-.12*bristle
                head.rotation_euler.z=.055*math.sin(phase*3)*bristle
                jaw.rotation_euler.x=-.22*bristle
                flap=-.16*bristle+.03*math.sin(phase*4);tip=-.12*bristle
                arms=-.18*bristle;tail=.15*math.sin(phase*3)*bristle
            elif name=="Happy":
                root.location.z=.25+.20*(1-math.cos(phase*2))*.5
                feet=.32;spine.rotation_euler.x=.13
                spine.rotation_euler.z=.055*math.sin(phase*2)
                neck.rotation_euler.z=-.05*math.sin(phase*2)
                flap=.22*math.sin(phase*3);tip=.12*math.sin(phase*3-.5)
                arms=-.18-.12*math.sin(phase*2);tail=.14*math.sin(phase*2)
            else:
                fall=min(1,max(0,(t-.10)/.62));smooth=fall*fall*(3-2*fall)
                # Settle onto the left flank, with the face turned sideways.
                root.location.x=.82*smooth;root.location.z=.07
                root.rotation_euler.x=.10*smooth
                root.rotation_euler.y=-1.52*smooth
                root.rotation_euler.z=-.08*smooth
                neck.rotation_euler.x=-.12*smooth;head.rotation_euler.z=.12*smooth
                jaw.rotation_euler.x=-.08*smooth
                flap=-.12*smooth;tip=-.35*smooth;arms=.55*smooth;feet=.50*smooth
                tail=0
            for sign,suffix in ((1,"L"),(-1,"R")):
                rig.pose.bones["wing."+suffix].rotation_euler.z=sign*flap
                rig.pose.bones["wingtip."+suffix].rotation_euler.z=sign*tip
                if name=="Death":
                    # Folding through local X brings each wing back along the body.
                    rig.pose.bones["wing."+suffix].rotation_euler.x=-1.50*smooth
                    rig.pose.bones["wingtip."+suffix].rotation_euler.x=-.35*smooth
                rig.pose.bones["arm."+suffix].rotation_euler.x=arms
                rig.pose.bones["foot."+suffix].rotation_euler.x=feet
            for i in range(1,5):
                rig.pose.bones[f"tail.{i:02}"].rotation_euler.z=tail*(1+i*.15)
                if name in ("Idle","Move","Happy"):
                    rig.pose.bones[f"tail.{i:02}"].rotation_euler.x=.035*math.sin(phase-i*.65)
            if name=="Death":
                # Let the curled tail lie beside the flank instead of standing up.
                tail_bone=rig.pose.bones["tail.01"]
                rest_rotation=tail_bone.bone.matrix_local.to_quaternion()
                relaxed=rest_rotation.inverted()@Quaternion((0,0,1),1.17*smooth)@rest_rotation
                tail_bone.rotation_euler=relaxed.to_euler("XYZ")
                bpy.context.view_layer.update()
                obj=rig.children[0].evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=obj.to_mesh()
                low=min((obj.matrix_world@v.co).z for v in mesh.vertices);obj.to_mesh_clear()
                # The studio floor is Z=-0.08; contact keeps 0.02 clearance.
                if low<-.06:root.location.z+=-.06-low
            for bone in rig.pose.bones:
                bone.keyframe_insert("location",frame=frame,group=bone.name)
                bone.keyframe_insert("rotation_euler",frame=frame,group=bone.name)
                bone.keyframe_insert("scale",frame=frame,group=bone.name)
        clips.append((name,action,last))
    rig.animation_data.action=clips[0][1];scene.frame_start=1;scene.frame_end=48;scene.frame_set(1)
    return clips
