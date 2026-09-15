"""Local 3D fly-CNS geometry for the dashboard (no neuPrint token required)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
GEOM_PATH = ROOT / "data" / "skeletons" / "geometry.json"

N_VIZ = 128
N_SILHOUETTE = 700


def default_geometry_path() -> Path:
    return GEOM_PATH


def load_or_build_geometry(body_ids: np.ndarray, path: Path | None = None) -> Dict[str, Any]:
    path = path or GEOM_PATH
    if path.exists():
        with path.open() as f:
            data = json.load(f)
        if data.get("neurons"):
            return data
    data = build_fly_cns_geometry(body_ids)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        json.dump(data, f)
    return data


def build_fly_cns_geometry(body_ids: np.ndarray, seed: int = 7) -> Dict[str, Any]:
    """Procedural male-CNS-shaped point cloud: two brain lobes + a VNC stalk.

    Used when SWC skeletons have not been cached. Stable for a given body_id list.
    """
    rng = np.random.default_rng(seed)
    n = int(len(body_ids))
    viz_count = min(N_VIZ, n)
    stride = max(1, n // viz_count)
    indices = np.arange(0, n, stride)[:viz_count]

    silhouette = _silhouette_points(rng, N_SILHOUETTE)
    neurons: List[Dict[str, Any]] = []
    for i, idx in enumerate(indices):
        region, xyz = _neuron_xyz(int(idx), int(body_ids[idx]), rng)
        neurons.append(
            {
                "index": int(idx),
                "body_id": int(body_ids[idx]),
                "x": round(float(xyz[0]), 3),
                "y": round(float(xyz[1]), 3),
                "z": round(float(xyz[2]), 3),
                "region": region,
            }
        )

    return {
        "source": "procedural_fly_cns",
        "silhouette": {
            "x": [round(float(v), 3) for v in silhouette[:, 0]],
            "y": [round(float(v), 3) for v in silhouette[:, 1]],
            "z": [round(float(v), 3) for v in silhouette[:, 2]],
        },
        "neurons": neurons,
    }


def _silhouette_points(rng: np.random.Generator, n: int) -> np.ndarray:
    n_lobe = int(n * 0.42)
    n_vnc = n - 2 * n_lobe
    left = _ellipsoid(rng, n_lobe, center=(-0.55, 0.15, 0.35), radii=(0.55, 0.42, 0.38))
    right = _ellipsoid(rng, n_lobe, center=(0.55, 0.15, 0.35), radii=(0.55, 0.42, 0.38))
    vnc = _ellipsoid(rng, n_vnc, center=(0.0, -1.15, -0.05), radii=(0.22, 0.95, 0.16))
    return np.vstack([left, right, vnc])


def _ellipsoid(rng: np.random.Generator, n: int, center, radii) -> np.ndarray:
    # Sample on and just inside an ellipsoid surface so it reads as a volume.
    u = rng.uniform(0, 2 * np.pi, n)
    v = rng.uniform(0, np.pi, n)
    r = rng.uniform(0.72, 1.0, n) ** (1 / 3)
    x = center[0] + radii[0] * r * np.cos(u) * np.sin(v)
    y = center[1] + radii[1] * r * np.sin(u) * np.sin(v)
    z = center[2] + radii[2] * r * np.cos(v)
    return np.stack([x, y, z], axis=1)


def _neuron_xyz(idx: int, body_id: int, rng: np.random.Generator):
    # Hash body_id so a given cell always sits in the same lobe.
    h = abs(int(body_id) * 2654435761) % 1000
    if h < 380:
        region = "AL_L"
        center, radii = (-0.5, 0.2, 0.4), (0.4, 0.32, 0.28)
    elif h < 760:
        region = "AL_R"
        center, radii = (0.5, 0.2, 0.4), (0.4, 0.32, 0.28)
    else:
        region = "VNC"
        center, radii = (0.0, -1.0, 0.0), (0.16, 0.7, 0.12)
    local = rng.normal(0, 1, 3)
    local = local / (np.linalg.norm(local) + 1e-6) * rng.uniform(0.1, 1.0)
    xyz = np.array(center) + np.array(radii) * local
    return region, xyz
