"""Focused checks for AR12 Aetherwing plus native-AR4 orbit ribbons."""

from __future__ import annotations

import argparse
import math
from pathlib import Path
import struct

from erebus_lion.model_codec import expand_xof_mszip
from rank_effect_packages.catalog import ASSET_ROOTS, GENDERS
from rank_effect_packages.formats import (
    extract_texture_references,
    validate_tga_texture,
)
from rank_effect_v2.ar11_bridge import (
    HALO_VERTICES,
    WING_ANCHOR_VERTICES,
    WING_CHANGED_VERTICES,
    Ar11HaloTransform,
    Ar11WingTransform,
    validate_ar11_wings,
)
from rank_effect_v2.ar11_outer_material import (
    OUTPUT_MATERIAL_FACE_COUNTS,
    OUTER_FACE_RANGES,
    author_ar11_outer_material,
)
from rank_effect_v2.ar12_aether import (
    AR12_HALO_SCALE,
    AR12_ROLE_ATLASES,
    AR12_WING_LATERAL_EXPANSION,
    AR12_WING_SHOULDER_WEIGHT,
    AR12_WING_VERTICAL_LIFT,
    Ar12HaloTransform,
    Ar12WingTransform,
    validate_ar12_halo,
    validate_ar12_wings,
)
from rank_effect_v2.ar12_atlas import (
    AR12_CANONICAL_REGIONS,
    author_ar12_canonical,
    author_ar12_private,
)
from rank_effect_v2.armor_ranks import (
    ARMOR_RANK_DESIGNS,
    source_rank_for,
    slot_roles_for_rank,
)
from rank_effect_v2.models import audit_model
from xmodel_sculpt.binary_x import parse_tokens
from xmodel_sculpt.mesh import discover_meshes
from xmodel_sculpt.sculpt import sculpt_xof_mszip

from TestArmorRank12Ar4 import (
    verify_ar4_model_contract,
    verify_ar4_package_model,
    verify_ar4_source_completion,
)


FULL_REGION = [0.0, 1.0, 0.0, 1.0]
EXPECTED_ROLES = {
    "animated-core": (
        "halo", "female_body_effect_0010.tga",
        ("082755", "155B9F", "419BD2"), 0.98, 214,
    ),
    "animated-butterfly": (
        "wings", "female_body_effect_0011.tga",
        ("092E68", "1768B8", "43A1DE"), 1.04, 232,
    ),
    "animated-rune": (
        "rune", "female_body_effect_0010.tga",
        ("06275C", "125AA4", "378FCB"), 0.90, 218,
    ),
    "outer-wing": (
        "outer_wings", "female_body_effect_0011.tga",
        ("06245B", "0E55AC", "2B8ADB"), 1.01, 226,
    ),
}
EXPECTED_SLOTS = {
    0: ("animated-core", 116, 100, (100,), 1),
    1: ("animated-butterfly", 976, 848, (0, 848), 1),
    2: ("animated-rune", 136, 128, (128,), 1),
}
EXPECTED_OUTER_RANGES = (
    (0, 27), (92, 127), (192, 255),
    (424, 451), (516, 551), (616, 679),
)


def _mesh(data: bytes, label: str):
    expanded = expand_xof_mszip(data, label)
    meshes = discover_meshes(expanded, parse_tokens(expanded))
    assert len(meshes) == 1
    return meshes[0]


def _palette_hex(palette) -> tuple[str, str, str]:
    return tuple(
        "".join(f"{round(channel * 255):02X}" for channel in colour)
        for colour in (palette.shadow, palette.middle, palette.highlight)
    )


def _contract_palette_hex(entry: dict[str, object]) -> tuple[str, str, str]:
    values = entry["palette"]
    assert isinstance(values, dict)
    return tuple(
        "".join(f"{round(float(channel) * 255):02X}" for channel in values[name])
        for name in ("shadow", "middle", "highlight")
    )


def _pixels(value: bytes):
    width, height = struct.unpack_from("<HH", value, 12)
    bytes_per_pixel = value[16] // 8
    assert (width, height) == (64, 64) and bytes_per_pixel in (3, 4)
    for offset in range(18, 18 + width * height * bytes_per_pixel, bytes_per_pixel):
        blue, green, red = value[offset : offset + 3]
        alpha = value[offset + 3] if bytes_per_pixel == 4 else 255
        yield red, green, blue, alpha


def _active_rgb(source: bytes, output: bytes) -> tuple[tuple[int, int, int], ...]:
    return tuple(
        after[:3]
        for before, after in zip(_pixels(source), _pixels(output))
        if before[3] > 0 and max(before[:3]) / 255.0 > 0.015
    )


def _mean_rgb(pixels: tuple[tuple[int, int, int], ...]) -> tuple[float, ...]:
    assert pixels
    return tuple(
        sum(pixel[channel] for pixel in pixels) / len(pixels)
        for channel in range(3)
    )


def _mean_luma(pixels: tuple[tuple[int, int, int], ...]) -> float:
    assert pixels
    return sum(
        0.2126 * red + 0.7152 * green + 0.0722 * blue
        for red, green, blue in pixels
    ) / len(pixels)


def maximum_rgb(data: bytes, label: str) -> int:
    info = validate_tga_texture(data, label)
    bytes_per_pixel = info.bits_per_pixel // 8
    end = 18 + info.width * info.height * bytes_per_pixel
    return max(
        max(data[offset : offset + 3])
        for offset in range(18, end, bytes_per_pixel)
    )


def _assert_model_payload_stable(source: bytes, output: bytes, label: str) -> None:
    before = audit_model(source, f"{label}:source")
    after = audit_model(output, f"{label}:output")
    for field in ("vertices", "faces", "uv_bounds", "animation_keys"):
        assert getattr(before, field) == getattr(after, field)


def _spans(points) -> tuple[float, float, float]:
    return tuple(
        max(point[axis] for point in points) - min(point[axis] for point in points)
        for axis in range(3)
    )


def _verify_atlases(client: Path) -> None:
    assert tuple(AR12_ROLE_ATLASES) == tuple(EXPECTED_ROLES)
    assert tuple(role for role, _region in AR12_CANONICAL_REGIONS) == (
        "animated-core", "animated-rune", "animated-butterfly"
    )
    expected_counts = {24: 2157, 32: 2402}
    for asset_root in ASSET_ROOTS:
        directory = client / asset_root / "effect"
        rendered: dict[str, bytes] = {}
        rendered_luma: dict[str, float] = {}
        for role, (_suffix, source_name, palette, gain, ceiling) in EXPECTED_ROLES.items():
            design = AR12_ROLE_ATLASES[role]
            assert _palette_hex(design.palette) == palette
            assert design.palette.region == (0.0, 1.0, 0.0, 1.0)
            assert (design.luma_gain, design.maximum_channel) == (gain, ceiling)
            assert all(blue > green > red for red, green, blue in (
                design.palette.shadow,
                design.palette.middle,
                design.palette.highlight,
            ))

            source = (directory / source_name).read_bytes()
            result = author_ar12_private(source, role).recolour
            assert result.changed_pixels == expected_counts[source[16]]
            assert result.alpha_changes == result.outside_region_changes == 0
            active = _active_rgb(source, result.encoded)
            assert len(active) == result.changed_pixels
            assert max(map(max, active)) == ceiling
            red, green, blue = _mean_rgb(active)
            assert blue > green > red
            rendered_luma[role] = _mean_luma(active)
            assert all(
                before[3] == after[3]
                for before, after in zip(_pixels(source), _pixels(result.encoded))
            )
            rendered[role] = result.encoded
        assert rendered["animated-rune"] != rendered["animated-butterfly"]
        assert 0.85 <= (
            rendered_luma["animated-rune"]
            / rendered_luma["animated-butterfly"]
        ) <= 0.88
        assert len(set(rendered.values())) == len(EXPECTED_ROLES)

        for gender in GENDERS:
            source = (directory / f"{gender}_body_effect_0009.gwo").read_bytes()
            authored = author_ar12_canonical(source)
            result = authored.recolour
            assert result.changed_pixels == expected_counts[source[16]]
            assert result.alpha_changes == result.outside_region_changes == 0
            assert tuple(segment.role for segment in authored.segments) == tuple(
                role for role, _region in AR12_CANONICAL_REGIONS
            )
            active = _active_rgb(source, result.encoded)
            red, green, blue = _mean_rgb(active)
            assert blue > green > red


def _verify_geometry(client: Path) -> None:
    verify_ar4_source_completion(client)
    assert source_rank_for(12) == 9
    assert slot_roles_for_rank(12) == (
        "animated-core", "animated-butterfly", "animated-rune"
    )
    assert (AR12_HALO_SCALE, AR12_WING_VERTICAL_LIFT) == (1.10, 0.58)
    assert (AR12_WING_LATERAL_EXPANSION, AR12_WING_SHOULDER_WEIGHT) == (
        0.24, 0.25
    )
    assert ARMOR_RANK_DESIGNS[12].placements is None

    reviewed = 0
    for asset_root in ASSET_ROOTS:
        directory = client / asset_root / "effect"
        for gender in GENDERS:
            stem = f"{gender}_body_effect_0009"
            sources = [
                (directory / f"{stem}_{slot}.jcs").read_bytes()
                for slot in range(3)
            ]
            for slot, source in enumerate(sources):
                role, vertices, faces, materials, animations = EXPECTED_SLOTS[slot]
                audit = audit_model(source, f"{stem}_{slot}.jcs")
                assert role == slot_roles_for_rank(12)[slot]
                assert (audit.vertices, audit.faces) == (vertices, faces)
                assert audit.material_face_counts == materials
                assert audit.animation_keys == animations

            halo_mesh = _mesh(sources[0], f"{stem}_0.jcs")
            halo = sculpt_xof_mszip(
                sources[0], Ar12HaloTransform(), label=f"{stem}_0.jcs:AR12"
            )
            assert halo.changed_vertices == HALO_VERTICES == 116
            _assert_model_payload_stable(sources[0], halo.encoded, f"{stem}:halo")
            halo_output = tuple(_mesh(halo.encoded, f"{stem}:AR12-halo").vertices)
            validate_ar12_halo(halo_mesh, halo_output)
            ar11_halo_transform = Ar11HaloTransform()
            ar11_halo = tuple(
                ar11_halo_transform(halo_mesh, index, point)
                for index, point in enumerate(halo_mesh.vertices)
            )
            source_spans = _spans(halo_mesh.vertices)
            ar11_spans = _spans(ar11_halo)
            ar12_spans = _spans(halo_output)
            assert all(
                ar12_spans[axis] > ar11_spans[axis] > source_spans[axis]
                for axis in (0, 1)
            )
            assert math.isclose(ar12_spans[2], source_spans[2], abs_tol=1e-7)

            material = author_ar11_outer_material(
                sources[1], label=f"{stem}_1.jcs:AR12-material"
            )
            assert material.output_material_face_counts == OUTPUT_MATERIAL_FACE_COUNTS
            assert OUTPUT_MATERIAL_FACE_COUNTS == (256, 592)
            assert material.outer_face_ranges == OUTER_FACE_RANGES == EXPECTED_OUTER_RANGES
            assert (material.inner_faces, material.shoulder_faces,
                    material.outer_faces) == (448, 144, 256)
            assert (material.changed_faces, material.changed_bytes) == (256, 256)

            wing_mesh = _mesh(sources[1], f"{stem}_1.jcs")
            wings = sculpt_xof_mszip(
                material.encoded, Ar12WingTransform(), label=f"{stem}_1.jcs:AR12"
            )
            assert wings.changed_vertices == WING_CHANGED_VERTICES == 464
            _assert_model_payload_stable(
                material.encoded, wings.encoded, f"{stem}:wings"
            )
            wing_output = tuple(_mesh(wings.encoded, f"{stem}:AR12-wings").vertices)
            metrics = validate_ar12_wings(wing_mesh, wing_output)
            assert math.isclose(metrics.top_lift, 0.58, abs_tol=1e-6)
            assert math.isclose(metrics.lateral_span_ratio, 1.24, abs_tol=1e-6)
            assert math.isclose(metrics.depth_span_ratio, 1.0, abs_tol=1e-7)
            assert metrics.anchor_drift <= 1e-7
            assert metrics.lateral_centroid_drift <= 1e-7
            anchors = sum(
                math.dist(before, after) <= 1e-7
                for before, after in zip(wing_mesh.vertices, wing_output)
            )
            assert anchors == WING_ANCHOR_VERTICES == 512

            ar11_transform = Ar11WingTransform()
            ar11_output = tuple(
                ar11_transform(wing_mesh, index, point)
                for index, point in enumerate(wing_mesh.vertices)
            )
            ar11_metrics = validate_ar11_wings(wing_mesh, ar11_output)
            assert metrics.top_lift > ar11_metrics.top_lift
            assert metrics.vertical_span_ratio > ar11_metrics.vertical_span_ratio
            assert metrics.lateral_span_ratio > ar11_metrics.lateral_span_ratio
            reviewed += 1
    assert reviewed == len(ASSET_ROOTS) * len(GENDERS)


def _verify_outer_material_contract(value: object) -> None:
    assert isinstance(value, dict)
    assert value["material_count"] == 2 and value["total_faces"] == 848
    assert value["base_material_index"] == 1
    assert value["outer_material_index"] == 0
    assert value["source_material_face_counts"] == [0, 848]
    assert value["output_material_face_counts"] == [256, 592]
    assert value["changed_faces"] == value["changed_bytes"] == 256
    assert value["selected_payload_bytes"] == 1024
    assert value["outer_face_ranges_inclusive"] == [
        list(item) for item in EXPECTED_OUTER_RANGES
    ]
    assert value["bands"] == {
        "inner": {"faces": 448},
        "shoulder": {"faces": 144},
        "outer": {"faces": 256},
    }


def verify_ar12_model_contract(entry: dict[str, object]) -> None:
    slot = int(entry["slot"])
    if slot == 2:
        verify_ar4_model_contract(entry)
        return
    role, vertices, faces, source_materials, animations = EXPECTED_SLOTS[slot]
    assert entry["source_rank"] == 9 and entry["role"] == role
    source = entry["source"]
    output = entry["output"]
    assert isinstance(source, dict) and isinstance(output, dict)
    assert (source["vertices"], source["faces"]) == (vertices, faces)
    assert (output["vertices"], output["faces"]) == (vertices, faces)
    assert source["material_face_counts"] == list(source_materials)
    assert output["material_face_counts"] == (
        [256, 592] if slot == 1 else list(source_materials)
    )
    assert source["animation_keys"] == output["animation_keys"] == animations
    assert source["uv_bounds"] == output["uv_bounds"]

    if slot == 0:
        assert entry["sculpted"] is True and entry["changed_vertices"] == 116
        assert entry["halo_scale"] == AR12_HALO_SCALE == 1.10
        assert entry["source_structural_sha256"] != entry["output_structural_sha256"]
    elif slot == 1:
        assert entry["sculpted"] is True and entry["changed_vertices"] == 464
        assert entry["source_structural_sha256"] != entry["output_structural_sha256"]
        assert entry["wing_profile"] == {
            "vertical_lift": 0.58,
            "lateral_expansion": 0.24,
            "shoulder_weight": 0.25,
        }
        _verify_outer_material_contract(entry["outer_material"])


def _verify_segment(
    segment: dict[str, object],
    role: str,
    region: list[float],
) -> None:
    _suffix, _source, palette, gain, ceiling = EXPECTED_ROLES[role]
    assert segment["role"] == role and segment["region"] == region
    assert _contract_palette_hex(segment) == palette
    assert segment["strength"] == 1.0
    assert segment["luma_gain"] == gain
    assert segment["maximum_channel"] == ceiling
    assert segment["active_pixels"] == segment["changed_pixels"]
    assert int(segment["active_pixels"]) > 0


def verify_ar12_contract_entries(entries: list[dict[str, object]]) -> None:
    assert len(entries) == 12
    for role in EXPECTED_ROLES:
        assert sum(entry["role"] == role for entry in entries) == 2
    assert sum(entry["role"] == "canonical-composite" for entry in entries) == 4
    for entry in entries:
        role = str(entry["role"])
        assert entry["source_rank"] == 9
        assert entry["preserve_luma"] is True
        assert entry["additive_glow"] is False
        if role in EXPECTED_ROLES:
            suffix, _source, palette, gain, ceiling = EXPECTED_ROLES[role]
            assert entry["region"] == FULL_REGION
            assert _contract_palette_hex(entry) == palette
            assert entry["strength"] == 1.0
            assert (entry["luma_gain"], entry["maximum_channel"]) == (gain, ceiling)
            assert entry["active_pixels"] == entry["changed_pixels"] == 2402
            assert Path(str(entry["target"])).name == (
                f"reborn_body_effect_0012_v2_{suffix}.tga"
            )
            segments = entry["segments"]
            assert isinstance(segments, list) and len(segments) == 1
            _verify_segment(segments[0], role, FULL_REGION)
        else:
            assert role == "canonical-composite"
            assert all(
                entry[key] is None
                for key in ("palette", "strength", "luma_gain", "maximum_channel")
            )
            assert entry["active_pixels"] == entry["changed_pixels"] == 2157
            segments = entry["segments"]
            assert isinstance(segments, list) and len(segments) == 3
            for segment, (segment_role, region) in zip(
                segments, AR12_CANONICAL_REGIONS
            ):
                _verify_segment(segment, segment_role, [
                    region.minimum_u, region.maximum_u,
                    region.minimum_v, region.maximum_v,
                ])


def verify_ar12_package_effects(package, effects) -> None:
    assert len(effects) == 4 and all(effect.rank == 12 for effect in effects)
    private_names = {
        f"reborn_body_effect_0012_v2_{values[0]}.tga"
        for values in EXPECTED_ROLES.values()
    }
    expected_references = (
        {b"reborn_body_effect_0012_v2_halo.tga"},
        {
            b"reborn_body_effect_0012_v2_wings.tga",
            b"reborn_body_effect_0012_v2_outer_wings.tga",
        },
    )
    ceilings = {
        f"reborn_body_effect_0012_v2_{suffix}.tga": ceiling
        for suffix, _source, _palette, _gain, ceiling in EXPECTED_ROLES.values()
    }
    for effect in effects:
        assert {path.name for path in effect.private_textures} == private_names
        models = sorted(effect.models, key=lambda value: value.name)
        assert len(models) == 3
        for slot, path in enumerate(models):
            data = package.assets[path]
            if slot == 2:
                verify_ar4_package_model(data, path.as_posix(), effect.gender)
                continue
            role, vertices, faces, _materials, animations = EXPECTED_SLOTS[slot]
            audit = audit_model(data, path.as_posix())
            assert role == slot_roles_for_rank(12)[slot]
            assert (audit.vertices, audit.faces) == (vertices, faces)
            assert audit.animation_keys == animations
            assert audit.material_face_counts == (
                (256, 592) if slot == 1 else EXPECTED_SLOTS[slot][3]
            )
            assert set(extract_texture_references(data, path.as_posix())) == (
                expected_references[slot]
            )
        for path in effect.private_textures:
            info = validate_tga_texture(package.assets[path], path.as_posix())
            assert info.bits_per_pixel == 32
            assert maximum_rgb(package.assets[path], path.as_posix()) == ceilings[path.name]
        canonical = package.assets[effect.canonical_texture]
        assert validate_tga_texture(
            canonical, effect.canonical_texture.as_posix()
        ).bits_per_pixel == 24
        assert maximum_rgb(canonical, effect.canonical_texture.as_posix()) <= 235


def verify_ar12_design(client: Path) -> None:
    _verify_atlases(client)
    _verify_geometry(client)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client-root", type=Path, required=True)
    client = parser.parse_args().client_root.resolve()
    assert client.is_dir()
    verify_ar12_design(client)
    print("PASS AR12 Aetherwing geometry, AR4 orbit-only slot, and blue materials")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
