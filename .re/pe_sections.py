import struct, pathlib
b = pathlib.Path(r"D:\Godswar Origin\Origin.exe").read_bytes()
pe = struct.unpack_from("<I", b, 0x3C)[0]
nsec = struct.unpack_from("<H", b, pe + 6)[0]
opt = struct.unpack_from("<H", b, pe + 20)[0]
print(f"PE at 0x{pe:X}, sections={nsec}, optheader={opt} (0x{opt:X})")
for i in range(nsec):
    h = pe + 24 + opt + i*40
    name = b[h:h+8].rstrip(b"\0").decode("latin-1")
    vsize, va, rsize, roff = struct.unpack_from("<IIII", b, h+8)
    chars = struct.unpack_from("<I", b, h+36)[0]
    ex = "EXEC" if chars & 0x20000000 else "    "
    wr = "WRITE" if chars & 0x80000000 else "     "
    print(f"  {name:<8} VA=0x{va+0x400000:08X} vsize=0x{vsize:<7X} rawoff=0x{roff:<7X} rawsize=0x{rsize:<7X} {ex} {wr}")
    if va + 0x400000 <= 0x9C3F00 < va + 0x400000 + max(vsize, rsize):
        print(f"      ^ VA 0x9C3F00 (frame guard cave) 落在这个节里")
    if va + 0x400000 <= 0x9C32B0 < va + 0x400000 + max(vsize, rsize):
        print(f"      ^ VA 0x9C32B0 (avatar guard cave) 落在这个节里")
