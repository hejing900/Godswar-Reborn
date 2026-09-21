#!/usr/bin/env python3
"""Pack approved Holy Suit material artwork into native 36px inventory cells.

Requires Pillow==12.0.0. First use: --native-atlas PATH/TO/Icon3.gwo copies only
the verified native header/extension into the source package. Later runs and
--check need only the repository sources; no installed client is accessed.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import struct

import PIL
from PIL import Image, ImageDraw, ImageOps

from level5_forge_icons.common import InstallError, TGA_FOOTER_SIGNATURE
from level5_forge_icons.tga_atlas import encode_pixel_sequence, parse_tga


SLUGS = ("runesteel", "arcanite", "seraphite", "divinium")
MATERIAL_NAMES = ("RuneSteel Ingot", "Arcanite Crystal", "Seraphite Core", "Divinium Essence")
PILLOW_VERSION = "12.0.0"
ATLAS_SIZE = 1024
STOCK_REFERENCE_SHA256 = "ee94261a9e34d6a63a88b89df991d6a6a876bee6f9b2c83e1fc8c39d6d3c6f24"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def png_bytes(image: Image.Image) -> bytes:
    stream = io.BytesIO()
    image.save(stream, format="PNG", compress_level=9)
    return stream.getvalue()


def native_format(source: Path, native_atlas: Path | None) -> tuple[bytes, dict, dict[Path, bytes]]:
    format_path = source / "native-tga-format.bin"
    provenance_path = source / "native-tga-format.json"
    if native_atlas is not None:
        original = native_atlas.read_bytes()
        native = parse_tga(original, str(native_atlas))
        data = native.prefix + native.extension
        provenance = {"reference_atlas": native_atlas.name, "reference_sha256": sha256(original),
                      "header_bytes": 18, "extension_bytes": 495, "sha256": sha256(data)}
        outputs = {format_path: data, provenance_path: json_bytes(provenance)}
    else:
        data = format_path.read_bytes()
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        outputs = {}
    expected = struct.pack("<BBBHHBHHHHBB", 0, 0, 10, 0, 0, 0, 0, 0,
                           ATLAS_SIZE, ATLAS_SIZE, 32, 0x08)
    if len(data) != 513 or data[:18] != expected or struct.unpack_from("<H", data, 18)[0] != 495:
        raise InstallError("Native TGA template must contain the verified 18-byte header and 495-byte extension")
    if sha256(data) != provenance["sha256"]:
        raise InstallError("Native TGA format provenance does not match its bytes")
    return data, provenance, outputs


def downscale(source: Image.Image, size: int) -> Image.Image:
    # Match the approved proposal's optical fit. Ignore almost invisible alpha
    # outside the shape, then retain its aspect ratio and one-pixel padding.
    bounds = source.getchannel("A").point(lambda alpha: 255 if alpha >= 8 else 0).getbbox()
    if bounds is None:
        raise InstallError("Source has no visible material artwork")
    scaled = ImageOps.contain(source.crop(bounds).convert("RGBa"), (size - 2, size - 2),
                              method=Image.Resampling.LANCZOS).convert("RGBA")
    result = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    result.paste(scaled, ((size - scaled.width) // 2, (size - scaled.height) // 2))
    if result.getchannel("A").getextrema()[0] != 0 or not result.getbbox():
        raise InstallError("Prepared icon must retain transparent padding and visible artwork")
    return result


def stock_frame(source: Path) -> Image.Image:
    data = (source / "platinum-stock-36.png").read_bytes()
    if sha256(data) != STOCK_REFERENCE_SHA256:
        raise InstallError("Stock material frame differs from the reviewed Platinum cell")
    with Image.open(io.BytesIO(data)) as image:
        if image.mode != "RGBA" or image.size != (36, 36):
            raise InstallError("Stock material frame must be the native36px RGBA cell")
        return image.getchannel("A").copy()


def pack_stock_variant(image: Image.Image, frame: Image.Image) -> Image.Image:
    # ImageGen supplies the palette variant. Sampling its enlarged36px grid
    # back to native size keeps the stock framing instead of adding padding.
    # Reuse only the native alpha plane (four transparent corner pixels).
    icon = image.resize((36, 36), Image.Resampling.NEAREST).convert("RGBA")
    icon.putalpha(frame)
    return icon


def encode_native(atlas: Image.Image, template: bytes) -> bytes:
    # Native descriptor0x08 stores scanlines bottom-to-top and pixels as BGRA.
    pixels = atlas.tobytes("raw", "BGRA", 0, -1)
    encoded = bytearray(template[:18])
    stride = ATLAS_SIZE * 4
    for offset in range(0, len(pixels), stride):
        row = pixels[offset:offset + stride]
        encoded.extend(encode_pixel_sequence([row[x:x + 4] for x in range(0, stride, 4)]))
    extension_offset = len(encoded)
    encoded.extend(template[18:])
    encoded.extend(struct.pack("<II", extension_offset, 0) + TGA_FOOTER_SIGNATURE)
    result = bytes(encoded)
    decoded = parse_tga(result, "HolySuitWare.gwo")
    if decoded.pixels != pixels or decoded.extension != template[18:]:
        raise InstallError("Native TGA round trip changed pixels or extension metadata")
    if any(p.pixel_start // ATLAS_SIZE != (p.pixel_start + p.pixel_count - 1) // ATLAS_SIZE
           for p in decoded.packets):
        raise InstallError("Native RLE packets must not cross scanline boundaries")
    with Image.open(io.BytesIO(result)) as reopened:
        if reopened.convert("RGBA").tobytes() != atlas.tobytes():
            raise InstallError("Independent Pillow decode changed native atlas orientation or alpha")
    return result


def preview(icons: list[Image.Image]) -> Image.Image:
    result = Image.new("RGBA", (1040, 330), (23, 27, 35, 255))
    draw = ImageDraw.Draw(result)
    draw.text((12, 8), "Holy Suit upgrade materials | 6x preview and actual 36px inventory size", fill="white")
    for column, (name, icon) in enumerate(zip(MATERIAL_NAMES, icons, strict=True)):
        x = column * 260
        draw.text((x + 12, 34), name, fill="white")
        for y, scale in ((54, 6), (286, 1)):
            left = x + 12
            rendered = icon.resize((icon.width * scale, icon.height * scale), Image.Resampling.NEAREST)
            # Preview-only checkerboard; generated atlas/icons retain real alpha.
            for cy in range(y, y + rendered.height, 12):
                for cx in range(left, left + rendered.width, 12):
                    color = (49, 55, 65) if ((cx - left) // 12 + (cy - y) // 12) % 2 else (33, 39, 48)
                    draw.rectangle((cx, cy, min(cx + 11, left + rendered.width - 1),
                                    min(cy + 11, y + rendered.height - 1)), fill=color)
            result.alpha_composite(rendered, (left, y))
    return result


def prepare(asset_root: Path, native_atlas: Path | None) -> dict[Path, bytes]:
    if PIL.__version__ != PILLOW_VERSION:
        raise InstallError(f"Reproducible resizing requires Pillow=={PILLOW_VERSION}; found {PIL.__version__}")
    source = asset_root / "source"
    generated = asset_root / "generated"
    template, provenance, outputs = native_format(source, native_atlas)
    atlas = Image.new("RGBA", (ATLAS_SIZE, ATLAS_SIZE), (0, 0, 0, 0))
    icons: list[Image.Image] = []
    entries = []
    generation_path = asset_root / "generation.json"
    generation = generation_path.read_bytes()
    stock_grid = json.loads(generation).get("framing") == "stock-36-grid"
    frame = stock_frame(source) if stock_grid else None
    for index, (slug, name) in enumerate(zip(SLUGS, MATERIAL_NAMES, strict=True)):
        path = source / f"{slug}.png"
        original = path.read_bytes()
        with Image.open(io.BytesIO(original)) as loaded:
            modes = ("RGB", "RGBA") if stock_grid else ("RGBA",)
            if loaded.mode not in modes or loaded.width > 4096 or loaded.height > 4096:
                raise InstallError(f"Expected bounded material image source: {path}")
            image = loaded.convert("RGBA")
        alpha_min, alpha_max = image.getchannel("A").getextrema()
        if (not stock_grid and alpha_min != 0) or alpha_max != 255:
            raise InstallError(f"Source must have real transparency and opaque artwork: {path}")
        icon = pack_stock_variant(image, frame) if frame is not None else downscale(image, 36)
        icons.append(icon)
        x = index * 36
        atlas.paste(icon, (x, 0))
        icon_name = f"{slug}-36.png"
        icon_data = png_bytes(icon)
        outputs[generated / icon_name] = icon_data
        entries.append({"slug": slug, "name": name, "item_id": 9014 + index, "tier": 5 + index,
                        "source": f"source/{slug}.png", "source_sha256": sha256(original),
                        "source_size": list(image.size), "source_alpha_bounds": list(image.getbbox()),
                        "source_optical_bounds": list(image.getchannel("A").point(
                            lambda alpha: 255 if alpha >= 8 else 0).getbbox()),
                        "icon": {"file": icon_name, "sha256": sha256(icon_data), "rect": [x, 0, 36, 36]}})
    outputs[generated / "HolySuitWare.gwo"] = encode_native(atlas, template)
    outputs[generated / "HolySuitWare.png"] = png_bytes(atlas)
    outputs[generated / "icons-native.png"] = png_bytes(atlas.crop((0, 0, 144, 36)))
    outputs[generated / "preview.png"] = png_bytes(preview(icons))
    manifest = {"schema_version": 2, "pipeline": "tools/PrepareHolySuitWareIcons.py",
                "pillow_version": PILLOW_VERSION,
                "resampling": ("stock36px grid; nearest sample; exact native Platinum alpha; no extra padding"
                               if stock_grid else "alpha>=8 optical bounds; premultiplied-alpha Lanczos; aspect fit; 1px padding"),
                "stock_reference_sha256": STOCK_REFERENCE_SHA256 if stock_grid else None,
                "generation": {"file": "generation.json", "sha256": sha256(generation)},
                "atlas": "HolySuitWare.gwo", "width": ATLAS_SIZE, "height": ATLAS_SIZE,
                "format": "TGA type10 RLE BGRA32; bottom-origin descriptor0x08; scanline-bounded packets",
                "native_format": provenance, "entries": entries,
                "outputs": {p.name: {"bytes": len(data), "sha256": sha256(data)} for p, data in
                            sorted(outputs.items()) if p.parent == generated}}
    outputs[generated / "manifest.json"] = json_bytes(manifest)
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asset-root", type=Path, default=Path(__file__).resolve().parents[1] / "assets/holy-suit-wares")
    parser.add_argument("--native-atlas", type=Path, help="Read-only native Icon3.gwo for initial format capture")
    parser.add_argument("--check", action="store_true", help="Verify every reproducible output without writing")
    args = parser.parse_args()
    outputs = prepare(args.asset_root.resolve(), args.native_atlas)
    changed = [path for path, data in outputs.items() if not path.exists() or path.read_bytes() != data]
    if args.check and changed:
        raise InstallError("Generated output differs: " + ", ".join(str(path) for path in changed))
    for path in changed:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(outputs[path])
    atlas = args.asset_root.resolve() / "generated/HolySuitWare.gwo"
    print(json.dumps({"verified": len(outputs), "written": len(changed), "atlas": str(atlas),
                      "sha256": sha256(outputs[atlas])}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
