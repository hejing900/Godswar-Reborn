"""Find the Lelantine Farm donation broadcast in the reference captures.

The shipped client builds the announcement itself. `SrvMsg.lua` renders note
type `SrvMsg_NOTE_181 = 33` as

    name .. SrvMsg_Lelantine_msg[note[0]] .. note[2] .. SrvMsg_Lelantine_msg[note[1]]

with `SrvMsg_Lelantine_msg` holding `51070 = SM_51070` ("捐献犬宝宝宠物蛋，
斯巴达阵营获得"), `51080 = SM_51080` (the Athenian twin) and `51090 = SM_51090`
("积分！"), and draws it on `CHANNEL_MIDDLE = 0`, the centre-screen
proclamation. So the wire carries no Chinese: it carries the type, the channel,
the donor's name and a note string like `51070#51090#110`.

This tool walks every captured frame and prints:
  * every opcode-10038 note, decoded as type/channel/name/note, and
  * every frame at all whose bytes spell one of the Lelantine message ids.
"""

import glob
import os
import re
import struct

HEADER = re.compile(
    r"^(?P<ts>\S+?) (?P<channel>LOGIN|GAME) (?P<dir>S->C|C->S) "
    r"bytes=(?P<bytes>\d+).*?opcode=(?P<opcode>\d+)")

NOTE_OPCODE = 10038
LELANTINE_IDS = (b"51070", b"51080", b"51090", b"5201", b"5301", b"5602")
ROOTS = (
    r"D:\Godswar-Reborn-main\captures",
    r"D:\Godswar-Reborn-main\tools\Godswar.CaptureProxy\bin",
)


def frames(payload):
    offset = 0
    while offset + 4 <= len(payload):
        length = int.from_bytes(payload[offset:offset + 2], "little")
        opcode = int.from_bytes(payload[offset + 2:offset + 4], "little")
        if length < 4 or offset + length > len(payload):
            break
        yield opcode, payload[offset:offset + length]
        offset += length


def text(field):
    end = field.find(b"\x00")
    raw = field if end < 0 else field[:end]
    return raw.decode("ascii", "replace")


def describe(frame):
    if len(frame) < 137:
        return f"short note len={len(frame)} hex={frame.hex().upper()}"
    note_type = struct.unpack_from("<i", frame, 4)[0]
    channel = frame[8]
    name = text(frame[9:73])
    note = text(frame[73:137])
    extra = frame[137:].hex().upper()
    return (f"type={note_type} channel={channel} name={name!r} "
            f"note={note!r}" + (f" extra={extra}" if extra else ""))


def main():
    logs = []
    for root in ROOTS:
        logs.extend(glob.glob(os.path.join(root, "**", "*.log"), recursive=True))
    print(f"logs: {len(logs)}")
    notes = 0
    ids = 0
    for path in sorted(set(logs)):
        pending = None
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                line = line.rstrip("\n")
                match = HEADER.match(line)
                if match:
                    pending = match
                    continue
                if pending is None or not line.startswith("CLEAR "):
                    continue
                payload = bytes.fromhex(line[6:].strip())
                for opcode, frame in frames(payload):
                    stamp = pending.group("ts")[11:23]
                    if opcode == NOTE_OPCODE:
                        notes += 1
                        print(f"{os.path.basename(path)} {stamp} "
                              f"{pending.group('dir')} 10038 "
                              f"{describe(frame)}")
                    elif any(marker in frame for marker in LELANTINE_IDS):
                        ids += 1
                        print(f"{os.path.basename(path)} {stamp} "
                              f"{pending.group('dir')} opcode={opcode} "
                              f"len={len(frame)} spells a Lelantine id: "
                              f"{frame.hex().upper()}")
                pending = None
    print(f"10038 notes: {notes}; frames spelling a Lelantine id: {ids}")


if __name__ == "__main__":
    main()
