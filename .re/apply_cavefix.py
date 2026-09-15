import struct, pathlib, hashlib
src = pathlib.Path(r"D:\Godswar Origin\Origin.exe")
data = bytearray(src.read_bytes())
old_vsize = struct.unpack_from("<I", data, 0x228)[0]
old_chars = struct.unpack_from("<I", data, 0x244)[0]
struct.pack_into("<I", data, 0x228, 0x000A8000)
struct.pack_into("<I", data, 0x244, old_chars | 0x20000000)
out = pathlib.Path(r"D:\Godswar Origin\Origin.exe.cavefix.tmp")
out.write_bytes(bytes(data))
print(f"VirtualSize 0x{old_vsize:X} -> 0x000A8000 ; Characteristics 0x{old_chars:08X} -> 0x{old_chars | 0x20000000:08X}")
