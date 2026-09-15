"""2D kinematic stand-in for the chassis (tests + sim_robot)."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class Box:
    x0: float
    y0: float
    x1: float
    y1: float

    def contains(self, x: float, y: float) -> bool:
        return self.x0 <= x <= self.x1 and self.y0 <= y <= self.y1


@dataclass
class SimpleWorld:
    width: float = 250.0
    height: float = 250.0
    x: float = 125.0
    y: float = 40.0
    theta: float = math.pi / 2  # facing +y
    vmax: float = 40.0  # cm/s at PWM 255
    wheel_base: float = 14.0
    obstacles: List[Box] = field(default_factory=list)
    max_range: float = 200.0

    def reset_clear_path(self) -> None:
        self.x, self.y, self.theta = 125.0, 40.0, math.pi / 2
        self.obstacles = []

    def reset_front_wall(self, wall_y: float = 120.0) -> None:
        self.reset_clear_path()
        self.obstacles = [Box(0, wall_y, self.width, wall_y + 8)]

    def reset_left_obstacle(self) -> None:
        self.reset_clear_path()
        self.obstacles = [Box(85, 55, 118, 150)]

    def reset_right_obstacle(self) -> None:
        self.reset_clear_path()
        self.obstacles = [Box(140, 80, 180, 160)]

    def step(self, left_pwm: int, right_pwm: int, dt: float) -> None:
        vl = (left_pwm / 255.0) * self.vmax
        vr = (right_pwm / 255.0) * self.vmax
        v = 0.5 * (vl + vr)
        omega = (vr - vl) / max(self.wheel_base, 1e-3)
        self.theta += omega * dt
        self.x += v * math.cos(self.theta) * dt
        self.y += v * math.sin(self.theta) * dt
        self.x = min(max(self.x, 5.0), self.width - 5.0)
        self.y = min(max(self.y, 5.0), self.height - 5.0)

    def distances(self) -> Tuple[float, float, float]:
        front = self._ray(0.0)
        left = self._ray(math.radians(50))
        right = self._ray(math.radians(-50))
        return front, left, right

    def _ray(self, bearing: float) -> float:
        ang = self.theta + bearing
        dx, dy = math.cos(ang), math.sin(ang)
        step = 1.0
        dist = 0.0
        x, y = self.x, self.y
        while dist < self.max_range:
            x += dx * step
            y += dy * step
            dist += step
            if x < 0 or y < 0 or x > self.width or y > self.height:
                return dist
            for box in self.obstacles:
                if box.contains(x, y):
                    return dist
        return self.max_range
