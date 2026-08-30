"""Focused checks for AR12's native-AR4 orbit-only slot."""

from __future__ import annotations

from pathlib import Path

from erebus_lion.model_codec import expand_xof_mszip
from rank_effect_packages.catalog import ASSET_ROOTS, GENDERS
from rank_effect_packages.formats import extract_texture_references
from rank_effect_v2.ar12_ar4 import (
    AR4_ANIMATION_TRACKS,
    AR4_COMPONENTS,
    AR4_DONOR_SHA256,
    AR4_FACES,
    AR4_MATERIAL_FACE_COUNTS,
    AR4_MATRIX_KEYS,
    AR4_OUTPUT_SHA256,
    AR4_REMOVED_COMPONENTS,
    AR4_REMOVED_FACES,
    AR4_REMOVED_VERTICES,
    AR4_STRUCTURAL_SHA256,
    AR4_TARGET_REFERENCES,
    AR4_VERTICES,
    author_ar12_ar4,
)
from rank_effect_v2.models import audit_model
from xmodel_sculpt.binary_x import (
    TOKEN_CBRACE,
    TOKEN_FLOAT_LIST,
    TOKEN_INTEGER_LIST,
    TOKEN_NAME,
    integer_list,
    parse_tokens,
)


def _verify_vertex_colours(data: bytes, label: str, gender: str) -> None:
    expanded = expand_xof_mszip(data, label)
    tokens = parse_tokens(expanded)
    starts = [
        index
        for index, token in enumerate(tokens)
        if token.kind == TOKEN_NAME and token.value == b"MeshVertexColors"
    ]
    if gender == "female":
        assert not starts
        return
    assert len(starts) == 1
    body = tokens[starts[0] + 3 :]
    body = body[: next(index for index, token in enumerate(body) if token.kind == TOKEN_CBRACE)]
    assert len(body) == AR4_VERTICES * 2
    for index in range(AR4_VERTICES):
        integer, colour = body[index * 2 : index * 2 + 2]
        expected = (AR4_VERTICES, 0) if index == 0 else (index,)
        assert integer.kind == TOKEN_INTEGER_LIST
        assert integer_list(expanded, integer) == expected
        assert colour.kind == TOKEN_FLOAT_LIST and colour.item_count == 4


def _verify_native_frame_and_timing(data: bytes, label: str, gender: str) -> None:
    expanded = expand_xof_mszip(data, label)
    tokens = parse_tokens(expanded)
    expected = b"female_body_000" if gender == "female" else b"male_body_000_chest"
    assert sum(token.kind == TOKEN_NAME and token.value == expected for token in tokens) == 2
    starts = [
        index
        for index, token in enumerate(tokens)
        if token.kind == TOKEN_NAME and token.value == b"AnimationKey"
    ]
    assert len(starts) == 1
    values = []
    for token in tokens[starts[0] + 1 :]:
        if token.kind == TOKEN_CBRACE:
            break
        if token.kind == TOKEN_INTEGER_LIST:
            values.append(integer_list(expanded, token))
    assert values[0][:2] == (4, AR4_MATRIX_KEYS)
    records = (values[0][2:], *values[1:])
    assert tuple(record[0] for record in records) == tuple(range(0, 1921, 160))
    assert all(record[1] == 16 for record in records)


def verify_ar4_source_completion(client: Path) -> None:
    reviewed = 0
    for asset_root in ASSET_ROOTS:
        directory = client / asset_root / "effect"
        for gender in GENDERS:
            source = (directory / f"{gender}_body_effect_0009_2.jcs").read_bytes()
            donor = (directory / f"{gender}_body_effect_0004_0.jcs").read_bytes()
            result = author_ar12_ar4(
                source,
                donor,
                gender=gender,
                main_texture=AR4_TARGET_REFERENCES[0],
                label=f"{asset_root}:{gender}:AR4",
            )
            audit = audit_model(result.encoded, f"{asset_root}:{gender}:AR12")
            assert result.donor_sha256 == AR4_DONOR_SHA256[gender]
            assert result.output_sha256 == AR4_OUTPUT_SHA256[gender]
            assert (audit.vertices, audit.faces) == (AR4_VERTICES, AR4_FACES)
            assert audit.material_face_counts == AR4_MATERIAL_FACE_COUNTS[gender]
            assert audit.animation_keys == AR4_ANIMATION_TRACKS
            assert extract_texture_references(
                result.encoded, f"{asset_root}:{gender}:AR12"
            ) == AR4_TARGET_REFERENCES
            _verify_vertex_colours(
                result.encoded, f"{asset_root}:{gender}:AR12", gender
            )
            _verify_native_frame_and_timing(
                result.encoded, f"{asset_root}:{gender}:AR12", gender
            )
            reviewed += 1
    assert reviewed == len(ASSET_ROOTS) * len(GENDERS)


def verify_ar4_model_contract(entry: dict[str, object]) -> None:
    gender = str(entry["gender"])
    source, output = entry["source"], entry["output"]
    assert isinstance(source, dict) and isinstance(output, dict)
    assert entry["source_rank"] == 9 and entry["role"] == "animated-rune"
    assert entry["sculpted"] is False and entry["changed_vertices"] == 0
    assert (source["vertices"], source["faces"]) == (136, 128)
    assert source["material_face_counts"] == [128]
    assert source["animation_keys"] == AR4_ANIMATION_TRACKS
    assert (output["vertices"], output["faces"]) == (AR4_VERTICES, AR4_FACES)
    assert output["material_face_counts"] == list(AR4_MATERIAL_FACE_COUNTS[gender])
    assert output["animation_keys"] == AR4_ANIMATION_TRACKS
    assert output["uv_bounds"] == [0.324909, 0.49609, 0.005242, 0.492655]
    assert output["uv_bounds"] != source["uv_bounds"]
    assert output["texture_references"] == [
        "ascii:" + value.decode("ascii") for value in AR4_TARGET_REFERENCES
    ]
    assert entry["source_structural_sha256"] != entry["output_structural_sha256"]
    assert entry["output_structural_sha256"] == AR4_STRUCTURAL_SHA256[gender]
    assert entry["native_ar4_orbit_source_rank"] == 4
    assert entry["native_ar4_orbit_donor_sha256"] == AR4_DONOR_SHA256[gender]
    assert entry["native_ar4_orbit_output_sha256"] == AR4_OUTPUT_SHA256[gender]
    extraction = entry["orbit_extraction"]
    assert isinstance(extraction, dict)
    assert extraction == {
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
    }
    roles = entry["material_roles"]
    assert isinstance(roles, list) and len(roles) == 1
    assert roles[0] == {
        "faces": AR4_FACES,
        "geometry_role": "orbit-loops",
        "texture_role": "animated-rune",
        "palette_role": "animated-rune",
        "target": AR4_TARGET_REFERENCES[0].decode("ascii"),
    }


def verify_ar4_package_model(data: bytes, label: str, gender: str) -> None:
    audit = audit_model(data, label)
    assert (audit.vertices, audit.faces) == (AR4_VERTICES, AR4_FACES)
    assert audit.material_face_counts == AR4_MATERIAL_FACE_COUNTS[gender]
    assert audit.animation_keys == AR4_ANIMATION_TRACKS
    assert extract_texture_references(data, label) == AR4_TARGET_REFERENCES
    _verify_vertex_colours(data, label, gender)
    _verify_native_frame_and_timing(data, label, gender)


__all__ = [
    "verify_ar4_model_contract",
    "verify_ar4_package_model",
    "verify_ar4_source_completion",
]
