import sys, struct
sys.path.insert(0, "tools")
import analyze_client_handler as A
image, sections = A.load_image()
lut = A.to_offset(sections, A.LUT_VA)
table = A.to_offset(sections, A.TABLE_VA)
for op in list(range(10060, 10100)):
    idx = image[lut + (op - A.OPCODE_BASE)]
    va = struct.unpack_from("<I", image, table + idx * 4)[0]
    print(f"op={op} handler=0x{va:X}")
