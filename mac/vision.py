"""Cheap camera → 3 visual closeness values (left / front / right strips)."""

from __future__ import annotations

import io
from typing import Optional, Tuple

import numpy as np


def visual_closeness(jpeg: Optional[bytes]) -> Tuple[float, float, float]:
    """Return (left, front, right) in 0..1 from edge energy in three strips.

    Invalid / missing frames → (0, 0, 0).
    """
    if not jpeg:
        return 0.0, 0.0, 0.0
    try:
        from PIL import Image
    except ImportError:
        return 0.0, 0.0, 0.0
    try:
        img = Image.open(io.BytesIO(jpeg)).convert("L")
        img = img.resize((96, 64))
        arr = np.asarray(img, dtype=np.float32)
    except Exception:
        return 0.0, 0.0, 0.0
    h, w = arr.shape
    w3 = max(1, w // 3)
    strips = (arr[:, :w3], arr[:, w3 : 2 * w3], arr[:, 2 * w3 :])
    energies = [_edge_energy(s) for s in strips]
    peak = max(energies) if energies else 0.0
    if peak <= 1e-6:
        return 0.0, 0.0, 0.0
    # Modest 0..0.6 range so ultrasonics remain the main range signal.
    scaled = [min(0.6, 0.6 * (e / peak) * min(1.0, e / 12.0)) for e in energies]
    left, front, right = scaled
    return float(left), float(front), float(right)


def _edge_energy(strip: np.ndarray) -> float:
    if strip.size < 4:
        return 0.0
    dx = np.abs(np.diff(strip, axis=1)).mean() if strip.shape[1] > 1 else 0.0
    dy = np.abs(np.diff(strip, axis=0)).mean() if strip.shape[0] > 1 else 0.0
    return float(dx + dy)
