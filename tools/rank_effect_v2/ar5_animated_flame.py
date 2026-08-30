"""Fail-closed authoring for native AR5 slot 2's animated flame."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
import struct

from erebus_lion.model_codec import compress_xof_mszip, expand_xof_mszip
from rank_effect_packages.errors import RankEffectError
from rank_effect_packages.formats import (
    extract_texture_references,
    structural_fingerprint,
)
from xmodel_sculpt.binary_x import (
    TOKEN_CBRACE,
    TOKEN_FLOAT_LIST,
    TOKEN_INTEGER_LIST,
    TOKEN_NAME,
    TOKEN_OBRACE,
    TOKEN_STRING,
    Token,
    float_list,
    integer_list,
    parse_tokens,
)
from xmodel_sculpt.mesh import MeshData, Vector3, discover_meshes

from .models import audit_model


AR5_ANIMATED_VERTICES = 200
AR5_ANIMATED_FACES = 150
AR5_ANIMATED_MATERIAL_FACE_COUNTS = (AR5_ANIMATED_FACES,)
AR5_ANIMATED_ANIMATION_TRACKS = 1
AR5_ANIMATED_MATRIX_KEYS = 73
AR5_ANIMATED_MATRIX_KEY_TYPE = 4
AR5_ANIMATED_MATRIX_WIDTH = 16
AR5_ANIMATED_KEY_STEP = 160
AR5_ANIMATED_KEY_END = 11_520
AR5_ANIMATED_SOURCE_TEXTURE = b"11.tga"
AR5_ANIMATED_SAFE_SCALE = (0.75, 1.25)
AR5_ANIMATED_DONOR_SHA256 = {
    "female": "7b43374750a9815b39af4dcef26b9145a8c9a26a1b23e4678f5e951afecb1702",
    "male": "7b43374750a9815b39af4dcef26b9145a8c9a26a1b23e4678f5e951afecb1702",
}
AR5_ANIMATED_EXPANDED_SHA256 = (
    "520e5143a28113579693d11c7fff24fe35aa278efdd88a3efc9d659f118fdfad"
)
AR5_ANIMATED_STRUCTURAL_SHA256 = (
    "8a0742225c66095c85d0227f3dd18897580a5c9c7355cf48e502a8ae11cdb236"
)
AR5_ANIMATED_TOPOLOGY_SHA256 = (
    "57364ce11d95af81c27af00acb1cf95eced7c899467c451a5e90127c252aec11"
)
AR5_ANIMATED_POSITION_PAYLOAD_SHA256 = (
    "49389814693b695405e239a17cbedfc32e4aa861abcafdcac2c7f11b42a79e2c"
)
AR5_ANIMATED_UV_PAYLOAD_SHA256 = (
    "e3896b486297cf66f123c5d127029ea8ee65ba2f0ebae709d20a7f3578d46aa2"
)
AR5_ANIMATED_ANIMATION_PAYLOAD_SHA256 = (
    "c6210ae755f92176b7c26a8874f8e87c818c5ae67b064555fc22967a099189b4"
)
AR5_ANIMATED_UV_BOUNDS = (
    0.022012563422322273,
    0.16132394969463348,
    0.012962937355041504,
    0.49387305974960327,
)
AR5_ANIMATED_NATIVE_BOUNDS = (
    (-0.7968435287475586, -1.6174840927124023, -1.698286533355713),
    (1.2852643728256226, 1.5518088340759277, 1.593671441078186),
)
AR5_ANIMATED_NATIVE_CENTROID = (
    0.13383727363077924,
    -0.022967572957277298,
    0.04990675910376012,
)


@dataclass(frozen=True, slots=True)
class AuthoredAr5AnimatedFlame:
    """The authored model and evidence for every permitted mutation."""

    encoded: bytes
    expanded: bytes
    donor_sha256: str
    output_sha256: str
    output_expanded_sha256: str
    source_structural_sha256: str
    output_structural_sha256: str
    model_scale: float
    scale_pivot: Vector3
    changed_vertices: int
    target_texture: str

    def contract_metadata(self) -> dict[str, object]:
        return {
            "geometry_family": "native-ar5-animated-flame",
            "native_ar5_source_rank": 5,
            "native_ar5_slot": 2,
            "native_ar5_donor_sha256": self.donor_sha256,
            "source_structural_sha256": self.source_structural_sha256,
            "output_sha256": self.output_sha256,
            "output_expanded_sha256": self.output_expanded_sha256,
            "output_structural_sha256": self.output_structural_sha256,
            "vertices": AR5_ANIMATED_VERTICES,
            "faces": AR5_ANIMATED_FACES,
            "material_face_counts": list(AR5_ANIMATED_MATERIAL_FACE_COUNTS),
            "animation": {
                "tracks": AR5_ANIMATED_ANIMATION_TRACKS,
                "matrix_keys": AR5_ANIMATED_MATRIX_KEYS,
                "matrix_width": AR5_ANIMATED_MATRIX_WIDTH,
                "key_type": AR5_ANIMATED_MATRIX_KEY_TYPE,
                "start_time": 0,
                "end_time": AR5_ANIMATED_KEY_END,
                "step": AR5_ANIMATED_KEY_STEP,
                "payload_sha256": AR5_ANIMATED_ANIMATION_PAYLOAD_SHA256,
                "preserved_exactly": True,
            },
            "texture_rewrite": {
                "source": AR5_ANIMATED_SOURCE_TEXTURE.decode("ascii"),
                "target": self.target_texture,
                "occurrences": 1,
            },
            "uv_transform": {
                "method": "identity",
                "native_bounds": list(AR5_ANIMATED_UV_BOUNDS),
                "payload_sha256": AR5_ANIMATED_UV_PAYLOAD_SHA256,
                "changed_values": 0,
            },
            "position_transform": {
                "method": (
                    "identity"
                    if self.model_scale == 1.0
                    else "uniform-about-native-centroid"
                ),
                "scale": self.model_scale,
                "pivot": list(self.scale_pivot),
                "changed_vertices": self.changed_vertices,
                "safe_scale_range": list(AR5_ANIMATED_SAFE_SCALE),
            },
        }


def _f32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", value))[0]


def _topology_sha256(mesh: MeshData) -> str:
    digest = hashlib.sha256()
    digest.update(struct.pack("<II", len(mesh.vertices), len(mesh.faces)))
    for face in mesh.faces:
        digest.update(struct.pack("<I", len(face)))
        digest.update(struct.pack(f"<{len(face)}I", *face))
    return digest.hexdigest()


def _single_mesh(expanded: bytes, tokens: tuple[Token, ...], label: str) -> MeshData:
    meshes = discover_meshes(expanded, tokens)
    if len(meshes) != 1:
        raise RankEffectError(f"AR5 animated-flame donor must contain one Mesh: {label}")
    return meshes[0]


def _uv_token(
    expanded: bytes, tokens: tuple[Token, ...], mesh: MeshData
) -> Token:
    candidates = [
        index
        for index in range(mesh.open_token_index + 1, mesh.close_token_index)
        if tokens[index].kind == TOKEN_NAME
        and tokens[index].value == b"MeshTextureCoords"
    ]
    if len(candidates) != 1:
        raise RankEffectError("AR5 animated flame must contain one UV object")
    index = candidates[0]
    body = tokens[index : index + 6]
    if (
        len(body) != 6
        or body[1].kind != TOKEN_NAME
        or body[1].value != b""
        or body[2].kind != TOKEN_OBRACE
        or body[3].kind != TOKEN_INTEGER_LIST
        or integer_list(expanded, body[3]) != (AR5_ANIMATED_VERTICES,)
        or body[4].kind != TOKEN_FLOAT_LIST
        or body[4].item_count != AR5_ANIMATED_VERTICES * 2
        or body[4].payload_offset is None
        or body[5].kind != TOKEN_CBRACE
    ):
        raise RankEffectError("AR5 animated-flame UV object layout changed")
    return body[4]


def _animation_contract(
    expanded: bytes, tokens: tuple[Token, ...], label: str
) -> tuple[tuple[int, ...], str]:
    starts = [
        index
        for index, token in enumerate(tokens)
        if token.kind == TOKEN_NAME and token.value == b"AnimationKey"
    ]
    if len(starts) != AR5_ANIMATED_ANIMATION_TRACKS:
        raise RankEffectError(f"AR5 animated-flame track count changed: {label}")
    start = starts[0]
    close = next(
        (index for index in range(start + 1, len(tokens))
         if tokens[index].kind == TOKEN_CBRACE),
        None,
    )
    if close is None:
        raise RankEffectError(f"AR5 animated-flame track is unbounded: {label}")
    integers = [
        integer_list(expanded, token)
        for token in tokens[start + 1 : close]
        if token.kind == TOKEN_INTEGER_LIST
    ]
    floats = [
        token
        for token in tokens[start + 1 : close]
        if token.kind == TOKEN_FLOAT_LIST
    ]
    if (
        len(integers) != AR5_ANIMATED_MATRIX_KEYS
        or len(floats) != AR5_ANIMATED_MATRIX_KEYS
        or integers[0][:2]
        != (AR5_ANIMATED_MATRIX_KEY_TYPE, AR5_ANIMATED_MATRIX_KEYS)
        or len(integers[0]) != 4
        or integers[0][3] != AR5_ANIMATED_MATRIX_WIDTH
        or any(len(value) != 2 or value[1] != AR5_ANIMATED_MATRIX_WIDTH
               for value in integers[1:])
        or any(token.item_count != AR5_ANIMATED_MATRIX_WIDTH for token in floats)
    ):
        raise RankEffectError(f"AR5 animated-flame matrix track changed: {label}")
    times = (integers[0][2], *(value[0] for value in integers[1:]))
    if times != tuple(range(0, AR5_ANIMATED_KEY_END + 1, AR5_ANIMATED_KEY_STEP)):
        raise RankEffectError(f"AR5 animated-flame key timing changed: {label}")
    payload_sha256 = hashlib.sha256(
        expanded[tokens[start].start : tokens[close].end]
    ).hexdigest()
    if payload_sha256 != AR5_ANIMATED_ANIMATION_PAYLOAD_SHA256:
        raise RankEffectError(f"AR5 animated-flame animation payload changed: {label}")
    return times, payload_sha256


def _validate_target_texture(value: bytes) -> None:
    if not isinstance(value, bytes):
        raise RankEffectError("AR5 animated-flame target texture must be bytes")
    lowered = value.lower()
    if (
        not value
        or len(value) > 127
        or b"\x00" in value
        or any(item < 0x20 or item > 0x7E for item in value)
        or not lowered.endswith((b".tga", b".gwo", b".dds", b".bmp"))
    ):
        raise RankEffectError(
            "AR5 animated-flame target texture must be a safe ASCII image name"
        )


def _rewrite_texture(expanded: bytes, target: bytes) -> bytes:
    tokens = parse_tokens(expanded)
    output = bytearray()
    cursor = changed = 0
    for token in tokens:
        output.extend(expanded[cursor : token.start])
        if token.kind == TOKEN_STRING and token.value == AR5_ANIMATED_SOURCE_TEXTURE:
            output.extend(struct.pack("<HI", TOKEN_STRING, len(target)))
            output.extend(target)
            output.extend(struct.pack("<H", 20))
            changed += 1
        else:
            output.extend(expanded[token.start : token.end])
        cursor = token.end
    output.extend(expanded[cursor:])
    if changed != 1:
        raise RankEffectError("AR5 animated-flame texture-reference count changed")
    rebuilt = bytes(output)
    parse_tokens(rebuilt)
    return rebuilt


def _scaled_vertices(
    mesh: MeshData, scale: float
) -> tuple[tuple[Vector3, ...], Vector3, int]:
    pivot = tuple(
        sum(point[axis] for point in mesh.vertices) / len(mesh.vertices)
        for axis in range(3)
    )
    if pivot != AR5_ANIMATED_NATIVE_CENTROID:
        raise RankEffectError("AR5 animated-flame native centroid changed")
    if scale == 1.0:
        return mesh.vertices, pivot, 0  # type: ignore[return-value]
    vertices = tuple(
        tuple(
            _f32(pivot[axis] + (point[axis] - pivot[axis]) * scale)
            for axis in range(3)
        )
        for point in mesh.vertices
    )
    changed = sum(
        struct.pack("<3f", *source) != struct.pack("<3f", *target)
        for source, target in zip(mesh.vertices, vertices)
    )
    if changed != AR5_ANIMATED_VERTICES:
        raise RankEffectError("AR5 animated-flame scale did not change every vertex")
    return vertices, pivot, changed  # type: ignore[return-value]


def author_ar5_animated_flame(
    donor: bytes,
    *,
    gender: str,
    target_texture: bytes,
    model_scale: float = 1.0,
    label: str = "female_body_effect_0005_2.jcs",
) -> AuthoredAr5AnimatedFlame:
    """Rewrite one texture name and optionally scale the native animated flame.

    Topology, UVs, material assignment, and the complete 73-key animation are
    retained byte-for-byte. Scaling is the only permitted geometry mutation.
    """

    expected_hash = AR5_ANIMATED_DONOR_SHA256.get(gender)
    donor_sha256 = hashlib.sha256(donor).hexdigest()
    if expected_hash is None or donor_sha256 != expected_hash:
        raise RankEffectError(f"Native AR5 animated-flame donor changed: {label}")
    try:
        scale = float(model_scale)
    except (TypeError, ValueError) as error:
        raise RankEffectError("AR5 animated-flame scale must be numeric") from error
    if (
        isinstance(model_scale, bool)
        or not math.isfinite(scale)
        or not AR5_ANIMATED_SAFE_SCALE[0] <= scale <= AR5_ANIMATED_SAFE_SCALE[1]
    ):
        raise RankEffectError(
            f"AR5 animated-flame scale must be within {AR5_ANIMATED_SAFE_SCALE}"
        )
    _validate_target_texture(target_texture)

    try:
        expanded_source = expand_xof_mszip(donor, label)
        tokens = parse_tokens(expanded_source)
        mesh = _single_mesh(expanded_source, tokens, label)
    except (ValueError, OSError) as error:
        raise RankEffectError(f"Invalid native AR5 animated flame {label}: {error}") from error
    source_structural = structural_fingerprint(donor, label)
    if (
        hashlib.sha256(expanded_source).hexdigest()
        != AR5_ANIMATED_EXPANDED_SHA256
        or source_structural != AR5_ANIMATED_STRUCTURAL_SHA256
        or len(mesh.vertices) != AR5_ANIMATED_VERTICES
        or len(mesh.faces) != AR5_ANIMATED_FACES
        or any(len(face) != 3 for face in mesh.faces)
        or mesh.normals
        or mesh.normal_faces
        or mesh.bounds != AR5_ANIMATED_NATIVE_BOUNDS
        or _topology_sha256(mesh) != AR5_ANIMATED_TOPOLOGY_SHA256
        or mesh.position_token.payload_offset is None
    ):
        raise RankEffectError("AR5 animated-flame mesh contract changed")
    position_payload = expanded_source[
        mesh.position_token.payload_offset : mesh.position_token.end
    ]
    if (
        hashlib.sha256(position_payload).hexdigest()
        != AR5_ANIMATED_POSITION_PAYLOAD_SHA256
    ):
        raise RankEffectError("AR5 animated-flame position payload changed")

    uv_token = _uv_token(expanded_source, tokens, mesh)
    assert uv_token.payload_offset is not None
    source_uvs = float_list(expanded_source, uv_token)
    uv_payload = expanded_source[uv_token.payload_offset : uv_token.end]
    uv_bounds = (
        min(source_uvs[0::2]),
        max(source_uvs[0::2]),
        min(source_uvs[1::2]),
        max(source_uvs[1::2]),
    )
    source_audit = audit_model(donor, f"{label}:source")
    if (
        hashlib.sha256(uv_payload).hexdigest() != AR5_ANIMATED_UV_PAYLOAD_SHA256
        or uv_bounds != AR5_ANIMATED_UV_BOUNDS
        or source_audit.material_face_counts != AR5_ANIMATED_MATERIAL_FACE_COUNTS
        or source_audit.animation_keys != AR5_ANIMATED_ANIMATION_TRACKS
        or extract_texture_references(donor, label)
        != (AR5_ANIMATED_SOURCE_TEXTURE,)
    ):
        raise RankEffectError("AR5 animated-flame UV/material contract changed")
    source_times, source_animation_hash = _animation_contract(
        expanded_source, tokens, f"{label}:source"
    )

    vertices, pivot, changed_vertices = _scaled_vertices(mesh, scale)
    mutable = bytearray(expanded_source)
    position_values = tuple(value for point in vertices for value in point)
    struct.pack_into(
        f"<{len(position_values)}f",
        mutable,
        mesh.position_token.payload_offset,
        *position_values,
    )
    expanded = _rewrite_texture(bytes(mutable), target_texture)
    try:
        output_tokens = parse_tokens(expanded)
        output_mesh = _single_mesh(expanded, output_tokens, f"{label}:output")
        encoded = compress_xof_mszip(expanded, label)
        decoded = expand_xof_mszip(encoded, label)
        reencoded = compress_xof_mszip(decoded, label)
    except (ValueError, OSError) as error:
        raise RankEffectError(f"AR5 animated-flame authoring failed: {error}") from error
    if decoded != expanded or reencoded != encoded:
        raise RankEffectError("AR5 animated-flame MSZIP round trip was not exact")

    output_uv_token = _uv_token(expanded, output_tokens, output_mesh)
    assert output_uv_token.payload_offset is not None
    output_uv_payload = expanded[
        output_uv_token.payload_offset : output_uv_token.end
    ]
    output_times, output_animation_hash = _animation_contract(
        expanded, output_tokens, f"{label}:output"
    )
    output_audit = audit_model(encoded, f"{label}:output")
    output_structural = structural_fingerprint(encoded, f"{label}:output")
    if (
        output_mesh.faces != mesh.faces
        or output_mesh.vertices != vertices
        or output_mesh.normals != mesh.normals
        or output_mesh.normal_faces != mesh.normal_faces
        or _topology_sha256(output_mesh) != AR5_ANIMATED_TOPOLOGY_SHA256
        or output_uv_payload != uv_payload
        or float_list(expanded, output_uv_token) != source_uvs
        or output_audit.material_face_counts != AR5_ANIMATED_MATERIAL_FACE_COUNTS
        or output_audit.animation_keys != AR5_ANIMATED_ANIMATION_TRACKS
        or output_times != source_times
        or output_animation_hash != source_animation_hash
        or extract_texture_references(encoded, label) != (target_texture,)
        or (scale == 1.0 and output_structural != source_structural)
    ):
        raise RankEffectError("AR5 animated-flame output contract changed")

    return AuthoredAr5AnimatedFlame(
        encoded=encoded,
        expanded=expanded,
        donor_sha256=donor_sha256,
        output_sha256=hashlib.sha256(encoded).hexdigest(),
        output_expanded_sha256=hashlib.sha256(expanded).hexdigest(),
        source_structural_sha256=source_structural,
        output_structural_sha256=output_structural,
        model_scale=scale,
        scale_pivot=pivot,
        changed_vertices=changed_vertices,
        target_texture=target_texture.decode("ascii"),
    )


__all__ = [
    "AR5_ANIMATED_ANIMATION_PAYLOAD_SHA256",
    "AR5_ANIMATED_ANIMATION_TRACKS",
    "AR5_ANIMATED_DONOR_SHA256",
    "AR5_ANIMATED_EXPANDED_SHA256",
    "AR5_ANIMATED_FACES",
    "AR5_ANIMATED_KEY_END",
    "AR5_ANIMATED_KEY_STEP",
    "AR5_ANIMATED_MATERIAL_FACE_COUNTS",
    "AR5_ANIMATED_MATRIX_KEYS",
    "AR5_ANIMATED_NATIVE_BOUNDS",
    "AR5_ANIMATED_NATIVE_CENTROID",
    "AR5_ANIMATED_SAFE_SCALE",
    "AR5_ANIMATED_SOURCE_TEXTURE",
    "AR5_ANIMATED_STRUCTURAL_SHA256",
    "AR5_ANIMATED_TOPOLOGY_SHA256",
    "AR5_ANIMATED_UV_BOUNDS",
    "AR5_ANIMATED_UV_PAYLOAD_SHA256",
    "AR5_ANIMATED_VERTICES",
    "AuthoredAr5AnimatedFlame",
    "author_ar5_animated_flame",
]
