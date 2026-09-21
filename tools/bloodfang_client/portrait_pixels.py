"""Dependency-free PNG decoding and deterministic area resampling for icons."""
import binascii
import struct
import zlib

from holy_suit_tiers.text import PatchError


def decode(png):
    if png[:8] != b'\x89PNG\r\n\x1a\n':
        raise PatchError('Portrait is not PNG')
    cursor, header, compressed, ended = 8, None, bytearray(), False
    while cursor < len(png):
        if cursor + 12 > len(png):
            raise PatchError('Truncated portrait PNG')
        length = struct.unpack_from('>I', png, cursor)[0]
        kind = png[cursor + 4:cursor + 8]
        end = cursor + 8 + length
        if end + 4 > len(png):
            raise PatchError('Truncated portrait PNG chunk')
        data = png[cursor + 8:end]
        if binascii.crc32(kind + data) & 0xffffffff != struct.unpack_from('>I', png, end)[0]:
            raise PatchError('Portrait PNG checksum differs')
        if kind == b'IHDR':
            if header is not None or length != 13:
                raise PatchError('Invalid portrait PNG header')
            header = struct.unpack('>IIBBBBB', data)
        elif kind == b'IDAT':
            if header is None:
                raise PatchError('Portrait pixels precede header')
            compressed.extend(data)
        elif kind == b'IEND':
            if length or end + 4 != len(png):
                raise PatchError('Portrait PNG has trailing data')
            ended = True
        elif kind in (b'tRNS', b'acTL'):
            raise PatchError('Use ordinary RGB/RGBA PNG without color-key transparency or animation')
        elif kind[:1].isupper() and kind != b'PLTE':
            raise PatchError('Unsupported critical portrait PNG chunk')
        cursor = end + 4
    if header is None or not ended:
        raise PatchError('Incomplete portrait PNG')
    width, height, depth, color, compression, filtering, interlace = header
    if (width != height or not 36 <= width <= 4096 or depth != 8 or
            color not in (2, 6) or compression or filtering or interlace):
        raise PatchError('Portrait must be a square 36..4096 pixel, noninterlaced 8-bit RGB/RGBA PNG')
    channels = 3 if color == 2 else 4
    stride = width * channels
    expected = height * (stride + 1)
    try:
        decompressor = zlib.decompressobj()
        filtered = decompressor.decompress(compressed, expected + 1)
        if len(filtered) != expected or not decompressor.eof or decompressor.unused_data:
            raise PatchError('Portrait PNG decoded size differs')
    except zlib.error as error:
        raise PatchError('Invalid portrait PNG compression') from error
    pixels = bytearray(width * height * 4)
    previous = bytearray(stride)
    for y in range(height):
        offset = y * (stride + 1)
        mode = filtered[offset]
        row = bytearray(filtered[offset + 1:offset + 1 + stride])
        if mode > 4:
            raise PatchError('Invalid portrait PNG filter')
        for index in range(stride):
            left = row[index - channels] if index >= channels else 0
            above = previous[index]
            diagonal = previous[index - channels] if index >= channels else 0
            predicted = left + above - diagonal
            distances = (abs(predicted - left), abs(predicted - above), abs(predicted - diagonal))
            paeth = (left, above, diagonal)[distances.index(min(distances))]
            predictor = (0, left, above, (left + above) // 2, paeth)[mode]
            row[index] = (row[index] + predictor) & 255
        for x in range(width):
            source, dest = x * channels, (y * width + x) * 4
            pixels[dest:dest + 3] = row[source:source + 3]
            pixels[dest + 3] = row[source + 3] if channels == 4 else 255
        previous = row
    return width, bytes(pixels)


def resample_bgra(width, rgba, size=36):
    """Premultiplied-alpha area average; integer weights avoid edge fringes."""
    output = bytearray(size * size * 4)
    total_weight = width * width
    for y in range(size):
        top, bottom = y * width, (y + 1) * width
        for x in range(size):
            left, right = x * width, (x + 1) * width
            red = green = blue = alpha = 0
            for sy in range(top // size, (bottom + size - 1) // size):
                wy = min(bottom, (sy + 1) * size) - max(top, sy * size)
                for sx in range(left // size, (right + size - 1) // size):
                    weight = wy * (min(right, (sx + 1) * size) - max(left, sx * size))
                    offset = (sy * width + sx) * 4
                    weighted_alpha = rgba[offset + 3] * weight
                    alpha += weighted_alpha
                    red += rgba[offset] * weighted_alpha
                    green += rgba[offset + 1] * weighted_alpha
                    blue += rgba[offset + 2] * weighted_alpha
            offset = (y * size + x) * 4
            if alpha:
                output[offset:offset + 4] = bytes((
                    (blue + alpha // 2) // alpha, (green + alpha // 2) // alpha,
                    (red + alpha // 2) // alpha, (alpha + total_weight // 2) // total_weight))
    if not any(output[3::4]):
        raise PatchError('Portrait is entirely transparent')
    return bytes(output)
