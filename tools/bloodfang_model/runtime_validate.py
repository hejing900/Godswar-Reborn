"""Read-only native hierarchy, indexed skin conversion and animation probe.

Uses the official d3dx9anim.h/d3dx9mesh.h ABI from pinned Microsoft.DXSDK.D3DX
9.29.952.8 (package SHA256 ead0906ae8a26c18a7525da7490127a2110f7c58f18293738283e30e97c6ea4b).
API: https://learn.microsoft.com/windows/win32/direct3d9/d3dxloadmeshhierarchyfromx
A hidden D3D9 device and Python-owned allocator objects are temporary. This
checks real loading, skin conversion, animation calls and GPU texture creation;
it does not draw the model or reproduce the game's 32-bit process/device state.
"""
import argparse
import ctypes as C
import json
import math
from pathlib import Path
import sys

from native_validate import PTR, UINT, HRESULT, PPTR, method, check, release
PUI=C.POINTER(UINT)
FLOAT=C.c_float


class Present(C.Structure):
    _fields_=[('width',UINT),('height',UINT),('format',UINT),('count',UINT),
              ('multisample',UINT),('quality',UINT),('swap',UINT),('window',PTR),
              ('windowed',C.c_int),('auto_depth',C.c_int),('depth_format',UINT),
              ('flags',UINT),('refresh',UINT),('interval',UINT)]


class MeshData(C.Structure):
    _fields_=[('type',UINT),('mesh',PTR)]


class MeshContainer(C.Structure):
    _fields_=[('name',PTR),('data',MeshData),('materials',PTR),('effects',PTR),
              ('num_materials',UINT),('adjacency',PTR),('skin',PTR),('next',PTR)]


class Frame(C.Structure):
    _fields_=[('name',PTR),('matrix',FLOAT*16),('mesh',PTR),('sibling',PTR),('child',PTR)]


class Allocator(C.Structure):
    _fields_=[('vtable',C.POINTER(PTR))]


def hidden_device():
    if sys.platform!='win32' or C.sizeof(PTR)!=8:
        raise OSError('This native ABI probe requires 64-bit Python on Windows')
    user=C.WinDLL('user32');kernel=C.WinDLL('kernel32')
    user.CreateWindowExW.argtypes=[UINT,C.c_wchar_p,C.c_wchar_p,UINT,C.c_int,C.c_int,
                                  C.c_int,C.c_int,PTR,PTR,PTR,PTR]
    user.CreateWindowExW.restype=PTR
    kernel.GetModuleHandleW.argtypes=[C.c_wchar_p];kernel.GetModuleHandleW.restype=PTR
    window=user.CreateWindowExW(0,'STATIC','Bloodfang native diagnostic',0,0,0,8,8,None,None,
                                kernel.GetModuleHandleW(None),None)
    if not window:raise OSError('Unable to create hidden diagnostic window')
    d3d=C.WinDLL('d3d9');d3d.Direct3DCreate9.argtypes=[UINT];d3d.Direct3DCreate9.restype=PTR
    interface=PTR(d3d.Direct3DCreate9(32))
    if not interface:raise OSError('Direct3DCreate9 failed')
    params=Present(8,8,0,1,0,0,1,window,1,0,0,0,0,0x80000000)
    device=PTR()
    create=method(interface,16,HRESULT,UINT,UINT,PTR,UINT,C.POINTER(Present),PPTR)
    attempts=[]
    for dtype,flags in [(1,0x20),(2,0x20),(4,0x20)]:
        value=create(interface,0,dtype,window,flags,C.byref(params),C.byref(device))
        attempts.append({'device_type':dtype,'hr':f'{value&0xffffffff:08x}'})
        if value>=0:return interface,device,window,attempts
    raise OSError('D3D9 device creation failed: '+str(attempts))


def stress_animation(controller,frames,seconds):
    """Exercise the game's SetTrackPosition(elapsed)/AdvanceTime(0) pattern."""
    if seconds<=0:return {'simulated_seconds':0,'updates':0}
    limits=[method(controller,i,UINT)(controller) for i in range(3,7)]
    clone=PTR()
    check(method(controller,41,HRESULT,UINT,UINT,UINT,UINT,PPTR)(controller,*limits,C.byref(clone)),
          'CloneAnimationController')
    animations=[]
    try:
        for name in (b'nomal_stand',b'nomal_run',b'nomal_attack_01'):
            animation=PTR()
            hr=method(clone,12,HRESULT,C.c_char_p,PPTR)(clone,name,C.byref(animation))
            if hr<0 and name==b'nomal_attack_01':
                hr=method(clone,12,HRESULT,C.c_char_p,PPTR)(clone,b'nomal_attack',C.byref(animation))
            check(hr,'GetAnimationSetByName');animations.append(animation)
        check(method(clone,19,HRESULT,UINT,FLOAT)(clone,0,1.),'SetTrackSpeed')
        check(method(clone,20,HRESULT,UINT,FLOAT)(clone,0,1.),'SetTrackWeight')
        check(method(clone,22,HRESULT,UINT,C.c_int)(clone,0,1),'SetTrackEnable')
        set_animation=method(clone,16,HRESULT,UINT,PTR)
        set_position=method(clone,21,HRESULT,UINT,C.c_double)
        advance=method(clone,13,HRESULT,C.c_double,PTR)
        count=round(seconds*60)
        for frame in range(count):
            check(set_animation(clone,0,animations[(frame//120)%3]),'Stress.SetTrackAnimationSet')
            check(set_position(clone,0,frame/60),'Stress.SetTrackPosition')
            check(advance(clone,0,None),'Stress.AdvanceTime')
            if frame%30==0 and not all(math.isfinite(v) for f in frames for v in f.matrix):
                raise ValueError('Nonfinite frame matrix during idle/run/attack stress')
        return {'simulated_seconds':seconds,'updates':count,'cloned_controller':True,
                'idle_run_attack_switches':count//120,'finite_matrices':True}
    finally:
        for animation in animations:release(animation)
        release(clone)


def probe(path,device,dll,stress_seconds):
    keep=[];frame_objects=[];containers=[];meshes=[];errors=[]
    def buffer(value):
        obj=C.create_string_buffer(value or b'');keep.append(obj);return C.cast(obj,PTR)

    @C.WINFUNCTYPE(HRESULT,PTR,C.c_char_p,PPTR)
    def create_frame(this,name,out):
        try:
            obj=Frame();obj.name=buffer(name)
            obj.matrix[:]=[float(i//4==i%4) for i in range(16)]
            frame_objects.append(obj);out[0]=C.cast(C.pointer(obj),PTR);return 0
        except Exception as ex:errors.append(str(ex));return -2147467259

    @C.WINFUNCTYPE(HRESULT,PTR,C.c_char_p,C.POINTER(MeshData),PTR,PTR,UINT,PTR,PTR,PPTR)
    def create_mesh(this,name,data,materials,effects,count,adjacency,skin,out):
        try:
            mesh=PTR(data.contents.mesh)
            row={'name':(name or b'').decode('ascii','replace'),'type':data.contents.type,
                 'faces':method(mesh,4,UINT)(mesh),'vertices':method(mesh,5,UINT)(mesh),
                 'fvf':method(mesh,6,UINT)(mesh),'materials':count}
            print('CREATE_MESH '+json.dumps(row),flush=True)
            obj=MeshContainer();obj.name=buffer(name);obj.data=data.contents;obj.num_materials=count
            method(mesh,1,UINT)(mesh)
            if materials and count:
                obj.materials=buffer(C.string_at(materials,count*80))
            if adjacency:obj.adjacency=buffer(C.string_at(adjacency,row['faces']*12))
            if skin:
                obj.skin=skin;sp=PTR(skin);method(sp,1,UINT)(sp)
                bones=method(sp,9,UINT)(sp);row['bones']=bones
                row['bone_names']=[method(sp,15,C.c_char_p,UINT)(sp,i).decode('ascii') for i in range(bones)]
                max_influences=UINT();combinations=UINT();table=PTR();converted=PTR()
                conversion=method(sp,26,HRESULT,PTR,UINT,UINT,PTR,PTR,PTR,PPTR,PUI,PUI,PPTR,PPTR)
                palette=min(bones,26)
                hr=conversion(sp,mesh,0x4000220,palette,adjacency,None,None,None,
                              C.byref(max_influences),C.byref(combinations),C.byref(table),C.byref(converted))
                row['indexed_skin_conversion']={'hr':f'{hr&0xffffffff:08x}','palette':palette,
                    'influences':max_influences.value,'bone_combinations':combinations.value}
                if hr>=0:
                    row['indexed_skin_conversion'].update(fvf=method(converted,6,UINT)(converted),
                        vertices=method(converted,5,UINT)(converted),faces=method(converted,4,UINT)(converted))
                release(converted);release(table)
            containers.append(obj);meshes.append(row);out[0]=C.cast(C.pointer(obj),PTR);return 0
        except Exception as ex:errors.append(str(ex));return -2147467259

    @C.WINFUNCTYPE(HRESULT,PTR,PTR)
    def destroy_frame(this,pointer):return 0

    @C.WINFUNCTYPE(HRESULT,PTR,PTR)
    def destroy_mesh(this,pointer):
        obj=C.cast(pointer,C.POINTER(MeshContainer)).contents
        release(PTR(obj.data.mesh));release(PTR(obj.skin));return 0

    callbacks=[create_frame,create_mesh,destroy_frame,destroy_mesh]
    table=(PTR*4)(*[C.cast(value,PTR) for value in callbacks]);allocator=Allocator(table)
    load=dll.D3DXLoadMeshHierarchyFromXA
    load.argtypes=[C.c_char_p,UINT,PTR,C.POINTER(Allocator),PTR,PPTR,PPTR];load.restype=HRESULT
    root=PTR();controller=PTR()
    hr=load(str(path).encode('mbcs'),0x220,device,C.byref(allocator),None,C.byref(root),C.byref(controller))
    result={'file':str(path),'load_hresult':f'{hr&0xffffffff:08x}','allocated_frame_callbacks':len(frame_objects),
            'meshes':meshes,'callback_errors':errors,'animations':[]}
    print('LOAD_RESULT '+json.dumps(result),flush=True)
    if hr>=0:
        seen=set();actual_frames=[]
        def walk(pointer):
            if not pointer:return
            if pointer in seen or len(seen)>10000:raise ValueError('Invalid native frame traversal')
            seen.add(pointer);frame=C.cast(pointer,C.POINTER(Frame)).contents;actual_frames.append(frame)
            walk(frame.child);walk(frame.sibling)
        walk(root.value);result['frames']=len(actual_frames)
        find=dll.D3DXFrameFind;find.argtypes=[PTR,C.c_char_p];find.restype=PTR
        result['missing_skin_frames']=[name for mesh in meshes for name in mesh.get('bone_names',[])
                                       if not find(root,name.encode())]
        if controller:
            result['controller_limits']=[method(controller,i,UINT)(controller) for i in range(3,7)]
            for index in range(method(controller,10,UINT)(controller)):
                animation=PTR()
                check(method(controller,11,HRESULT,UINT,PPTR)(controller,index,C.byref(animation)),'GetAnimationSet')
                name=method(animation,3,C.c_char_p)(animation).decode('ascii')
                period=method(animation,4,C.c_double)(animation)
                tracks=method(animation,6,UINT)(animation)
                check(method(controller,16,HRESULT,UINT,PTR)(controller,0,animation),'SetTrackAnimationSet')
                check(method(controller,19,HRESULT,UINT,FLOAT)(controller,0,1.),'SetTrackSpeed')
                check(method(controller,20,HRESULT,UINT,FLOAT)(controller,0,1.),'SetTrackWeight')
                check(method(controller,22,HRESULT,UINT,C.c_int)(controller,0,1),'SetTrackEnable')
                check(method(controller,14,HRESULT)(controller),'ResetTime')
                for delta in (0.,.016,.1,.5,1.,5.):
                    check(method(controller,13,HRESULT,C.c_double,PTR)(controller,delta,None),'AdvanceTime')
                    if not all(math.isfinite(v) for f in frame_objects for v in f.matrix):
                        raise ValueError('Nonfinite animated matrix: '+name)
                result['animations'].append({'name':name,'period_seconds':period,'tracks':tracks,'advanced':True})
                release(animation)
            result['animation_stress']=stress_animation(controller,actual_frames,stress_seconds)
        texture=path.with_suffix('.gwo')
        create_texture=dll.D3DXCreateTextureFromFileA
        create_texture.argtypes=[PTR,C.c_char_p,PPTR];create_texture.restype=HRESULT
        gpu_texture=PTR();tex_hr=create_texture(device,str(texture).encode('mbcs'),C.byref(gpu_texture))
        result['gpu_texture_hresult']=f'{tex_hr&0xffffffff:08x}';release(gpu_texture)
    release(controller)
    if root:
        destroy=dll.D3DXFrameDestroy;destroy.argtypes=[PTR,C.POINTER(Allocator)];destroy.restype=HRESULT
        result['destroy_hresult']=f'{destroy(root,C.byref(allocator))&0xffffffff:08x}'
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('models',type=Path,nargs='+')
    parser.add_argument('--report',type=Path)
    parser.add_argument('--stress-seconds',type=float,default=300)
    args=parser.parse_args()
    if not 0<=args.stress_seconds<=3600:parser.error('stress seconds must be in [0,3600]')
    interface,device,window,attempts=hidden_device()
    dll=C.WinDLL(r'C:\Windows\System32\d3dx9_31.dll')
    result={'runtime':'System32 d3dx9_31 (64-bit)','device_attempts':attempts,'models':[]}
    try:
        for model in args.models:
            print('START '+str(model),flush=True)
            result['models'].append(probe(model.resolve(),device,dll,args.stress_seconds))
    finally:
        release(device);release(interface)
        user=C.WinDLL('user32');user.DestroyWindow.argtypes=[PTR];user.DestroyWindow(window)
    result['passed']=all(m['load_hresult']=='00000000' and m.get('gpu_texture_hresult')=='00000000'
                         and not m.get('missing_skin_frames') and not m['callback_errors']
                         and all(x.get('indexed_skin_conversion',{}).get('hr')=='00000000' for x in m['meshes'])
                         for m in result['models'])
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2),flush=True)
    return 0 if result['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
