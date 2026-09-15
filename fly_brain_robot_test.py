"""
fly_brain_robot.py

Loads a subset of the MaleCNS connectome (cached locally after the first
run), builds a simple leaky-integrate-and-fire (LIF) simulation on top of
the REAL synaptic wiring, lets you monitor activity as a spike raster, and
stubs out the loop for turning distance-sensor readings into motor output.

IMPORTANT CONTEXT (read before running):
- This does not run in real time on a Raspberry Pi. Run this file on
  your PC (RTX 3060) once you've prototyped it on the Mac. The Pi/Arduino
  side only sends sensor readings over the network and receives back two
  floats (left/right wheel speed).
- After the first successful run, the connectome data is cached to
  CACHE_PATH on disk. Every run after that loads straight from disk --
  no network call, no neuprint dependency at runtime. Delete the cache
  file (or bump ROI_CRITERIA) to force a fresh fetch.
- PyTorch's Apple Silicon GPU backend (MPS) does not support sparse
  tensors as of this writing -- it's an open, unresolved PyTorch
  limitation, not something fixable here. Since the connectivity matrix
  must stay sparse (a dense 166k x 166k matrix would be well over 100GB),
  this script always runs the sparse connectivity matmul on CPU unless
  CUDA is available (i.e. on your PC with the RTX 3060). On the Mac,
  that means CPU-only, which is fine for a small ROI but won't scale to
  the full connectome for real-time control -- that's what the PC is for.
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

# ---------------------------------------------------------------------------
# 1. CONNECTIVITY: LOAD FROM LOCAL CACHE, OR FETCH + CACHE ON FIRST RUN
# ---------------------------------------------------------------------------

CACHE_PATH = "connectome_cache.npz"
ROI_CRITERIA = ["AL(R)"]  # example: right antennal lobe -- adjust freely


_client = None  # holds a real reference so it isn't garbage-collected


def get_client():
    """Creates (or reuses) the neuprint client, only when actually needed --
    i.e. only when fetching connectivity for the first time, or fetching
    3D skeletons for plot_3d_activity. Not needed at all if you're just
    re-running the LIF sim from a cached connectome."""
    global _client
    if _client is not None:
        return _client

    from neuprint import Client

    token = os.environ.get("NEUPRINT_TOKEN")
    if not token:
        raise RuntimeError(
            'Set your neuprint token first: export NEUPRINT_TOKEN="..." '
            "(get it from https://neuprint.janelia.org -> Account -> Auth Token)"
        )
    _client = Client("https://neuprint.janelia.org", dataset="male-cns:v1.0", token=token)
    return _client


def load_connectivity():
    if os.path.exists(CACHE_PATH):
        print(f"Loading cached connectome from {CACHE_PATH} (no network needed)")
        data = np.load(CACHE_PATH)
        return data["rows"], data["cols"], data["weights"], data["body_ids"]

    print("No local cache found. Fetching from neuprint (one-time, needs network)...")
    from neuprint import fetch_adjacencies, NeuronCriteria as NC

    get_client()  # populates the cached client used implicitly by fetch_adjacencies below

    # Start small and specific. The full CNS is ~166,700 neurons / ~125M
    # synapses -- great for the PC's GPU once this works, but too much to
    # debug interactively at first. Browse neuron types/ROIs in neuPrint
    # Explorer before picking this.
    criteria = NC(rois=ROI_CRITERIA)
    neurons_df, roi_conn_df = fetch_adjacencies(criteria, criteria)

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
    weights = weights / weights.max()  # raw synapse counts are large, normalize

    np.savez(CACHE_PATH, rows=rows, cols=cols, weights=weights, body_ids=body_ids)
    print(f"Cached to {CACHE_PATH} -- future runs won't touch the network.")
    return rows, cols, weights, body_ids


rows, cols, weights, body_ids = load_connectivity()
id_to_idx = {b: i for i, b in enumerate(body_ids)}
n_neurons = len(body_ids)
print(f"Simulating {n_neurons} neurons, {len(rows)} directed connections")

# Sparse tensor ops aren't supported on Apple's MPS backend (see note at
# top of file), so this only ever uses CUDA (your PC) or CPU (the Mac).
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Running on: {device}" + (" (CPU-only on this machine -- expected on M1)" if device == "cpu" else ""))

W = torch.sparse_coo_tensor(
    torch.from_numpy(np.stack([rows, cols]).astype(np.int64)),
    torch.from_numpy(weights.astype(np.float32)),
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
    return raster


def run_and_plot_live(n_steps: int = 200):
    """Same as run_and_plot, but updates the raster on screen as it runs
    instead of only showing it at the end. Slower (redraws every step) but
    much more useful for tuning V_THRESH/V_DECAY/INPUT_GAIN interactively."""
    plt.ion()
    fig, ax = plt.subplots(figsize=(10, 6))
    raster = np.zeros((n_neurons, n_steps))
    img = ax.imshow(raster, aspect="auto", cmap="Greys", vmin=0, vmax=1)
    ax.set_xlabel("timestep")
    ax.set_ylabel("neuron index")
    ax.set_title("Live spike raster")

    ext = torch.zeros(n_neurons, device=device)
    for t in range(n_steps):
        ext.zero_()
        ext[SENSOR_IDX] = 1.0
        s = step(ext)
        raster[:, t] = s.cpu().numpy()
        img.set_data(raster)
        plt.pause(0.001)

    plt.ioff()
    plt.show()
    return raster


def plot_3d_activity(raster: np.ndarray):
    """Maps total spike counts per neuron onto their real 3D shapes, using
    navis. This is the useful one: instead of an abstract grid, you see
    WHERE in the actual brain volume activity concentrated.

    Requires navis + navis.interfaces.neuprint (installed via navis[all]).
    Note: fetching skeletons for a large neuron count is slow the first
    time; keep your test ROI small while iterating.
    """
    import navis
    import navis.interfaces.neuprint as neu
    import matplotlib.cm as cm
    import matplotlib.colors as mcolors

    total_spikes = raster.sum(axis=1)  # spikes per neuron across the whole run
    vmax = total_spikes.max() if total_spikes.max() > 0 else 1
    norm = mcolors.Normalize(vmin=0, vmax=vmax)
    cmap = cm.get_cmap("plasma")

    skeletons = neu.fetch_skeletons(body_ids, client=get_client())

    idx_by_id = id_to_idx
    for skel in skeletons:
        i = idx_by_id.get(skel.id)
        activity = total_spikes[i] if i is not None else 0
        skel.color = cmap(norm(activity))

    # backend="plotly" opens an interactive browser view you can rotate/zoom
    navis.plot3d(skeletons, backend="plotly")


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


# ---------------------------------------------------------------------------
# SENSOR SCENARIOS -- exercise sensor -> brain -> motor with fake data,
# no hardware needed yet
# ---------------------------------------------------------------------------


def make_scenario(name: str, n_steps: int = 200):
    """Returns synthetic (left, center, right) distance readings in cm for
    a test scenario, standing in for your 3 real distance sensors."""
    if name == "clear_path":
        left = center = right = np.full(n_steps, 100.0)
    elif name == "approaching_wall":
        # something dead ahead getting closer, sides stay clear
        center = np.linspace(100, 5, n_steps)
        left = np.full(n_steps, 100.0)
        right = np.full(n_steps, 100.0)
    elif name == "obstacle_left":
        # something on the left getting closer, ahead/right stay clear
        left = np.linspace(100, 5, n_steps)
        center = np.full(n_steps, 100.0)
        right = np.full(n_steps, 100.0)
    elif name == "obstacle_right":
        right = np.linspace(100, 5, n_steps)
        center = np.full(n_steps, 100.0)
        left = np.full(n_steps, 100.0)
    else:
        raise ValueError(f"unknown scenario: {name!r}")
    return left, center, right


def _run_and_plot_sensor_trace(left, center, right, title: str):
    """Shared core: feeds arrays of (left, center, right) distance readings
    through the network step by step and plots sensor input, spike raster,
    and motor readout together. Used by both run_sensor_scenario (presets)
    and test_fixed_distances (your own numbers)."""
    n_steps = len(left)
    raster = np.zeros((n_neurons, n_steps))
    left_speeds = np.zeros(n_steps)
    right_speeds = np.zeros(n_steps)

    for t in range(n_steps):
        ext = sensors_to_input(left[t], center[t], right[t])
        s = step(ext)
        raster[:, t] = s.cpu().numpy()
        left_speeds[t], right_speeds[t] = readout_to_motors(s)

    fig, axes = plt.subplots(
        3, 1, figsize=(10, 9), sharex=True,
        gridspec_kw={"height_ratios": [1, 3, 1]},
    )

    axes[0].plot(left, label="left")
    axes[0].plot(center, label="center")
    axes[0].plot(right, label="right")
    axes[0].set_ylabel("distance (cm)")
    axes[0].set_title(f"Sensor input -- {title}")
    axes[0].legend(loc="upper right", fontsize="small")

    axes[1].imshow(raster, aspect="auto", cmap="Greys")
    axes[1].set_ylabel("neuron index")
    axes[1].set_title("Resulting spike raster")

    axes[2].plot(left_speeds, label="left wheel")
    axes[2].plot(right_speeds, label="right wheel")
    axes[2].set_xlabel("timestep")
    axes[2].set_ylabel("motor readout")
    axes[2].set_title("Motor output (placeholder MOTOR_IDX readout)")
    axes[2].legend(loc="upper right", fontsize="small")

    plt.tight_layout()
    plt.show()
    return raster, left_speeds, right_speeds


def run_sensor_scenario(name: str = "approaching_wall", n_steps: int = 200):
    """Feeds a synthetic sensor scenario through the network step by step
    and plots sensor input, the resulting spike raster, and the motor
    readout together, so you can see the whole sensor -> brain -> motor
    pipeline working before any real hardware is connected.

    NOTE: SENSOR_IDX/MOTOR_IDX are still the placeholder neuron indices
    from section 3, so the "response" here is exercising the mechanics
    of the pipeline, not demonstrating anything biologically meaningful
    yet. Swap those for real neuron-type indices once you've explored
    the data in neuPrint Explorer.
    """
    left, center, right = make_scenario(name, n_steps)
    return _run_and_plot_sensor_trace(left, center, right, title=f"scenario: {name}")


def test_fixed_distances(dist_left: float, dist_center: float, dist_right: float, n_steps: int = 200):
    """Hold your own 3 distance readings (in cm) constant for the whole
    run and watch how the network responds. This is the quickest way to
    manually explore behavior, e.g.:

        test_fixed_distances(dist_left=50, dist_center=5, dist_right=50)

    simulates being right up against something dead ahead while the
    sides stay clear. Smaller number = closer/more urgent (matches how
    a real distance sensor reads: low value = close object).
    """
    left = np.full(n_steps, float(dist_left))
    center = np.full(n_steps, float(dist_center))
    right = np.full(n_steps, float(dist_right))
    title = f"left={dist_left}cm, center={dist_center}cm, right={dist_right}cm (held constant)"
    return _run_and_plot_sensor_trace(left, center, right, title=title)


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
    raster = run_and_plot()

    # Once the basic raster looks reasonable, try these:
    # raster = run_and_plot_live()      # watch it run, better for tuning
    # plot_3d_activity(raster)          # see activity on the real anatomy

    # See the full sensor -> brain -> motor pipeline with fake sensor data:
    # run_sensor_scenario("approaching_wall")
    # run_sensor_scenario("obstacle_left")
    # run_sensor_scenario("obstacle_right")
    # run_sensor_scenario("clear_path")

    # Or set your own 3 distance readings directly (cm, lower = closer):
    # test_fixed_distances(dist_left=50, dist_center=5, dist_right=50)
