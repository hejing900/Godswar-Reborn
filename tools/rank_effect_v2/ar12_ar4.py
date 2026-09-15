"""Validated native-AR4 orbit-only extraction for AR12 slot 2."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
import struct

from erebus_lion.model_codec import compress_xof_mszip, expand_xof_mszip
from rank_effect_packages.errors import RankEffectError
from rank_effect_packages.formats import extract_texture_references, structural_fingerprint
from xmodel_sculpt.binary_x import (
    TOKEN_CBRACE,
    TOKEN_FLOAT_LIST,
    TOKEN_INTEGER_LIST,
    TOKEN_NAME,
    TOKEN_STRING,
    Token,
    integer_list,
    parse_tokens,
)
from xmodel_sculpt.mesh import MeshData, discover_meshes

from .models import audit_model


AR4_REMOVED_VERTICES = 48
AR4_REMOVED_FACES = 24
AR4_REMOVED_COMPONENTS = 12
AR4_DONOR_VERTICES = 184
AR4_DONOR_FACES = 152
AR4_DONOR_COMPONENTS = 16
AR4_VERTICES = 136
AR4_FACES = 128
AR4_COMPONENTS = 4
AR4_ANIMATION_TRACKS = 1
AR4_MATRIX_KEYS = 13
AR4_SOURCE_REFERENCE = b"11.tga"
AR4_TARGET_REFERENCE = b"reborn_body_effect_0012_v2_rune.tga"
AR4_TARGET_REFERENCES = (AR4_TARGET_REFERENCE, AR4_TARGET_REFERENCE)
AR4_DONOR_SHA256 = {
    "female": "b3593e1d26b57bff32fe9252bafdff25ff2eda05f76be5b652b43a478d06b101",
    "male": "0217121fa71eca189dfb0fd5107f9c3352ece18cb2269c375980f854d35109af",
}
AR4_STRUCTURAL_SHA256 = {
    "female": "6e826113438c393f1e3f0a5cdb5f312a5965180b85618fc3a99a12b0f007fc16",
    "male": "7714e1d4adf86b8858372c848dedad554e641f8408870eeebe1e000975cd56d9",
}
AR4_OUTPUT_SHA256 = {
    "female": "7a7fe7f1827e842d65fdca87962acf9edff8f1e524a5262d9f6bbb318b151f29",
    "male": "f4eec46b19168eb9b1eaf1475102dee2eb5b49b31cc1d24138948410f6992b6b",
}
AR4_MATERIAL_FACE_COUNTS = {
    "female": (0, 128),
    "male": (0, 0, 128),
}


@dataclass(frozen=True, slots=True)
class AuthoredAr12Ar4:
    encoded: bytes
    donor_sha256: str
    output_sha256: str
    texture_references: tuple[str, str]

    def contract_metadata(self) -> dict[str, object]:
        return {
            "native_ar4_orbit_source_rank": 4,
            "native_ar4_orbit_donor_sha256": self.donor_sha256,
            "native_ar4_orbit_output_sha256": self.output_sha256,
            "orbit_extraction": {
                "removed_cage_vertices": AR4_REMOVED_VERTICES,
                "removed_cage_faces": AR4_REMOVED_FACES,
                "removed_cage_components": AR4_REMOVED_COMPONENTS,
                "output_vertices": AR4_VERTICES,
                "output_faces": AR4_FACES,
                "output_components": AR4_COMPONENTS,
                "native_animation_tracks": AR4_ANIMATION_TRACKS,
                "native_matrix_keys": AR4_MATRIX_KEYS,
                "native_spin_degrees_per_key": 30,
                "native_spin_end_time": 1920,
            },
            "material_roles": [
                {
                    "faces": AR4_FACES,
                    "geometry_role": "orbit-loops",
                    "texture_role": "animated-rune",
                    "palette_role": "animated-rune",
                    "target": self.texture_references[-1],
                }
            ],
        }


def _single_mesh(encoded: bytes, label: str) -> MeshData:
    expanded = expand_xof_mszip(encoded, label)
    meshes = discover_meshes(expanded, parse_tokens(expanded))
    if len(meshes) != 1:
        raise RankEffectError(f"AR4 orbit extraction requires one Mesh: {label}")
    return meshes[0]


def _component_count(mesh: MeshData) -> int:
    neighbours = [set() for _vertex in mesh.vertices]
    for face in mesh.faces:
        for left, right in zip(face, face[1:] + face[:1]):
            neighbours[left].add(right)
            neighbours[right].add(left)
    remaining = set(range(len(mesh.vertices)))
    count = 0
    while remaining:
        count += 1
        pending = [remaining.pop()]
        while pending:
            for neighbour in neighbours[pending.pop()]:
                if neighbour in remaining:
                    remaining.remove(neighbour)
                    pending.append(neighbour)
    return count


def _matrix_key_times(encoded: bytes, label: str) -> tuple[int, ...]:
    expanded = expand_xof_mszip(encoded, label)
    tokens = parse_tokens(expanded)
    starts = [
        index
        for index, token in enumerate(tokens)
        if token.kind == TOKEN_NAME and token.value == b"AnimationKey"
    ]
    if len(starts) != AR4_ANIMATION_TRACKS:
        raise RankEffectError(f"AR4 animation-track count changed: {label}")
    values: list[tuple[int, ...]] = []
    for token in tokens[starts[0] + 1 :]:
        if token.kind == TOKEN_CBRACE:
            break
        if token.kind == TOKEN_INTEGER_LIST:
            values.append(integer_list(expanded, token))
    if not values or values[0][:2] != (4, AR4_MATRIX_KEYS):
        raise RankEffectError(f"AR4 matrix animation header changed: {label}")
    records = (values[0][2:], *values[1:])
    if any(len(record) != 2 or record[1] != 16 for record in records):
        raise RankEffectError(f"AR4 matrix animation width changed: {label}")
    return tuple(record[0] for record in records)


def _integer_token(values: tuple[int, ...]) -> bytes:
    return (
        struct.pack("<HI", TOKEN_INTEGER_LIST, len(values))
        + struct.pack(f"<{len(values)}I", *values)
    )


def _float_token(payload: bytes, count: int) -> bytes:
    if len(payload) != count * 4:
        raise RankEffectError("AR4 float-token payload length changed")
    return struct.pack("<HI", TOKEN_FLOAT_LIST, count) + payload


def _template_index(
    tokens: tuple[Token, ...], mesh: MeshData, name: bytes
) -> int | None:
    candidates = [
        index
        for index in range(mesh.open_token_index + 1, mesh.close_token_index)
        if tokens[index].kind == TOKEN_NAME and tokens[index].value == name
    ]
    if len(candidates) > 1:
        raise RankEffectError(f"AR4 contains duplicate {name!r} templates")
    return candidates[0] if candidates else None


def _replace_ranges(
    expanded: bytes,
    replacements: list[tuple[int, int, bytes]],
) -> bytes:
    output = bytearray()
    cursor = 0
    for start, end, value in sorted(replacements):
        if start < cursor or end < start or end > len(expanded):
            raise RankEffectError("AR4 orbit replacement ranges overlap")
        output.extend(expanded[cursor:start])
        output.extend(value)
        cursor = end
    output.extend(expanded[cursor:])
    return bytes(output)


def _strip_vertex_colours(
    expanded: bytes,
    tokens: tuple[Token, ...],
    mesh: MeshData,
    gender: str,
) -> tuple[int, int, bytes] | None:
    template = _template_index(tokens, mesh, b"MeshVertexColors")
    if gender == "female":
        if template is not None:
            raise RankEffectError("Female AR4 unexpectedly gained vertex colours")
        return None
    if template is None or template + 3 >= mesh.close_token_index:
        raise RankEffectError("Male AR4 vertex-colour template changed")
    body_start = template + 3
    close = next(
        (
            index
            for index in range(body_start, mesh.close_token_index)
            if tokens[index].kind == TOKEN_CBRACE
        ),
        None,
    )
    if close is None:
        raise RankEffectError("Male AR4 vertex colours are not bounded")
    body = tokens[body_start:close]
    if len(body) != AR4_DONOR_VERTICES * 2:
        raise RankEffectError("Male AR4 vertex-colour record count changed")
    colours: list[bytes] = []
    for index in range(AR4_DONOR_VERTICES):
        integer, colour = body[index * 2 : index * 2 + 2]
        values = integer_list(expanded, integer)
        expected = (AR4_DONOR_VERTICES, 0) if index == 0 else (index,)
        if values != expected or colour.kind != TOKEN_FLOAT_LIST or colour.item_count != 4:
            raise RankEffectError("Male AR4 vertex-colour layout changed")
        colours.append(expanded[colour.start : colour.end])
    authored = bytearray()
    for index, colour in enumerate(colours[AR4_REMOVED_VERTICES:]):
        values = (AR4_VERTICES, 0) if index == 0 else (index,)
        authored.extend(_integer_token(values))
        authored.extend(colour)
    return body[0].start, body[-1].end, bytes(authored)


def _strip_ar4_cage(donor: bytes, gender: str, label: str) -> bytes:
    expanded = expand_xof_mszip(donor, label)
    tokens = parse_tokens(expanded)
    meshes = discover_meshes(expanded, tokens)
    if len(meshes) != 1:
        raise RankEffectError(f"AR4 donor must contain one Mesh: {label}")
    mesh = meshes[0]
    if mesh.normals or mesh.normal_faces:
        raise RankEffectError("AR4 orbit donor unexpectedly contains normals")
    position_index = next(
        index for index, token in enumerate(tokens) if token.start == mesh.position_token.start
    )
    count_token = tokens[position_index - 1]
    if integer_list(expanded, count_token) != (AR4_DONOR_VERTICES,):
        raise RankEffectError("AR4 vertex-count token changed")
    position = mesh.position_token
    if position.payload_offset is None:
        raise RankEffectError("AR4 vertex payload has no offset")
    position_payload = expanded[
        position.payload_offset + AR4_REMOVED_VERTICES * 12 :
        position.payload_offset + AR4_DONOR_VERTICES * 12
    ]

    faces: list[int] = [AR4_FACES]
    for face in mesh.faces[AR4_REMOVED_FACES:]:
        if min(face) < AR4_REMOVED_VERTICES:
            raise RankEffectError("AR4 orbit face still touches cage geometry")
        rewritten = tuple(index - AR4_REMOVED_VERTICES for index in face)
        faces.extend((len(rewritten), *rewritten))

    material_index = _template_index(tokens, mesh, b"MeshMaterialList")
    if material_index is None:
        raise RankEffectError("AR4 donor has no material list")
    material_token = next(
        token
        for token in tokens[material_index + 1 : mesh.close_token_index]
        if token.kind == TOKEN_INTEGER_LIST
    )
    material_values = integer_list(expanded, material_token)
    material_count, face_count, *face_materials = material_values
    if face_count != AR4_DONOR_FACES or len(face_materials) != face_count:
        raise RankEffectError("AR4 material face list changed")
    retained_materials = tuple(face_materials[AR4_REMOVED_FACES:])
    expected_material = 1 if gender == "female" else 2
    if retained_materials != (expected_material,) * AR4_FACES:
        raise RankEffectError("AR4 orbit material band changed")

    uv_index = _template_index(tokens, mesh, b"MeshTextureCoords")
    if uv_index is None or uv_index + 4 >= mesh.close_token_index:
        raise RankEffectError("AR4 donor has no bounded UV template")
    uv_count, uv_token = tokens[uv_index + 3 : uv_index + 5]
    if (
        integer_list(expanded, uv_count) != (AR4_DONOR_VERTICES,)
        or uv_token.kind != TOKEN_FLOAT_LIST
        or uv_token.item_count != AR4_DONOR_VERTICES * 2
        or uv_token.payload_offset is None
    ):
        raise RankEffectError("AR4 UV layout changed")
    uv_payload = expanded[
        uv_token.payload_offset + AR4_REMOVED_VERTICES * 8 :
        uv_token.payload_offset + AR4_DONOR_VERTICES * 8
    ]

    replacements = [
        (count_token.start, count_token.end, _integer_token((AR4_VERTICES,))),
        (
            position.start,
            position.end,
            _float_token(position_payload, AR4_VERTICES * 3),
        ),
        (mesh.face_token.start, mesh.face_token.end, _integer_token(tuple(faces))),
        (
            material_token.start,
            material_token.end,
            _integer_token((material_count, AR4_FACES, *retained_materials)),
        ),
        (uv_count.start, uv_count.end, _integer_token((AR4_VERTICES,))),
        (
            uv_token.start,
            uv_token.end,
            _float_token(uv_payload, AR4_VERTICES * 2),
        ),
    ]
    colours = _strip_vertex_colours(expanded, tokens, mesh, gender)
    if colours is not None:
        replacements.append(colours)
    stripped = _replace_ranges(expanded, replacements)
    try:
        parse_tokens(stripped)
        encoded = compress_xof_mszip(stripped, label)
    except (ValueError, OSError) as error:
        raise RankEffectError(f"AR4 orbit extraction failed: {error}") from error
    if expand_xof_mszip(encoded, label) != stripped:
        raise RankEffectError("AR4 orbit extraction failed MSZIP round trip")
    return encoded


def _rewrite_material_occurrences(
    donor: bytes, label: str, target_reference: bytes
) -> bytes:
    if (
        not target_reference
        or len(target_reference) > 127
        or any(value < 0x20 or value > 0x7E for value in target_reference)
    ):
        raise RankEffectError(f"AR4 target texture is not safe ASCII: {label}")
    expanded = expand_xof_mszip(donor, label)
    tokens = parse_tokens(expanded)
    output = bytearray()
    cursor = occurrence = 0
    for token in tokens:
        output.extend(expanded[cursor : token.start])
        if token.kind == TOKEN_STRING and token.value == AR4_SOURCE_REFERENCE:
            target = target_reference
            output.extend(struct.pack("<HI", TOKEN_STRING, len(target)))
            output.extend(target)
            output.extend(struct.pack("<H", 20))
            occurrence += 1
        else:
            output.extend(expanded[token.start : token.end])
        cursor = token.end
    output.extend(expanded[cursor:])
    if occurrence != 2:
        raise RankEffectError(f"AR4 material-reference count changed: {label}")
    encoded = compress_xof_mszip(bytes(output), label)
    if extract_texture_references(encoded, label) != (target_reference,) * 2:
        raise RankEffectError(f"AR4 orbit material failed round trip: {label}")
    return encoded


def author_ar12_ar4(
    source: bytes,
    donor: bytes,
    *,
    gender: str,
    main_texture: bytes,
    label: str,
) -> AuthoredAr12Ar4:
    """Retain only AR4's four native circling ribbons for AR12 slot 2."""

    if gender not in AR4_DONOR_SHA256:
        raise RankEffectError(f"Unsupported AR4 donor gender: {gender}")
    donor_sha256 = hashlib.sha256(donor).hexdigest()
    if donor_sha256 != AR4_DONOR_SHA256[gender]:
        raise RankEffectError(f"AR4 donor hash changed: {label}")

    source_mesh = _single_mesh(source, f"{label}:AR9-subset")
    donor_mesh = _single_mesh(donor, f"{label}:AR4-donor")
    source_audit = audit_model(source, f"{label}:AR9-subset")
    donor_audit = audit_model(donor, f"{label}:AR4-donor")
    if (source_audit.vertices, source_audit.faces) != (AR4_VERTICES, AR4_FACES):
        raise RankEffectError(f"AR12 loop subset topology changed: {label}")
    if source_audit.material_face_counts != (AR4_FACES,):
        raise RankEffectError(f"AR12 loop subset material changed: {label}")
    if (donor_audit.vertices, donor_audit.faces) != (
        AR4_DONOR_VERTICES,
        AR4_DONOR_FACES,
    ):
        raise RankEffectError(f"AR4 donor topology changed: {label}")
    if donor_audit.animation_keys != AR4_ANIMATION_TRACKS:
        raise RankEffectError(f"AR4 donor animation changed: {label}")
    if _matrix_key_times(donor, label) != tuple(range(0, 1921, 160)):
        raise RankEffectError(f"AR4 matrix animation timing changed: {label}")
    if extract_texture_references(donor, label) != (AR4_SOURCE_REFERENCE,) * 2:
        raise RankEffectError(f"AR4 donor texture layout changed: {label}")
    if _component_count(donor_mesh) != AR4_DONOR_COMPONENTS:
        raise RankEffectError(f"AR4 donor component count changed: {label}")

    loop_vertices = donor_mesh.vertices[AR4_REMOVED_VERTICES:]
    if max(math.dist(left, right) for left, right in zip(source_mesh.vertices, loop_vertices)) > 1e-6:
        raise RankEffectError(f"AR4 donor no longer contains the AR12 loops: {label}")
    loop_faces = tuple(
        tuple(index - AR4_REMOVED_VERTICES for index in face)
        for face in donor_mesh.faces[AR4_REMOVED_FACES:]
    )
    if source_mesh.faces != loop_faces:
        raise RankEffectError(f"AR4 donor loop topology changed: {label}")

    stripped = _strip_ar4_cage(donor, gender, label)
    encoded = _rewrite_material_occurrences(stripped, label, main_texture)
    output_audit = audit_model(encoded, f"{label}:orbit-only")
    output_mesh = _single_mesh(encoded, f"{label}:orbit-only")
    if (output_audit.vertices, output_audit.faces) != (AR4_VERTICES, AR4_FACES):
        raise RankEffectError(f"AR4 orbit output topology changed: {label}")
    if output_audit.material_face_counts != AR4_MATERIAL_FACE_COUNTS[gender]:
        raise RankEffectError(f"AR4 orbit output materials changed: {label}")
    if output_audit.animation_keys != AR4_ANIMATION_TRACKS:
        raise RankEffectError(f"AR4 orbit output animation changed: {label}")
    if _component_count(output_mesh) != AR4_COMPONENTS:
        raise RankEffectError(f"AR4 orbit output component count changed: {label}")
    if output_mesh.vertices != loop_vertices or output_mesh.faces != loop_faces:
        raise RankEffectError(f"AR4 orbit output differs from donor loops: {label}")
    if _matrix_key_times(encoded, label) != tuple(range(0, 1921, 160)):
        raise RankEffectError(f"AR4 orbit output timing changed: {label}")

    structural = structural_fingerprint(encoded, label)
    expected_structural = AR4_STRUCTURAL_SHA256[gender]
    if expected_structural and structural != expected_structural:
        raise RankEffectError(f"AR4 orbit structural fingerprint changed: {label}")
    output_sha256 = hashlib.sha256(encoded).hexdigest()
    expected_output = AR4_OUTPUT_SHA256[gender]
    if (
        main_texture == AR4_TARGET_REFERENCE
        and expected_output
        and output_sha256 != expected_output
    ):
        raise RankEffectError(f"AR4 orbit payload changed: {label}")
    return AuthoredAr12Ar4(
        encoded,
        donor_sha256,
        output_sha256,
        (main_texture.decode("ascii"), main_texture.decode("ascii")),
    )


__all__ = [
    "AR4_ANIMATION_TRACKS",
    "AR4_COMPONENTS",
    "AR4_DONOR_SHA256",
    "AR4_FACES",
    "AR4_MATERIAL_FACE_COUNTS",
    "AR4_MATRIX_KEYS",
    "AR4_OUTPUT_SHA256",
    "AR4_REMOVED_COMPONENTS",
    "AR4_REMOVED_FACES",
    "AR4_REMOVED_VERTICES",
    "AR4_STRUCTURAL_SHA256",
    "AR4_TARGET_REFERENCE",
    "AR4_TARGET_REFERENCES",
    "AR4_VERTICES",
    "AuthoredAr12Ar4",
    "author_ar12_ar4",
]
