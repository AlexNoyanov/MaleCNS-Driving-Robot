"""Line protocol shared by Arduino firmware comments, Pi agent, and tests."""

from __future__ import annotations

from typing import Optional, Tuple


def parse_sensor_line(line: str) -> Optional[Tuple[float, float, float]]:
    line = line.strip().replace("\r", "")
    if not line.startswith("S,"):
        return None
    parts = line.split(",")
    if len(parts) != 4:
        return None
    try:
        return float(parts[1]), float(parts[2]), float(parts[3])
    except ValueError:
        return None


def format_motor_line(left: int, right: int) -> str:
    left = max(-255, min(255, int(left)))
    right = max(-255, min(255, int(right)))
    return f"M,{left},{right}\n"


def parse_motor_line(line: str) -> Optional[Tuple[int, int]]:
    line = line.strip().replace("\r", "")
    if not line.startswith("M,"):
        return None
    parts = line.split(",")
    if len(parts) != 3:
        return None
    try:
        return int(parts[1]), int(parts[2])
    except ValueError:
        return None
