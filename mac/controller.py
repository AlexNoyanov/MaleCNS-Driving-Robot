"""Hybrid + failsafe wheel commands for the 2WD fly-brain robot.

The connectome dynamics are real; this mapping is engineered so the robot
turns *away* from the nearest obstacle and stops if the link goes stale.
"""

from __future__ import annotations

from typing import Optional, Tuple

EMERGENCY_CM = 12.0
STALE_TELEMETRY_S = 0.30
CRUISE = 160
K_TURN = 140.0
K_FRONT = 180.0
K_BRAIN = 90.0
K_VISION = 50.0
BACKUP_PWM = -180
SPIN_PWM = 200


def clip_pwm(v: float) -> int:
    return int(max(-255, min(255, round(v))))


def is_valid_cm(cm: Optional[float]) -> bool:
    return cm is not None and cm >= 0


def closeness(cm: Optional[float], scale: float = 90.0) -> float:
    """1 at 0 cm, 0 at `scale` cm and beyond. Invalid readings contribute 0."""
    if not is_valid_cm(cm):
        return 0.0
    return max(0.0, min(1.0, (scale - float(cm)) / scale))


def nearest_hit(front: Optional[float], left: Optional[float], right: Optional[float]):
    candidates = []
    if is_valid_cm(front):
        candidates.append(("front", float(front)))
    if is_valid_cm(left):
        candidates.append(("left", float(left)))
    if is_valid_cm(right):
        candidates.append(("right", float(right)))
    if not candidates:
        return None, None
    name, dist = min(candidates, key=lambda kv: kv[1])
    return name, dist


def emergency_spin(nearest: str) -> Tuple[int, int]:
    if nearest == "left":
        return SPIN_PWM, -SPIN_PWM  # turn right, away from left
    if nearest == "right":
        return -SPIN_PWM, SPIN_PWM  # turn left, away from right
    return BACKUP_PWM, BACKUP_PWM  # front: reverse


def hybrid_command(
    front_cm: Optional[float],
    left_cm: Optional[float],
    right_cm: Optional[float],
    left_rate: float,
    right_rate: float,
    vis_left: float = 0.0,
    vis_front: float = 0.0,
    vis_right: float = 0.0,
    mode: str = "hybrid",
    manual_left: int = 0,
    manual_right: int = 0,
    telemetry_age_s: Optional[float] = 0.0,
) -> Tuple[int, int, bool]:
    """Return (left_pwm, right_pwm, emergency).

    Failsafe: stale or missing telemetry → motors 0.
    """
    if telemetry_age_s is None or telemetry_age_s > STALE_TELEMETRY_S:
        return 0, 0, False

    nearest, dist = nearest_hit(front_cm, left_cm, right_cm)
    if nearest is not None and dist is not None and dist < EMERGENCY_CM:
        left, right = emergency_spin(nearest)
        return left, right, True

    if mode == "manual":
        return clip_pwm(manual_left), clip_pwm(manual_right), False

    left_c = closeness(left_cm) + K_VISION / max(K_TURN, 1.0) * max(0.0, vis_left)
    right_c = closeness(right_cm) + K_VISION / max(K_TURN, 1.0) * max(0.0, vis_right)
    front_c = closeness(front_cm) + K_VISION / max(K_FRONT, 1.0) * max(0.0, vis_front)

    # Positive turn_right ⇒ faster left wheel, slower right wheel ⇒ yaw right.
    turn_right = K_TURN * (left_c - right_c) + K_BRAIN * (left_rate - right_rate)
    front_brake = K_FRONT * front_c

    if mode == "brain":
        drive = 70 + 140 * (0.5 * (left_rate + right_rate))
        left_pwm = drive + turn_right - front_brake
        right_pwm = drive - turn_right - front_brake
        return clip_pwm(left_pwm), clip_pwm(right_pwm), False

    # hybrid (default) and any unknown mode
    left_pwm = CRUISE + turn_right - front_brake
    right_pwm = CRUISE - turn_right - front_brake
    return clip_pwm(left_pwm), clip_pwm(right_pwm), False
