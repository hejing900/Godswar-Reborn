"""Prepare the user's miniature Wonderland dragon without altering boss assets.

Preserves the native mesh, skin, skeleton, facing and original animation keys.
Only embedded texture names and missing pet animation aliases are adapted;
the pet's miniature scale is configured separately in Pet.xml.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from erebus_lion.model_codec import compress_xof_mszip, expand_xof_mszip
from xmodel_sculpt.binary_x import parse_tokens
from xmodel_sculpt.mesh import discover_meshes

SOURCE_MODEL = 'monster_dragon_014.jcs'
SOURCE_TEXTURE = 'monster_dragon_013.gwo'
SOURCE_MODEL_SHA = 'a14b2ecff4e966d4b07daab8b0d0b8e596eddf128c0609af684c7b2e0965f581'
SOURCE_TEXTURE_SHA = 'afa6e9b228320db15c780aa20531b88ecb2e2306ef7e7abf1724b0823f3fe292'
TARGET_MODEL = 'Bloodfang_male_001.jcs'
TARGET_TEXTURE = 'Bloodfang_male_001.gwo'
ALIASES = {'nomal_attack': 'nomal_attack_01',
           'nomal_angry': 'nomal_attack_02', 'nomal_happy': 'nomal_stand'}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encoded_text(kind, text):
    value = text.encode('ascii')
    return struct.pack('<HI', kind, len(value)) + value + (b'\x14\0' if kind == 2 else b'')


def replace_spans(data, changes):
    result = data
    end = len(data)
    for start, stop, replacement in sorted(changes, reverse=True):
        if not 0 <= start < stop <= end:
            raise ValueError('Overlapping or invalid native token edits')
        result = result[:start] + replacement + result[stop:]
        end = start
    return result


def animation_spans(data):
    tokens = parse_tokens(data)
    closes, stack = {}, []
    for i, token in enumerate(tokens):
        if token.kind == 10:
            stack.append(i)
        elif token.kind == 11:
            if not stack:
                raise ValueError('Unbalanced native braces')
            closes[stack.pop()] = i
    if stack:
        raise ValueError('Unbalanced native braces')
    result = {}
    for i, token in enumerate(tokens[:-2]):
        if (token.kind == 1 and token.value == b'AnimationSet'
                and tokens[i + 1].kind == 1 and tokens[i + 2].kind == 10):
            label = tokens[i + 1].value.decode('ascii')
            if label in result:
                raise ValueError('Duplicate native animation set')
            result[label] = (token.start, tokens[closes[i + 2]].end)
    return result


def alias_animation(data, label):
    tokens = parse_tokens(data)
    if tokens[0].value != b'AnimationSet' or tokens[1].kind != 1:
        raise ValueError('Expected one complete native animation set')
    edits = [(tokens[1].start, tokens[1].end, encoded_text(1, label))]
    # Animation object names are optional. Keep copied named objects unique;
    # references to skeleton frames and every numeric animation key stay intact.
    for i, token in enumerate(tokens[:-2]):
        if (token.kind == 1 and token.value == b'Animation'
                and tokens[i + 1].kind == 1 and tokens[i + 2].kind == 10):
            name = tokens[i + 1]
            edits.append((name.start, name.end,
                          encoded_text(1, label + '_' + name.value.decode('ascii'))))
    return replace_spans(data, edits)


def adapt(model, texture):
    if sha(model) != SOURCE_MODEL_SHA or sha(texture) != SOURCE_TEXTURE_SHA:
        raise ValueError('Wonderland source model or selected texture differs from reviewed assets')
    original = expand_xof_mszip(model, SOURCE_MODEL)
    tokens = parse_tokens(original)
    changes = []
    expected = {'monster_dragon_014.tga', 'monster_dragon_013.tga'}
    seen = []
    for i, token in enumerate(tokens[:-2]):
        if (token.kind == 1 and token.value == b'TextureFilename'
                and tokens[i + 1].kind == 10 and tokens[i + 2].kind == 2):
            value = tokens[i + 2]
            seen.append(value.value.decode('ascii'))
            changes.append((value.start, value.end, encoded_text(2, TARGET_TEXTURE)))
    if len(seen) != 2 or set(seen) != expected:
        raise ValueError('Unexpected native material texture references')
    adapted = replace_spans(original, changes)
    original_sets = animation_spans(original)
    if set(original_sets) != {'nomal_stand', 'nomal_run', 'nomal_die',
                              *(f'nomal_attack_0{i}' for i in range(1, 5))}:
        raise ValueError('Unexpected Wonderland dragon action inventory')
    for alias, source in ALIASES.items():
        start, end = original_sets[source]
        adapted += alias_animation(original[start:end], alias)
    encoded = compress_xof_mszip(adapted, TARGET_MODEL)
    decoded = expand_xof_mszip(encoded, TARGET_MODEL)
    # Original stream tokens are identical except the two reviewed texture
    # strings; appended aliases never change any existing native action.
    revised_tokens = parse_tokens(decoded)
    for before, after in zip(tokens, revised_tokens[:len(tokens)], strict=True):
        old, new = original[before.start:before.end], decoded[after.start:after.end]
        if old != new and not (before.kind == after.kind == 2
                              and before.value.decode('ascii') in expected
                              and after.value == TARGET_TEXTURE.encode('ascii')):
            raise ValueError('Adaptation changed original geometry, skeleton or animation data')
    revised_sets = animation_spans(decoded)
    for label, (start, end) in original_sets.items():
        a, b = revised_sets[label]
        if original[start:end] != decoded[a:b]:
            raise ValueError('Original boss animation was changed')
    before_mesh, after_mesh = discover_meshes(original), discover_meshes(decoded)
    if len(before_mesh) != 1 or len(after_mesh) != 1:
        raise ValueError('Expected one native dragon mesh')
    for field in ('vertices', 'faces', 'normals', 'normal_faces'):
        if getattr(before_mesh[0], field) != getattr(after_mesh[0], field):
            raise ValueError('Boss geometry differs after adaptation')
    return encoded, {'status': 'native-source-preserved',
        'source_model': SOURCE_MODEL, 'source_texture': SOURCE_TEXTURE,
        'source_model_sha256': sha(model), 'source_texture_sha256': sha(texture),
        'model_sha256': sha(encoded), 'texture_sha256': sha(texture),
        'vertices': len(after_mesh[0].vertices), 'triangles': len(after_mesh[0].faces),
        'native_forward': '-Z; unchanged', 'scale_location': 'Pet.xml only',
        'original_animations': list(original_sets), 'pet_aliases': ALIASES,
        'original_numeric_tokens_preserved': True,
        'original_animation_blocks_byte_identical': True,
        'texture_bytes_unchanged': True, 'in_game_verified': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--client-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    model = (args.client_root / 'Monster' / SOURCE_MODEL).read_bytes()
    texture = (args.client_root / 'Monster' / SOURCE_TEXTURE).read_bytes()
    encoded, report = adapt(model, texture)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / TARGET_MODEL).write_bytes(encoded)
    (args.output / TARGET_TEXTURE).write_bytes(texture)
    (args.output / 'adaptation-report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
