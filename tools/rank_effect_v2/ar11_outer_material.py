"""Fail-closed outer-wing material selection for the AR9-derived AR11 wings."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
import struct

from erebus_lion.model_codec import compress_xof_mszip, expand_xof_mszip
from rank_effect_packages.errors import RankEffectError
from xmodel_sculpt.binary_x import (
    TOKEN_CBRACE,
    TOKEN_INTEGER_LIST,
    TOKEN_NAME,
    TOKEN_OBRACE,
    Token,
    integer_list,
    parse_tokens,
)
from xmodel_sculpt.mesh import MeshData, discover_meshes

from .ar11_bridge import (
    WING_ANCHOR_VERTICES,
    WING_CHANGED_VERTICES,
    WING_FACES,
    WING_SHOULDER_WEIGHT,
    WING_VERTICAL_LIFT,
    WING_VERTICES,
    Ar11WingTransform,
)


BASE_MATERIAL_INDEX = 1
OUTER_MATERIAL_INDEX = 0
MATERIAL_COUNT = 2
INNER_FACE_COUNT = 448
SHOULDER_FACE_COUNT = 144
OUTER_FACE_COUNT = 256
OUTPUT_MATERIAL_FACE_COUNTS = (OUTER_FACE_COUNT, WING_FACES - OUTER_FACE_COUNT)
OUTER_FACE_RANGES = (
    (0, 27),
    (92, 127),
    (192, 255),
    (424, 451),
    (516, 551),
    (616, 679),
)

_DONOR_EXPANDED_SHA256 = (
    "718c1e928b28627248c5256755f7faf393633263c94f1209781210caf7d2b4f0"
)
_MATERIAL_LIST_TEMPLATE = b"MeshMaterialList"
_MATERIAL_REFERENCES = (
    b"Material__34_Material__22Sub0",
    b"Material__34_female_body_effect_0005Sub1",
)
_INDEX_BYTES = 4
_BAND_INNER = "inner"
_BAND_SHOULDER = "shoulder"
_BAND_OUTER = "outer"


@dataclass(frozen=True, slots=True)
class Ar11OuterMaterialResult:
    """Authored model plus auditable material-selection metadata."""

    encoded: bytes
    expanded: bytes
    source_sha256: str
    output_sha256: str
    source_expanded_sha256: str
    output_expanded_sha256: str
    immutable_expanded_sha256: str
    material_count: int
    total_faces: int
    base_material_index: int
    outer_material_index: int
    source_material_face_counts: tuple[int, ...]
    output_material_face_counts: tuple[int, ...]
    inner_faces: int
    shoulder_faces: int
    outer_faces: int
    changed_faces: int
    outer_face_ranges: tuple[tuple[int, int], ...]
    selected_payload_bytes: int
    changed_bytes: int

    def contract_metadata(self) -> dict[str, object]:
        """Return JSON-ready fields for the rank-effect package contract."""

        return {
            "outer_material": {
                "material_count": self.material_count,
                "total_faces": self.total_faces,
                "base_material_index": self.base_material_index,
                "outer_material_index": self.outer_material_index,
                "source_material_face_counts": list(
                    self.source_material_face_counts
                ),
                "output_material_face_counts": list(
                    self.output_material_face_counts
                ),
                "changed_faces": self.changed_faces,
                "selected_payload_bytes": self.selected_payload_bytes,
                "changed_bytes": self.changed_bytes,
                "immutable_expanded_sha256": self.immutable_expanded_sha256,
                "outer_face_ranges_inclusive": [
                    list(face_range) for face_range in self.outer_face_ranges
                ],
                "bands": {
                    _BAND_INNER: {"faces": self.inner_faces},
                    _BAND_SHOULDER: {"faces": self.shoulder_faces},
                    _BAND_OUTER: {"faces": self.outer_faces},
                },
            }
        }


@dataclass(frozen=True, slots=True)
class _MaterialListLayout:
    index_token: Token
    material_count: int
    face_count: int
    face_materials: tuple[int, ...]


def _matching_close(
    tokens: tuple[Token, ...], open_index: int, parent_close: int
) -> int:
    depth = 0
    for index in range(open_index, parent_close + 1):
        if tokens[index].kind == TOKEN_OBRACE:
            depth += 1
        elif tokens[index].kind == TOKEN_CBRACE:
            depth -= 1
            if depth == 0:
                return index
            if depth < 0:
                break
    raise RankEffectError("AR11 MeshMaterialList is not bounded by its Mesh")


def _read_material_list(
    expanded: bytes,
    tokens: tuple[Token, ...],
    mesh: MeshData,
) -> _MaterialListLayout:
    candidates = [
        index
        for index in range(mesh.open_token_index + 1, mesh.close_token_index)
        if tokens[index].kind == TOKEN_NAME
        and tokens[index].value == _MATERIAL_LIST_TEMPLATE
    ]
    if len(candidates) != 1:
        raise RankEffectError(
            "AR11 wing donor must contain exactly one MeshMaterialList object"
        )

    name_index = candidates[0]
    if (
        name_index + 2 >= mesh.close_token_index
        or tokens[name_index + 1].kind != TOKEN_NAME
        or tokens[name_index + 1].value != b""
        or tokens[name_index + 2].kind != TOKEN_OBRACE
    ):
        raise RankEffectError("AR11 MeshMaterialList object header drifted")
    open_index = name_index + 2
    close_index = _matching_close(tokens, open_index, mesh.close_token_index)
    body = tokens[open_index + 1 : close_index]
    if len(body) != 7 or body[0].kind != TOKEN_INTEGER_LIST:
        raise RankEffectError("AR11 MeshMaterialList body layout drifted")
    for material_index, reference in enumerate(_MATERIAL_REFERENCES):
        offset = 1 + material_index * 3
        if (
            body[offset].kind != TOKEN_OBRACE
            or body[offset + 1].kind != TOKEN_NAME
            or body[offset + 1].value != reference
            or body[offset + 2].kind != TOKEN_CBRACE
        ):
            raise RankEffectError(
                f"AR11 material reference {material_index} drifted"
            )

    index_token = body[0]
    values = integer_list(expanded, index_token)
    if len(values) < 2:
        raise RankEffectError("AR11 material face list is incomplete")
    material_count, face_count = values[:2]
    face_materials = values[2:]
    if (
        material_count != MATERIAL_COUNT
        or face_count != WING_FACES
        or len(face_materials) != face_count
        or index_token.item_count != WING_FACES + 2
        or index_token.payload_offset is None
        or index_token.end - index_token.payload_offset
        != (WING_FACES + 2) * _INDEX_BYTES
    ):
        raise RankEffectError("AR11 material face-list contract drifted")
    if any(index >= material_count for index in face_materials):
        raise RankEffectError("AR11 material face list contains an invalid index")
    return _MaterialListLayout(
        index_token,
        material_count,
        face_count,
        tuple(face_materials),
    )


def _authoritative_vertex_bands(mesh: MeshData) -> tuple[str, ...]:
    """Classify vertices through the reviewed AR11 transform itself."""

    transform = Ar11WingTransform()
    shoulder_lift = WING_VERTICAL_LIFT * WING_SHOULDER_WEIGHT
    bands: list[str] = []
    for vertex_index, point in enumerate(mesh.vertices):
        output = transform(mesh, vertex_index, point)
        lift = output[0] - point[0]
        if not math.isclose(output[2], point[2], rel_tol=0.0, abs_tol=1e-9):
            raise RankEffectError("AR11 wing band plan unexpectedly changes depth")
        if math.isclose(lift, 0.0, rel_tol=0.0, abs_tol=1e-9):
            bands.append(_BAND_INNER)
        elif math.isclose(lift, shoulder_lift, rel_tol=0.0, abs_tol=1e-9):
            bands.append(_BAND_SHOULDER)
        elif math.isclose(lift, WING_VERTICAL_LIFT, rel_tol=0.0, abs_tol=1e-9):
            bands.append(_BAND_OUTER)
        else:
            raise RankEffectError(
                f"AR11 wing vertex {vertex_index} has an unknown component band"
            )
    if (
        len(bands) != WING_VERTICES
        or bands.count(_BAND_INNER) != WING_ANCHOR_VERTICES
        or bands.count(_BAND_SHOULDER) + bands.count(_BAND_OUTER)
        != WING_CHANGED_VERTICES
    ):
        raise RankEffectError("AR11 wing vertex-band counts drifted")
    return tuple(bands)


def _authoritative_face_bands(mesh: MeshData) -> tuple[str, ...]:
    vertex_bands = _authoritative_vertex_bands(mesh)
    face_bands: list[str] = []
    for face_index, face in enumerate(mesh.faces):
        bands = {vertex_bands[vertex_index] for vertex_index in face}
        if len(bands) != 1:
            raise RankEffectError(
                f"AR11 wing face {face_index} crosses transform bands"
            )
        face_bands.append(bands.pop())
    counts = tuple(
        face_bands.count(band)
        for band in (_BAND_INNER, _BAND_SHOULDER, _BAND_OUTER)
    )
    if counts != (INNER_FACE_COUNT, SHOULDER_FACE_COUNT, OUTER_FACE_COUNT):
        raise RankEffectError("AR11 wing face-band counts drifted")
    return tuple(face_bands)


def _inclusive_ranges(indices: tuple[int, ...]) -> tuple[tuple[int, int], ...]:
    if not indices:
        return ()
    ranges: list[tuple[int, int]] = []
    start = previous = indices[0]
    for index in indices[1:]:
        if index <= previous:
            raise RankEffectError("AR11 outer face indexes are not strictly ordered")
        if index != previous + 1:
            ranges.append((start, previous))
            start = index
        previous = index
    ranges.append((start, previous))
    return tuple(ranges)


def _assert_only_ranges_changed(
    source: bytes,
    result: bytes,
    ranges: tuple[tuple[int, int], ...],
) -> tuple[str, int]:
    if len(source) != len(result):
        raise RankEffectError("AR11 outer material changed expanded model length")
    digest = hashlib.sha256()
    cursor = 0
    changed_bytes = 0
    source_index = struct.pack("<I", BASE_MATERIAL_INDEX)
    result_index = struct.pack("<I", OUTER_MATERIAL_INDEX)
    for start, end in ranges:
        if start < cursor or end - start != _INDEX_BYTES:
            raise RankEffectError(
                "AR11 material-index payload ranges overlap or drifted"
            )
        if source[cursor:start] != result[cursor:start]:
            raise RankEffectError(
                "AR11 outer material changed bytes outside selected face indexes"
            )
        if source[start:end] != source_index or result[start:end] != result_index:
            raise RankEffectError("AR11 selected material-index replacement drifted")
        digest.update(source[cursor:start])
        digest.update(struct.pack("<QQ", start, end - start))
        changed_bytes += sum(
            left != right for left, right in zip(source[start:end], result[start:end])
        )
        cursor = end
    if source[cursor:] != result[cursor:]:
        raise RankEffectError("AR11 outer material changed trailing immutable bytes")
    digest.update(source[cursor:])
    if changed_bytes != len(ranges):
        raise RankEffectError("AR11 changed material-index byte count drifted")
    return digest.hexdigest(), changed_bytes


def author_ar11_outer_material(
    source: bytes,
    *,
    label: str = "female_body_effect_0009_1.jcs",
) -> Ar11OuterMaterialResult:
    """Assign only reviewed outer-wing faces to the donor's material zero."""

    try:
        expanded_source = expand_xof_mszip(source, label)
        source_tokens = parse_tokens(expanded_source)
        source_meshes = discover_meshes(expanded_source, source_tokens)
    except (ValueError, OSError) as error:
        raise RankEffectError(f"Invalid AR11 wing donor {label}: {error}") from error
    if len(source_meshes) != 1:
        raise RankEffectError("AR11 wing donor must contain exactly one Mesh")
    mesh = source_meshes[0]
    face_bands = _authoritative_face_bands(mesh)
    outer_faces = tuple(
        face_index
        for face_index, band in enumerate(face_bands)
        if band == _BAND_OUTER
    )
    outer_ranges = _inclusive_ranges(outer_faces)
    if outer_ranges != OUTER_FACE_RANGES:
        raise RankEffectError("AR11 outer-wing face ranges drifted")

    layout = _read_material_list(expanded_source, source_tokens, mesh)
    if layout.face_materials != (BASE_MATERIAL_INDEX,) * WING_FACES:
        raise RankEffectError(
            "AR11 wing donor face materials are not exact material one"
        )
    source_expanded_sha256 = hashlib.sha256(expanded_source).hexdigest()
    if source_expanded_sha256 != _DONOR_EXPANDED_SHA256:
        raise RankEffectError("AR11 wing expanded donor fingerprint drifted")

    assert layout.index_token.payload_offset is not None
    target = bytearray(expanded_source)
    payload_ranges: list[tuple[int, int]] = []
    for face_index in outer_faces:
        start = (
            layout.index_token.payload_offset
            + (2 + face_index) * _INDEX_BYTES
        )
        end = start + _INDEX_BYTES
        if target[start:end] != struct.pack("<I", BASE_MATERIAL_INDEX):
            raise RankEffectError(
                f"AR11 wing face {face_index} material changed before authoring"
            )
        target[start:end] = struct.pack("<I", OUTER_MATERIAL_INDEX)
        payload_ranges.append((start, end))

    expanded = bytes(target)
    immutable_sha256, changed_bytes = _assert_only_ranges_changed(
        expanded_source, expanded, tuple(payload_ranges)
    )
    try:
        result_tokens = parse_tokens(expanded)
        result_meshes = discover_meshes(expanded, result_tokens)
    except ValueError as error:
        raise RankEffectError(
            f"Authored AR11 outer-material model is invalid: {error}"
        ) from error
    if source_tokens != result_tokens or source_meshes != result_meshes:
        raise RankEffectError("AR11 outer material changed Mesh or token structure")
    result_layout = _read_material_list(expanded, result_tokens, result_meshes[0])
    expected_materials = tuple(
        OUTER_MATERIAL_INDEX if band == _BAND_OUTER else BASE_MATERIAL_INDEX
        for band in face_bands
    )
    if result_layout.face_materials != expected_materials:
        raise RankEffectError(
            "AR11 outer material failed exact post-authoring validation"
        )
    output_counts = tuple(
        expected_materials.count(index) for index in range(MATERIAL_COUNT)
    )
    if output_counts != OUTPUT_MATERIAL_FACE_COUNTS:
        raise RankEffectError("AR11 output material face counts drifted")

    try:
        encoded = compress_xof_mszip(expanded, label)
        decoded = expand_xof_mszip(encoded, label)
    except (ValueError, OSError) as error:
        raise RankEffectError(
            f"AR11 outer material MSZIP round trip failed: {error}"
        ) from error
    if decoded != expanded or compress_xof_mszip(decoded, label) != encoded:
        raise RankEffectError("AR11 outer material MSZIP round trip was not exact")

    return Ar11OuterMaterialResult(
        encoded=encoded,
        expanded=expanded,
        source_sha256=hashlib.sha256(source).hexdigest(),
        output_sha256=hashlib.sha256(encoded).hexdigest(),
        source_expanded_sha256=source_expanded_sha256,
        output_expanded_sha256=hashlib.sha256(expanded).hexdigest(),
        immutable_expanded_sha256=immutable_sha256,
        material_count=layout.material_count,
        total_faces=layout.face_count,
        base_material_index=BASE_MATERIAL_INDEX,
        outer_material_index=OUTER_MATERIAL_INDEX,
        source_material_face_counts=(0, WING_FACES),
        output_material_face_counts=output_counts,
        inner_faces=face_bands.count(_BAND_INNER),
        shoulder_faces=face_bands.count(_BAND_SHOULDER),
        outer_faces=len(outer_faces),
        changed_faces=len(payload_ranges),
        outer_face_ranges=outer_ranges,
        selected_payload_bytes=len(payload_ranges) * _INDEX_BYTES,
        changed_bytes=changed_bytes,
    )


__all__ = [
    "BASE_MATERIAL_INDEX",
    "OUTER_MATERIAL_INDEX",
    "OUTPUT_MATERIAL_FACE_COUNTS",
    "OUTER_FACE_RANGES",
    "Ar11OuterMaterialResult",
    "author_ar11_outer_material",
]
