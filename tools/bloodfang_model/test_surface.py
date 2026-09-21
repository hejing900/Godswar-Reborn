"""Negative controls for the independent native surface readback gate."""
import copy
import struct
from types import SimpleNamespace
import unittest

from validate_surface import compare_corners, read_texture


class IndependentSurfaceTests(unittest.TestCase):
    def fixture(self):
        vertices = [
            {'position': [0, 1, 2], 'normal': [1, 0, 0], 'uv': [0, .25]},
            {'position': [3, 4, 5], 'normal': [0, 1, 0], 'uv': [.5, .75]},
            {'position': [6, 7, 8], 'normal': [0, 0, 1], 'uv': [1, 1]},
        ]
        document = {'vertices': vertices, 'triangles': [{'vertices': [0, 1, 2]}],
                    'texture': {'uv_origin': 'bottom_left'}}
        mesh = SimpleNamespace(
            vertices=[vertices[1]['position'], vertices[2]['position'], vertices[0]['position']],
            faces=[[2, 0, 1]], normal_faces=[[1, 2, 0]],
            normals=[vertices[2]['normal'], vertices[0]['normal'], vertices[1]['normal']],
        )
        return document, mesh, [[.5, .25], [1, 0], [0, .75]]

    def test_follows_distinct_native_position_and_normal_corner_indices(self):
        document, mesh, uvs = self.fixture()
        self.assertEqual(3, compare_corners(document, mesh, uvs))

    def test_rejects_uv_flip_palette_substitution_or_lost_seam(self):
        for replacement in ([0, .25], [.0625, .0625], [.5, .25]):
            document, mesh, uvs = self.fixture()
            uvs[2] = replacement
            with self.assertRaisesRegex(ValueError, 'UV'):
                compare_corners(document, mesh, uvs)

    def test_rejects_changed_corner_normal_and_winding(self):
        document, mesh, uvs = self.fixture()
        changed = copy.deepcopy(mesh)
        changed.normal_faces[0] = [2, 1, 0]
        with self.assertRaisesRegex(ValueError, 'normal'):
            compare_corners(document, changed, uvs)
        mesh.faces[0] = [0, 2, 1]
        with self.assertRaisesRegex(ValueError, 'position'):
            compare_corners(document, mesh, uvs)

    def test_texture_decoder_preserves_orientation_channels_and_alpha(self):
        header = struct.pack('<BBBHHBHHHHBB', 0, 0, 10, 0, 0, 0, 0, 0, 2, 2, 32, 40)
        # Two distinct top pixels, one repeated bottom pixel, including alpha.
        encoded = header + bytes([1, 3, 2, 1, 4, 7, 6, 5, 8, 129, 11, 10, 9, 12])
        width, height, rgba, packets = read_texture(encoded)
        self.assertEqual((2, 2), (width, height))
        self.assertEqual(bytes([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 9, 10, 11, 12]), rgba)
        self.assertEqual({'raw': 1, 'repeated': 1}, packets)
        inverted = bytearray(encoded)
        inverted[17] = 8
        with self.assertRaisesRegex(ValueError, 'top-origin'):
            read_texture(inverted)

    def test_texture_decoder_rejects_native_invalid_scanline_and_trailing_data(self):
        header = struct.pack('<BBBHHBHHHHBB', 0, 0, 10, 0, 0, 0, 0, 0, 2, 2, 32, 40)
        with self.assertRaisesRegex(ValueError, 'scanline'):
            read_texture(header + bytes([131, 1, 2, 3, 4]))
        with self.assertRaisesRegex(ValueError, 'trailing'):
            read_texture(header + bytes([129, 1, 2, 3, 4, 129, 1, 2, 3, 4, 0]))


if __name__ == '__main__':
    unittest.main()
