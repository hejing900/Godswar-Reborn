"""Package checks for AR13/AR14's native-UV animated-flame binding."""

from rank_effect_packages.formats import (
    extract_texture_references,
    validate_tga_texture,
)
from rank_effect_v2.atlas import raw_truecolour_tga


SOURCE_FOOTPRINT = (0, 11, 0, 32)
FOOTPRINT_PIXELS = 12 * 33
CAPSTONE_BINDING_METADATA = {
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


def _coordinates(rectangle):
    left, right, top, bottom = rectangle
    return tuple(
        (x, y)
        for y in range(top, bottom + 1)
        for x in range(left, right + 1)
    )


def _pixel(data, info, x, y):
    assert info.image_type == 2
    stride = info.bits_per_pixel // 8
    row = y if info.descriptor & 0x20 else info.height - 1 - y
    column = info.width - 1 - x if info.descriptor & 0x10 else x
    offset = 18 + (row * info.width + column) * stride
    return data[offset:offset + stride]


def _footprint(data, info):
    return tuple(
        _pixel(data, info, x, y) for x, y in _coordinates(SOURCE_FOOTPRINT)
    )


def _raw(data, label):
    output = raw_truecolour_tga(data, label)
    return output, validate_tga_texture(output, f"{label}:raw")


def verify_capstone_flame_texture_binding(package, effect, native_flame_gwo):
    """Prove slot 2 and both runtime atlases use one native-UV flame crop."""

    expected_name = f"reborn_body_effect_{effect.rank:04d}_v2_flame.tga"
    matches = [path for path in effect.private_textures if path.name == expected_name]
    assert len(matches) == 1, f"AR{effect.rank} must package one flame atlas"
    private_path = matches[0]
    private, private_info = _raw(
        package.assets[private_path], private_path.as_posix()
    )
    canonical, canonical_info = _raw(
        package.assets[effect.canonical_texture], effect.canonical_texture.as_posix()
    )
    source, source_info = _raw(native_flame_gwo, "native AR5 canonical GWO")
    assert (
        private_info.width,
        private_info.height,
        private_info.bits_per_pixel,
    ) == (64, 64, 32)
    assert (
        canonical_info.width,
        canonical_info.height,
        canonical_info.bits_per_pixel,
    ) == (64, 64, 24)
    assert (
        source_info.width,
        source_info.height,
        source_info.bits_per_pixel,
    ) == (64, 64, 32)

    models = sorted(effect.models, key=lambda path: path.name)
    assert len(models) == 3
    references = extract_texture_references(
        package.assets[models[2]], models[2].as_posix()
    )
    assert references == (expected_name.encode("ascii"),), (
        f"AR{effect.rank} slot 2 must bind the animated-flame private atlas"
    )

    source_pixels = _footprint(source, source_info)
    private_pixels = _footprint(private, private_info)
    canonical_pixels = _footprint(canonical, canonical_info)
    assert len(source_pixels) == len(private_pixels) == len(canonical_pixels) == (
        FOOTPRINT_PIXELS
    )
    assert tuple(pixel[:3] for pixel in private_pixels) == canonical_pixels, (
        f"AR{effect.rank} private/canonical flame BGR must match at native UVs"
    )
    assert bytes(pixel[3] for pixel in private_pixels) == bytes(
        pixel[3] for pixel in source_pixels
    ), f"AR{effect.rank} private flame must preserve native AR5 alpha"
    assert any(max(pixel[:3]) and pixel[3] for pixel in private_pixels), (
        f"AR{effect.rank} animated-flame footprint is invisible"
    )
