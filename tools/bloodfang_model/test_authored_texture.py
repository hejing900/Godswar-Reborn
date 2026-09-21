"""Baked atlas regressions: strict rows, true UVs, exact sRGB texels."""
from io import BytesIO
from pathlib import Path
import struct
import tempfile
import unittest

from PIL import Image

from native_export import prepare_vertices
from native_texture import authored_texture, encode_bgra


class AuthoredTextureTests(unittest.TestCase):
    def test_mixed_runs_and_raw_packets_remain_in_rows(self):
        width, height = 256, 4
        pixels = []
        for y in range(height):
            pixels += [bytes((i % 256, y * 30, 90, 255)) for i in range(80)]
            pixels += [bytes((9, 10, 11, 255))] * (width - 80)
        data = encode_bgra(width, height, pixels)
        cursor, decoded, kinds = 18, [], set()
        while len(decoded) < width * height:
            packet = data[cursor]
            cursor += 1
            count = (packet & 127) + 1
            self.assertLessEqual(count, width - len(decoded) % width)
            kinds.add(bool(packet & 128))
            if packet & 128:
                decoded += [data[cursor:cursor + 4]] * count
                cursor += 4
            else:
                decoded += [data[i:i + 4] for i in range(cursor, cursor + count * 4, 4)]
                cursor += count * 4
        self.assertEqual(len(data), cursor)
        self.assertEqual(pixels, decoded)
        self.assertEqual({True, False}, kinds)
        self.assertEqual(b''.join(pixels), Image.open(BytesIO(data)).convert('RGBA').tobytes('raw', 'BGRA'))

    def test_png_roundtrip_keeps_alpha_and_srgb_channels(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image = Image.new('RGBA', (4, 4))
            image.putdata([(n * 13, n * 7, 255 - n, n * 17) for n in range(16)])
            image.save(root / 'original.png')
            spec = dict(path='original.png', uv_origin='bottom_left', color_space='sRGB')
            authored_texture(spec, root, root / 'native.gwo')
            decoded = Image.open(root / 'native.gwo').convert('RGBA')
            self.assertEqual(image.tobytes(), decoded.tobytes())
            spec['path'] = '../outside.png'
            with self.assertRaises(ValueError):
                authored_texture(spec, root, root / 'native.gwo')

    def test_native_uv_converts_bottom_origin_without_palette_replacement(self):
        doc = {'materials': [{}], 'texture': {'uv_origin': 'bottom_left'},
               'vertices': [{'uv': [u, v]} for u, v in ((.1, .2), (.3, .4), (.8, .9))],
               'triangles': [{'material': 0, 'vertices': [0, 1, 2]}]}
        vertices, faces = prepare_vertices(doc)
        self.assertEqual([(v['uv'][0], round(v['uv'][1], 5)) for v in vertices],
                         [(.1, .8), (.3, .6), (.8, .1)])
        self.assertEqual([[0, 1, 2]], faces)
        self.assertEqual([.1, .2], doc['vertices'][0]['uv'])
        palette, _ = prepare_vertices(doc, [(.25, .75)])
        self.assertTrue(all(v['uv'] == (.25, .75) for v in palette))


if __name__ == '__main__':
    unittest.main()
