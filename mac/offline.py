"""Offline matplotlib checks (no robot, no dashboard)."""

from __future__ import annotations

import numpy as np

from mac.brain import FlyBrain
from mac.controller import hybrid_command


def make_scenario(name: str, n_steps: int = 200):
    if name == "clear_path":
        left = center = right = np.full(n_steps, 100.0)
    elif name == "approaching_wall":
        center = np.linspace(100, 5, n_steps)
        left = np.full(n_steps, 100.0)
        right = np.full(n_steps, 100.0)
    elif name == "obstacle_left":
        left = np.linspace(100, 5, n_steps)
        center = np.full(n_steps, 100.0)
        right = np.full(n_steps, 100.0)
    elif name == "obstacle_right":
        right = np.linspace(100, 5, n_steps)
        center = np.full(n_steps, 100.0)
        left = np.full(n_steps, 100.0)
    else:
        raise ValueError(name)
    return left, center, right


def test_fixed_distances(dist_left: float, dist_center: float, dist_right: float, n_steps: int = 200):
    brain = FlyBrain()
    left = np.full(n_steps, float(dist_left))
    center = np.full(n_steps, float(dist_center))
    right = np.full(n_steps, float(dist_right))
    return _plot(brain, left, center, right, f"L={dist_left} F={dist_center} R={dist_right}")


def run_sensor_scenario(name: str = "approaching_wall", n_steps: int = 200):
    brain = FlyBrain()
    left, center, right = make_scenario(name, n_steps)
    return _plot(brain, left, center, right, name)


def _plot(brain: FlyBrain, left, center, right, title: str):
    import matplotlib.pyplot as plt

    n_steps = len(left)
    raster = np.zeros((brain.n_neurons, n_steps))
    lp = np.zeros(n_steps)
    rp = np.zeros(n_steps)
    for t in range(n_steps):
        ext = brain.sensors_to_input(left[t], center[t], right[t])
        s = brain.step(ext)
        raster[:, t] = s
        lr, rr = brain.readout(s)
        lp[t], rp[t], _ = hybrid_command(center[t], left[t], right[t], lr, rr, telemetry_age_s=0.0)

    fig, axes = plt.subplots(3, 1, figsize=(10, 9), sharex=True, gridspec_kw={"height_ratios": [1, 3, 1]})
    axes[0].plot(left, label="left")
    axes[0].plot(center, label="front")
    axes[0].plot(right, label="right")
    axes[0].set_ylabel("cm")
    axes[0].set_title(title)
    axes[0].legend(fontsize="small")
    axes[1].imshow(raster, aspect="auto", cmap="Greys")
    axes[1].set_ylabel("neuron")
    axes[2].plot(lp, label="left pwm")
    axes[2].plot(rp, label="right pwm")
    axes[2].legend(fontsize="small")
    axes[2].set_xlabel("step")
    plt.tight_layout()
    plt.show()
    return raster, lp, rp


if __name__ == "__main__":
    test_fixed_distances(50, 5, 50)
