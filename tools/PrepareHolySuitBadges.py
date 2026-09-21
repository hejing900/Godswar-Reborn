#!/usr/bin/env python3
"""Pack approved gear artwork into four cells of a pinned native main atlas.

Requires Pillow==12.0.0. Sources and the untouched original main.gwo live in
assets/holy-suit-badges/source. This tool never reads or writes the installed
client. --check regenerates every output in memory and verifies exact bytes.
Only optical framing, resizing, and atlas packing are performed. Source art
and colors are retained; high-resolution padding below alpha8 is discarded.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path

import PIL
from PIL import Image, ImageDraw

from level5_forge_icons.common import InstallError
from level5_forge_icons.tga_atlas import (
    display_pixel_index, parse_tga, patch_atlas, validate_generated_atlas,
)


PILLOW_VERSION = "12.0.0"
BASE_SHA256 = "fe614cf23605b20694187d079328057f461a2e82c5e8a3bd4a4e3318a754ccdc"
BADGES = ((5, "runesteel", 774, 355), (6, "arcanite", 744, 355),
          (7, "seraphite", 714, 355), (8, "divinium", 684, 355))
SIZE = 30
OPTICAL_ALPHA_THRESHOLD = 8
PREVIOUS_BODY_CENTER_COLUMNS = 19
BODY_CENTER_COLUMNS = 25
FRAMING_SUPERSAMPLE = 8


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def png_bytes(image: Image.Image) -> bytes:
    stream = io.BytesIO()
    image.save(stream, format="PNG", compress_level=9)
    return stream.getvalue()


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def image_from_atlas(atlas) -> Image.Image:
    return Image.frombytes("RGBA", (atlas.width, atlas.height), atlas.pixels,
                           "raw", "BGRA", 0, -1)


def optical_metrics(image: Image.Image) -> dict:
    solid = image.getchannel("A").point(lambda value: 255 if value >= 128 else 0)
    return {"bounds": list(solid.getbbox()), "solid_pixels": sum(value > 0 for value in solid.tobytes()),
            "middle_band_solid_pixels": sum(value > 0 for value in solid.crop((0, 10, SIZE, 20)).tobytes())}


def previous_icon(original: Image.Image) -> Image.Image:
    if original.size == (SIZE, SIZE):
        return original.copy()
    bounds = original.getchannel("A").point(lambda value: 255 if value >= OPTICAL_ALPHA_THRESHOLD else 0).getbbox()
    return fit_optical_body(original.crop(bounds), PREVIOUS_BODY_CENTER_COLUMNS)


def fit_optical_body(body: Image.Image, center_columns: int = BODY_CENTER_COLUMNS) -> Image.Image:
    # Keep the shoulder tips inside the fixed cell while giving the narrow
    # breastplate/waist more space: sourcequarters map to2.5/25/2.5columns.
    # The preceding19-column fit reached the cell edges but remained visibly
    # thinner than Common. Compare both full and middle-band opaque coverage.
    # This continuous, monotonic three-strip mapping retains the entire image;
    # it does not crop, paint, recolor, or synthesize any part of the armor.
    extent = SIZE * FRAMING_SUPERSAMPLE
    normalized = body.convert("RGBa").resize((extent, extent), Image.Resampling.LANCZOS)
    left = (SIZE - center_columns) * FRAMING_SUPERSAMPLE // 2
    right = extent - left
    quarter = extent // 4
    strips = ((0, left, 0, quarter), (left, right, quarter, 3 * quarter),
              (right, extent, 3 * quarter, extent))
    mesh = [((start, 0, end, extent),
             (source_start, 0, source_start, extent, source_end, extent, source_end, 0))
            for start, end, source_start, source_end in strips]
    widened = normalized.transform((extent, extent), Image.Transform.MESH, mesh, Image.Resampling.BICUBIC)
    return widened.resize((SIZE, SIZE), Image.Resampling.LANCZOS).convert("RGBA")


def prepare_icon(data: bytes, label: str) -> tuple[Image.Image, dict]:
    with Image.open(io.BytesIO(data)) as loaded:
        if loaded.format != "PNG" or loaded.mode != "RGBA":
            raise InstallError(f"Expected RGBA PNG source: {label}")
        if not (SIZE <= loaded.width <= 4096 and SIZE <= loaded.height <= 4096):
            raise InstallError(f"Expected source dimensions between 30 and 4096: {label}")
        original = loaded.copy()
    alpha = original.getchannel("A")
    if alpha.getextrema() != (0, 255):
        raise InstallError(f"Source requires genuine transparency and opaque artwork: {label}")
    # A few almost-transparent generated pixels can span the entire canvas.
    # Frame the actual armor instead. No removed pixel has alpha>=8, and the
    # complete optical bounds fit the cell without clipping shoulder/boot art.
    optical_bounds = alpha.point(lambda value: 255 if value >= OPTICAL_ALPHA_THRESHOLD else 0).getbbox()
    if optical_bounds is None:
        raise InstallError(f"Source has no visible optical body: {label}")
    if original.size == (SIZE, SIZE):
        # Native fixtures and authored30px sprites are already framed.
        icon = original.copy()
    else:
        icon = fit_optical_body(original.crop(optical_bounds))
    visible = sum(value > 0 for value in icon.getchannel("A").tobytes())
    if visible < 100 or icon.getchannel("A").getextrema()[0] != 0:
        raise InstallError(f"Prepared badge is empty, too small, or lacks transparency: {label}")
    return icon, {"source_size": list(original.size), "source_alpha_bounds": list(alpha.getbbox()),
                  "source_optical_bounds": list(optical_bounds),
                  "icon_alpha_bounds": list(icon.getchannel("A").getbbox()), "visible_pixels": visible,
                  "optical_alpha128_before": optical_metrics(previous_icon(original)),
                  "optical_alpha128_after": optical_metrics(icon)}


def make_preview(original: Image.Image, icons: list[Image.Image], before_icons: list[Image.Image]) -> Image.Image:
    result = Image.new("RGBA", (1200, 540), (24, 28, 36, 255))
    draw = ImageDraw.Draw(result)
    draw.text((12, 8), "Holy Suit gear badges | top: installed framing / bottom: fuller torso | stock references at left", fill="white")
    stock = [("stock Common", original.crop((864, 165, 894, 195))),
             ("stock Platinum", original.crop((744, 165, 774, 195)))]
    columns = [(name, picture, picture) for name, picture in stock]
    columns.extend((slug, before, after) for (_, slug, _, _), before, after in
                   zip(BADGES, before_icons, icons, strict=True))
    for column, (label, before, after) in enumerate(columns):
        left = column * 200 + 10
        draw.text((left, 34), label, fill="white")
        for picture, top in ((before, 56), (after, 302)):
            for cy in range(top, top + 180, 12):
                for cx in range(left, left + 180, 12):
                    color = (49, 55, 65) if ((cx - left) // 12 + (cy - top) // 12) % 2 else (33, 39, 48)
                    draw.rectangle((cx, cy, cx + 11, cy + 11), fill=color)
            result.alpha_composite(picture.resize((180, 180), Image.Resampling.NEAREST), (left, top))
            result.alpha_composite(picture, (left, top + 190))
            draw.text((left + 40, top + 197), "native30px", fill="white")
    return result


def prepare(asset_root: Path) -> dict[Path, bytes]:
    if PIL.__version__ != PILLOW_VERSION:
        raise InstallError(f"Reproducible resizing requires Pillow=={PILLOW_VERSION}; found {PIL.__version__}")
    source, generated = asset_root / "source", asset_root / "generated"
    base_path = source / "main.gwo"
    base_data = base_path.read_bytes()
    if sha256(base_data) != BASE_SHA256:
        raise InstallError("Source main.gwo is not the reviewed original atlas")
    base = parse_tga(base_data, str(base_path))
    original = image_from_atlas(base)
    stock_metrics = {"Common": optical_metrics(original.crop((864, 165, 894, 195))),
                     "Platinum": optical_metrics(original.crop((744, 165, 774, 195)))}
    if original.crop((684, 355, 714, 385)).getchannel("A").getextrema() != (0, 0):
        raise InstallError("Divinium destination must be completely transparent in the original atlas")
    outputs: dict[Path, bytes] = {}
    desired: dict[int, bytes] = {}
    entries, icons, before_icons, source_hashes = [], [], [], set()
    for tier, slug, x, y in BADGES:
        path = source / f"{slug}.png"
        data = path.read_bytes()
        source_hash = sha256(data)
        if source_hash in source_hashes:
            raise InstallError("Each tier requires its own artwork; duplicate sources were provided")
        source_hashes.add(source_hash)
        icon, details = prepare_icon(data, str(path))
        if details["source_size"] != [SIZE, SIZE]:
            for metric in ("solid_pixels", "middle_band_solid_pixels"):
                if details["optical_alpha128_after"][metric] < stock_metrics["Common"][metric]:
                    raise InstallError(f"Prepared badge is optically smaller than Common ({metric}): {slug}")
        icons.append(icon)
        with Image.open(io.BytesIO(data)) as unframed:
            before_icons.append(previous_icon(unframed.convert("RGBA")))
        pixels = icon.tobytes("raw", "BGRA")
        for row in range(SIZE):
            for column in range(SIZE):
                index = display_pixel_index(base, x + column, y + row)
                if index in desired:
                    raise InstallError("Badge destination cells overlap")
                offset = (row * SIZE + column) * 4
                desired[index] = pixels[offset:offset + 4]
        name = f"{slug}-30.png"
        encoded = png_bytes(icon)
        outputs[generated / name] = encoded
        entries.append({"tier": tier, "slug": slug, "rect": [x, y, SIZE, SIZE],
                        "source": f"source/{slug}.png", "source_sha256": source_hash,
                        "icon": {"file": name, "sha256": sha256(encoded)}, **details})
    atlas_bytes = patch_atlas(base, desired)
    # This compares every decoded byte with the original plus exactly the four
    # requested rectangles, and preserves header, extension, and footer fields.
    packed = validate_generated_atlas(base, atlas_bytes, desired, "HolySuitBadges.gwo")
    if any(packet.pixel_start // base.width !=
           (packet.pixel_start + packet.pixel_count - 1) // base.width for packet in packed.packets):
        raise InstallError("Native RLE packets must remain within individual scanlines")
    atlas_image = image_from_atlas(packed)
    with Image.open(io.BytesIO(atlas_bytes)) as independently_decoded:
        if independently_decoded.convert("RGBA").tobytes() != atlas_image.tobytes():
            raise InstallError("Independent decoder found an orientation or alpha mismatch")
    for tier, x in enumerate((864, 834, 804, 774, 744)):
        bounds = (x, 165, x + SIZE, 195)
        if original.crop(bounds).tobytes() != atlas_image.crop(bounds).tobytes():
            raise InstallError(f"Protected original tier{tier} badge changed")
    outputs[generated / "HolySuitBadges.gwo"] = atlas_bytes
    outputs[generated / "HolySuitBadges.png"] = png_bytes(atlas_image)
    native_row = Image.new("RGBA", (4 * SIZE, SIZE))
    for index, icon in enumerate(icons):
        native_row.paste(icon, (index * SIZE, 0))
    outputs[generated / "badges-native.png"] = png_bytes(native_row)
    outputs[generated / "preview.png"] = png_bytes(make_preview(original, icons, before_icons))
    changed_count = sum(base.pixels[index * 4:index * 4 + 4] != pixel for index, pixel in desired.items())
    manifest = {"schema_version": 1, "pipeline": "tools/PrepareHolySuitBadges.py",
                "pillow_version": PILLOW_VERSION, "atlas": "HolySuitBadges.gwo",
                "width": base.width, "height": base.height,
                "format": "Native TGA type10 RLE BGRA32; bottom-origin descriptor0x08",
                "resampling": "premultiplied-alpha Lanczos8x; alpha>=8 optical bounds; continuous three-strip bicubic width fit; native30px copied exactly",
                "optical_framing": {"alpha_threshold": OPTICAL_ALPHA_THRESHOLD,
                                    "discarded_padding_max_alpha": OPTICAL_ALPHA_THRESHOLD - 1,
                                    "source_center_fraction": 0.5,
                                    "previous_destination_center_columns": PREVIOUS_BODY_CENTER_COLUMNS,
                                    "destination_center_columns": BODY_CENTER_COLUMNS,
                                    "supersampling": FRAMING_SUPERSAMPLE,
                                    "stock_alpha128": stock_metrics},
                "base_atlas": {"file": "source/main.gwo", "sha256": BASE_SHA256, "bytes": len(base_data)},
                "entries": entries, "owned_pixels": len(desired), "changed_pixels": changed_count,
                "preserved_pixels": base.width * base.height - len(desired),
                "validation": {"outside_cells_identical": True, "native_metadata_preserved": True,
                               "tier0_through4_identical": True, "independent_decode_matches": True,
                               "new_divinium_cell_originally_transparent": True},
                "outputs": {path.name: {"bytes": len(data), "sha256": sha256(data)}
                            for path, data in sorted(outputs.items())}}
    outputs[generated / "manifest.json"] = json_bytes(manifest)
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asset-root", type=Path,
                        default=Path(__file__).resolve().parents[1] / "assets/holy-suit-badges")
    parser.add_argument("--check", action="store_true", help="Verify outputs without writing")
    args = parser.parse_args()
    outputs = prepare(args.asset_root.resolve())
    changed = [path for path, data in outputs.items() if not path.exists() or path.read_bytes() != data]
    if args.check and changed:
        raise InstallError("Generated output differs: " + ", ".join(str(path) for path in changed))
    for path in changed:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(outputs[path])
    atlas_path = args.asset_root.resolve() / "generated/HolySuitBadges.gwo"
    print(json.dumps({"verified": len(outputs), "written": len(changed), "atlas": str(atlas_path),
                      "sha256": sha256(outputs[atlas_path])}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
