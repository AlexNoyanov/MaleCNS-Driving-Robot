const pills = {
  brain: document.querySelector('[data-k="brain"]'),
  wifi: document.querySelector('[data-k="wifi"]'),
  serial: document.querySelector('[data-k="serial"]'),
  camera: document.querySelector('[data-k="camera"]'),
};

let geometry = null;
let brainReady = false;
const rasterCanvas = document.getElementById("raster");
const ctx = rasterCanvas.getContext("2d");

async function init() {
  const g = await fetch("/api/geometry").then((r) => r.json());
  geometry = g;
  const sil = g.silhouette || { x: [], y: [], z: [] };
  const neu = g.neurons || [];
  const traceSil = {
    type: "scatter3d",
    mode: "markers",
    x: sil.x, y: sil.y, z: sil.z,
    marker: { size: 2, color: "rgba(90,110,140,0.35)" },
    hoverinfo: "skip",
    name: "CNS outline",
  };
  const traceN = {
    type: "scatter3d",
    mode: "markers",
    x: neu.map((n) => n.x),
    y: neu.map((n) => n.y),
    z: neu.map((n) => n.z),
    marker: { size: 5, color: neu.map(() => 0), colorscale: "Hot", cmin: 0, cmax: 1, line: { width: 0 } },
    text: neu.map((n) => `${n.region} · ${n.body_id}`),
    name: "neurons",
  };
  Plotly.newPlot("brain3d", [traceSil, traceN], {
    paper_bgcolor: "#10141c",
    plot_bgcolor: "#10141c",
    margin: { l: 0, r: 0, t: 0, b: 0 },
    scene: {
      bgcolor: "#10141c",
      xaxis: { visible: false },
      yaxis: { visible: false },
      zaxis: { visible: false },
      camera: { eye: { x: 1.6, y: 1.4, z: 0.9 } },
    },
    showlegend: false,
  }, { displayModeBar: false, responsive: true });
  brainReady = true;
  document.getElementById("geom-hint").textContent =
    (g.source === "procedural_fly_cns" ? "Procedural local CNS (offline) · " : "Cached skeletons · ") +
    neu.length + " tracked neurons";
}

function setPill(el, on, bad) {
  el.classList.toggle("on", !!on && !bad);
  el.classList.toggle("bad", !!bad);
}

function distBar(cm) {
  if (cm == null || cm < 0) return 0;
  return Math.max(0, Math.min(100, (80 - cm) / 80 * 100));
}

function fmtCm(cm) {
  if (cm == null || cm < 0) return "miss";
  return cm.toFixed(0) + " cm";
}

function drawRaster(rows) {
  const w = rasterCanvas.width;
  const h = rasterCanvas.height;
  ctx.fillStyle = "#05070a";
  ctx.fillRect(0, 0, w, h);
  if (!rows || !rows.length) return;
  const cols = rows.length;
  const nr = rows[0].length;
  const cw = w / cols;
  const ch = h / nr;
  ctx.fillStyle = "#f5c542";
  for (let t = 0; t < cols; t++) {
    const col = rows[t];
    for (let i = 0; i < nr; i++) {
      if (col[i]) ctx.fillRect(t * cw, i * ch, Math.max(1, cw), Math.max(1, ch * 0.8));
    }
  }
}

function applyState(s) {
  setPill(pills.brain, s.sim_hz > 1, false);
  setPill(pills.wifi, s.robot_connected, s.robot_connected && s.telemetry_age_s > 0.4);
  setPill(pills.serial, s.serial_ok, s.robot_connected && !s.serial_ok);
  setPill(pills.camera, s.camera_ok, s.robot_connected && !s.camera_ok);

  document.getElementById("bar-l").style.width = distBar(s.left_cm) + "%";
  document.getElementById("bar-f").style.width = distBar(s.front_cm) + "%";
  document.getElementById("bar-r").style.width = distBar(s.right_cm) + "%";
  document.getElementById("txt-l").textContent = fmtCm(s.left_cm);
  document.getElementById("txt-f").textContent = fmtCm(s.front_cm);
  document.getElementById("txt-r").textContent = fmtCm(s.right_cm);

  document.getElementById("m-l").value = s.left_pwm;
  document.getElementById("m-r").value = s.right_pwm;
  document.getElementById("pwm-l").textContent = s.left_pwm;
  document.getElementById("pwm-r").textContent = s.right_pwm;

  document.getElementById("emergency").classList.toggle("show", !!s.emergency);
  document.getElementById("manual-box").classList.toggle("show", s.mode === "manual");
  document.getElementById("mode-tag").textContent = s.robot_connected ? s.mode : s.mode + " · idle demo";

  document.getElementById("st-hz").textContent = (s.sim_hz || 0) + " Hz";
  document.getElementById("st-n").textContent = s.n_neurons;
  document.getElementById("st-syn").textContent = (s.n_synapses || 0).toLocaleString();
  document.getElementById("st-spk").textContent = (s.spike_rate || 0).toFixed(3);
  document.getElementById("st-age").textContent = s.robot_connected ? (s.telemetry_age_s || 0).toFixed(2) + " s" : "no Pi";
  document.getElementById("st-rssi").textContent = s.wifi_rssi == null ? "—" : s.wifi_rssi + " dBm";
  document.getElementById("cam-meta").textContent = s.camera_ok
    ? (s.camera_fps || 0) + " fps"
    : (s.robot_connected ? "camera down" : "idle — connect Pi for live video");

  document.querySelectorAll("#modes button").forEach((b) => {
    b.classList.toggle("active", b.dataset.mode === s.mode);
  });

  drawRaster(s.raster);
  if (brainReady && s.activity && s.activity.length) {
    Plotly.restyle("brain3d", { "marker.color": [s.activity] }, [1]);
  }
  if (window.updateFlyDriver) {
    window.updateFlyDriver(s.left_pwm, s.right_pwm, s.left_cm, s.front_cm, s.right_cm);
  }
}

function connect() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ui`);
  ws.onmessage = (ev) => {
    const s = JSON.parse(ev.data);
    applyState(s);
  };
  ws.onclose = () => setTimeout(connect, 1000);
  window._uiws = ws;
}

document.querySelectorAll("#modes button").forEach((b) => {
  b.addEventListener("click", () => {
    fetch("/api/mode", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode: b.dataset.mode }),
    });
  });
});

function sendManual() {
  const left = Number(document.getElementById("sl-l").value);
  const right = Number(document.getElementById("sl-r").value);
  fetch("/api/mode", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode: "manual", manual_left: left, manual_right: right }),
  });
}
document.getElementById("sl-l").addEventListener("input", sendManual);
document.getElementById("sl-r").addEventListener("input", sendManual);
document.getElementById("stop").addEventListener("click", () => {
  document.getElementById("sl-l").value = 0;
  document.getElementById("sl-r").value = 0;
  sendManual();
});

init().then(connect);
if (window.initFlyDriver) {
  window.initFlyDriver(document.getElementById("fly-driver"));
}
