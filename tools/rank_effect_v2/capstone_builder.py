"""Build AR4-orbit/AR9-wing/AR5-animated-flame capstones."""

from __future__ import annotations

from pathlib import Path

from erebus_lion.model_codec import expand_xof_mszip
from rank_effect_packages.catalog import GENDERS
from rank_effect_packages.errors import RankEffectError
from rank_effect_packages.formats import structural_fingerprint
from xmodel_sculpt.binary_x import parse_tokens
from xmodel_sculpt.mesh import discover_meshes
from xmodel_sculpt.sculpt import sculpt_xof_mszip

from .ar11_bridge import WING_CHANGED_VERTICES
from .ar11_outer_material import author_ar11_outer_material
from .ar12_aether import (
    AR12_WING_LATERAL_EXPANSION,
    AR12_WING_SHOULDER_WEIGHT,
    AR12_WING_VERTICAL_LIFT,
    Ar12WingTransform,
    validate_ar12_wings,
)
from .ar12_ar4 import AR4_STRUCTURAL_SHA256, author_ar12_ar4
from .ar13_ar14 import (
    CAPSTONE_CANONICAL_REGIONS,
    CAPSTONE_FLAME_SCALE,
    CAPSTONE_ROLE_ATLASES,
    author_capstone_canonical,
    author_capstone_private,
)
from .ar5_animated_flame import author_ar5_animated_flame
from .armor_contracts import record_atlas, record_model
from .armor_ranks import (
    ARMOR_CLONE_SOURCE_RANK,
    ARMOR_ORBIT_SOURCE_RANK,
    slot_roles_for_rank,
    source_rank_for_slot,
)
from .package_io import PackageShard, regular
from .models import audit_model
from .atlas import RecolourResult
from .capstone_flame_atlas import author_capstone_flame_atlas
from .capstone_private_flame import author_capstone_private_flame


_PRIVATE_SPECS = (
    ("animated-flame", "female_body_effect_0005.gwo", "flame", 5),
    ("animated-butterfly", "female_body_effect_0011.tga", "wings", 9),
    ("outer-wing", "female_body_effect_0011.tga", "outer_wings", 9),
    ("animated-rune", "female_body_effect_0010.tga", "orbit", 9),
)
_AR12_WING_STRUCTURE = (
    "2abdbcb19b1c6e44632f884f474788163518abe42b810a640b118640f223c4a8"
)


def _single_mesh(encoded: bytes, label: str):
    expanded = expand_xof_mszip(encoded, label)
    meshes = discover_meshes(expanded, parse_tokens(expanded))
    if len(meshes) != 1:
        raise RankEffectError(f"Capstone JCS must contain one Mesh: {label}")
    return meshes[0]


def _binding_metadata() -> dict[str, object]:
    return {
        "runtime_binding": "native-uv-consistent-canonical-and-jcs-material",
        "canonical_family": "native-ar9-with-native-uv-ar5-animated-flame-crop",
        "native_uv_disjoint_packing": True,
        "ar5_flame_uv_remapped": False,
        "canonical_flame_crop_packed": True,
        "declared_flame_texture_crop_packed": True,
        "flame_footprints_equivalent": True,
        "native_ar5_canonical_crop_source": True,
        "native_ar5_canonical_installed_wholesale": False,
    }


def _changed_canonical_pixels(before: bytes, after: bytes) -> int:
    """Count final BGR mutations without double-counting the packed crop."""

    payload_end = 18 + 64 * 64 * 3
    if (
        len(before) != len(after)
        or before[:18] != after[:18]
        or before[payload_end:] != after[payload_end:]
    ):
        raise RankEffectError("Capstone canonical layout changed while composing")
    return sum(
        before[offset : offset + 3] != after[offset : offset + 3]
        for offset in range(18, payload_end, 3)
    )


def _private_atlases(
    client: Path,
    shard: PackageShard,
    asset_root: str,
    rank: int,
    contracts: list[dict[str, object]],
) -> dict[str, Path]:
    directory = client / asset_root / "effect"
    result: dict[str, Path] = {}
    for role, source_name, suffix, source_rank in _PRIVATE_SPECS:
        source = regular(directory / source_name, f"native {role} atlas")
        design = CAPSTONE_ROLE_ATLASES[rank][role]
        authored = (
            author_capstone_private_flame(
                source,
                rank=rank,
                design=design,
            )
            if role == "animated-flame"
            else author_capstone_private(source, rank, role)
        )
        target = Path(asset_root) / "effect" / (
            f"reborn_body_effect_{rank:04d}_v2_{suffix}.tga"
        )
        shard.add(target, authored.recolour.encoded)
        result[role] = target
        entry = record_atlas(
            contracts,
            rank=rank,
            asset_root=asset_root,
            role=role,
            source_rank=source_rank,
            source=source,
            result=authored.recolour,
            target=target,
            additive_glow=False,
            preserve_luma=True,
            palette=design.palette,
            luma_gain=design.luma_gain,
            maximum_channel=design.maximum_channel,
        )
        entry.update(authored.contract_metadata())
        entry.update(_binding_metadata())
        entry["atlas_authority"] = "declared-jcs-material-tga"
        entry["geometry_family"] = "non-authoritative-material-metadata"
    return result


def _canonical_atlas(
    client: Path,
    shard: PackageShard,
    asset_root: str,
    gender: str,
    rank: int,
    contracts: list[dict[str, object]],
) -> Path:
    directory = client / asset_root / "effect"
    source_path = directory / (
        f"{gender}_body_effect_{ARMOR_CLONE_SOURCE_RANK:04d}.gwo"
    )
    source = regular(source_path, "native AR9 canonical atlas")
    segmented = author_capstone_canonical(source, rank)
    flame_source_path = directory / f"{gender}_body_effect_0005.gwo"
    flame_source = regular(
        flame_source_path, "native AR5 animated-flame canonical crop source"
    )
    packed = author_capstone_flame_atlas(
        segmented.recolour.encoded,
        flame_source,
        rank=rank,
        design=CAPSTONE_ROLE_ATLASES[rank]["animated-flame"],
    )
    cumulative = RecolourResult(
        packed.encoded, _changed_canonical_pixels(source, packed.encoded), 0, 0
    )
    target = Path(asset_root) / "effect" / f"{gender}_body_effect_{rank:04d}.gwo"
    shard.add(target, packed.encoded)
    entry = record_atlas(
        contracts,
        rank=rank,
        asset_root=asset_root,
        gender=gender,
        role="canonical-composite",
        source_rank=ARMOR_CLONE_SOURCE_RANK,
        source=source,
        result=cumulative,
        target=target,
        additive_glow=False,
        preserve_luma=True,
    )
    entry.update(segmented.contract_metadata())
    entry["segmented_ar9_changed_pixels"] = segmented.recolour.changed_pixels
    entry["flame_crop_target_changed_pixels"] = packed.target_changed_pixels
    entry.update(packed.contract_metadata())
    entry.update(_binding_metadata())
    entry["changed_pixels"] = cumulative.changed_pixels
    entry["canonical_flame_native_uv_crop_packed"] = True
    entry["native_ar5_crop_source"] = flame_source_path.name
    entry["canonical_layout"] = {
        "width": 64,
        "height": 64,
        "bits_per_pixel": 24,
        "header_preserved": True,
        "footer_preserved": True,
        "native_ar9_mask_preserved_outside_packed_flame": True,
        "regions": [
            {
                "role": role,
                "u": [region.minimum_u, region.maximum_u],
                "v": [region.minimum_v, region.maximum_v],
            }
            for role, region in CAPSTONE_CANONICAL_REGIONS
        ],
    }
    return target


def _author_wings(source: bytes, label: str):
    material = author_ar11_outer_material(source, label=label)
    authored = sculpt_xof_mszip(
        material.encoded, Ar12WingTransform(), label=f"{label}:AR12"
    )
    if authored.changed_vertices != WING_CHANGED_VERTICES:
        raise RankEffectError("Capstone wings missed approved AR12 vertices")
    source_mesh = _single_mesh(source, f"{label}:source")
    output_mesh = _single_mesh(authored.encoded, f"{label}:output")
    validate_ar12_wings(source_mesh, tuple(output_mesh.vertices))
    audit = audit_model(authored.encoded, f"{label}:output")
    if (
        structural_fingerprint(authored.encoded, label) != _AR12_WING_STRUCTURE
        or audit.material_face_counts != (256, 592)
    ):
        raise RankEffectError("Capstone wings differ from approved AR12 structure")
    return authored.encoded, authored.changed_vertices, material


def build_capstone(
    client: Path,
    shard: PackageShard,
    asset_root: str,
    rank: int,
    contracts: list[dict[str, object]],
    rewrite,
) -> None:
    if rank not in (13, 14):
        raise RankEffectError(f"Capstone builder only supports AR13/AR14, got AR{rank}")
    if tuple(source_rank_for_slot(rank, slot) for slot in range(3)) != (4, 9, 5):
        raise RankEffectError(f"AR{rank} source route is not AR4/AR9/AR5")

    directory = client / asset_root / "effect"
    private = _private_atlases(client, shard, asset_root, rank, contracts)
    roles = slot_roles_for_rank(rank)
    if roles != ("animated-rune", "animated-butterfly", "animated-flame"):
        raise RankEffectError(f"AR{rank} slot roles are not orbit/butterfly/flame")

    for gender in GENDERS:
        canonical = _canonical_atlas(
            client, shard, asset_root, gender, rank, contracts
        )
        target_stem = f"{gender}_body_effect_{rank:04d}"
        ar9_stem = f"{gender}_body_effect_{ARMOR_CLONE_SOURCE_RANK:04d}"
        models: list[Path] = []
        for slot, role in enumerate(roles):
            source_slot = slot
            ar4_completion = None
            flame = None
            outer_material = None
            if slot == 0:
                source_rank = ARMOR_ORBIT_SOURCE_RANK
                source_path = directory / f"{gender}_body_effect_0004_0.jcs"
                source = regular(source_path, f"AR{rank} native AR4 orbit donor")
                subset_path = directory / f"{ar9_stem}_2.jcs"
                subset = regular(subset_path, "native AR9 orbit subset")
                ar4_completion = author_ar12_ar4(
                    subset,
                    source,
                    gender=gender,
                    main_texture=private[role].name.encode("ascii"),
                    label=str(source_path),
                )
                output = ar4_completion.encoded
                changed_vertices = 0
            elif slot == 1:
                source_rank = ARMOR_CLONE_SOURCE_RANK
                source_path = directory / f"{ar9_stem}_{source_slot}.jcs"
                source = regular(source_path, f"AR{rank} native AR9 {role} donor")
                authored, changed_vertices, outer_material = _author_wings(
                    source, str(source_path)
                )
                mapping = {
                    b"female_body_effect_0011.tga": private[role].name.encode("ascii"),
                    b"11.tga": private["outer-wing"].name.encode("ascii"),
                }
                output = rewrite(authored, mapping, str(source_path))
            else:
                source_rank = 5
                source_path = directory / f"{gender}_body_effect_0005_2.jcs"
                source = regular(
                    source_path, f"AR{rank} native AR5 animated-flame donor"
                )
                flame = author_ar5_animated_flame(
                    source,
                    gender=gender,
                    target_texture=private[role].name.encode("ascii"),
                    model_scale=CAPSTONE_FLAME_SCALE[rank],
                    label=str(source_path),
                )
                output = flame.encoded
                changed_vertices = flame.changed_vertices

            target = Path(asset_root) / "effect" / f"{target_stem}_{slot}.jcs"
            shard.add(target, output)
            models.append(target)
            contract = record_model(
                contracts,
                rank=rank,
                asset_root=asset_root,
                gender=gender,
                slot=slot,
                role=role,
                source_rank=source_rank,
                source_path=source_path,
                target=target,
                source=source,
                output=output,
                sculpted=changed_vertices > 0,
                changed_vertices=changed_vertices,
            )
            contract["source_slot"] = source_slot
            contract.update(_binding_metadata())
            if slot == 0:
                assert ar4_completion is not None
                contract["geometry_family"] = "exact-native-ar4-orbit-only"
                contract["source_route"] = "native-ar4-slot0-orbit-only"
                contract["output_structural_contract"] = AR4_STRUCTURAL_SHA256[gender]
                contract.update(ar4_completion.contract_metadata())
                if contract["output_structural_sha256"] != AR4_STRUCTURAL_SHA256[gender]:
                    raise RankEffectError(f"AR{rank} changed native AR4 orbit structure")
            elif slot == 1:
                assert outer_material is not None
                contract["geometry_family"] = "exact-approved-ar12-butterfly"
                contract["approved_ar12_structural_sha256"] = _AR12_WING_STRUCTURE
                contract["wing_profile"] = {
                    "vertical_lift": AR12_WING_VERTICAL_LIFT,
                    "lateral_expansion": AR12_WING_LATERAL_EXPANSION,
                    "shoulder_weight": AR12_WING_SHOULDER_WEIGHT,
                }
                contract.update(outer_material.contract_metadata())
            else:
                assert flame is not None
                contract.update(flame.contract_metadata())
                contract["source_route"] = (
                    "native-ar5-slot2-animated-flame-native-uv"
                )
                contract["vertical_offset_hack"] = False
                contract["frame_transform_hack"] = False

        source_routes = [
            {
                "rank": 4,
                "slot": 0,
                "role": roles[0],
                "route": "exact-native-ar4-orbit-only",
            },
            {"rank": 9, "slot": 1, "role": roles[1]},
            {
                "rank": 5,
                "slot": 2,
                "role": roles[2],
                "route": "native-ar5-slot2-animated-flame-native-uv",
            },
        ]
        shard.effects.append(
            {
                "kind": "armor",
                "rank": rank,
                "asset_root": asset_root,
                "gender": gender,
                "class": None,
                "models": [path.as_posix() for path in models],
                "canonical_texture": canonical.as_posix(),
                "private_textures": [
                    private[role].as_posix()
                    for role, _source, _suffix, _source_rank in _PRIVATE_SPECS
                ],
                "private_texture_count": 4,
                "source_routes": source_routes,
                **_binding_metadata(),
                "native_ar5_geometry_present": True,
                "native_ar5_gwo_used": True,
                "native_ar5_gwo_used_as_crop_source": True,
                "native_ar5_gwo_installed_wholesale": False,
            }
        )


__all__ = ["build_capstone"]
