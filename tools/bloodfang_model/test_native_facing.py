"""Keep the native pet forward convention independent of exporter constants."""
import unittest

from native_export import PRESENTATION as EXPORTED_PRESENTATION
from validate_animation import PRESENTATION as EXPECTED_PRESENTATION, transpose
from validate_facing import check_basis


class NativeFacingTests(unittest.TestCase):
    def test_export_and_independent_pose_expectation_face_native_minus_z(self):
        self.assertEqual(1., check_basis(EXPORTED_PRESENTATION)["determinant"])
        self.assertEqual(1., check_basis(transpose(EXPECTED_PRESENTATION))["determinant"])

    def test_previous_backwards_rotation_is_rejected(self):
        backwards = [1., 0., 0., 0., 0., 0., -1., 0.,
                     0., 1., 0., 0., 0., 0., 0., 1.]
        with self.assertRaisesRegex(ValueError, "Facing contract failed"):
            check_basis(backwards)

    def test_forward_axis_only_reflection_is_rejected(self):
        reflected = [1., 0., 0., 0., 0., 0., 1., 0.,
                     0., 1., 0., 0., 0., 0., 0., 1.]
        with self.assertRaisesRegex(ValueError, "Facing contract failed"):
            check_basis(reflected)


if __name__ == "__main__":
    unittest.main()
