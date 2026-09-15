import unittest

from mac.controller import hybrid_command
from mac.world import SimpleWorld


class ClosedLoopTests(unittest.TestCase):
    def test_does_not_drive_through_front_wall(self):
        world = SimpleWorld()
        world.reset_front_wall(wall_y=110)
        hit = False
        min_front = 999.0
        for _ in range(500):
            front, left, right = world.distances()
            min_front = min(min_front, front)
            lp, rp, _em = hybrid_command(front, left, right, 0.0, 0.0, telemetry_age_s=0.0)
            world.step(lp, rp, 0.05)
            if any(b.contains(world.x, world.y) for b in world.obstacles):
                hit = True
                break
        self.assertFalse(hit, f"robot entered the wall at x={world.x:.1f} y={world.y:.1f}")
        self.assertLess(min_front, 30.0)

    def test_left_obstacle_yaws_right(self):
        world = SimpleWorld()
        world.reset_left_obstacle()
        theta0 = world.theta
        min_left = 999.0
        min_theta = theta0
        for _ in range(12):
            front, left, right = world.distances()
            if left >= 0:
                min_left = min(min_left, left)
            lp, rp, _ = hybrid_command(front, left, right, 0.0, 0.0, telemetry_age_s=0.0)
            world.step(lp, rp, 0.05)
            min_theta = min(min_theta, world.theta)
        self.assertLess(min_left, 40.0)
        # Facing +y, a right turn decreases heading while the left obstacle is in view.
        self.assertLess(min_theta, theta0 - 0.15)

    def test_disconnect_failsafe_stops_motion(self):
        world = SimpleWorld()
        world.reset_clear_path()
        x0, y0 = world.x, world.y
        for _ in range(30):
            front, left, right = world.distances()
            lp, rp, _ = hybrid_command(front, left, right, 0.0, 0.0, telemetry_age_s=1.0)
            self.assertEqual((lp, rp), (0, 0))
            world.step(lp, rp, 0.05)
        self.assertAlmostEqual(world.x, x0, places=3)
        self.assertAlmostEqual(world.y, y0, places=3)

    def test_arduino_watchdog_style_stop(self):
        """If motor commands freeze, the sim (like Arduino) zeros PWM after 200 ms."""
        world = SimpleWorld()
        world.reset_clear_path()
        world.step(200, 200, 0.15)
        y_moving = world.y
        last_cmd = 0.0
        # 250 ms with no new command
        dt = 0.05
        age = 0.0
        while age < 0.25:
            pwm = (200, 200) if age < 0.20 else (0, 0)
            world.step(*pwm, dt)
            age += dt
            last_cmd = pwm
        self.assertEqual(last_cmd, (0, 0))
        self.assertGreater(y_moving, 40.0)
