"""FastAPI brain server + live dashboard.

Run on the Mac:

    python -m mac.server

Dashboard: http://127.0.0.1:8000
Pi connects to ws://<mac-ip>:8000/robot
"""

from __future__ import annotations

import asyncio
import json
import struct
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from mac.brain import FlyBrain
from mac.controller import STALE_TELEMETRY_S, hybrid_command
from mac.geometry import MESH_PATH, load_or_build_geometry
from mac.vision import visual_closeness

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_DIR = Path(__file__).resolve().parent / "dashboard"
FRAME_MAGIC = b"JPEG"

app = FastAPI(title="Fly Brain Robot")
app.mount("/static", StaticFiles(directory=str(DASHBOARD_DIR)), name="static")

brain: Optional[FlyBrain] = None
geometry: Dict[str, Any] = {}
viz_indices: List[int] = []

robot_ws: Optional[WebSocket] = None
ui_clients: Set[WebSocket] = set()

state: Dict[str, Any] = {
    "mode": "hybrid",
    "manual_left": 0,
    "manual_right": 0,
    "front_cm": -1.0,
    "left_cm": -1.0,
    "right_cm": -1.0,
    "left_pwm": 0,
    "right_pwm": 0,
    "left_rate": 0.0,
    "right_rate": 0.0,
    "emergency": False,
    "robot_connected": False,
    "serial_ok": False,
    "camera_ok": False,
    "camera_fps": 0.0,
    "wifi_rssi": None,
    "sim_hz": 0.0,
    "spike_rate": 0.0,
    "device": "cpu",
    "n_neurons": 0,
    "n_synapses": 0,
    "telemetry_age_s": 99.0,
    "last_robot_msg": 0.0,
    "vis_left": 0.0,
    "vis_front": 0.0,
    "vis_right": 0.0,
    "region_activity": {
        "left": 0.0, "front": 0.0, "right": 0.0,
        "motor_left": 0.0, "motor_right": 0.0, "global": 0.0,
    },
}

last_jpeg: bytes = b""
raster: List[List[int]] = []
activity: List[float] = []
_idle_t = 0
lock = asyncio.Lock()


def _placeholder_jpeg() -> bytes:
    try:
        from PIL import Image, ImageDraw
        import io

        img = Image.new("RGB", (640, 400), (10, 12, 18))
        draw = ImageDraw.Draw(img)
        draw.rectangle([24, 24, 616, 376], outline=(245, 197, 66), width=3)
        draw.text((48, 180), "Waiting for Raspberry Pi camera…", fill=(220, 220, 220))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=70)
        return buf.getvalue()
    except Exception:
        return b""


class ModeBody(BaseModel):
    mode: Optional[str] = None
    manual_left: Optional[int] = None
    manual_right: Optional[int] = None


def _idle_distances(t: int) -> tuple[float, float, float]:
    """Synthetic approaching-wall when no robot is connected (dashboard still alive)."""
    phase = (t % 400) / 400.0
    front = 100.0 - 90.0 * phase
    return front, 80.0, 80.0


@app.on_event("startup")
async def startup() -> None:
    global brain, geometry, viz_indices, activity, last_jpeg
    brain = FlyBrain()
    geometry = load_or_build_geometry(brain.body_ids)
    viz_indices = [int(n["index"]) for n in geometry.get("neurons", [])]
    activity = [0.0] * len(viz_indices)
    state["device"] = brain.device
    state["n_neurons"] = brain.n_neurons
    state["n_synapses"] = int(len(brain.rows))
    print(
        f"MaleCNS local: {brain.n_neurons} neurons, {len(brain.rows)} synapses, "
        f"device={brain.device}, cache={brain.cache_path}"
    )
    last_jpeg = _placeholder_jpeg()
    asyncio.create_task(control_loop())


@app.get("/")
async def index() -> HTMLResponse:
    html = (DASHBOARD_DIR / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(html)


@app.get("/api/geometry")
async def api_geometry() -> JSONResponse:
    return JSONResponse(geometry)


@app.get("/api/brain-mesh")
async def api_brain_mesh():
    if not MESH_PATH.exists():
        return JSONResponse({"error": "brain_mesh.json missing"}, status_code=404)
    return FileResponse(MESH_PATH, media_type="application/json")


@app.get("/api/state")
async def api_state() -> JSONResponse:
    return JSONResponse(_ui_payload())


@app.post("/api/mode")
async def api_mode(body: ModeBody) -> JSONResponse:
    async with lock:
        if body.mode in ("hybrid", "brain", "manual"):
            state["mode"] = body.mode
        if body.manual_left is not None:
            state["manual_left"] = int(max(-255, min(255, body.manual_left)))
        if body.manual_right is not None:
            state["manual_right"] = int(max(-255, min(255, body.manual_right)))
    return JSONResponse({"ok": True, "mode": state["mode"]})


@app.get("/camera/stream")
async def camera_stream() -> StreamingResponse:
    async def gen():
        boundary = b"frame"
        while True:
            frame = last_jpeg
            if frame:
                yield (
                    b"--" + boundary + b"\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    b"Content-Length: " + str(len(frame)).encode() + b"\r\n\r\n"
                    + frame
                    + b"\r\n"
                )
            await asyncio.sleep(1 / 12)

    return StreamingResponse(gen(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.websocket("/robot")
async def robot_socket(ws: WebSocket) -> None:
    global robot_ws, last_jpeg
    await ws.accept()
    async with lock:
        robot_ws = ws
        state["robot_connected"] = True
    try:
        while True:
            msg = await ws.receive()
            if msg.get("type") == "websocket.disconnect":
                break
            data = msg.get("bytes")
            if data:
                jpeg = _parse_jpeg_blob(data)
                if jpeg:
                    last_jpeg = jpeg
                    state["camera_ok"] = True
                continue
            text = msg.get("text")
            if not text:
                continue
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                continue
            if payload.get("type") != "telemetry":
                continue
            async with lock:
                state["front_cm"] = float(payload.get("front_cm", -1))
                state["left_cm"] = float(payload.get("left_cm", -1))
                state["right_cm"] = float(payload.get("right_cm", -1))
                state["serial_ok"] = bool(payload.get("serial_ok", False))
                state["camera_ok"] = bool(payload.get("camera_ok", state["camera_ok"]))
                state["camera_fps"] = float(payload.get("camera_fps") or 0)
                state["wifi_rssi"] = payload.get("wifi_rssi")
                state["last_robot_msg"] = time.time()
    except WebSocketDisconnect:
        pass
    finally:
        async with lock:
            if robot_ws is ws:
                robot_ws = None
                state["robot_connected"] = False
                state["serial_ok"] = False
                state["left_pwm"] = 0
                state["right_pwm"] = 0


@app.websocket("/ui")
async def ui_socket(ws: WebSocket) -> None:
    await ws.accept()
    ui_clients.add(ws)
    try:
        await ws.send_json(_ui_payload())
        while True:
            raw = await ws.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if data.get("type") == "mode":
                await api_mode(ModeBody(**{k: data.get(k) for k in ("mode", "manual_left", "manual_right")}))
            elif data.get("type") == "manual":
                await api_mode(
                    ModeBody(manual_left=data.get("left"), manual_right=data.get("right"), mode="manual")
                )
    except WebSocketDisconnect:
        pass
    finally:
        ui_clients.discard(ws)


def _parse_jpeg_blob(data: bytes) -> Optional[bytes]:
    if len(data) >= 8 and data[:4] == FRAME_MAGIC:
        (n,) = struct.unpack(">I", data[4:8])
        blob = data[8 : 8 + n]
        if blob[:2] == b"\xff\xd8":
            return blob
    if data[:2] == b"\xff\xd8":
        return data
    return None


def _ui_payload() -> Dict[str, Any]:
    return {
        **{k: state[k] for k in state},
        "raster": raster[-120:],
        "activity": activity,
        "raster_n": len(brain.raster_idx) if brain else 0,
    }


async def control_loop() -> None:
    global raster, activity, _idle_t, last_jpeg
    assert brain is not None
    last = time.perf_counter()
    hz_ema = 0.0
    while True:
        t0 = time.perf_counter()
        async with lock:
            mode = state["mode"]
            robot_on = state["robot_connected"]
            age = time.time() - state["last_robot_msg"] if state["last_robot_msg"] else 99.0
            if robot_on:
                front, left, right = state["front_cm"], state["left_cm"], state["right_cm"]
                telem_age = age
            else:
                _idle_t += 1
                front, left, right = _idle_distances(_idle_t)
                telem_age = 0.0 if mode != "manual" else 99.0
                # Idle demo drives the brain only; never send PWM without a robot.
            vis_l, vis_f, vis_r = visual_closeness(last_jpeg if robot_on else None)
            state["vis_left"], state["vis_front"], state["vis_right"] = vis_l, vis_f, vis_r
            state["telemetry_age_s"] = age if robot_on else 99.0

        ext = brain.sensors_to_input(left, front, right, vis_l, vis_f, vis_r)
        spikes = brain.step(ext)
        left_rate, right_rate = brain.readout(spikes)

        left_pwm, right_pwm, emergency = hybrid_command(
            front,
            left,
            right,
            left_rate,
            right_rate,
            vis_l,
            vis_f,
            vis_r,
            mode=mode,
            manual_left=state["manual_left"],
            manual_right=state["manual_right"],
            telemetry_age_s=telem_age,
        )
        send_left, send_right = left_pwm, right_pwm
        if not robot_on:
            # Idle demo still animates the fly pilot; never command hardware.
            send_left, send_right = 0, 0

        row = brain.raster_row(spikes)
        raster.append(row)
        if len(raster) > 240:
            raster = raster[-180:]
        activity = brain.activity_for_indices(viz_indices)
        regions = brain.region_activity()

        now = time.perf_counter()
        dt = now - last
        last = now
        inst_hz = 1.0 / dt if dt > 1e-6 else 0.0
        hz_ema = 0.9 * hz_ema + 0.1 * inst_hz if hz_ema else inst_hz

        async with lock:
            state["left_rate"] = round(left_rate, 4)
            state["right_rate"] = round(right_rate, 4)
            state["left_pwm"] = left_pwm
            state["right_pwm"] = right_pwm
            state["emergency"] = emergency
            state["sim_hz"] = round(hz_ema, 1)
            state["spike_rate"] = round(float(spikes.mean()), 4)
            state["region_activity"] = regions
            if not robot_on:
                state["front_cm"] = front
                state["left_cm"] = left
                state["right_cm"] = right

        ws = robot_ws
        if ws is not None:
            try:
                await ws.send_json({"type": "motors", "left": send_left, "right": send_right})
            except Exception:
                pass

        payload = _ui_payload()
        dead = []
        for client in list(ui_clients):
            try:
                await client.send_json(payload)
            except Exception:
                dead.append(client)
        for c in dead:
            ui_clients.discard(c)

        elapsed = time.perf_counter() - t0
        await asyncio.sleep(max(0.0, 0.05 - elapsed))  # ~20 Hz


def main() -> None:
    import uvicorn

    uvicorn.run("mac.server:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()
