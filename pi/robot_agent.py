#!/usr/bin/env python3
"""Raspberry Pi 4 robot agent.

Reads HC-SR04 distances + applies motor PWM over USB serial to Arduino.
Streams JPEG frames and telemetry to the Mac brain server over Wi-Fi.

The Pi initiates the connection:

    python3 pi/robot_agent.py --mac-host 192.168.1.20

On Raspberry Pi OS Bookworm:

    sudo apt install python3-picamera2 python3-serial python3-pip
    pip3 install websockets pillow --break-system-packages

See docs/WIRING.md for USB / camera / power.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import struct
import sys
import threading
import time
from pathlib import Path
from typing import Optional

from shared.protocol import format_motor_line, parse_sensor_line

try:
    import serial
    from serial.tools import list_ports
except ImportError:  # pragma: no cover
    serial = None
    list_ports = None


DEFAULT_BAUD = 115200
FRAME_MAGIC = b"JPEG"


def detect_serial_port(explicit: Optional[str]) -> Optional[str]:
    if explicit:
        return explicit
    if list_ports is None:
        return None
    preferred = []
    others = []
    for p in list_ports.comports():
        dev = p.device
        if "ttyACM" in dev or "ttyUSB" in dev or "usbmodem" in dev or "usbserial" in dev:
            preferred.append(dev)
        else:
            others.append(dev)
    if preferred:
        return preferred[0]
    return others[0] if others else None


def wifi_rssi() -> Optional[int]:
    """Best-effort RSSI on Linux; None on Mac / missing iwconfig."""
    for cmd in (
        "iwconfig 2>/dev/null | grep -i -- 'signal level'",
        "iw dev wlan0 link 2>/dev/null | grep 'signal:'",
    ):
        try:
            import subprocess

            out = subprocess.check_output(cmd, shell=True, text=True, timeout=1.0)
        except Exception:
            continue
        for token in out.replace("=", " ").replace(":", " ").split():
            if token.lstrip("-").isdigit():
                val = int(token)
                if -120 <= val <= 0:
                    return val
    return None


class SerialBridge:
    def __init__(self, port: Optional[str], baud: int) -> None:
        self.port_name = port
        self.baud = baud
        self._ser = None
        self.front_cm = -1.0
        self.left_cm = -1.0
        self.right_cm = -1.0
        self.left_pwm = 0
        self.right_pwm = 0
        self.serial_ok = False
        self.last_rx = 0.0
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._rx_buf = ""

    def start(self) -> None:
        if serial is None:
            print("pyserial not installed; running without Arduino", file=sys.stderr)
            return
        if not self.port_name:
            print("No serial port found; running without Arduino", file=sys.stderr)
            return
        try:
            self._ser = serial.Serial(self.port_name, self.baud, timeout=0.05)
            self.serial_ok = True
            print(f"Arduino serial open: {self.port_name} @ {self.baud}")
        except Exception as exc:
            print(f"Serial open failed ({self.port_name}): {exc}", file=sys.stderr)
            self._ser = None
            self.serial_ok = False
            return
        self._thread = threading.Thread(target=self._read_loop, name="serial-rx", daemon=True)
        self._thread.start()

    def _read_loop(self) -> None:
        assert self._ser is not None
        while not self._stop.is_set():
            try:
                data = self._ser.read(256)
            except Exception:
                with self._lock:
                    self.serial_ok = False
                time.sleep(0.2)
                continue
            if not data:
                continue
            try:
                text = data.decode("ascii", errors="ignore")
            except Exception:
                continue
            self._rx_buf += text.replace("\r", "")
            while "\n" in self._rx_buf:
                line, self._rx_buf = self._rx_buf.split("\n", 1)
                parsed = parse_sensor_line(line)
                if parsed is None:
                    continue
                front, left, right = parsed
                with self._lock:
                    self.front_cm = front
                    self.left_cm = left
                    self.right_cm = right
                    self.last_rx = time.time()
                    self.serial_ok = True

    def send_motors(self, left: int, right: int) -> None:
        left = max(-255, min(255, int(left)))
        right = max(-255, min(255, int(right)))
        with self._lock:
            self.left_pwm = left
            self.right_pwm = right
            ser = self._ser
        if ser is None:
            return
        try:
            ser.write(format_motor_line(left, right).encode("ascii"))
            ser.flush()
        except Exception:
            with self._lock:
                self.serial_ok = False

    def stop(self) -> None:
        self._stop.set()
        try:
            self.send_motors(0, 0)
        except Exception:
            pass
        if self._ser is not None:
            try:
                self._ser.close()
            except Exception:
                pass

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "front_cm": self.front_cm,
                "left_cm": self.left_cm,
                "right_cm": self.right_cm,
                "left_pwm": self.left_pwm,
                "right_pwm": self.right_pwm,
                "serial_ok": self.serial_ok and (time.time() - self.last_rx < 1.0 if self.last_rx else False),
            }


class CameraSource:
    def __init__(self, width: int = 640, height: int = 480, fps: int = 15) -> None:
        self.width = width
        self.height = height
        self.fps = fps
        self.last_jpeg: Optional[bytes] = None
        self.measured_fps = 0.0
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self.ok = False

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="camera", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        grab = self._open()
        period = 1.0 / max(1, self.fps)
        stamps: list[float] = []
        while not self._stop.is_set():
            t0 = time.time()
            jpeg = grab()
            if jpeg:
                with self._lock:
                    self.last_jpeg = jpeg
                    self.ok = True
                now = time.time()
                stamps.append(now)
                stamps = [s for s in stamps if now - s < 2.0]
                if len(stamps) >= 2:
                    self.measured_fps = (len(stamps) - 1) / max(1e-3, stamps[-1] - stamps[0])
            dt = time.time() - t0
            time.sleep(max(0.0, period - dt))

    def _open(self):
        try:
            from picamera2 import Picamera2  # type: ignore
            from picamera2.encoders import JpegEncoder  # noqa: F401
            import io

            cam = Picamera2()
            cfg = cam.create_preview_configuration(
                main={"size": (self.width, self.height), "format": "RGB888"}
            )
            cam.configure(cfg)
            cam.start()
            print("Camera: picamera2")

            def grab() -> Optional[bytes]:
                arr = cam.capture_array()
                return _rgb_to_jpeg(arr)

            return grab
        except Exception as exc:
            print(f"picamera2 unavailable ({exc}); trying OpenCV / placeholder")

        try:
            import cv2

            cap = cv2.VideoCapture(0)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            if cap.isOpened():
                print("Camera: OpenCV VideoCapture(0)")

                def grab() -> Optional[bytes]:
                    ok, frame = cap.read()
                    if not ok:
                        return None
                    ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
                    return buf.tobytes() if ok else None

                return grab
        except Exception as exc:
            print(f"OpenCV camera unavailable ({exc})")

        print("Camera: placeholder frames")

        def grab_placeholder() -> Optional[bytes]:
            return _placeholder_jpeg(self.width, self.height)

        return grab_placeholder

    def get_jpeg(self) -> Optional[bytes]:
        with self._lock:
            return self.last_jpeg

    def stop(self) -> None:
        self._stop.set()


def _rgb_to_jpeg(arr) -> Optional[bytes]:
    try:
        from PIL import Image
        import numpy as np

        if arr.ndim == 3 and arr.shape[2] == 4:
            arr = arr[:, :, :3]
        img = Image.fromarray(np.asarray(arr))
        import io

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=70)
        return buf.getvalue()
    except Exception:
        return None


def _placeholder_jpeg(width: int, height: int) -> bytes:
    try:
        from PIL import Image, ImageDraw

        img = Image.new("RGB", (width, height), (18, 22, 28))
        draw = ImageDraw.Draw(img)
        draw.rectangle([20, 20, width - 20, height - 20], outline=(245, 197, 66), width=3)
        draw.text((40, height // 2 - 10), "No camera — placeholder", fill=(220, 220, 220))
        import io

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=70)
        return buf.getvalue()
    except Exception:
        # Minimal JPEG SOI/EOI is not enough for browsers; return empty.
        return b""


def pack_jpeg_message(jpeg: bytes) -> bytes:
    return FRAME_MAGIC + struct.pack(">I", len(jpeg)) + jpeg


async def run_agent(args: argparse.Namespace) -> None:
    port = detect_serial_port(args.serial)
    bridge = SerialBridge(port, args.baud)
    camera = CameraSource(args.width, args.height, args.fps)
    bridge.start()
    camera.start()

    uri = f"ws://{args.mac_host}:{args.mac_port}/robot"
    print(f"Connecting to Mac brain at {uri}")

    try:
        import websockets
    except ImportError as exc:
        raise SystemExit("Install websockets: pip install websockets") from exc

    backoff = 1.0
    while True:
        try:
            async with websockets.connect(uri, max_size=2_000_000, ping_interval=20) as ws:
                print("WebSocket connected")
                backoff = 1.0
                await _session(ws, bridge, camera, args)
        except asyncio.CancelledError:
            break
        except Exception as exc:
            print(f"WS error: {exc}; retry in {backoff:.1f}s")
            bridge.send_motors(0, 0)
            await asyncio.sleep(backoff)
            backoff = min(8.0, backoff * 1.5)


async def _session(ws, bridge: SerialBridge, camera: CameraSource, args: argparse.Namespace) -> None:
    last_frame = 0.0
    telem_period = 1.0 / max(5.0, args.telem_hz)
    last_telem = 0.0

    async def sender() -> None:
        nonlocal last_frame, last_telem
        while True:
            now = time.time()
            if now - last_telem >= telem_period:
                snap = bridge.snapshot()
                msg = {
                    "type": "telemetry",
                    "front_cm": snap["front_cm"],
                    "left_cm": snap["left_cm"],
                    "right_cm": snap["right_cm"],
                    "left_pwm": snap["left_pwm"],
                    "right_pwm": snap["right_pwm"],
                    "serial_ok": snap["serial_ok"],
                    "camera_ok": camera.ok,
                    "camera_fps": round(camera.measured_fps, 1),
                    "wifi_rssi": wifi_rssi(),
                    "ts": now,
                }
                await ws.send(json.dumps(msg))
                last_telem = now
            if now - last_frame >= 1.0 / max(1, args.fps):
                jpeg = camera.get_jpeg()
                if jpeg:
                    await ws.send(pack_jpeg_message(jpeg))
                last_frame = now
            await asyncio.sleep(0.01)

    async def receiver() -> None:
        async for raw in ws:
            if isinstance(raw, bytes):
                continue
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if data.get("type") == "motors":
                bridge.send_motors(int(data.get("left", 0)), int(data.get("right", 0)))

    try:
        await asyncio.gather(sender(), receiver())
    finally:
        bridge.send_motors(0, 0)


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Pi robot agent for Fly Brain Robot")
    p.add_argument("--mac-host", default=os.environ.get("MAC_HOST", "127.0.0.1"))
    p.add_argument("--mac-port", type=int, default=int(os.environ.get("MAC_PORT", "8000")))
    p.add_argument("--serial", default=os.environ.get("ARDUINO_PORT"))
    p.add_argument("--baud", type=int, default=DEFAULT_BAUD)
    p.add_argument("--width", type=int, default=640)
    p.add_argument("--height", type=int, default=480)
    p.add_argument("--fps", type=int, default=12)
    p.add_argument("--telem-hz", type=float, default=20.0)
    return p.parse_args(argv)


def main() -> None:
    args = parse_args()
    try:
        asyncio.run(run_agent(args))
    except KeyboardInterrupt:
        print("\nStopping; motors off")


if __name__ == "__main__":
    # Allow `python pi/robot_agent.py` from repo root or from pi/
    repo = Path(__file__).resolve().parents[1]
    if str(repo) not in sys.path:
        sys.path.insert(0, str(repo))
    main()
