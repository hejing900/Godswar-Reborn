import argparse
import hashlib
import math
from pathlib import Path
import struct

from rank_effect_packages.catalog import ASSET_ROOTS, GENDERS
from rank_effect_packages.formats import structural_fingerprint as fingerprint
from rank_effect_v2.armor_ranks import (
    ARMOR_CLONE_SOURCE_RANK as CLONE_RANK,
    ARMOR_ORBIT_SOURCE_RANK as ORBIT_RANK,
    ARMOR_RANKS, ARMOR_RANK_DESIGNS as DESIGNS, AR11_ROLE_ATLASES as AR11_ATLASES,
    AR9_DERIVED_ARMOR_RANKS as AR9_RANKS, CLONE_SLOT_ROLES,
    CAPSTONE_ARMOR_RANKS as CAPSTONE_RANKS,
    CAPSTONE_SLOT_ROLES, design_for_rank, slot_roles_for_rank, source_rank_for,
    source_rank_for_slot, validate_design_catalogue,
)
from rank_effect_v2.ar13_ar14 import (
    CAPSTONE_CANONICAL_REGIONS,
    CAPSTONE_ROLE_ATLASES as CAPSTONE_ATLASES,
    NATIVE_AR9_CANONICAL_SHA256,
    author_capstone_canonical, author_capstone_private,
)
from rank_effect_v2.capstone_builder import (
    _PRIVATE_SPECS as CAPSTONE_SPECS,
)
from rank_effect_v2.ar11_bridge import (
    HALO_FACES, HALO_SCALE, HALO_VERTICES, WING_CHANGED_VERTICES,
    WING_COMPONENTS, WING_FACES, WING_VERTICES,
    Ar11HaloTransform, Ar11WingTransform, validate_ar11_halo, validate_ar11_wings,
)
from rank_effect_v2.ar11_outer_material import author_ar11_outer_material
from rank_effect_v2.ar12_ar4 import (
    AR4_ANIMATION_TRACKS, AR4_DONOR_FACES, AR4_DONOR_SHA256,
    AR4_DONOR_VERTICES,
)
from rank_effect_v2.ar5_animated_flame import (
    AR5_ANIMATED_ANIMATION_TRACKS, AR5_ANIMATED_DONOR_SHA256,
    AR5_ANIMATED_FACES, AR5_ANIMATED_MATERIAL_FACE_COUNTS,
    AR5_ANIMATED_UV_BOUNDS, AR5_ANIMATED_VERTICES,
)
from rank_effect_v2.atlas import Region, recolour_luminance
from rank_effect_v2.capstone_private_flame import author_capstone_private_flame
from rank_effect_v2.models import audit_model
from erebus_lion.model_codec import expand_xof_mszip
from xmodel_sculpt.binary_x import parse_tokens
from xmodel_sculpt.mesh import discover_meshes
from xmodel_sculpt.sculpt import sculpt_xof_mszip


EXPECTED_PALETTES = {
    10: ("626970", "AAB2B9", "F5F7F8"), 11: ("244A70", "5D9FD0", "A9D7EA"),
    12: ("092E68", "1768B8", "43A1DE"), 13: ("200207", "700B1A", "BE2335"),
    14: ("3A3422", "B7A66D", "F8EBC5"),
}

EXPECTED_AR11_ROLE_ATLASES = {
    "animated-core": (("182F49", "386B91", "72ACC5"), .94, 200),
    "animated-butterfly": (("244A70", "5D9FD0", "A9D7EA"), 1., 220),
    "animated-rune": (("276D87", "63C4DE", "BFEFFF"), 1.08, 230),
    "outer-wing": (("0D294B", "285F94", "6F9FC7"), .95, 208),
}

EXPECTED_CAPSTONE_ROLE_ATLASES = {
    13: {
        "animated-core": (("1A0206", "620916", "B01D30"), .5, 150),
        "animated-rune": (("120104", "4D0711", "8F1525"), .51, 155),
        "animated-butterfly": (("200207", "700B1A", "BE2335"), .52, 160),
        "outer-wing": (("2A0204", "8E0913", "DA1D28"), .58, 180),
        "animated-flame": (("5A2800", "E6A000", "FFF080"), .86, 238),
    }, 14: {
        "animated-core": (("29261C", "8F835A", "E5D7A8"), .94, 218),
        "animated-rune": (("24221B", "746B4C", "C9BB8F"), .96, 220),
        "animated-butterfly": (("3A3422", "B7A66D", "F8EBC5"), 1., 232),
        "outer-wing": (("55481F", "DDC371", "FFFBE6"), 1.06, 245),
        "animated-flame": (("071F5B", "178ED6", "BDEFFF"), 1.03, 245),
    },
}

EXPECTED_AR9_SLOTS = {
    0: (116, 100, (100,), 1, "558628f87eb52aff06c0113714c8fdf20c3104581c4519d3c8e9aad8eba34982"),
    1: (976, 848, (0, 848), 1, "82bb71925b3a0e5589eb19df3b35de2407ee6139387a8a708cd8c0fdd54669cd"),
    2: (136, 128, (128,), 1, "b63a5fdc4e1759b63d60641bb9a7bece52980c551e8ea075ad1d81f1b1fb673c"),
}

def _source_mesh(data: bytes, label: str):
    expanded = expand_xof_mszip(data, label)
    meshes = discover_meshes(expanded, parse_tokens(expanded))
    assert len(meshes) == 1
    return meshes[0]


def _pixels(value: bytes):
    width, height = struct.unpack_from("<HH", value, 12)
    bytes_per_pixel = value[16] // 8
    assert value[2] == 2 and (width, height) == (64, 64)
    assert bytes_per_pixel in (3, 4)
    result = []
    for offset in range(18, 18 + width * height * bytes_per_pixel, bytes_per_pixel):
        blue, green, red = value[offset : offset + 3]
        alpha = value[offset + 3] if bytes_per_pixel == 4 else 255
        result.append((red, green, blue, alpha))
    return tuple(result)


def _luma(pixel):
    return 0.2126 * pixel[0] + 0.7152 * pixel[1] + 0.0722 * pixel[2]


def _mean_rgb(pixels, indices):
    return tuple(
        sum(pixels[index][channel] for index in indices) / len(indices)
        for channel in range(3)
    )


def _palette_hex(palette):
    return tuple(
        "".join(f"{round(channel * 255):02X}" for channel in colour)
        for colour in (palette.shadow, palette.middle, palette.highlight)
    )


def _atlas_specs(atlases):
    return {
        role: (_palette_hex(atlas.palette), atlas.luma_gain, atlas.maximum_channel)
        for role, atlas in atlases.items()
    }


def _render(source, rank, *, additive, preserve_luma):
    palette = design_for_rank(rank).palette
    return recolour_luminance(
        source,
        Region(*palette.region),
        palette.shadow,
        palette.middle,
        palette.highlight,
        strength=palette.strength,
        additive_glow=additive,
        preserve_luma=preserve_luma,
    )


def _verify_ar10_rendering(client):
    expected_counts = {24: 2157, 32: 2402}
    for asset_root in ASSET_ROOTS:
        directory = client / asset_root / "effect"
        sources = [
            *(directory / f"{gender}_body_effect_0009.gwo" for gender in GENDERS),
            directory / "female_body_effect_0010.tga",
            directory / "female_body_effect_0011.tga",
            directory / "11.tga",
        ]
        for path in sources:
            source = path.read_bytes()
            result = _render(source, 10, additive=False, preserve_luma=True)
            before, after = _pixels(source), _pixels(result.encoded)
            changed = {
                index
                for index, (left, right) in enumerate(zip(before, after))
                if left[:3] != right[:3]
            }
            assert result.changed_pixels == len(changed) == expected_counts[source[16]]
            assert result.alpha_changes == result.outside_region_changes == 0
            assert all(before[index][3] == after[index][3] for index in changed)
            assert all(max(after[index][:3]) < 255 for index in changed)
            changed_rows = {index // 64 for index in changed}
            assert min(changed_rows) < 16 and max(changed_rows) > 48
            before_luma = sum(_luma(before[index]) for index in changed) / len(changed)
            after_luma = sum(_luma(after[index]) for index in changed) / len(changed)
            assert abs(before_luma - after_luma) < 0.1
            mean = _mean_rgb(after, changed)
            assert max(mean) - min(mean) < 12.0


def _verify_ar11_rendering(client):
    source_names = {
        "animated-core": "female_body_effect_0010.tga",
        "animated-butterfly": "female_body_effect_0011.tga",
        "animated-rune": "female_body_effect_0010.tga",
        "outer-wing": "female_body_effect_0011.tga",
    }
    expected_counts = {24: 2157, 32: 2402}
    for asset_root in ASSET_ROOTS:
        directory = client / asset_root / "effect"
        actual_gains = {}
        rendered = {}
        for role, source_name in source_names.items():
            atlas = AR11_ATLASES[role]
            palette = atlas.palette
            source = (directory / source_name).read_bytes()
            result = recolour_luminance(
                source,
                Region(*palette.region),
                palette.shadow,
                palette.middle,
                palette.highlight,
                strength=palette.strength,
                preserve_luma=True,
                luma_gain=atlas.luma_gain,
                maximum_channel=atlas.maximum_channel,
            )
            before, after = _pixels(source), _pixels(result.encoded)
            changed = {
                index
                for index, (left, right) in enumerate(zip(before, after))
                if left[:3] != right[:3]
            }
            eligible = {
                index
                for index, pixel in enumerate(before)
                if pixel[3] > 0 and max(pixel[:3]) / 255.0 > 0.015
            }
            assert changed == eligible
            assert len(changed) == expected_counts[source[16]]
            assert result.changed_pixels == len(changed)
            assert result.alpha_changes == result.outside_region_changes == 0
            assert {index // 64 for index in changed} == set(range(64))
            assert all(before[index][3] == after[index][3] for index in range(4096))
            assert max(max(after[index][:3]) for index in changed) <= atlas.maximum_channel
            payload_end = 18 + 4096 * (source[16] // 8)
            assert result.encoded[payload_end:] == source[payload_end:]

            source_luma = sum(_luma(before[index]) for index in changed)
            output_luma = sum(_luma(after[index]) for index in changed)
            actual_gains[role] = output_luma / source_luma
            assert math.isclose(
                actual_gains[role], atlas.luma_gain, rel_tol=0.0, abs_tol=0.002
            )
            red, green, blue = _mean_rgb(after, changed)
            assert blue > green > red
            rendered[role] = result.encoded

        assert (
            actual_gains["animated-core"]
            < actual_gains["animated-butterfly"]
            < actual_gains["animated-rune"]
        )
        assert len(set(rendered.values())) == len(AR11_ATLASES)


def _verify_capstone_rendering(client):
    donors = {
        "animated-core": "female_body_effect_0010.tga",
        "animated-rune": "female_body_effect_0010.tga",
        "animated-butterfly": "female_body_effect_0011.tga",
        "outer-wing": "female_body_effect_0011.tga",
        "animated-flame": "female_body_effect_0005.gwo",
    }
    for asset_root in ASSET_ROOTS:
        directory = client / asset_root / "effect"
        for rank, roles in CAPSTONE_ATLASES.items():
            for gender in GENDERS:
                source = (directory / f"{gender}_body_effect_0009.gwo").read_bytes()
                assert hashlib.sha256(source).hexdigest() == (
                    NATIVE_AR9_CANONICAL_SHA256
                )
                authored = author_capstone_canonical(source, rank)
                assert authored.active_pixels == authored.recolour.changed_pixels == 2157
                assert tuple(segment.role for segment in authored.segments) == tuple(
                    role for role, _region in CAPSTONE_CANONICAL_REGIONS
                )
                assert tuple(segment.active_pixels for segment in authored.segments) == (
                    760, 358, 1039,
                )
                assert authored.recolour.encoded[:18] == source[:18]
                assert len(authored.recolour.encoded) == len(source)

            for role, atlas in roles.items():
                source = (directory / donors[role]).read_bytes()
                if role == "animated-flame":
                    authored = author_capstone_private_flame(
                        source, rank=rank, design=atlas
                    )
                    metadata = authored.contract_metadata()
                    assert authored.recolour.changed_pixels == 255
                    assert authored.sampled_pixels == 396
                    assert authored.outside_footprint_changes == authored.alpha_changes == 0
                    assert metadata["texture_source"] == "native-ar5-canonical-gwo"
                    assert metadata["sampling"]["method"] == "native-uv-no-remap"
                    continue
                authored = author_capstone_private(source, rank, role)
                assert authored.active_pixels == authored.recolour.changed_pixels == 2402
                assert authored.recolour.alpha_changes == 0
                active = [
                    index for index, pixel in enumerate(_pixels(source))
                    if pixel[3] > 0 and max(pixel[:3]) / 255.0 > 0.015
                ]
                output = _pixels(authored.recolour.encoded)
                assert max(max(output[index][:3]) for index in active) <= (
                    atlas.maximum_channel
                )


def _verify_ar9_structure(client):
    reviewed = 0
    for asset_root in ASSET_ROOTS:
        for gender in GENDERS:
            for slot, expected in EXPECTED_AR9_SLOTS.items():
                path = client / asset_root / "effect" / (
                    f"{gender}_body_effect_{CLONE_RANK:04d}_{slot}.jcs"
                )
                source = path.read_bytes()
                audit = audit_model(source, str(path))
                vertices, faces, materials, animations, expected_hash = expected
                assert (audit.vertices, audit.faces) == (vertices, faces)
                assert audit.material_face_counts == materials
                assert audit.animation_keys == animations
                assert fingerprint(source, str(path)) == expected_hash
                reviewed += 1
    assert reviewed == len(ASSET_ROOTS) * len(GENDERS) * 3


def _verify_ar11_geometry(client):
    assert (HALO_VERTICES, HALO_FACES, HALO_SCALE) == (116, 100, 1.05)
    assert (WING_VERTICES, WING_FACES, WING_COMPONENTS) == (976, 848, 64)

    reviewed = 0
    for asset_root in ASSET_ROOTS:
        for gender in GENDERS:
            stem = f"{gender}_body_effect_{CLONE_RANK:04d}"
            directory = client / asset_root / "effect"

            halo_path = directory / f"{stem}_0.jcs"
            halo_source = halo_path.read_bytes()
            halo_mesh = _source_mesh(halo_source, str(halo_path))
            halo = sculpt_xof_mszip(
                halo_source, Ar11HaloTransform(), label=f"{halo_path}:AR11"
            )
            assert halo.changed_vertices == HALO_VERTICES
            halo_output = _source_mesh(halo.encoded, f"{halo_path}:AR11")
            validate_ar11_halo(halo_mesh, tuple(halo_output.vertices))
            assert all(
                math.isclose(before[2], after[2], rel_tol=0.0, abs_tol=1e-7)
                for before, after in zip(halo_mesh.vertices, halo_output.vertices)
            )

            wing_path = directory / f"{stem}_1.jcs"
            wing_source = wing_path.read_bytes()
            wing_mesh = _source_mesh(wing_source, str(wing_path))
            material = author_ar11_outer_material(
                wing_source, label=f"{wing_path}:outer-material"
            )
            assert (material.source_material_face_counts,
                    material.output_material_face_counts, material.changed_faces
                    ) == ((0, 848), (256, 592), 256)
            assert (material.inner_faces, material.shoulder_faces,
                    material.outer_faces) == (448, 144, 256)
            material_mesh = _source_mesh(material.encoded, f"{wing_path}:material-output")
            assert (material_mesh.vertices, material_mesh.faces) == (
                wing_mesh.vertices, wing_mesh.faces)
            wings = sculpt_xof_mszip(
                material.encoded, Ar11WingTransform(), label=f"{wing_path}:AR11"
            )
            assert wings.changed_vertices == WING_CHANGED_VERTICES
            wing_output = _source_mesh(wings.encoded, f"{wing_path}:AR11")
            metrics = validate_ar11_wings(wing_mesh, tuple(wing_output.vertices))
            assert metrics.lateral_centroid_drift <= 1e-7

            rune_path = directory / f"{stem}_2.jcs"
            rune = rune_path.read_bytes()
            assert fingerprint(rune, str(rune_path)) == EXPECTED_AR9_SLOTS[2][4]
            assert audit_model(rune, str(rune_path)).animation_keys == 1
            reviewed += 1
    assert reviewed == len(ASSET_ROOTS) * len(GENDERS)


def _verify_ar4_orbit_donors(client):
    for asset_root in ASSET_ROOTS:
        for gender in GENDERS:
            path = client / asset_root / "effect" / (
                f"{gender}_body_effect_{ORBIT_RANK:04d}_0.jcs"
            )
            source = path.read_bytes()
            audit = audit_model(source, str(path))
            assert hashlib.sha256(source).hexdigest() == AR4_DONOR_SHA256[gender]
            assert (audit.vertices, audit.faces, audit.animation_keys) == (
                AR4_DONOR_VERTICES, AR4_DONOR_FACES, AR4_ANIMATION_TRACKS,
            )


def _verify_ar5_animated_flame_donors(client):
    for asset_root in ASSET_ROOTS:
        for gender in GENDERS:
            path = client / asset_root / "effect" / f"{gender}_body_effect_0005_2.jcs"
            source = path.read_bytes()
            audit = audit_model(source, str(path))
            assert hashlib.sha256(source).hexdigest() == AR5_ANIMATED_DONOR_SHA256[gender]
            actual = (audit.vertices, audit.faces, audit.material_face_counts,
                      audit.animation_keys, audit.uv_bounds)
            expected = (AR5_ANIMATED_VERTICES, AR5_ANIMATED_FACES,
                        AR5_ANIMATED_MATERIAL_FACE_COUNTS,
                        AR5_ANIMATED_ANIMATION_TRACKS, AR5_ANIMATED_UV_BOUNDS)
            assert actual == expected
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--client-root", type=Path, required=True)
    client = parser.parse_args().client_root.resolve()
    assert client.is_dir()

    validate_design_catalogue()
    assert (CLONE_RANK, ORBIT_RANK) == (9, 4)
    assert tuple(DESIGNS) == ARMOR_RANKS == (10, 11, 12, 13, 14)
    assert AR9_RANKS == (10, 11, 12)
    assert CAPSTONE_RANKS == (13, 14)
    assert all(source_rank_for(rank) == 9 for rank in AR9_RANKS)
    assert all(slot_roles_for_rank(rank) == CLONE_SLOT_ROLES for rank in AR9_RANKS)
    assert dict(CAPSTONE_SLOT_ROLES) == {
        13: ("animated-rune", "animated-butterfly", "animated-flame"),
        14: ("animated-rune", "animated-butterfly", "animated-flame"),
    }
    assert CAPSTONE_SPECS == (
        ("animated-flame", "female_body_effect_0005.gwo", "flame", 5),
        ("animated-butterfly", "female_body_effect_0011.tga", "wings", 9),
        ("outer-wing", "female_body_effect_0011.tga", "outer_wings", 9),
        ("animated-rune", "female_body_effect_0010.tga", "orbit", 9),
    )
    expected_sources = {13: (4, 9, 5), 14: (4, 9, 5)}
    for rank, sources in expected_sources.items():
        assert tuple(source_rank_for_slot(rank, slot) for slot in range(3)) == sources
        assert source_rank_for(rank) == sources[0]

    assert {
        rank: _palette_hex(design.palette)
        for rank, design in DESIGNS.items()
    } == EXPECTED_PALETTES
    assert _atlas_specs(AR11_ATLASES) == EXPECTED_AR11_ROLE_ATLASES
    assert {rank: _atlas_specs(roles) for rank, roles
            in CAPSTONE_ATLASES.items()} == EXPECTED_CAPSTONE_ROLE_ATLASES
    atlases = list(AR11_ATLASES.values())
    atlases += [atlas for roles in CAPSTONE_ATLASES.values()
                for atlas in roles.values()]
    assert all(atlas.palette.region == (0., 1., 0., 1.) for atlas in atlases)
    assert all(design.palette.region == (0., 1., 0., 1.)
               and design.palette.strength == 1. for design in DESIGNS.values())

    _verify_ar10_rendering(client)
    _verify_ar11_rendering(client)
    _verify_capstone_rendering(client)
    _verify_ar9_structure(client)
    _verify_ar11_geometry(client)
    _verify_ar4_orbit_donors(client)
    _verify_ar5_animated_flame_donors(client)

    assert Path(__file__).stat().st_size < 20 * 1024
    print("PASS armor")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
