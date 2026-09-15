#!/usr/bin/env python3
"""Optional one-time skeleton download for richer 3D (needs NEUPRINT_TOKEN).

If the token is unset, writes a procedural fly-CNS point cloud from the
local connectome cache so the dashboard stays fully offline.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mac.brain import load_connectivity  # noqa: E402
from mac.geometry import GEOM_PATH, build_fly_cns_geometry, load_or_build_geometry  # noqa: E402


def fetch_navis_subset(body_ids, n: int = 80):
    import navis
    import navis.interfaces.neuprint as neu
    from mac.brain import get_client

    client = get_client()
    stride = max(1, len(body_ids) // n)
    subset = [int(b) for b in body_ids[::stride][:n]]
    print(f"Fetching {len(subset)} skeletons from neuPrint…")
    skels = neu.fetch_skeletons(subset, client=client)
    neurons = []
    for skel in skels:
        nodes = getattr(skel, "nodes", None)
        if nodes is None or len(nodes) == 0:
            continue
        # navis NodeTable typically has x, y, z
        xs = nodes["x"].to_numpy()
        ys = nodes["y"].to_numpy()
        zs = nodes["z"].to_numpy()
        # downsample polyline
        step = max(1, len(xs) // 40)
        neurons.append(
            {
                "index": int(list(body_ids).index(int(skel.id))) if int(skel.id) in set(map(int, body_ids)) else 0,
                "body_id": int(skel.id),
                "x": float(xs[::step].mean()),
                "y": float(ys[::step].mean()),
                "z": float(zs[::step].mean()),
                "region": "cached_swc",
                "polyline": {
                    "x": [float(v) for v in xs[::step]],
                    "y": [float(v) for v in ys[::step]],
                    "z": [float(v) for v in zs[::step]],
                },
            }
        )
    # Normalize coordinates into ~[-1.5, 1.5]
    import numpy as np

    pts = np.array([[n["x"], n["y"], n["z"]] for n in neurons])
    center = pts.mean(axis=0)
    scale = (np.abs(pts - center).max() + 1e-6)
    sil_x, sil_y, sil_z = [], [], []
    for n in neurons:
        n["x"] = (n["x"] - center[0]) / scale
        n["y"] = (n["y"] - center[1]) / scale
        n["z"] = (n["z"] - center[2]) / scale
        if "polyline" in n:
            n["polyline"]["x"] = [(v - center[0]) / scale for v in n["polyline"]["x"]]
            n["polyline"]["y"] = [(v - center[1]) / scale for v in n["polyline"]["y"]]
            n["polyline"]["z"] = [(v - center[2]) / scale for v in n["polyline"]["z"]]
            sil_x.extend(n["polyline"]["x"])
            sil_y.extend(n["polyline"]["y"])
            sil_z.extend(n["polyline"]["z"])
    return {
        "source": "navis_neuprint_cache",
        "silhouette": {"x": sil_x[::3], "y": sil_y[::3], "z": sil_z[::3]},
        "neurons": neurons,
    }


def main() -> None:
    _rows, _cols, _w, body_ids, cache = load_connectivity()
    print(f"Connectome cache: {cache} ({len(body_ids)} neurons)")
    GEOM_PATH.parent.mkdir(parents=True, exist_ok=True)
    if os.environ.get("NEUPRINT_TOKEN"):
        try:
            data = fetch_navis_subset(body_ids)
            GEOM_PATH.write_text(json.dumps(data))
            print(f"Wrote neuPrint skeletons → {GEOM_PATH}")
            return
        except Exception as exc:
            print(f"Skeleton fetch failed ({exc}); writing procedural geometry instead")
    data = load_or_build_geometry(body_ids, GEOM_PATH)
    print(f"Wrote local geometry ({data.get('source')}) → {GEOM_PATH}")


if __name__ == "__main__":
    main()
