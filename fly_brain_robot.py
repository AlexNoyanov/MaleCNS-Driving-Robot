"""
fly_brain_robot.py

Loads a subset of the MaleCNS connectome via neuprint, builds a simple
leaky-integrate-and-fire (LIF) simulation on top of the REAL synaptic
wiring, lets you monitor activity as a spike raster, and stubs out the
loop for turning distance-sensor readings into motor output.

IMPORTANT CONTEXT (read before running):
- This does not run in real time on a Raspberry Pi. Run this file on
  your PC (RTX 3060). The Pi/Arduino side only sends sensor readings
  over the network and receives back two floats (left/right wheel speed).
- The mapping from "sensor data" to specific neurons, and from specific
  neurons to "motor output", is NOT biologically validated. It's the same
  arbitrary-mapping approach used by hobbyist connectome demos (DOOMFLY,
  etc). The wiring is real; what counts as "sensory" or "motor" here is
  a placeholder you should replace once you've explored the data in
  neuPrint Explorer (https://neuprint.janelia.org) and picked real
  neuron types you want to use.
- Synapse counts in the connectome are unsigned (no + / - weight given
  directly). This script treats everything as excitatory for a first
  pass. Pulling neurotransmitter predictions per neuron and using them
  to sign the weights is a natural next step, not included here.
- fetch_adjacencies' exact return columns can vary by neuprint-python
  version. If this errors on a column name, print roi_conn_df.columns
  and adjust -- I couldn't test this against the live API from here.
"""

import os

import numpy as np
import torch
import matplotlib.pyplot as plt
from neuprint import Client, fetch_adjacencies, NeuronCriteria as NC

# ---------------------------------------------------------------------------
# 1. CONNECT + PULL CONNECTIVITY
# ---------------------------------------------------------------------------

TOKEN = os.environ.get("NEUPRINT_TOKEN")
if not TOKEN:
    raise RuntimeError(
        "This legacy script always hits neuPrint. Prefer: python -m mac.server "
        "(uses connectome_cache.npz, no token). To fetch anyway: export NEUPRINT_TOKEN=..."
    )
client = Client("https://neuprint.janelia.org", dataset="male-cns:v1.0", token=TOKEN)

# Start small and specific. The full CNS is ~166,700 neurons / ~125M
# synapses -- great for your GPU once this works, but too much to debug
# interactively at first. Pick a manageable ROI or cell-type group.
# Browse neuron types/ROIs in neuPrint Explorer before picking this.
criteria = NC(rois=["AL(R)"])  # example: right antennal lobe -- adjust freely

neurons_df, roi_conn_df = fetch_adjacencies(criteria, criteria)

# Aggregate synapse-level rows into one weight per (pre, post) neuron pair.
conn = (
    roi_conn_df.groupby(["bodyId_pre", "bodyId_post"])["weight"]
    .sum()
    .reset_index()
)

body_ids = sorted(set(conn.bodyId_pre) | set(conn.bodyId_post))
id_to_idx = {b: i for i, b in enumerate(body_ids)}
n_neurons = len(body_ids)
print(f"Simulating {n_neurons} neurons, {len(conn)} directed connections")

rows = conn.bodyId_pre.map(id_to_idx).to_numpy()
cols = conn.bodyId_post.map(id_to_idx).to_numpy()
weights = conn.weight.to_numpy(dtype=np.float32)
weights = weights / weights.max()  # raw synapse counts are large, normalize

device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Running on: {device}")

W = torch.sparse_coo_tensor(
    torch.tensor(np.stack([rows, cols])),
    torch.tensor(weights),
    size=(n_neurons, n_neurons),
).to(device)

# ---------------------------------------------------------------------------
# 2. LIF SIMULATION STATE
# ---------------------------------------------------------------------------

V = torch.zeros(n_neurons, device=device)       # membrane potential
spikes = torch.zeros(n_neurons, device=device)  # this step's spikes

V_THRESH = 1.0
V_DECAY = 0.9       # leak factor per step
INPUT_GAIN = 0.5


def step(external_input: torch.Tensor) -> torch.Tensor:
    """external_input: (n_neurons,) tensor, nonzero only at the indices
    you've designated as 'sensory' input."""
    global V, spikes
    synaptic_input = torch.sparse.mm(W.t(), spikes.unsqueeze(1)).squeeze(1)
    V = V * V_DECAY + synaptic_input + INPUT_GAIN * external_input
    spikes = (V >= V_THRESH).float()
    V = V * (1 - spikes)  # reset neurons that just fired
    return spikes


# ---------------------------------------------------------------------------
# 3. CHOOSE SENSORY + MOTOR NEURON POPULATIONS (placeholder indices)
# ---------------------------------------------------------------------------

# These are arbitrary picks for now, same approach the hobbyist connectome
# demos use. Replace with real neuron-type indices once you've explored
# the data and decided what "input" and "output" should mean here.
SENSOR_IDX = list(range(0, min(10, n_neurons)))
MOTOR_IDX = list(range(10, min(20, n_neurons)))

# ---------------------------------------------------------------------------
# 4. MONITORING: SPIKE RASTER
# ---------------------------------------------------------------------------


def run_and_plot(n_steps: int = 200):
    raster = np.zeros((n_neurons, n_steps))
    ext = torch.zeros(n_neurons, device=device)
    for t in range(n_steps):
        ext.zero_()
        ext[SENSOR_IDX] = 1.0  # constant stimulation for this demo
        s = step(ext)
        raster[:, t] = s.cpu().numpy()

    plt.figure(figsize=(10, 6))
    plt.imshow(raster, aspect="auto", cmap="Greys")
    plt.xlabel("timestep")
    plt.ylabel("neuron index")
    plt.title("Spike raster (real MaleCNS wiring, synthetic stimulation)")
    plt.tight_layout()
    plt.show()


# ---------------------------------------------------------------------------
# 5. ROBOT CONTROL LOOP (stub -- wire up your Pi/Arduino socket here)
# ---------------------------------------------------------------------------


def sensors_to_input(dist_left: float, dist_center: float, dist_right: float) -> torch.Tensor:
    ext = torch.zeros(n_neurons, device=device)
    ext[SENSOR_IDX[0]] = 1.0 / max(dist_left, 1)
    ext[SENSOR_IDX[1]] = 1.0 / max(dist_center, 1)
    ext[SENSOR_IDX[2]] = 1.0 / max(dist_right, 1)
    return ext


def readout_to_motors(s: torch.Tensor) -> tuple[float, float]:
    left_rate = s[MOTOR_IDX[:5]].mean().item()
    right_rate = s[MOTOR_IDX[5:]].mean().item()
    return left_rate, right_rate


def receive_from_pi():
    """Replace with your actual socket/HTTP read from the Pi.
    Should return (dist_left, dist_center, dist_right) in cm."""
    raise NotImplementedError


def send_to_pi(left_speed: float, right_speed: float):
    """Replace with your actual socket/HTTP send to the Pi."""
    raise NotImplementedError


def control_loop():
    while True:
        dist_left, dist_center, dist_right = receive_from_pi()
        ext = sensors_to_input(dist_left, dist_center, dist_right)
        s = step(ext)
        left_speed, right_speed = readout_to_motors(s)
        send_to_pi(left_speed, right_speed)


if __name__ == "__main__":
    # Start here: confirms the connectome loads and the sim runs at all,
    # before wiring up real hardware.
    run_and_plot()
