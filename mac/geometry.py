"""Local 3D fly-CNS geometry for the dashboard (no neuPrint token required)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
GEOM_PATH = ROOT / "data" / "skeletons" / "geometry.json"
MESH_PATH = ROOT / "data" / "skeletons" / "brain_mesh.json"
LAYOUT_VERSION = 3

N_VIZ = 160
N_SILHOUETTE = 500


def default_geometry_path() -> Path:
    return GEOM_PATH


def load_or_build_geometry(body_ids: np.ndarray, path: Path | None = None) -> Dict[str, Any]:
    path = path or GEOM_PATH
    if path.exists():
        with path.open() as f:
            data = json.load(f)
        if data.get("layout_version") == LAYOUT_VERSION and data.get("neurons"):
            return data
    data = build_fly_cns_geometry(body_ids)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        json.dump(data, f)
    return data


def build_fly_cns_geometry(body_ids: np.ndarray, seed: int = 7) -> Dict[str, Any]:
    """Place I/O neurons on a fly-CNS layout that matches the navis neuropil mesh.

    Sensory/motor indices 0–49 match FlyBrain in mac/brain.py so those cells
    actually light up. Extra cells fill the two antennal lobes + VNC.
    """
    rng = np.random.default_rng(seed)
    n = int(len(body_ids))

    neurons: List[Dict[str, Any]] = []
    used = set()

    def add_cluster(indices, region: str, role: str, center, radii, jitter=0.12):
        for k, idx in enumerate(indices):
            if idx >= n or idx in used:
                continue
            used.add(idx)
            off = rng.normal(0, jitter, 3)
            xyz = np.array(center, dtype=float) + np.array(radii) * np.clip(off, -1, 1)
            neurons.append(
                {
                    "index": int(idx),
                    "body_id": int(body_ids[idx]),
                    "x": round(float(xyz[0]), 4),
                    "y": round(float(xyz[1]), 4),
                    "z": round(float(xyz[2]), 4),
                    "region": region,
                    "role": role,
                }
            )

    # Same index ranges as FlyBrain.sensor_* / motor_*
    add_cluster(range(0, min(10, n)), "AL_L", "sensor_left", (-0.55, 0.05, 0.15), (0.22, 0.14, 0.16))
    add_cluster(range(10, min(20, n)), "AL_C", "sensor_front", (0.0, 0.22, 0.28), (0.18, 0.12, 0.14))
    add_cluster(range(20, min(30, n)), "AL_R", "sensor_right", (0.55, 0.05, 0.15), (0.22, 0.14, 0.16))
    add_cluster(range(30, min(40, n)), "VNC_L", "motor_left", (-0.12, -0.55, -0.35), (0.1, 0.28, 0.1))
    add_cluster(range(40, min(50, n)), "VNC_R", "motor_right", (0.12, -0.55, -0.35), (0.1, 0.28, 0.1))

    leftover = [i for i in range(n) if i not in used]
    need = max(0, min(N_VIZ, n) - len(neurons))
    if leftover and need:
        pick = leftover[:: max(1, len(leftover) // need)][:need]
        for idx in pick:
            h = abs(int(body_ids[idx]) * 2654435761) % 1000
            if h < 400:
                region, center, radii = "AL_L", (-0.5, 0.0, 0.1), (0.35, 0.22, 0.22)
            elif h < 800:
                region, center, radii = "AL_R", (0.5, 0.0, 0.1), (0.35, 0.22, 0.22)
            else:
                region, center, radii = "VNC", (0.0, -0.6, -0.3), (0.14, 0.4, 0.12)
            local = rng.normal(0, 1, 3)
            local = local / (np.linalg.norm(local) + 1e-6) * rng.uniform(0.15, 1.0)
            xyz = np.array(center) + np.array(radii) * local
            neurons.append(
                {
                    "index": int(idx),
                    "body_id": int(body_ids[idx]),
                    "x": round(float(xyz[0]), 4),
                    "y": round(float(xyz[1]), 4),
                    "z": round(float(xyz[2]), 4),
                    "region": region,
                    "role": "hidden",
                }
            )

    sil = _silhouette_points(rng, N_SILHOUETTE)
    return {
        "source": "navis_neuropil_plus_io_layout",
        "layout_version": LAYOUT_VERSION,
        "silhouette": {
            "x": [round(float(v), 3) for v in sil[:, 0]],
            "y": [round(float(v), 3) for v in sil[:, 1]],
            "z": [round(float(v), 3) for v in sil[:, 2]],
        },
        "neurons": neurons,
        "mesh_url": "/api/brain-mesh",
    }


def _silhouette_points(rng: np.random.Generator, n: int) -> np.ndarray:
    n_lobe = int(n * 0.42)
    n_vnc = n - 2 * n_lobe
    left = _ellipsoid(rng, n_lobe, center=(-0.55, 0.05, 0.12), radii=(0.5, 0.32, 0.28))
    right = _ellipsoid(rng, n_lobe, center=(0.55, 0.05, 0.12), radii=(0.5, 0.32, 0.28))
    vnc = _ellipsoid(rng, n_vnc, center=(0.0, -0.7, -0.28), radii=(0.16, 0.55, 0.14))
    return np.vstack([left, right, vnc])


def _ellipsoid(rng: np.random.Generator, n: int, center, radii) -> np.ndarray:
    u = rng.uniform(0, 2 * np.pi, n)
    v = rng.uniform(0, np.pi, n)
    r = rng.uniform(0.72, 1.0, n) ** (1 / 3)
    x = center[0] + radii[0] * r * np.cos(u) * np.sin(v)
    y = center[1] + radii[1] * r * np.sin(u) * np.sin(v)
    z = center[2] + radii[2] * r * np.cos(v)
    return np.stack([x, y, z], axis=1)
