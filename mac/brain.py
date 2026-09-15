"""Local MaleCNS LIF simulation on the cached synaptic graph.

Loads data/connectome_cache.npz (or connectome_cache.npz) with no network
and no neuPrint token. PyTorch sparse mm is used when available; otherwise
a NumPy COO fallback keeps the Mac demo running.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Sequence, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
CACHE_CANDIDATES = (
    ROOT / "data" / "connectome_cache.npz",
    ROOT / "connectome_cache.npz",
)

V_THRESH = 1.0
V_DECAY = 0.9
INPUT_GAIN = 0.5
ROI_CRITERIA = ["AL(R)"]


def find_cache_path() -> Optional[Path]:
    for p in CACHE_CANDIDATES:
        if p.exists():
            return p
    return None


def get_client():
    """neuPrint client — only for one-time fetch / skeleton download."""
    from neuprint import Client

    token = os.environ.get("NEUPRINT_TOKEN")
    if not token:
        raise RuntimeError(
            'Set NEUPRINT_TOKEN (https://neuprint.janelia.org → Account → Auth Token). '
            "Not needed when connectome_cache.npz already exists."
        )
    return Client("https://neuprint.janelia.org", dataset="male-cns:v1.0", token=token)


def load_connectivity(cache_path: Optional[Path] = None):
    path = cache_path or find_cache_path()
    if path is not None and path.exists():
        data = np.load(path)
        return (
            np.asarray(data["rows"]),
            np.asarray(data["cols"]),
            np.asarray(data["weights"], dtype=np.float32),
            np.asarray(data["body_ids"]),
            path,
        )

    print("No local cache found. Fetching from neuPrint (one-time, needs NEUPRINT_TOKEN)...")
    from neuprint import fetch_adjacencies, NeuronCriteria as NC

    get_client()
    criteria = NC(rois=ROI_CRITERIA)
    _neurons_df, roi_conn_df = fetch_adjacencies(criteria, criteria)
    conn = (
        roi_conn_df.groupby(["bodyId_pre", "bodyId_post"])["weight"]
        .sum()
        .reset_index()
    )
    body_ids = np.array(sorted(set(conn.bodyId_pre) | set(conn.bodyId_post)))
    id_to_idx = {b: i for i, b in enumerate(body_ids)}
    rows = conn.bodyId_pre.map(id_to_idx).to_numpy()
    cols = conn.bodyId_post.map(id_to_idx).to_numpy()
    weights = conn.weight.to_numpy(dtype=np.float32)
    weights = weights / weights.max()
    dest = ROOT / "data" / "connectome_cache.npz"
    dest.parent.mkdir(parents=True, exist_ok=True)
    np.savez(dest, rows=rows, cols=cols, weights=weights, body_ids=body_ids)
    print(f"Cached to {dest}")
    return rows, cols, weights, body_ids, dest


class FlyBrain:
    def __init__(self, cache_path: Optional[Path] = None) -> None:
        rows, cols, weights, body_ids, path = load_connectivity(cache_path)
        self.cache_path = path
        self.rows = rows.astype(np.int64)
        self.cols = cols.astype(np.int64)
        self.weights = weights.astype(np.float32)
        self.body_ids = body_ids
        self.n_neurons = int(len(body_ids))
        self.id_to_idx = {int(b): i for i, b in enumerate(body_ids)}

        n = self.n_neurons
        self.sensor_left = list(range(0, min(10, n)))
        self.sensor_front = list(range(10, min(20, n)))
        self.sensor_right = list(range(20, min(30, n)))
        self.motor_left = list(range(30, min(40, n)))
        self.motor_right = list(range(40, min(50, n)))

        self._use_torch = False
        self._W = None
        self._device = "cpu"
        try:
            import torch

            self._torch = torch
            if torch.cuda.is_available():
                self._device = "cuda"
            # MPS cannot sparse-mm; stay on CPU on Apple Silicon.
            self._W = torch.sparse_coo_tensor(
                torch.from_numpy(np.stack([self.rows, self.cols]).astype(np.int64)),
                torch.from_numpy(self.weights),
                size=(n, n),
            ).to(self._device)
            self.V = torch.zeros(n, device=self._device)
            self.spikes = torch.zeros(n, device=self._device)
            self._use_torch = True
        except Exception:
            self._torch = None
            self.V = np.zeros(n, dtype=np.float32)
            self.spikes = np.zeros(n, dtype=np.float32)

        self.raster_idx = np.linspace(0, n - 1, num=min(96, n), dtype=int)
        self._ema = np.zeros(n, dtype=np.float32)

    @property
    def device(self) -> str:
        if self._use_torch:
            return self._device
        return "numpy"

    def reset(self) -> None:
        if self._use_torch:
            self.V.zero_()
            self.spikes.zero_()
        else:
            self.V[:] = 0
            self.spikes[:] = 0
        self._ema[:] = 0

    def sensors_to_input(
        self,
        dist_left: float,
        dist_center: float,
        dist_right: float,
        vis_left: float = 0.0,
        vis_front: float = 0.0,
        vis_right: float = 0.0,
    ):
        def inj(cm: float, vis: float) -> float:
            if cm is None or cm < 0:
                sonic = 0.0
            else:
                sonic = 1.0 / max(float(cm), 1.0)
            return sonic + 0.5 * max(0.0, float(vis))

        if self._use_torch:
            ext = self._torch.zeros(self.n_neurons, device=self._device)
            v_l, v_f, v_r = inj(dist_left, vis_left), inj(dist_center, vis_front), inj(dist_right, vis_right)
            if self.sensor_left:
                ext[self.sensor_left] = v_l
            if self.sensor_front:
                ext[self.sensor_front] = v_f
            if self.sensor_right:
                ext[self.sensor_right] = v_r
            return ext
        ext = np.zeros(self.n_neurons, dtype=np.float32)
        ext[self.sensor_left] = inj(dist_left, vis_left)
        ext[self.sensor_front] = inj(dist_center, vis_front)
        ext[self.sensor_right] = inj(dist_right, vis_right)
        return ext

    def step(self, external_input) -> np.ndarray:
        if self._use_torch:
            synaptic = self._torch.sparse.mm(self._W.t(), self.spikes.unsqueeze(1)).squeeze(1)
            self.V = self.V * V_DECAY + synaptic + INPUT_GAIN * external_input
            self.spikes = (self.V >= V_THRESH).float()
            self.V = self.V * (1 - self.spikes)
            s = self.spikes.detach().cpu().numpy().astype(np.float32)
        else:
            synaptic = np.zeros(self.n_neurons, dtype=np.float32)
            np.add.at(synaptic, self.cols, self.weights * self.spikes[self.rows])
            self.V = self.V * V_DECAY + synaptic + INPUT_GAIN * external_input
            self.spikes = (self.V >= V_THRESH).astype(np.float32)
            self.V = self.V * (1.0 - self.spikes)
            s = self.spikes
        self._ema = 0.85 * self._ema + 0.15 * s
        return s

    def readout(self, spikes: Optional[np.ndarray] = None) -> Tuple[float, float]:
        s = spikes if spikes is not None else (
            self.spikes.detach().cpu().numpy() if self._use_torch else self.spikes
        )
        left = float(np.mean(s[self.motor_left])) if self.motor_left else 0.0
        right = float(np.mean(s[self.motor_right])) if self.motor_right else 0.0
        return left, right

    def raster_row(self, spikes: np.ndarray) -> list:
        return [int(v) for v in (spikes[self.raster_idx] > 0.5)]

    def activity_for_indices(self, indices: Sequence[int]) -> list:
        return [round(float(self._ema[i]), 4) for i in indices]
