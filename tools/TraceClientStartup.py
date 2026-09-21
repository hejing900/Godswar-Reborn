"""Trace a newly launched client's startup errors; never attach to a player session.

Uses Windows debug events to record exceptions and MessageBox arguments. Stops
only the child it created, before showing an intercepted diagnostic dialog.
Does not patch files, read credentials, send packets or log in.
"""
import argparse
import ctypes as C
from ctypes import wintypes as W
import json
from pathlib import Path
import struct
import time

import pefile

K=C.WinDLL('kernel32',use_last_error=True)
PTR=C.c_void_p
SIZE=C.c_size_t
DWORD=C.c_uint32

class Startup(C.Structure):
    _fields_=[('cb',DWORD),('reserved',PTR),('desktop',PTR),('title',PTR),
        ('x',DWORD),('y',DWORD),('cx',DWORD),('cy',DWORD),('charsx',DWORD),
        ('charsy',DWORD),('fill',DWORD),('flags',DWORD),('show',C.c_uint16),
        ('reserved2size',C.c_uint16),('reserved2',PTR),('stdin',PTR),('stdout',PTR),('stderr',PTR)]

class ProcessInfo(C.Structure):
    _fields_=[('process',PTR),('thread',PTR),('pid',DWORD),('tid',DWORD)]

class ExceptionRecord(C.Structure):
    _fields_=[('code',DWORD),('flags',DWORD),('record',PTR),('address',PTR),
        ('count',DWORD),('info',SIZE*15)]

class ExceptionInfo(C.Structure):
    _fields_=[('record',ExceptionRecord),('first',DWORD)]

class CreateProcess(C.Structure):
    _fields_=[('file',PTR),('process',PTR),('thread',PTR),('base',PTR),
        ('debug_offset',DWORD),('debug_size',DWORD),('tls',PTR),('start',PTR),('image_name',PTR),('unicode',C.c_uint16)]

class LoadDll(C.Structure):
    _fields_=[('file',PTR),('base',PTR),('debug_offset',DWORD),('debug_size',DWORD),('name',PTR),('unicode',C.c_uint16)]

class DebugString(C.Structure):
    _fields_=[('data',PTR),('unicode',C.c_uint16),('length',C.c_uint16)]

class EventPayload(C.Union):
    _fields_=[('exception',ExceptionInfo),('created',CreateProcess),('dll',LoadDll),('debug',DebugString),('exit_code',DWORD)]

class DebugEvent(C.Structure):
    _fields_=[('code',DWORD),('pid',DWORD),('tid',DWORD),('payload',EventPayload)]

def api(name,restype,args):
    value=getattr(K,name);value.restype=restype;value.argtypes=args;return value

create=api('CreateProcessW',W.BOOL,[W.LPCWSTR,W.LPWSTR,PTR,PTR,W.BOOL,DWORD,PTR,W.LPCWSTR,C.POINTER(Startup),C.POINTER(ProcessInfo)])
wait=api('WaitForDebugEvent',W.BOOL,[C.POINTER(DebugEvent),DWORD])
resume=api('ContinueDebugEvent',W.BOOL,[DWORD,DWORD,DWORD])
read=api('ReadProcessMemory',W.BOOL,[PTR,PTR,PTR,SIZE,C.POINTER(SIZE)])
write=api('WriteProcessMemory',W.BOOL,[PTR,PTR,PTR,SIZE,C.POINTER(SIZE)])
protect=api('VirtualProtectEx',W.BOOL,[PTR,PTR,SIZE,DWORD,C.POINTER(DWORD)])
flush=api('FlushInstructionCache',W.BOOL,[PTR,PTR,SIZE])
thread_open=api('OpenThread',PTR,[DWORD,W.BOOL,DWORD])
context_get=api('Wow64GetThreadContext',W.BOOL,[PTR,PTR])
context_set=api('Wow64SetThreadContext',W.BOOL,[PTR,PTR])
terminate=api('TerminateProcess',W.BOOL,[PTR,DWORD])
close=api('CloseHandle',W.BOOL,[PTR])
detach=api('DebugActiveProcessStop',W.BOOL,[DWORD])
kill_on_exit=api('DebugSetProcessKillOnExit',W.BOOL,[W.BOOL])
file_name=api('GetFinalPathNameByHandleW',DWORD,[PTR,W.LPWSTR,DWORD,DWORD])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe',type=Path,default=Path('C:/Godswar Origin/Origin.exe'))
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--seconds',type=int,default=20)
    parser.add_argument('--interactive',action='store_true',help='Show the diagnostic client for manual login; detach instead of closing it')
    args=parser.parse_args()
    if not 1<=args.seconds<=(600 if args.interactive else 45): raise ValueError('Trace duration exceeds its mode limit')
    exe=args.exe.resolve()
    pe=pefile.PE(str(exe),fast_load=False)
    if pe.OPTIONAL_HEADER.Magic!=0x10b: raise ValueError('Expected x86 game executable')
    wanted={}
    for module in pe.DIRECTORY_ENTRY_IMPORT:
        for symbol in module.imports:
            if symbol.name in (b'MessageBoxA',b'MessageBoxW',b'MessageBoxExA',b'MessageBoxExW'):
                wanted[symbol.address]=symbol.name.decode()
    info=ProcessInfo();startup=Startup();startup.cb=C.sizeof(startup)
    startup.flags=1;startup.show=5 if args.interactive else 0
    command=C.create_unicode_buffer('"'+str(exe)+'"')
    if not create(str(exe),command,None,None,False,2,None,str(exe.parent),C.byref(startup),C.byref(info)):
        raise C.WinError(C.get_last_error())
    if args.interactive:kill_on_exit(False)
    result={'pid':info.pid,'exe':str(exe),'events':[],'dialog':None,'timed_out':False,'hooks':[]}
    print(json.dumps({'diagnostic_client_pid':info.pid,'interactive':args.interactive}),flush=True)
    hooks={};base=pe.OPTIONAL_HEADER.ImageBase;finished=False;pending=None
    def memory(address,length):
        data=C.create_string_buffer(length);actual=SIZE()
        if not read(info.process,address,data,length,C.byref(actual)) or actual.value!=length:
            raise C.WinError(C.get_last_error())
        return data.raw
    def text_at(address,wide):
        if not address:return ''
        step=2 if wide else 1;data=bytearray()
        for offset in range(0,4096,step):
            chunk=memory(address+offset,step)
            if chunk==b'\0'*step:break
            data+=chunk
        return data.decode('utf-16-le' if wide else 'mbcs',errors='replace')
    def hook_messages():
        for address,name in wanted.items():
            try:
                target=struct.unpack('<I',memory(address-base+loaded_base,4))[0]
                # At the native64 loader breakpoint, x86 imports can still
                # contain unresolved RVAs. Never treat those as code pointers.
                if target<0x10000 or loaded_base<=target<loaded_base+pe.OPTIONAL_HEADER.SizeOfImage or target in hooks:continue
                original=memory(target,1)
                old=DWORD();written=SIZE()
                if not protect(info.process,target,1,0x40,C.byref(old)):continue
                try:
                    if not write(info.process,target,C.c_char_p(b'\xcc'),1,C.byref(written)):continue
                    flush(info.process,target,1)
                    hooks[target]=(name,original)
                    result['hooks'].append({'name':name,'target':hex(target),'original':original.hex()})
                finally:
                    ignored=DWORD();protect(info.process,target,1,old.value,C.byref(ignored))
            except OSError:continue
    def restore_hooks():
        for address,(_,original) in hooks.items():
            old=DWORD();written=SIZE()
            if not protect(info.process,address,1,0x40,C.byref(old)):continue
            try:
                if memory(address,1)==b'\xcc':
                    write(info.process,address,C.c_char_p(original),1,C.byref(written))
                    flush(info.process,address,1)
            finally:
                ignored=DWORD();protect(info.process,address,1,old.value,C.byref(ignored))
    def thread_snapshot(tid):
        thread=thread_open(0x0058,False,tid)
        try:
            context=C.create_string_buffer(716);struct.pack_into('<I',context,0,0x10007)
            if not context_get(thread,context):return {}
            esp=struct.unpack_from('<I',context,196)[0]
            registers={name:hex(struct.unpack_from('<I',context,offset)[0]) for name,offset in
                [('edi',156),('esi',160),('ebx',164),('edx',168),('ecx',172),('eax',176),('ebp',180),('eip',184),('esp',196)]}
            try:stack=[hex(v) for v in struct.unpack('<48I',memory(esp,192))]
            except OSError:stack=[]
            return {'registers':registers,'stack':stack}
        finally:
            if thread:close(thread)
    loaded_base=base
    try:
        deadline=time.monotonic()+args.seconds
        while time.monotonic()<deadline:
            event=DebugEvent()
            if not wait(C.byref(event),250):continue
            pending=event
            disposition=0x10002 # DBG_CONTINUE
            if event.code==3:
                loaded_base=event.payload.created.base
                result['events'].append({'kind':'process_created','base':hex(loaded_base)})
                if event.payload.created.file:close(event.payload.created.file)
            elif event.code==6:
                if event.payload.dll.file:
                    path=C.create_unicode_buffer(1024)
                    if file_name(event.payload.dll.file,path,len(path),0):
                        result['events'].append({'kind':'dll','base':hex(event.payload.dll.base),'path':path.value})
                    close(event.payload.dll.file)
            elif event.code==8:
                try:
                    # Keep library diagnostic strings, not arbitrary process buffers.
                    result['events'].append({'kind':'debug','message':text_at(event.payload.debug.data,event.payload.debug.unicode!=0)})
                except OSError:pass
            elif event.code==1:
                ex=event.payload.exception;address=ex.record.address or 0
                result['events'].append({'kind':'exception','code':hex(ex.record.code),
                    'address':hex(address),'first_chance':bool(ex.first),
                    'parameters':[hex(ex.record.info[i]) for i in range(min(ex.record.count,15))],
                    **(thread_snapshot(event.tid) if ex.record.code not in (0x80000003,0x4000001f) else {})})
                if address in hooks:
                    thread=thread_open(0x0058,False,event.tid)
                    try:
                        context=C.create_string_buffer(716)
                        struct.pack_into('<I',context,0,0x10007)
                        if not context_get(thread,context):raise C.WinError(C.get_last_error())
                        esp=struct.unpack_from('<I',context,196)[0]
                        stack=struct.unpack('<5I',memory(esp,20))
                        name=hooks[address][0]
                        result['dialog']={'api':name,'text':text_at(stack[2],name.endswith('W')),
                            'caption':text_at(stack[3],name.endswith('W')),'return_address':hex(stack[0]),'type':stack[4]}
                        if args.interactive:
                            restore_hooks()
                            struct.pack_into('<I',context,184,address)
                            if not context_set(thread,context):raise C.WinError(C.get_last_error())
                            resume(event.pid,event.tid,disposition);pending=None
                        break
                    finally:
                        if thread:close(thread)
                if ex.record.code==0x4000001f:hook_messages()
                elif ex.record.code==0x80000003:pass
                else:disposition=0x80010001 # DBG_EXCEPTION_NOT_HANDLED
            elif event.code==5:
                result['exit_code']=hex(event.payload.exit_code);finished=True
            resume(event.pid,event.tid,disposition);pending=None
            if finished:break
        else:result['timed_out']=True
    finally:
        # This is always the exact child process handle returned by CreateProcess.
        if not finished:
            if args.interactive:
                restore_hooks()
                if pending:resume(pending.pid,pending.tid,0x10002)
                result['detached']=bool(detach(info.pid))
            else:
                terminate(info.process,0)
                if pending:resume(pending.pid,pending.tid,0x10002)
        close(info.thread);close(info.process)
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
