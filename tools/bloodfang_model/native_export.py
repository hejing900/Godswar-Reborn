"""Export authored Bloodfang geometry/poses to the client's binary-X container.

Only standard template declarations are read from the inspected native schema.
All mesh coordinates, topology, bones, weights, colors and motions come from the
original Blender document. This module never installs or replaces client files.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from erebus_lion.model_codec import compress_xof_mszip, expand_xof_mszip
from xmodel_sculpt.binary_x import parse_tokens
from xmodel_sculpt.mesh import discover_meshes
from bloodfang_model.native_texture import authored_texture

IDENTITY = [1., 0., 0., 0., 0., 1., 0., 0., 0., 0., 1., 0., 0., 0., 0., 1.]
# Proper row-vector rotation: Blender (X,Y,Z) -> client (-X,Z,Y).
# Authored front -Y must face native -Z, as the stock Dragon head/tail do.
PRESENTATION = [-1., 0., 0., 0., 0., 0., 1., 0., 0., 1., 0., 0., 0., 0., 0., 1.]
CLIPS = {
    'idle': 'nomal_stand', 'death': 'nomal_die', 'angry': 'nomal_angry',
    'happy': 'nomal_happy', 'attack': 'nomal_attack', 'move': 'nomal_run',
    'run': 'nomal_run',
}


def name(value):
    raw = value.encode('ascii')
    return struct.pack('<HI', 1, len(raw)) + raw


def string(value):
    raw = value.encode('ascii')
    return struct.pack('<HI', 2, len(raw)) + raw + struct.pack('<H', 20)


def integers(values):
    return struct.pack(f'<HI{len(values)}I', 6, len(values), *values)


def floats(values):
    if not all(math.isfinite(v) for v in values):
        raise ValueError('Non-finite authored model data')
    return struct.pack(f'<HI{len(values)}f', 7, len(values), *values)


def node(kind, body, label=None):
    return name(kind) + (name(label) if label else b'') + b'\x0a\0' + body + b'\x0b\0'


def transpose(value):
    if len(value) != 16:
        raise ValueError('Expected a 4x4 matrix')
    return [value[j * 4 + i] for i in range(4) for j in range(4)]


def inverse(value):
    rows = [list(value[i * 4:i * 4 + 4]) + IDENTITY[i * 4:i * 4 + 4] for i in range(4)]
    for col in range(4):
        pivot = max(range(col, 4), key=lambda r: abs(rows[r][col]))
        if abs(rows[pivot][col]) < 1e-10:
            raise ValueError('Singular bind matrix')
        rows[col], rows[pivot] = rows[pivot], rows[col]
        scale = rows[col][col]
        rows[col] = [v / scale for v in rows[col]]
        for row in range(4):
            if row != col:
                factor = rows[row][col]
                rows[row] = [a - factor * b for a, b in zip(rows[row], rows[col])]
    return [v for row in rows for v in row[4:]]


def atlas(materials, destination):
    """An original palette texture; TGA32 RLE is the inspected GWO image format."""
    if not 1 <= len(materials) <= 64:
        raise ValueError('Palette supports 1..64 authored materials')
    size, cells = 256, 8
    colors = []
    for material in materials:
        rgba = material['base_color']
        # Blender base colors are linear; store the image in sRGB.
        def srgb(v):
            v = max(0., min(1., float(v)))
            return round(255 * (12.92 * v if v <= .0031308 else 1.055 * v ** (1 / 2.4) - .055))
        colors.append(bytes([srgb(rgba[2]), srgb(rgba[1]), srgb(rgba[0]), 255]))
    pixels = [colors[min((y // 32) * cells + x // 32, len(colors) - 1)]
              for y in range(size) for x in range(size)]
    # Top-origin output, alpha depth 8. Avoid repeating native metadata tails.
    data = bytearray(struct.pack('<BBBHHBHHHHBB', 0, 0, 10, 0, 0, 0, 0, 0, size, size, 32, 40))
    cursor = 0
    while cursor < len(pixels):
        run = 1
        # D3DX9 rejects an RLE packet that crosses a TGA scanline, even though
        # header-only inspection and permissive image decoders accept it.
        row_remaining = size - cursor % size
        while cursor + run < len(pixels) and run < min(128, row_remaining) and pixels[cursor + run] == pixels[cursor]:
            run += 1
        data.append(0x80 | (run - 1))
        data.extend(pixels[cursor])
        cursor += run
    destination.write_bytes(data)
    return [((i % cells + .5) / cells, (i // cells + .5) / cells) for i in range(len(materials))]


def prepare_vertices(document, palette=None):
    # Split at material boundaries. Every triangle samples its original material's
    # atlas cell; no native pet texture or geometry is used.
    vertices, faces, mapped = [], [], {}
    source = document['vertices']
    for triangle in document['triangles']:
        mat = triangle['material']
        if not 0 <= mat < len(document['materials']) or len(triangle['vertices']) != 3:
            raise ValueError('Invalid authored triangle/material')
        face = []
        for original in triangle['vertices']:
            key = (original, mat)
            if key not in mapped:
                value = dict(source[original])
                if palette is not None:
                    value['uv'] = palette[mat]
                else:
                    uv = value['uv']
                    if len(uv) != 2 or not all(math.isfinite(v) and 0 <= v <= 1 for v in uv):
                        raise ValueError('Authored atlas UV must be finite and inside the image')
                    value['uv'] = (uv[0], 1 - uv[1]) if document['texture']['uv_origin'] == 'bottom_left' else tuple(uv)
                mapped[key] = len(vertices)
                vertices.append(value)
            face.append(mapped[key])
        if len(set(face)) != 3:
            raise ValueError('Degenerate authored triangle')
        faces.append(face)
    return vertices, faces


def mesh_body(vertices, faces, bones, texture):
    face_values = [len(faces)] + [v for face in faces for v in [3, *face]]
    result = integers([len(vertices)]) + floats([v for vertex in vertices for v in vertex['position']])
    result += integers(face_values)
    result += node('MeshNormals', integers([len(vertices)]) +
                   floats([v for vertex in vertices for v in vertex['normal']]) + integers(face_values))
    result += node('MeshTextureCoords', integers([len(vertices)]) +
                   floats([v for vertex in vertices for v in vertex['uv']]))
    material = node('Material', floats([1, 1, 1, 1, 12, .10, .10, .10, 0, 0, 0]) +
                    node('TextureFilename', string(texture)), 'BloodfangPalette')
    result += node('MeshMaterialList', integers([1, len(faces)] + [0] * len(faces)) + material)
    by_bone = {bone['name']: [] for bone in bones}
    for index, vertex in enumerate(vertices):
        weights = vertex['weights']
        if not weights or abs(sum(w['weight'] for w in weights) - 1) > 1e-5:
            raise ValueError('Skin weights must sum to one')
        for weight in weights:
            if weight['bone'] not in by_bone or not 0 < weight['weight'] <= 1:
                raise ValueError('Invalid skin bone or weight')
            by_bone[weight['bone']].append((index, weight['weight']))
    active = [b for b in bones if by_bone[b['name']]]
    vertex_max = max(len(v['weights']) for v in vertices)
    face_max = max(len({w['bone'] for i in face for w in vertices[i]['weights']}) for face in faces)
    result += node('XSkinMeshHeader', integers([vertex_max, face_max, len(active)]))
    for bone in active:
        weights = by_bone[bone['name']]
        result += node('SkinWeights', string(bone['name']) +
                       integers([len(weights)] + [i for i, _ in weights]) +
                       floats([weight for _, weight in weights] + transpose(inverse(bone['matrix_world']))))
    return result


def bone_frames(bones, parent=None):
    children = [bone for bone in bones if bone['parent'] == parent]
    return b''.join(node('Frame', node('FrameTransformMatrix', floats(transpose(bone['matrix_local']))) +
                         bone_frames(bones, bone['name']), bone['name']) for bone in children)


def action_set(action, label, bones):
    start = action['frame_start']
    frames = action['keyframes']
    if len(frames) < 2 or action['fps'] <= 0:
        raise ValueError('An animation needs at least two authored poses')
    pieces = []
    for bone in bones:
        keys = []
        previous = -1
        for frame in frames:
            tick = round((frame['frame'] - start) * 4800 / action['fps'])
            if tick <= previous:
                raise ValueError('Animation keys must advance')
            previous = tick
            matrix = frame['bones'][bone['name']]['matrix_local']
            keys.append(integers(([4, len(frames)] if not keys else []) + [tick, 16]) +
                        floats(transpose(matrix)))
        reference = b'\x0a\0' + name(bone['name']) + b'\x0b\0'
        pieces.append(node('Animation', reference + node('AnimationKey', b''.join(keys)),
                           label + '_' + bone['name']))
    return node('AnimationSet', b''.join(pieces), label)


def export_document(document, schema, output, texture_directory=None):
    output.mkdir(parents=True, exist_ok=True)
    if document['coordinate_system'] != 'RH_Z_UP_FRONT_MINUS_Y':
        raise ValueError('Unexpected authored coordinate system')
    bones = document['bones']
    names = [b['name'] for b in bones]
    if len(set(names)) != len(names) or not bones:
        raise ValueError('Duplicate/missing original bone names')
    # Schema import is declarations only, never the source file's Material/Frame.
    template_tokens = parse_tokens(schema)
    cursor, declarations = 0, 0
    while cursor < len(template_tokens):
        if cursor + 2 >= len(template_tokens) or [t.kind for t in template_tokens[cursor:cursor + 3]] != [31, 1, 10]:
            raise ValueError('Native schema contains object data')
        declarations += 1
        cursor += 3
        depth = 1
        while cursor < len(template_tokens) and depth:
            if template_tokens[cursor].kind == 10: depth += 1
            elif template_tokens[cursor].kind == 11: depth -= 1
            cursor += 1
        if depth: raise ValueError('Malformed schema braces')
    if declarations != 8:
        raise ValueError('Unexpected schema declaration count')
    texture_name = 'Bloodfang_male_001.gwo'
    texture_info = None
    if 'texture' in document:
        if texture_directory is None:
            raise ValueError('Provide the authored mesh directory for its original texture')
        texture_info = authored_texture(document['texture'], texture_directory, output / texture_name)
        palette = None
    else:
        palette = atlas(document['materials'], output / texture_name)
    vertices, faces = prepare_vertices(document, palette)
    authored = node('Frame', node('FrameTransformMatrix', floats(IDENTITY)) +
                    bone_frames(bones) + node('Mesh', mesh_body(vertices, faces, bones, texture_name),
                                              'BloodfangOriginalSkin'), 'BloodfangAuthoringRoot')
    root = node('Frame', node('FrameTransformMatrix', floats(PRESENTATION)) + authored,
                'BloodfangPresentationRoot')
    actions, labels = [], []
    for action in document['actions']:
        label = CLIPS.get(action['name'].lower(), action['name'])
        if label in labels: raise ValueError('Duplicate animation name')
        labels.append(label)
        actions.append(action_set(action, label, bones))
        if label == 'nomal_attack':
            actions.append(action_set(action, 'nomal_attack_01', bones))
            labels.append('nomal_attack_01')
    required = {'nomal_stand', 'nomal_run', 'nomal_attack', 'nomal_die', 'nomal_angry', 'nomal_happy'}
    if not required.issubset(labels):
        raise ValueError('Missing native action names')
    # Native samples omit AnimTicksPerSecond. 4800 is the chosen export timebase;
    # the game's playback speed must still be checked when this species is added.
    expanded = schema + root + b''.join(actions)
    result = compress_xof_mszip(expanded, 'Bloodfang_male_001.jcs')
    model = output / 'Bloodfang_male_001.jcs'
    model.write_bytes(result)
    inspected = discover_meshes(expand_xof_mszip(model.read_bytes(), model.name))
    if len(inspected) != 1 or len(inspected[0].vertices) != len(vertices) or len(inspected[0].faces) != len(faces):
        raise ValueError('Exported topology readback differs')
    report = {'status': 'structural-readback-passed', 'model': str(model),
              'authorship': 'All geometry, skin weights, bone transforms and animation poses are authored from scratch.',
              'vertices': len(vertices), 'triangles': len(faces), 'bones': len(bones),
              'animation_sets': labels, 'native_schema_declarations': declarations,
              'native_coordinate_mapping': '(-X,Z,Y); Y_UP_FRONT_MINUS_Z',
              'authored_texture': texture_info,
              'export_ticks_per_second': 4800, 'in_game_playback_verified': False,
              'native_schema_sha256': hashlib.sha256(schema).hexdigest(),
              'model_sha256': hashlib.sha256(result).hexdigest(),
              'texture_sha256': hashlib.sha256((output / texture_name).read_bytes()).hexdigest()}
    (output / 'export-report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('document', type=Path)
    parser.add_argument('--schema', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = export_document(json.loads(args.document.read_text(encoding='utf-8')),
                             args.schema.read_bytes(), args.output, args.document.parent)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
