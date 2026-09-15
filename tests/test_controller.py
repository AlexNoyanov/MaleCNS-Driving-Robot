import unittest

from mac.controller import (
    EMERGENCY_CM,
    clip_pwm,
    closeness,
    emergency_spin,
    hybrid_command,
)


class ControllerTests(unittest.TestCase):
    def test_stale_telemetry_zero_pwm(self):
        l, r, e = hybrid_command(100, 100, 100, 0.0, 0.0, telemetry_age_s=1.0)
        self.assertEqual((l, r, e), (0, 0, False))

    def test_missing_age_is_stale(self):
        l, r, e = hybrid_command(100, 100, 100, 0.0, 0.0, telemetry_age_s=None)
        self.assertEqual((l, r), (0, 0))

    def test_clear_path_goes_forward(self):
        l, r, e = hybrid_command(100, 100, 100, 0.0, 0.0, telemetry_age_s=0.0)
        self.assertFalse(e)
        self.assertGreater(l, 80)
        self.assertGreater(r, 80)

    def test_left_obstacle_turns_right(self):
        l, r, e = hybrid_command(80, 16, 80, 0.0, 0.0, telemetry_age_s=0.0)
        self.assertFalse(e)
        self.assertGreater(l, r)

    def test_right_obstacle_turns_left(self):
        l, r, e = hybrid_command(80, 80, 16, 0.0, 0.0, telemetry_age_s=0.0)
        self.assertFalse(e)
        self.assertGreater(r, l)

    def test_front_emergency_reverses(self):
        l, r, e = hybrid_command(8, 80, 80, 0.0, 0.0, telemetry_age_s=0.0)
        self.assertTrue(e)
        self.assertLess(l, 0)
        self.assertLess(r, 0)
        self.assertLess(8, EMERGENCY_CM)

    def test_left_emergency_spins_right(self):
        l, r = emergency_spin("left")
        self.assertGreater(l, 0)
        self.assertLess(r, 0)

    def test_manual_passthrough(self):
        l, r, e = hybrid_command(
            80, 80, 80, 0, 0, mode="manual", manual_left=40, manual_right=-15, telemetry_age_s=0.0
        )
        self.assertEqual((l, r, e), (40, -15, False))

    def test_clip(self):
        self.assertEqual(clip_pwm(400), 255)
        self.assertEqual(clip_pwm(-400), -255)

    def test_invalid_distance_zero_closeness(self):
        self.assertEqual(closeness(-1), 0.0)
        self.assertEqual(closeness(None), 0.0)
