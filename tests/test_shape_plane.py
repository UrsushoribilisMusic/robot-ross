"""Check emitted relative moves without constructing a serial connection."""
import importlib.util
from pathlib import Path
import re
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('shape_plane_under_test', Path(__file__).resolve().parents[1] / 'skills/huenit/huenit_draw.py')
draw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(draw)


class FakeArm:
    def __init__(self):
        self.commands = []

    def send(self, command, **kwargs):
        self.commands.append(command)

    def wait_motion(self):
        pass


class ShapePlaneTests(unittest.TestCase):
    def setUp(self):
        for key, value in [('TILT_SLOPE_X', .01), ('TILT_SLOPE', .035), ('Z_UP', 3.)]:
            change = patch.object(draw, key, value)
            change.start()
            self.addCleanup(change.stop)
        self.serial = patch.object(draw.serial, 'Serial', side_effect=AssertionError('Tests must never open a serial port'))
        self.serial.start()
        self.addCleanup(self.serial.stop)

    def test_x_only_moves_apply_saved_x_slope_in_both_directions(self):
        arm = FakeArm()
        draw.draw_to(arm, 40, 0)
        draw.draw_to(arm, -40, 0)
        self.assertIn(' Z0.400 ', arm.commands[0])
        self.assertIn(' Z-0.400 ', arm.commands[1])

    def test_diagonal_travel_combines_both_slopes(self):
        arm = FakeArm()
        draw.move_to(arm, -20, -20)
        self.assertIn(' Z-0.900 ', arm.commands[0])

    def test_y_only_and_flat_plane_behavior_retained(self):
        arm = FakeArm()
        draw.draw_to(arm, 0, 40)
        self.assertIn(' Z1.400 ', arm.commands[0])
        with patch.object(draw, 'TILT_SLOPE_X', 0), patch.object(draw, 'TILT_SLOPE', 0):
            draw.draw_to(arm, 40, 40)
        self.assertNotIn(' Z', arm.commands[1])

    def test_square_returns_to_same_xyz_without_accumulated_plane_offset(self):
        arm = FakeArm()
        draw.move_to(arm, -20, -20)
        draw.draw_square(arm, 40)
        draw.move_to(arm, 20, 20)
        position = dict(X=0., Y=0., Z=0.)
        for command in arm.commands:
            for axis, number in re.findall(r'([XYZ])(-?\d+(?:\.\d+)?)', command):
                position[axis] += float(number)
        for axis in position:
            self.assertAlmostEqual(position[axis], 0., places=6)
        self.assertIn(' Z-3.00 ', arm.commands[1])
        self.assertIn(' Z3.00 ', arm.commands[-2])


if __name__ == '__main__':
    unittest.main()
