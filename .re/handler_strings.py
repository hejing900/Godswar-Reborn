import sys, struct, capstone
sys.path.insert(0, "tools")
import analyze_client_handler as A
image, sections = A.load_image()
lut = A.to_offset(sections, A.LUT_VA); table = A.to_offset(sections, A.TABLE_VA)
def cstr(va, limit=120):
    try:
        off = A.to_offset(sections, va)
    except ValueError:
        return None
    end = image.find(b"\x00", off, off + limit)
    raw = image[off:end if end > 0 else off+limit]
    try:
        return raw.decode("ascii")
    except UnicodeDecodeError:
        return None
eng = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
eng.detail = True
for op in range(10060, 10110):
    idx = image[lut + (op - A.OPCODE_BASE)]
    va = struct.unpack_from("<I", image, table + idx * 4)[0]
    code = image[A.to_offset(sections, va):A.to_offset(sections, va) + 0x60]
    strings = []
    for ins in eng.disasm(code, va):
        for o in ins.operands:
            if o.type == capstone.x86.X86_OP_IMM and 0x940000 <= o.imm <= 0x980000:
                s = cstr(o.imm)
                if s and len(s) > 3:
                    strings.append(f"0x{o.imm:X}={s!r}")
    print(f"op={op} va=0x{va:X} " + " | ".join(strings))
