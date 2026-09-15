#!/usr/bin/env python3
"""Pretend to be the Raspberry Pi: connect to the Mac brain over WebSocket.

Drives a 2D kinematic world so you can demo the closed loop without hardware.

    python -m mac.server          # terminal 1
    python -m mac.sim_robot       # terminal 2
"""

from __future__ import annotations

import argparse
import asyncio
import json
import struct
import time

from mac.world import SimpleWorld

FRAME_MAGIC = b"JPEG"


def _fake_jpeg(world: SimpleWorld, front: float, left: float, right: float) -> bytes:
    try:
        from PIL import Image, ImageDraw
        import io

        img = Image.new("RGB", (320, 240), (12, 16, 22))
        draw = ImageDraw.Draw(img)
        # Closer = taller red bar in that third of the frame.
        w = 320 // 3
        for i, d in enumerate((left, front, right)):
            h = int(max(4, 200 * (1.0 - min(d, 150) / 150)))
            color = (220, 70, 70) if d < 12 else (80, 180, 140)
            draw.rectangle([i * w + 8, 240 - h, (i + 1) * w - 8, 230], fill=color)
        draw.text((8, 8), f"sim x={world.x:.0f} y={world.y:.0f}", fill=(230, 230, 230))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=65)
        return buf.getvalue()
    except Exception:
        return b""


async def run(args: argparse.Namespace) -> None:
    import websockets

    world = SimpleWorld()
    if args.scenario == "front":
        world.reset_front_wall()
    elif args.scenario == "left":
        world.reset_left_obstacle()
    elif args.scenario == "right":
        world.reset_right_obstacle()
    else:
        world.reset_clear_path()

    uri = f"ws://{args.host}:{args.port}/robot"
    print(f"sim_robot → {uri} scenario={args.scenario}")
    left_pwm = right_pwm = 0
    last_cmd = time.time()

    async with websockets.connect(uri, max_size=2_000_000) as ws:
        async def sender():
            nonlocal last_cmd
            while True:
                # Arduino-like 200 ms failsafe inside the sim.
                if time.time() - last_cmd > 0.20:
                    world.step(0, 0, 0.05)
                else:
                    world.step(left_pwm, right_pwm, 0.05)
                front, left, right = world.distances()
                msg = {
                    "type": "telemetry",
                    "front_cm": round(front, 1),
                    "left_cm": round(left, 1),
                    "right_cm": round(right, 1),
                    "left_pwm": left_pwm,
                    "right_pwm": right_pwm,
                    "serial_ok": True,
                    "camera_ok": True,
                    "camera_fps": 12.0,
                    "wifi_rssi": -40,
                    "ts": time.time(),
                }
                await ws.send(json.dumps(msg))
                jpeg = _fake_jpeg(world, front, left, right)
                if jpeg:
                    await ws.send(FRAME_MAGIC + struct.pack(">I", len(jpeg)) + jpeg)
                await asyncio.sleep(0.05)

        async def receiver():
            nonlocal left_pwm, right_pwm, last_cmd
            async for raw in ws:
                if isinstance(raw, bytes):
                    continue
                data = json.loads(raw)
                if data.get("type") == "motors":
                    left_pwm = int(data.get("left", 0))
                    right_pwm = int(data.get("right", 0))
                    last_cmd = time.time()

        await asyncio.gather(sender(), receiver())


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--scenario", default="front", choices=("clear", "front", "left", "right"))
    args = p.parse_args()
    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        print("sim_robot stopped")


if __name__ == "__main__":
    main()
