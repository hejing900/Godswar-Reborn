"""Build AR10 and coordinate focused AR11-AR14 authoring."""

from __future__ import annotations

from pathlib import Path

from rank_effect_packages.catalog import ASSET_ROOTS, GENDERS
from rank_effect_packages.errors import RankEffectError
from rank_effect_packages.formats import structural_fingerprint

from .armor_ranks import (
    ARMOR_CLONE_SOURCE_RANK,
    ARMOR_RANK_DESIGNS,
    CAPSTONE_ARMOR_RANKS,
    AtlasPalette,
    slot_roles_for_rank,
)
from .ar11_builder import build_ar11_bridge
from .ar12_builder import build_ar12_aether
from .armor_contracts import record_atlas as _record_atlas
from .armor_contracts import record_model as _record_model
from .atlas import RecolourResult, Region, recolour_luminance
from .capstone_builder import build_capstone
from .package_io import PackageShard, regular


def _recolour(
    source: bytes,
    rank: int,
    *,
    additive_glow: bool,
    preserve_luma: bool,
    palette: AtlasPalette | None = None,
    luma_gain: float = 1.0,
    maximum_channel: int = 255,
) -> RecolourResult:
    selected = palette or ARMOR_RANK_DESIGNS[rank].palette
    result = recolour_luminance(
        source,
        Region(*selected.region),
        selected.shadow,
        selected.middle,
        selected.highlight,
        strength=selected.strength,
        additive_glow=additive_glow,
        preserve_luma=preserve_luma,
        luma_gain=luma_gain,
        maximum_channel=maximum_channel,
    )
    if (
        result.changed_pixels <= 0
        or result.alpha_changes != 0
        or result.outside_region_changes != 0
    ):
        raise RankEffectError(f"AR{rank} atlas did not preserve alpha/detail")
    return result


def _build_ar9_clone(
    client: Path,
    shard: PackageShard,
    asset_root: str,
    contracts: list[dict[str, object]],
    rewrite,
) -> None:
    rank = 10
    directory = client / asset_root / "effect"
    mapping: dict[bytes, bytes] = {}
    private: list[Path] = []
    bindings = (
        ("animated-core", b"female_body_effect_0010.tga", "ar9_core"),
        ("animated-butterfly", b"female_body_effect_0011.tga", "ar9_butterfly"),
        ("declared-unused", b"11.tga", "ar9_declared"),
    )
    for role, reference, suffix in bindings:
        source_path = directory / reference.decode("ascii")
        source = regular(source_path, f"native AR9 {role} atlas")
        result = _recolour(
            source, rank, additive_glow=False, preserve_luma=True
        )
        target = Path(asset_root) / "effect" / (
            f"reborn_body_effect_{rank:04d}_v2_{suffix}.tga"
        )
        shard.add(target, result.encoded)
        mapping[reference] = target.name.encode("ascii")
        private.append(target)
        _record_atlas(
            contracts,
            rank=rank,
            asset_root=asset_root,
            role=role,
            source_rank=ARMOR_CLONE_SOURCE_RANK,
            source=source,
            result=result,
            target=target,
            additive_glow=False,
            preserve_luma=True,
        )

    for gender in GENDERS:
        source_stem = f"{gender}_body_effect_{ARMOR_CLONE_SOURCE_RANK:04d}"
        target_stem = f"{gender}_body_effect_{rank:04d}"
        canonical_source_path = directory / f"{source_stem}.gwo"
        canonical_source = regular(canonical_source_path, "native AR9 canonical atlas")
        canonical_result = _recolour(
            canonical_source, rank, additive_glow=False, preserve_luma=True
        )
        canonical = Path(asset_root) / "effect" / f"{target_stem}.gwo"
        shard.add(canonical, canonical_result.encoded)
        _record_atlas(
            contracts,
            rank=rank,
            asset_root=asset_root,
            gender=gender,
            role="canonical",
            source_rank=ARMOR_CLONE_SOURCE_RANK,
            source=canonical_source,
            result=canonical_result,
            target=canonical,
            additive_glow=False,
            preserve_luma=True,
        )

        models: list[Path] = []
        for slot, role in enumerate(slot_roles_for_rank(rank)):
            source_path = directory / f"{source_stem}_{slot}.jcs"
            source = regular(source_path, "protected native AR9 JCS clone source")
            output = rewrite(source, mapping, str(source_path))
            target = Path(asset_root) / "effect" / f"{target_stem}_{slot}.jcs"
            if structural_fingerprint(source, str(source_path)) != structural_fingerprint(
                output, str(target)
            ):
                raise RankEffectError(f"AR10 clone changed protected AR9 structure: {target}")
            shard.add(target, output)
            models.append(target)
            _record_model(
                contracts,
                rank=rank,
                asset_root=asset_root,
                gender=gender,
                slot=slot,
                role=role,
                source_rank=ARMOR_CLONE_SOURCE_RANK,
                source_path=source_path,
                target=target,
                source=source,
                output=output,
                sculpted=False,
                changed_vertices=0,
            )
        shard.effects.append(
            {
                "kind": "armor",
                "rank": rank,
                "asset_root": asset_root,
                "gender": gender,
                "class": None,
                "models": [path.as_posix() for path in models],
                "canonical_texture": canonical.as_posix(),
                "private_textures": [path.as_posix() for path in private],
            }
        )


def build_armor_shards(
    client: Path,
    stage: Path,
    contracts: list[dict[str, object]],
    rewrite,
) -> list[PackageShard]:
    """Create one bounded shard per rank without mutating protected donors."""

    shards = {
        rank: PackageShard(stage, f"armor-{rank:02d}-role-aware")
        for rank in ARMOR_RANK_DESIGNS
    }
    for asset_root in ASSET_ROOTS:
        _build_ar9_clone(client, shards[10], asset_root, contracts, rewrite)
        build_ar11_bridge(client, shards[11], asset_root, contracts, rewrite)
        build_ar12_aether(client, shards[12], asset_root, contracts, rewrite)
        for rank in CAPSTONE_ARMOR_RANKS:
            build_capstone(client, shards[rank], asset_root, rank, contracts, rewrite)
    return list(shards.values())
