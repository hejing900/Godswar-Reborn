"""Extract the verified native Isle 8 collision grid for server navigation."""
from pathlib import Path
import argparse
import gzip
import hashlib
import struct

SOURCE_SHA256 = "375b51547593b82924c6a6c809316e070b44536a853a8e75080ce5dad49cf292"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] /
                        "src/Godswar.Server/Game/Navigation/WonderlandFinalIsland.grid.gz")
    args = parser.parse_args()
    source = args.source.read_bytes()
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA256:
        raise SystemExit("Unrecognized Fane.hmp; re-audit its collision layout before extracting.")
    if struct.unpack_from("<HHff", source) != (128, 128, 4.0, 4.0):
        raise SystemExit("Unexpected Fane geometry header.")
    xmin, zmin, width, height = -36, -124, 432, 912
    cells = bytearray()
    for row in range(height):
        native_row = int((256 - (zmin + (row + .5) / 4)) * 4)
        offset = 262432 + native_row * 2048 + (xmin + 256) * 4
        cells.extend(1 if value == 0 else 0 for value in source[offset:offset + width])
    payload = b"WNV1" + struct.pack("<iiii", xmin, zmin, width, height) + cells
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(gzip.compress(payload, compresslevel=9, mtime=0))
    print(f"{args.output}: {len(cells)} quarter-unit cells, {args.output.stat().st_size} bytes")


if __name__ == "__main__":
    main()
