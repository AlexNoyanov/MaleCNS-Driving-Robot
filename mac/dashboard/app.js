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
  if (window.initCnsViewer) {
    await window.initCnsViewer(document.getElementById("brain3d"));
  }
  brainReady = true;
  document.getElementById("geom-hint").textContent =
    "Click a lobe or chip · drag to orbit · +/− or scroll to zoom";
  if (window.initFlyEye) {
    window.initFlyEye(document.getElementById("fly-eye"));
  }
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
  const eyeMeta = document.getElementById("fly-eye-meta");
  if (eyeMeta) {
    eyeMeta.textContent = s.camera_ok
      ? "compound eyes · " + (s.camera_fps || 0) + " fps"
      : "compound eyes · idle mosaic";
  }

  document.querySelectorAll("#modes button").forEach((b) => {
    b.classList.toggle("active", b.dataset.mode === s.mode);
  });

  drawRaster(s.raster);
  if (window.updateCnsViewer) {
    window.updateCnsViewer(s.activity, s.region_activity || {});
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
