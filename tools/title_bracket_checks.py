"""Small independent x86 interpreter for the bounded title formatter wrapper."""
import struct


def execute_formatter(code: bytes, name: bytes, *, forced_result=None):
    registers = dict(eax=0, ecx=0, edx=0x2000, esi=0x11223344, edi=0x55667788, esp=0x8000)
    original = registers.copy()
    memory = {}

    def write(address, value):
        for index, byte in enumerate(value):
            memory[address + index] = byte

    def read(address, size):
        if address >= 0x400000:
            return code[address - 0x400000:address - 0x400000 + size]
        return bytes(memory[address + index] for index in range(size))

    def number(address):
        return struct.unpack("<I", read(address, 4))[0]

    def push(value):
        registers['esp'] -= 4
        write(registers['esp'], struct.pack('<I', value))

    def pop():
        value = number(registers['esp'])
        registers['esp'] += 4
        return value

    def c_string(address):
        result = bytearray()
        while read(address, 1) != b'\0':
            result.extend(read(address, 1))
            address += 1
        return bytes(result)

    write(0x2000, b'\xa5' * 80)
    write(0x3000, name + b'\0')
    write(0x8000, struct.pack('<III', 0x10000, 0x9503F8, 0x3000))
    pc, zero, below, direction, calls = 0x420921, False, False, 1, 0
    for _ in range(100):
        if pc == 0x10000:
            assert registers['esp'] == 0x8004
            assert registers['esi'] == original['esi'] and registers['edi'] == original['edi']
            assert direction == 1
            assert read(0x3000, len(name) + 1) == name + b'\0'
            assert read(0x2040, 16) == b'\xa5' * 16
            result = read(0x2000, 64)
            return result.split(b'\0')[0], registers['eax'], calls
        if pc == 0x402DF0:
            assert registers['edx'] == 0x2000
            assert c_string(number(registers['esp'] + 4)) == b'[%s]'
            assert number(registers['esp'] + 8) == 0x3000
            formatted = b'[' + c_string(0x3000) + b']'
            write(0x2000, (formatted + b'\0')[:64])
            registers['eax'] = (len(formatted) if len(formatted) <= 64 else -1) & 0xFFFFFFFF
            if forced_result is not None:
                registers['eax'] = forced_result & 0xFFFFFFFF
            # Caller-saved values are deliberately clobbered by the CRT stub.
            registers['edx'], registers['ecx'] = 0xDEADBEEF, 0xBAD
            calls += 1
            pc = pop()
            continue
        ins = read(pc, 12)
        if ins[0] in (0x56, 0x57):
            push(registers['esi' if ins[0] == 0x56 else 'edi']); pc += 1
        elif ins[0] in (0x5E, 0x5F):
            registers['esi' if ins[0] == 0x5E else 'edi'] = pop(); pc += 1
        elif ins[:2] in (b'\x89\xd7', b'\x89\xfa', b'\x89\xd6'):
            target, source = {b'\x89\xd7': ('edi', 'edx'), b'\x89\xfa': ('edx', 'edi'),
                              b'\x89\xd6': ('esi', 'edx')}[ins[:2]]
            registers[target] = registers[source]; pc += 2
        elif ins[:3] == b'\xff\x74\x24':
            push(number(registers['esp'] + ins[3])); pc += 4
        elif ins[0] in (0xE8, 0xE9):
            following = pc + 5
            if ins[0] == 0xE8:
                push(following)
            pc = following + struct.unpack_from('<i', ins, 1)[0]
        elif ins[:3] == b'\x83\xc4\x08':
            registers['esp'] += 8; pc += 3
        elif ins[:2] == b'\x83\xf8':
            zero, below = registers['eax'] == ins[2], registers['eax'] < ins[2]; pc += 3
        elif ins[:2] == b'\x80\x3a':
            zero = read(registers['edx'], 1)[0] == ins[2]; pc += 3
        elif ins[:4] == b'\x66\x81\x7a\x01':
            zero = read(registers['edx'] + 1, 2) == ins[4:6]; pc += 6
        elif ins[:2] == b'\x81\x3e':
            zero = read(registers['esi'], 4) == ins[2:6]; pc += 6
        elif ins[:2] == b'\x81\x7e':
            zero = read(registers['esi'] + ins[2], 4) == ins[3:7]; pc += 7
        elif ins[:3] == b'\x66\x81\x7e':
            zero = read(registers['esi'] + ins[3], 2) == ins[4:6]; pc += 6
        elif ins[:2] == b'\x80\x7e':
            zero = read(registers['esi'] + ins[2], 1)[0] == ins[3]; pc += 4
        elif ins[0] in (0x75, 0x76, 0x77):
            take = {0x75: not zero, 0x76: zero or below, 0x77: not zero and not below}[ins[0]]
            pc += 2 + (struct.unpack('b', ins[1:2])[0] if take else 0)
        elif ins[:3] == b'\x8d\x74\x02':
            registers['esi'] = registers['edx'] + registers['eax'] + struct.unpack('b', ins[3:4])[0]
            pc += 4
        elif ins[:3] == b'\x8d\x7e\x01':
            registers['edi'] = registers['esi'] + 1; pc += 3
        elif ins[0] == 0x46:
            registers['esi'] += 1; pc += 1
        elif ins[0] == 0xB9:
            registers['ecx'] = struct.unpack_from('<I', ins, 1)[0]; pc += 5
        elif ins[:2] == b'\xf3\xa4':
            while registers['ecx']:
                write(registers['edi'], read(registers['esi'], 1))
                registers['edi'] += direction; registers['esi'] += direction; registers['ecx'] -= 1
            pc += 2
        elif ins[:2] == b'\xc6\x07':
            write(registers['edi'], ins[2:3]); pc += 3
        elif ins[0] in (0xFC, 0xFD):
            direction = 1 if ins[0] == 0xFC else -1; pc += 1
        elif ins[0] == 0xC3:
            pc = pop()
        else:
            raise AssertionError(f'Unsupported instruction {ins.hex()} at {pc:X}')
    raise AssertionError('Title formatter did not return')
