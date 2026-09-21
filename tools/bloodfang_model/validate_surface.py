"""Independent readback of authored triangle corners and native texture texels.

This reader never imports native_export/native_texture or recreates their mesh
mapping. It follows the actual native face and normal indices corner by corner,
and decodes native TGA packets independently before comparing the original PNG.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import sys

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from erebus_lion.model_codec import expand_xof_mszip
from xmodel_sculpt.binary_x import parse_tokens, integer_list, float_list
from xmodel_sculpt.mesh import discover_meshes


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def read_texture(data):
    """Decode the strict row-bounded TGA32 contract without an export helper."""
    if len(data) < 18:
        raise ValueError('Truncated native texture')
    header = struct.unpack_from('<BBBHHBHHHHBB', data)
    width, height = header[8:10]
    if (header[:8] != (0, 0, 10, 0, 0, 0, 0, 0) or
            header[10:] != (32, 40) or not 1 <= width <= 4096 or
            not 1 <= height <= 4096):
        raise ValueError('Expected a top-origin, uncolormapped native TGA32 RLE image')
    total = width * height
    bgra = bytearray(total * 4)
    cursor = 18
    count = 0
    packets = {'raw': 0, 'repeated': 0}
    while count < total:
        if cursor >= len(data):
            raise ValueError('Native texture packet is truncated')
        packet = data[cursor]
        cursor += 1
        length = (packet & 127) + 1
        if length > width - count % width:
            raise ValueError('Native texture packet crosses a scanline')
        amount = 4 if packet & 128 else length * 4
        if cursor + amount > len(data):
            raise ValueError('Native texture pixel payload is truncated')
        payload = data[cursor:cursor + amount]
        bgra[count * 4:(count + length) * 4] = payload * length if packet & 128 else payload
        packets['repeated' if packet & 128 else 'raw'] += 1
        cursor += amount
        count += length
    if cursor != len(data):
        raise ValueError('Native texture has unexpected trailing data')
    rgba = bytearray(bgra)
    rgba[0::4], rgba[2::4] = bgra[2::4], bgra[0::4]
    return width, height, bytes(rgba), packets


def read_uvs(data, tokens, mesh):
    matches = []
    for index in range(mesh.open_token_index + 1, mesh.close_token_index):
        if tokens[index].kind == 1 and tokens[index].value == b'MeshTextureCoords':
            cursor = index + 1
            if tokens[cursor].kind == 1:
                cursor += 1
            if tokens[cursor].kind != 10:
                raise ValueError('Malformed native texture-coordinate object')
            if [t.kind for t in tokens[cursor + 1:cursor + 4]] != [6, 7, 11]:
                raise ValueError('Unexpected native texture-coordinate body')
            counts = integer_list(data, tokens[cursor + 1])
            values = float_list(data, tokens[cursor + 2])
            if counts != (len(mesh.vertices),) or len(values) != len(mesh.vertices) * 2:
                raise ValueError('Native texture-coordinate count differs from mesh vertices')
            matches.append(tuple(zip(values[0::2], values[1::2])))
    if len(matches) != 1:
        raise ValueError('Expected exactly one native texture-coordinate object')
    return matches[0]


def exact_float32(actual, expected, label):
    if len(actual) != len(expected) or not all(math.isfinite(v) for v in expected):
        raise ValueError(f'{label}: authored vector is malformed')
    rounded = struct.unpack(f'<{len(expected)}f', struct.pack(f'<{len(expected)}f', *expected))
    if tuple(actual) != rounded:
        raise ValueError(f'{label}: native {tuple(actual)} differs from authored {rounded}')


def compare_corners(document, mesh, uvs):
    triangles = document['triangles']
    if len(mesh.faces) != len(triangles) or len(mesh.normal_faces) != len(triangles):
        raise ValueError('Native face or normal-face count differs from authored triangles')
    origin = document['texture']['uv_origin']
    if origin not in ('bottom_left', 'top_left'):
        raise ValueError('Unknown authored UV origin')
    corners = 0
    for face_index, (face, triangle) in enumerate(zip(mesh.faces, triangles)):
        normal_face = mesh.normal_faces[face_index]
        if len(face) != 3 or len(triangle['vertices']) != 3 or len(normal_face) != 3:
            raise ValueError('Expected triangle corners in both representations')
        for corner, (native_index, authored_index) in enumerate(zip(face, triangle['vertices'])):
            authored = document['vertices'][authored_index]
            label = f'face {face_index}, corner {corner}'
            exact_float32(mesh.vertices[native_index], authored['position'], label + ' position')
            normal = mesh.normals[normal_face[corner]]
            exact_float32(normal, authored['normal'], label + ' normal')
            uv = authored['uv']
            expected = (uv[0], 1 - uv[1]) if origin == 'bottom_left' else uv
            exact_float32(uvs[native_index], expected, label + ' UV')
            corners += 1
    return corners


def validate(document_path, model_path, texture_path):
    document_bytes = document_path.read_bytes()
    document = json.loads(document_bytes)
    if document.get('coordinate_system') != 'RH_Z_UP_FRONT_MINUS_Y':
        raise ValueError('Unexpected authored coordinate system')
    texture = document.get('texture')
    if not texture or texture.get('color_space') != 'sRGB':
        raise ValueError('Surface validation requires the original sRGB atlas specification')
    source = (document_path.parent / texture['path']).resolve()
    if not source.is_relative_to(document_path.parent.resolve()):
        raise ValueError('Original texture escapes the authored document directory')
    model_bytes = model_path.read_bytes()
    expanded = expand_xof_mszip(model_bytes, model_path.name)
    tokens = parse_tokens(expanded)
    meshes = discover_meshes(expanded, tokens)
    if len(meshes) != 1:
        raise ValueError('Expected one original native mesh')
    mesh = meshes[0]
    uvs = read_uvs(expanded, tokens, mesh)
    corners = compare_corners(document, mesh, uvs)
    filenames = [tokens[i + 2].value for i, token in enumerate(tokens[:-2])
                 if token.kind == 1 and token.value == b'TextureFilename' and
                 tokens[i + 1].kind == 10 and tokens[i + 2].kind == 2]
    if filenames != [texture_path.name.encode('ascii')]:
        raise ValueError('Native mesh references an unexpected texture filename')
    texture_bytes = texture_path.read_bytes()
    width, height, native_rgba, packets = read_texture(texture_bytes)
    with Image.open(source) as image:
        if image.format != 'PNG' or image.size != (width, height):
            raise ValueError('Original PNG dimensions differ from native texture')
        original_rgba = image.convert('RGBA').tobytes()
    if original_rgba != native_rgba:
        difference = next(i for i, (a, b) in enumerate(zip(original_rgba, native_rgba)) if a != b)
        pixel, channel = divmod(difference, 4)
        raise ValueError(f'Native texture changed PNG pixel ({pixel % width},{pixel // width}), channel {channel}')
    return {
        'status': 'passed', 'document': str(document_path), 'model': str(model_path),
        'texture': str(texture_path), 'original_png': str(source),
        'document_sha256': sha256(document_bytes), 'model_sha256': sha256(model_bytes),
        'texture_sha256': sha256(texture_bytes), 'original_png_sha256': sha256(source.read_bytes()),
        'native_vertices': len(mesh.vertices), 'triangles': len(mesh.faces),
        'triangle_corners_checked': corners, 'positions_float32_exact': True,
        'normals_float32_exact': True, 'authored_corner_uvs_float32_exact': True,
        'authored_uv_origin': texture['uv_origin'], 'native_uv_origin': 'top_left',
        'width': width, 'height': height, 'texels_checked': width * height,
        'original_srgb_rgba_texels_exact': True, 'top_to_bottom_orientation_exact': True,
        'row_bounded_native_packets': packets, 'native_texture_reference_exact': True,
        'export_helper_imports': 0,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('document', type=Path)
    parser.add_argument('--model', required=True, type=Path)
    parser.add_argument('--texture', required=True, type=Path)
    parser.add_argument('--report', required=True, type=Path)
    args = parser.parse_args()
    result = validate(args.document, args.model, args.texture)
    args.report.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
