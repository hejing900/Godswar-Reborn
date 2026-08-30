"""Prove a capstone release differs from its reference only by flame colour."""

from __future__ import annotations

import argparse
from pathlib import Path

from rank_effect_packages.catalog import ASSET_ROOTS, GENDERS
from rank_effect_packages.formats import validate_tga_texture
from rank_effect_packages.installer import installation_assets
from rank_effect_packages.package import LoadedPackage, load_package


RANKS = (13, 14)
FLAME_FOOTPRINT = (0, 11, 0, 32)
EXPECTED_PACKAGE_ASSETS = 142
EXPECTED_INSTALL_TARGETS = 158


def _allowed_changes() -> set[Path]:
    result: set[Path] = set()
    for root in ASSET_ROOTS:
        directory = Path(root) / "effect"
        for rank in RANKS:
            result.update(
                directory / f"{gender}_body_effect_{rank:04d}.gwo"
                for gender in GENDERS
            )
            result.add(directory / f"reborn_body_effect_{rank:04d}_v2_flame.tga")
    assert len(result) == 6 * len(RANKS)
    return result


def _layout(data: bytes, label: str, expected_bits: int):
    info = validate_tga_texture(data, label)
    assert info.image_type == 2, f"{label} must be an uncompressed TGA"
    assert (info.width, info.height, info.bits_per_pixel) == (
        64, 64, expected_bits
    ), f"{label} layout changed"
    start = 18 + data[0]
    end = start + 64 * 64 * (expected_bits // 8)
    assert end + info.suffix_bytes == len(data), f"{label} payload bounds changed"
    return info, start, end


def _pixel(data: bytes, info, start: int, x: int, y: int) -> bytes:
    row = y if info.descriptor & 0x20 else 63 - y
    column = 63 - x if info.descriptor & 0x10 else x
    stride = info.bits_per_pixel // 8
    offset = start + (row * 64 + column) * stride
    return data[offset : offset + stride]


def _changed_pixels(
    before: bytes, after: bytes, label: str, expected_bits: int
) -> tuple[set[tuple[int, int]], object, int]:
    before_info, before_start, before_end = _layout(
        before, f"{label}:reference", expected_bits
    )
    after_info, after_start, after_end = _layout(
        after, f"{label}:candidate", expected_bits
    )
    assert before_info == after_info, f"{label} TGA metadata changed"
    assert before[:before_start] == after[:after_start], f"{label} header changed"
    assert before[before_end:] == after[after_end:], f"{label} footer changed"
    changed = {
        (x, y)
        for y in range(64)
        for x in range(64)
        if _pixel(before, before_info, before_start, x, y)
        != _pixel(after, after_info, after_start, x, y)
    }
    assert changed, f"{label} did not change colour"
    return changed, after_info, after_start


def _footprint() -> set[tuple[int, int]]:
    left, right, top, bottom = FLAME_FOOTPRINT
    return {(x, y) for y in range(top, bottom + 1)
            for x in range(left, right + 1)}


def _verify_canonical(before: bytes, after: bytes, label: str) -> None:
    changed, _info, _start = _changed_pixels(before, after, label, 24)
    assert changed <= _footprint(), f"{label} changed outside the flame footprint"


def _verify_private(before: bytes, after: bytes, label: str) -> None:
    changed, info, start = _changed_pixels(before, after, label, 32)
    assert changed <= _footprint(), f"{label} changed outside the flame footprint"
    assert all(
        _pixel(before, info, start, x, y)[3]
        == _pixel(after, info, start, x, y)[3]
        for y in range(64) for x in range(64)
    ), f"{label} alpha changed"


def _assert_same_paths(
    before: dict[Path, bytes],
    after: dict[Path, bytes],
    paths,
    label: str,
) -> None:
    mismatches = [path.as_posix() for path in paths if before[path] != after[path]]
    assert not mismatches, f"{label} changed: {', '.join(sorted(mismatches))}"


def _effect_structures(package: LoadedPackage) -> dict[str, str]:
    return {effect.key: effect.structural_sha256 for effect in package.effects}


def _verify_candidate_binding(candidate: dict[Path, bytes]) -> None:
    footprint = _footprint()
    for root in ASSET_ROOTS:
        directory = Path(root) / "effect"
        for rank in RANKS:
            private_path = directory / f"reborn_body_effect_{rank:04d}_v2_flame.tga"
            private = candidate[private_path]
            private_info, private_start, _ = _layout(
                private, private_path.as_posix(), 32
            )
            for gender in GENDERS:
                canonical_path = directory / f"{gender}_body_effect_{rank:04d}.gwo"
                canonical = candidate[canonical_path]
                canonical_info, canonical_start, _ = _layout(
                    canonical, canonical_path.as_posix(), 24
                )
                assert all(
                    _pixel(canonical, canonical_info, canonical_start, x, y)
                    == _pixel(private, private_info, private_start, x, y)[:3]
                    for x, y in footprint
                ), f"{canonical_path} and {private_path} flame BGR differ"


def _target_maps(
    reference: LoadedPackage,
    candidate: LoadedPackage,
    client_root: Path | None,
) -> tuple[dict[Path, bytes], dict[Path, bytes]]:
    assert set(reference.assets) == set(candidate.assets), "package target set changed"
    assert len(reference.assets) == len(candidate.assets) == EXPECTED_PACKAGE_ASSETS
    if client_root is None:
        return dict(reference.assets), dict(candidate.assets)
    client = client_root.resolve()
    assert client.is_dir(), f"clean client root is missing: {client}"
    before = installation_assets(client, reference)
    after = installation_assets(client, candidate)
    assert set(before) == set(after), "transactional install target set changed"
    assert len(before) == len(after) == EXPECTED_INSTALL_TARGETS
    return before, after


def verify(
    reference_root: Path,
    candidate_root: Path,
    client_root: Path | None,
) -> None:
    reference = load_package(reference_root.resolve())
    candidate = load_package(candidate_root.resolve())
    assert reference.manifest["package_id"] == candidate.manifest["package_id"]
    assert reference.manifest["coverage"] == candidate.manifest["coverage"]
    assert _effect_structures(reference) == _effect_structures(candidate), (
        "effect structural hashes changed"
    )
    before, after = _target_maps(reference, candidate, client_root)
    assert all(
        len(path.parts) == 3
        and path.parts[0] in ASSET_ROOTS
        and path.parts[1] == "effect"
        for path in before
    ), "release gained a non-effect/gameplay target"

    changed = {path for path in before if before[path] != after[path]}
    allowed = _allowed_changes()
    assert changed == allowed, (
        "palette-only target diff changed: "
        f"missing={sorted((allowed - changed), key=str)}, "
        f"unexpected={sorted((changed - allowed), key=str)}"
    )
    changed_payload_records = {
        (side, path) for path in changed for side in ("reference", "candidate")
    }
    assert len(changed) == 12 and len(changed_payload_records) == 24

    all_paths = set(before)
    _assert_same_paths(before, after, (p for p in all_paths if p.suffix == ".jcs"),
                       "JCS/model bytes")
    _assert_same_paths(
        before,
        after,
        (p for p in all_paths if p.name.endswith(
            ("_v2_wings.tga", "_v2_outer_wings.tga", "_v2_orbit.tga"))),
        "wing/orbit texture bytes",
    )
    _assert_same_paths(
        before,
        after,
        (p for p in all_paths if not any(
            f"body_effect_{rank:04d}" in p.name for rank in RANKS)),
        "non-capstone bytes",
    )

    for path in sorted(changed, key=lambda value: value.as_posix()):
        if path.suffix == ".gwo":
            _verify_canonical(before[path], after[path], path.as_posix())
        else:
            assert path.name.endswith("_v2_flame.tga")
            _verify_private(before[path], after[path], path.as_posix())
    _verify_candidate_binding(candidate.assets)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-package", type=Path, required=True)
    parser.add_argument("--candidate-package", type=Path, required=True)
    parser.add_argument("--client-root", type=Path)
    arguments = parser.parse_args()
    verify(
        arguments.reference_package,
        arguments.candidate_package,
        arguments.client_root,
    )
    assert Path(__file__).stat().st_size < 20_000
    mode = "installation" if arguments.client_root else "package"
    print(f"PASS capstone flame palette-only {mode} differential")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
