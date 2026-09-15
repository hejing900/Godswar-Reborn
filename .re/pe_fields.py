import struct, pathlib
b = pathlib.Path(r"D:\Godswar Origin\Origin.exe").read_bytes()
pe = struct.unpack_from("<I", b, 0x3C)[0]
nsec = struct.unpack_from("<H", b, pe+6)[0]
opt = struct.unpack_from("<H", b, pe+20)[0]
tbl = pe + 24 + opt
for i in range(nsec):
    h = tbl + i*40
    name = b[h:h+8].rstrip(b"\0").decode("latin-1")
    vsize, va, rsize, roff = struct.unpack_from("<IIII", b, h+8)
    chars = struct.unpack_from("<I", b, h+36)[0]
    print(f"{name:<8} secHdr=0x{h:X} VirtualSize@0x{h+8:X}=0x{vsize:X} Characteristics@0x{h+36:X}=0x{chars:08X}")
print("SizeOfImage@opt+56 = 0x%X" % struct.unpack_from("<I", b, pe+24+56)[0])
# 洞里的字节是否全 0
hole = b[0x5C3090:0x5C4000]
print("0x5C3090..0x5C4000 非零字节数:", sum(1 for x in hole if x))
