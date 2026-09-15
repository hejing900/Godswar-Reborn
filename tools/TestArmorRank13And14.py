"""AR13/AR14 AR4-orbit, AR12-wing, and AR5-animated-flame contracts."""

import argparse
import hashlib
import json
from pathlib import Path
import struct

from ArmorRank13And14BindingChecks import (
    CAPSTONE_BINDING_METADATA as BINDING,
    SOURCE_FOOTPRINT,
    verify_capstone_flame_texture_binding,
)
from erebus_lion.model_codec import expand_xof_mszip
from rank_effect_packages.catalog import ASSET_ROOTS, GENDERS
from rank_effect_packages.formats import structural_fingerprint, validate_tga_texture
from rank_effect_packages.package import load_package
from rank_effect_v2.ar12_ar4 import (
    AR4_FACES,
    AR4_MATERIAL_FACE_COUNTS,
    AR4_STRUCTURAL_SHA256,
    AR4_VERTICES,
    author_ar12_ar4,
)
from rank_effect_v2.ar13_ar14 import (
    CAPSTONE_FLAME_SCALE,
    CAPSTONE_ROLE_ATLASES,
    NATIVE_AR9_CANONICAL_SHA256,
    author_capstone_canonical,
)
from rank_effect_v2.ar5_animated_flame import (
    AR5_ANIMATED_ANIMATION_PAYLOAD_SHA256,
    AR5_ANIMATED_ANIMATION_TRACKS,
    AR5_ANIMATED_DONOR_SHA256,
    AR5_ANIMATED_FACES,
    AR5_ANIMATED_KEY_END,
    AR5_ANIMATED_KEY_STEP,
    AR5_ANIMATED_MATERIAL_FACE_COUNTS,
    AR5_ANIMATED_MATRIX_KEYS,
    AR5_ANIMATED_STRUCTURAL_SHA256,
    AR5_ANIMATED_UV_BOUNDS,
    AR5_ANIMATED_UV_PAYLOAD_SHA256,
    AR5_ANIMATED_VERTICES,
    author_ar5_animated_flame,
)
from rank_effect_v2.armor_ranks import (
    CAPSTONE_ARMOR_RANKS,
    slot_roles_for_rank,
    source_rank_for_slot,
)
from rank_effect_v2.capstone_builder import _PRIVATE_SPECS, _author_wings
from rank_effect_v2.capstone_flame_atlas import (
    AR9_WING_ORBIT_MIN_BILINEAR_X,
    CAPSTONE_FLAME_OUTPUT_SHA256,
    FLAME_COPIED_PIXELS,
    FLAME_RECOLOURED_PIXELS,
    FLAME_SOURCE_TEXELS,
    FLAME_TARGET_CHANGED_PIXELS,
    FLAME_TARGET_TEXELS,
    FLAME_WING_ORBIT_GAP_COLUMNS,
    NATIVE_AR5_FLAME_CROP_BGRA_SHA256,
    NATIVE_AR5_FLAME_GWO_SHA256,
    NATIVE_AR5_FLAME_RAW_SHA256,
    NATIVE_AR9_ACTIVE_MASK_SHA256,
    TINTED_AR5_FLAME_CROP_BGR_SHA256,
    TINTED_AR5_FLAME_RAW_SHA256,
    author_capstone_flame_atlas,
    decode_native_ar5_flame,
)
from rank_effect_v2.capstone_private_flame import author_capstone_private_flame
from rank_effect_v2.models import audit_model
from xmodel_sculpt.binary_x import TOKEN_FLOAT_LIST, TOKEN_NAME, float_list, parse_tokens
from xmodel_sculpt.mesh import discover_meshes


WING_STRUCTURE = "2abdbcb19b1c6e44632f884f474788163518abe42b810a640b118640f223c4a8"
FLAME_STRUCTURES = {
    13: AR5_ANIMATED_STRUCTURAL_SHA256,
    14: "4ebaeda7eadd365426da3f642700bcdcef679436736ec52447fab87552b9258d",
}
SLOT_ROLES = ("animated-rune", "animated-butterfly", "animated-flame")
PRIVATE = (
    ("animated-flame", "female_body_effect_0005.gwo", "flame", 5),
    ("animated-butterfly", "female_body_effect_0011.tga", "wings", 9),
    ("outer-wing", "female_body_effect_0011.tga", "outer_wings", 9),
    ("animated-rune", "female_body_effect_0010.tga", "orbit", 9),
)


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _f32(value):
    return struct.unpack("<f", struct.pack("<f", value))[0]


def _mesh_uv(data, label):
    expanded = expand_xof_mszip(data, label)
    tokens = parse_tokens(expanded)
    meshes = discover_meshes(expanded, tokens)
    assert len(meshes) == 1
    index = next(
        i for i, token in enumerate(tokens)
        if token.kind == TOKEN_NAME and token.value == b"MeshTextureCoords"
    )
    entry = next(
        token for token in tokens[index:index + 10]
        if token.kind == TOKEN_FLOAT_LIST
    )
    return meshes[0], float_list(expanded, entry)


def _pixel(data, x, y, channels):
    info = validate_tga_texture(data, "texture")
    assert info.image_type == 2 and (info.width, info.height) == (64, 64)
    stride = info.bits_per_pixel // 8
    row = y if info.descriptor & 0x20 else 63 - y
    column = 63 - x if info.descriptor & 0x10 else x
    offset = 18 + (row * 64 + column) * stride
    return data[offset:offset + channels]


def _rect(data, rectangle, channels):
    left, right, top, bottom = rectangle
    return b"".join(
        _pixel(data, x, y, channels)
        for y in range(top, bottom + 1)
        for x in range(left, right + 1)
    )


def _flame_animation_metadata():
    return {
        "tracks": 1,
        "matrix_keys": 73,
        "matrix_width": 16,
        "key_type": 4,
        "start_time": 0,
        "end_time": AR5_ANIMATED_KEY_END,
        "step": AR5_ANIMATED_KEY_STEP,
        "payload_sha256": AR5_ANIMATED_ANIMATION_PAYLOAD_SHA256,
        "preserved_exactly": True,
    }


def _direct(directory, gender, rank):
    ar4 = (directory / f"{gender}_body_effect_0004_0.jcs").read_bytes()
    subset = (directory / f"{gender}_body_effect_0009_2.jcs").read_bytes()
    orbit = author_ar12_ar4(
        subset,
        ar4,
        gender=gender,
        main_texture=f"reborn_body_effect_{rank:04d}_v2_orbit.tga".encode(),
        label=f"AR{rank} orbit",
    ).encoded
    wing_source = (directory / f"{gender}_body_effect_0009_1.jcs").read_bytes()
    wings = _author_wings(wing_source, f"AR{rank} wings")[0]
    flame_source = (directory / f"{gender}_body_effect_0005_2.jcs").read_bytes()
    flame = author_ar5_animated_flame(
        flame_source,
        gender=gender,
        target_texture=f"reborn_body_effect_{rank:04d}_v2_flame.tga".encode(),
        model_scale=CAPSTONE_FLAME_SCALE[rank],
        label=f"AR{rank} flame",
    )
    ar9 = (directory / f"{gender}_body_effect_0009.gwo").read_bytes()
    segmented = author_capstone_canonical(ar9, rank)
    flame_gwo = (directory / f"{gender}_body_effect_0005.gwo").read_bytes()
    design = CAPSTONE_ROLE_ATLASES[rank]["animated-flame"]
    canonical = author_capstone_flame_atlas(
        segmented.recolour.encoded, flame_gwo, rank=rank, design=design
    )
    private = author_capstone_private_flame(flame_gwo, rank=rank, design=design)
    return orbit, wings, flame_source, flame, ar9, segmented, flame_gwo, canonical, private


def _verify_catalogue():
    assert CAPSTONE_ARMOR_RANKS == (13, 14)
    assert CAPSTONE_FLAME_SCALE == {13: 1.0, 14: 1.06}
    assert _PRIVATE_SPECS == PRIVATE
    assert FLAME_SOURCE_TEXELS == FLAME_TARGET_TEXELS == SOURCE_FOOTPRINT
    assert FLAME_COPIED_PIXELS == 396 and FLAME_RECOLOURED_PIXELS == 255
    assert FLAME_TARGET_CHANGED_PIXELS == 296
    assert AR9_WING_ORBIT_MIN_BILINEAR_X == 20
    assert FLAME_WING_ORBIT_GAP_COLUMNS == 8
    assert AR5_ANIMATED_ANIMATION_TRACKS == 1
    assert AR5_ANIMATED_MATRIX_KEYS == 73
    for rank in CAPSTONE_ARMOR_RANKS:
        assert slot_roles_for_rank(rank) == SLOT_ROLES
        assert tuple(source_rank_for_slot(rank, slot) for slot in range(3)) == (4, 9, 5)


def _verify_flame_model(source, authored, rank, gender):
    source_mesh, source_uv = _mesh_uv(source, "native AR5 slot 2")
    output_mesh, output_uv = _mesh_uv(authored.encoded, "authored AR5 flame")
    assert _sha(source) == AR5_ANIMATED_DONOR_SHA256[gender]
    assert structural_fingerprint(source, "native AR5 slot 2") == (
        AR5_ANIMATED_STRUCTURAL_SHA256
    )
    assert output_mesh.faces == source_mesh.faces
    assert output_uv == source_uv
    assert (
        min(output_uv[0::2]), max(output_uv[0::2]),
        min(output_uv[1::2]), max(output_uv[1::2]),
    ) == AR5_ANIMATED_UV_BOUNDS
    scale = CAPSTONE_FLAME_SCALE[rank]
    for before, after in zip(source_mesh.vertices, output_mesh.vertices):
        expected = tuple(
            _f32(
                authored.scale_pivot[axis]
                + (before[axis] - authored.scale_pivot[axis]) * scale
            )
            for axis in range(3)
        )
        assert after == expected
    assert authored.changed_vertices == (0 if rank == 13 else 200)
    audit = audit_model(authored.encoded, "authored AR5 flame")
    assert (
        audit.vertices,
        audit.faces,
        audit.material_face_counts,
        audit.animation_keys,
        audit.uv_bounds,
    ) == (
        AR5_ANIMATED_VERTICES,
        AR5_ANIMATED_FACES,
        AR5_ANIMATED_MATERIAL_FACE_COUNTS,
        1,
        AR5_ANIMATED_UV_BOUNDS,
    )
    assert authored.output_structural_sha256 == FLAME_STRUCTURES[rank]
    metadata = authored.contract_metadata()
    assert metadata["animation"] == _flame_animation_metadata()
    assert metadata["uv_transform"] == {
        "method": "identity",
        "native_bounds": list(AR5_ANIMATED_UV_BOUNDS),
        "payload_sha256": AR5_ANIMATED_UV_PAYLOAD_SHA256,
        "changed_values": 0,
    }


def _verify_atlases(segmented, flame_gwo, canonical, private, rank):
    assert _sha(flame_gwo) == NATIVE_AR5_FLAME_GWO_SHA256
    raw = decode_native_ar5_flame(flame_gwo)
    assert _sha(raw) == NATIVE_AR5_FLAME_RAW_SHA256
    assert _sha(_rect(raw, FLAME_SOURCE_TEXELS, 4)) == (
        NATIVE_AR5_FLAME_CROP_BGRA_SHA256
    )
    assert _sha(canonical.encoded) == CAPSTONE_FLAME_OUTPUT_SHA256[rank]
    assert _sha(private.encoded) == TINTED_AR5_FLAME_RAW_SHA256[rank]
    private_bgr = _rect(private.encoded, FLAME_SOURCE_TEXELS, 3)
    assert _sha(private_bgr) == TINTED_AR5_FLAME_CROP_BGR_SHA256[rank]
    assert _rect(canonical.encoded, FLAME_TARGET_TEXELS, 3) == private_bgr
    private_bgra = _rect(private.encoded, FLAME_SOURCE_TEXELS, 4)
    source_bgra = _rect(raw, FLAME_SOURCE_TEXELS, 4)
    assert private_bgra[3::4] == source_bgra[3::4]
    assert set(private_bgra[3::4]) == {255}
    target = {
        (x, y)
        for y in range(FLAME_TARGET_TEXELS[2], FLAME_TARGET_TEXELS[3] + 1)
        for x in range(FLAME_TARGET_TEXELS[0], FLAME_TARGET_TEXELS[1] + 1)
    }
    assert all(
        _pixel(segmented.recolour.encoded, x, y, 3)
        == _pixel(canonical.encoded, x, y, 3)
        for y in range(64) for x in range(64) if (x, y) not in target
    )
    assert canonical.copied_pixels == private.sampled_pixels == 396
    assert canonical.source_recoloured_pixels == private.source_recoloured_pixels == 255
    assert canonical.target_changed_pixels == 296
    assert private.outside_footprint_changes == private.alpha_changes == 0


def _verify_direct_authoring(client):
    for asset_root in ASSET_ROOTS:
        directory = client / asset_root / "effect"
        for gender in GENDERS:
            for rank in CAPSTONE_ARMOR_RANKS:
                direct = _direct(directory, gender, rank)
                orbit, wings, source, flame, ar9, segmented, gwo, canonical, private = direct
                assert structural_fingerprint(orbit, "orbit") == AR4_STRUCTURAL_SHA256[gender]
                assert structural_fingerprint(wings, "wings") == WING_STRUCTURE
                assert _sha(ar9) == NATIVE_AR9_CANONICAL_SHA256
                _verify_flame_model(source, flame, rank, gender)
                _verify_atlases(segmented, gwo, canonical, private, rank)


def _effect_entries(root):
    manifest = json.loads((root / "rank-effect-manifest.json").read_text(encoding="utf-8"))
    result = []
    for name in manifest["effect_manifests"]:
        result.extend(json.loads((root / name).read_text(encoding="utf-8"))["effects"])
    return result


def _assert_binding(entry):
    assert all(entry[key] == value for key, value in BINDING.items())


def _verify_model_contract(entry, rank):
    slot = entry["slot"]
    expected = ((4, "animated-rune"), (9, "animated-butterfly"), (5, "animated-flame"))
    assert (entry["source_rank"], entry["role"]) == expected[slot]
    assert entry["source_slot"] == slot
    if slot == 0:
        assert entry["geometry_family"] == "exact-native-ar4-orbit-only"
        assert entry["source_route"] == "native-ar4-slot0-orbit-only"
        assert entry["output_structural_sha256"] == AR4_STRUCTURAL_SHA256[entry["gender"]]
    elif slot == 1:
        assert entry["geometry_family"] == "exact-approved-ar12-butterfly"
        assert entry["approved_ar12_structural_sha256"] == WING_STRUCTURE
        assert entry["output_structural_sha256"] == WING_STRUCTURE
    else:
        assert entry["geometry_family"] == "native-ar5-animated-flame"
        assert entry["native_ar5_slot"] == 2
        assert entry["source_route"] == "native-ar5-slot2-animated-flame-native-uv"
        assert entry["output_structural_sha256"] == FLAME_STRUCTURES[rank]
        assert entry["animation"] == _flame_animation_metadata()
        assert entry["uv_transform"]["method"] == "identity"
        assert entry["uv_transform"]["changed_values"] == 0
        assert entry["position_transform"]["scale"] == CAPSTONE_FLAME_SCALE[rank]
        assert entry["vertical_offset_hack"] is entry["frame_transform_hack"] is False


def _verify_atlas_contract(entry, rank):
    role = entry["role"]
    if role == "canonical-composite":
        assert entry["source_rank"] == 9
        assert entry["native_flame_gwo_sha256"] == NATIVE_AR5_FLAME_GWO_SHA256
        assert entry["native_flame_raw_sha256"] == NATIVE_AR5_FLAME_RAW_SHA256
        assert entry["native_ar5_crop_source"].endswith("body_effect_0005.gwo")
        assert entry["ar5_canonical_gwo_used_as_texture_donor_only"] is True
        assert entry["packing"] == {
            "method": "same-native-uv-footprint",
            "source_bilinear_texels": list(FLAME_SOURCE_TEXELS),
            "target_bilinear_texels": list(FLAME_TARGET_TEXELS),
            "uv_translation": [0.0, 0.0],
            "scale": [1.0, 1.0],
            "native_uv_preserved": True,
            "copied_pixels": 396,
            "target_changed_pixels": 296,
            "source_recoloured_pixels": 255,
            "source_alpha": "all-255; safely omitted by 24-bit canonical",
            "prior_target_nonzero_pixels": 246,
        }
        assert entry["collision_proof"] == {
            "flame_max_bilinear_x": 11,
            "wing_orbit_min_bilinear_x": 20,
            "separating_texel_columns": 8,
            "disjoint": True,
        }
        assert entry["native_ar9_input_mask_sha256"] == NATIVE_AR9_ACTIVE_MASK_SHA256
    elif role == "animated-flame":
        assert entry["source_rank"] == 5
        assert entry["source_sha256"] == NATIVE_AR5_FLAME_GWO_SHA256
        assert entry["texture_source"] == "native-ar5-canonical-gwo"
        assert entry["palette_role"] == "animated-flame"
        assert entry["sampling"]["method"] == "native-uv-no-remap"
        assert entry["sampling"]["source_bilinear_texels"] == list(FLAME_SOURCE_TEXELS)
        assert entry["sampling"]["canonical_private_sampled_bgr_identical"] is True
    else:
        assert entry["source_rank"] == 9
    if role != "canonical-composite":
        assert entry["atlas_authority"] == "declared-jcs-material-tga"


def verify_capstone_package(package, contracts, client):
    assert len(package.effects) == 24 and len(package.assets) == 142
    assert all("body_effect_0005.gwo" not in path.name for path in package.assets)
    assert all(_sha(data) != NATIVE_AR5_FLAME_GWO_SHA256 for data in package.assets.values())
    manifests = [
        entry for entry in _effect_entries(package.root)
        if entry["kind"] == "armor" and entry["rank"] in (13, 14)
    ]
    assert len(manifests) == 8
    for entry in manifests:
        _assert_binding(entry)
        assert entry["source_routes"] == [
            {"rank": 4, "slot": 0, "role": "animated-rune", "route": "exact-native-ar4-orbit-only"},
            {"rank": 9, "slot": 1, "role": "animated-butterfly"},
            {"rank": 5, "slot": 2, "role": "animated-flame", "route": "native-ar5-slot2-animated-flame-native-uv"},
        ]
        assert entry["native_ar5_gwo_used_as_crop_source"] is True
        assert entry["native_ar5_gwo_installed_wholesale"] is False

    effects = [effect for effect in package.effects if effect.kind == "armor" and effect.rank in (13, 14)]
    assert len(effects) == 8
    for effect in effects:
        directory = client / effect.asset_root / "effect"
        flame_gwo = (directory / f"{effect.gender}_body_effect_0005.gwo").read_bytes()
        verify_capstone_flame_texture_binding(package, effect, flame_gwo)
        expected = (
            AR4_STRUCTURAL_SHA256[effect.gender], WING_STRUCTURE,
            FLAME_STRUCTURES[effect.rank],
        )
        actual = tuple(
            structural_fingerprint(package.assets[path], path.as_posix())
            for path in sorted(effect.models, key=lambda path: path.name)
        )
        assert actual == expected
        assert effect.structural_sha256 == _sha("\n".join(expected).encode("ascii"))
        audits = [
            audit_model(package.assets[path], path.as_posix())
            for path in sorted(effect.models, key=lambda path: path.name)
        ]
        assert (audits[0].vertices, audits[0].faces, audits[0].material_face_counts) == (
            AR4_VERTICES, AR4_FACES, AR4_MATERIAL_FACE_COUNTS[effect.gender]
        )
        assert audits[1].material_face_counts == (256, 592)
        assert (audits[2].vertices, audits[2].faces, audits[2].animation_keys) == (200, 150, 1)

    relevant = [
        entry for entry in contracts
        if entry.get("effect") in {"armor-ar13", "armor-ar14", "armor-ar13-atlas", "armor-ar14-atlas"}
    ]
    assert len(contracts) == 138 and len(relevant) == 48
    for entry in relevant:
        _assert_binding(entry)
    for rank in (13, 14):
        models = [entry for entry in relevant if entry["effect"] == f"armor-ar{rank}"]
        atlases = [entry for entry in relevant if entry["effect"] == f"armor-ar{rank}-atlas"]
        assert len(models) == len(atlases) == 12
        for entry in models:
            _verify_model_contract(entry, rank)
        for entry in atlases:
            _verify_atlas_contract(entry, rank)


def _load_contracts(root):
    index = json.loads((root / "generated/role-contract.json").read_text(encoding="utf-8"))
    contracts = []
    for name in index["contract_manifests"]:
        contracts.extend(json.loads((root / name).read_text(encoding="utf-8"))["contracts"])
    return contracts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client-root", type=Path, required=True)
    parser.add_argument("--package-root", type=Path)
    arguments = parser.parse_args()
    client = arguments.client_root.resolve()
    assert client.is_dir()
    _verify_catalogue()
    _verify_direct_authoring(client)
    if arguments.package_root:
        root = arguments.package_root.resolve()
        verify_capstone_package(load_package(root), _load_contracts(root), client)
    assert Path(__file__).stat().st_size < 20_000
    assert Path(__file__).with_name("ArmorRank13And14BindingChecks.py").stat().st_size < 20_000
    print("PASS AR13/AR14 native-UV animated-flame capstones")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
