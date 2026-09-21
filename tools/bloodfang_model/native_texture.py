"""Strict row-bounded TGA textures accepted by the game's D3DX9 loader."""
from pathlib import Path
import struct

def encode_bgra(width, height, pixels):
    """Top-origin TGA32 RLE, with neither raw nor repeated packets crossing rows."""
    if not 1 <= width <= 4096 or not 1 <= height <= 4096:
        raise ValueError('Unexpected native texture dimensions')
    if len(pixels) != width * height or any(len(p) != 4 for p in pixels):
        raise ValueError('Texture must supply one BGRA pixel per texel')
    result = bytearray(struct.pack('<BBBHHBHHHHBB', 0, 0, 10, 0, 0, 0, 0, 0,
                                   width, height, 32, 40))
    for row in range(height):
        cursor, end = row * width, (row + 1) * width
        while cursor < end:
            run = 1
            while run < min(128, end - cursor) and pixels[cursor + run] == pixels[cursor]:
                run += 1
            if run > 1:
                result.append(128 | (run - 1))
                result.extend(pixels[cursor])
                cursor += run
                continue
            start = cursor
            cursor += 1
            while cursor < min(start + 128, end):
                if cursor + 1 < end and pixels[cursor] == pixels[cursor + 1]:
                    break
                cursor += 1
            result.append(cursor - start - 1)
            result.extend(b''.join(pixels[start:cursor]))
    return bytes(result)


def authored_texture(specification, directory, destination):
    """Encode an original baked sRGB atlas; refuse ambiguous source conventions."""
    from PIL import Image

    if specification.get('color_space') != 'sRGB':
        raise ValueError('Authored texture must declare sRGB pixels')
    if specification.get('uv_origin') not in ('bottom_left', 'top_left'):
        raise ValueError('Authored texture must declare its UV origin')
    root = Path(directory).resolve()
    source = (root / specification['path']).resolve()
    if not source.is_relative_to(root) or not source.is_file():
        raise ValueError('Authored texture must be inside the mesh document directory')
    with Image.open(source) as original:
        image = original.convert('RGBA')
        width, height = image.size
        if width & (width - 1) or height & (height - 1):
            raise ValueError('Native texture must have power-of-two dimensions')
        raw = image.tobytes('raw', 'BGRA')
    pixels = [raw[i:i + 4] for i in range(0, len(raw), 4)]
    destination.write_bytes(encode_bgra(width, height, pixels))
    return {'source': str(source), 'width': width, 'height': height,
            'uv_origin': specification['uv_origin'], 'color_space': 'sRGB'}
