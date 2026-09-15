# MaleCNS Fly Brain driving two-wheeled Robot project
<img width="618" height="409" alt="Screenshot 2026-09-15 at 22 37 58" src="https://github.com/user-attachments/assets/2d9a8ef0-f298-49c9-a2aa-4406d33785ef" />



## Making Fruit Fly brain model to drive a bot in real life, getting video from camera, distances from ultrasonic sensors  
<img width="800" height="449" alt="ezgif com-video-to-gif-converter" src="https://github.com/user-attachments/assets/88699a0c-5c37-47d6-91ce-a8032cab439f" />


Arduino (motors + 3× HC-SR04) ↔ Raspberry Pi 4 (camera + Wi-Fi) ↔ Mac M1
(local MaleCNS LIF brain + live dashboard).

The connectome in `connectome_cache.npz` / `data/connectome_cache.npz` is a
real `male-cns:v1.0` subset (AL(R), ~4057 neurons). After that file exists,
**no neuPrint token is required**.


## 1. Wire the robot

Follow **[docs/WIRING.md](docs/WIRING.md)** for the **L293D** pinout on this acrylic 2WD chassis
(4×AA pack → L293D motor power, Arduino → L293D logic, Pi USB → Arduino only).

Flash [`firmware/arduino_robot/arduino_robot.ino`](firmware/arduino_robot/arduino_robot.ino)
with Arduino IDE. Serial monitor at 115200 should print `S,<front>,<left>,<right>`.
Type `M,180,180` (from the Pi later) to spin both wheels forward — **jack the wheels up first**.

## 2. Mac brain + dashboard (Python 3.10+)

```bash
cd Brain-AI
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-mac.txt
python -m mac.server
```

Open http://127.0.0.1:8000 — you should see the 3D fly CNS, spike raster, and
an idle approaching-wall demo (no robot yet).

Optional richer 3D (one-time, needs `NEUPRINT_TOKEN`):

```bash
export NEUPRINT_TOKEN="…"
python scripts/cache_skeletons.py
```

Without a token, `scripts/cache_skeletons.py` still writes a local procedural CNS.

## 3. Raspberry Pi 4

Same Wi-Fi as the Mac. USB from Pi → Arduino. CSI camera on the ribbon.

```bash
sudo apt install python3-picamera2 python3-serial python3-pip
pip3 install -r requirements-pi.txt --break-system-packages
python3 pi/robot_agent.py --mac-host <MAC_LAN_IP>
```

The Pi **opens** `ws://<mac>:8000/robot`. Allow Python incoming connections on
the Mac firewall if prompted.

## 4. Closed loop without hardware

```bash
python -m mac.server          # terminal 1
python -m mac.sim_robot --scenario front   # terminal 2
```

Modes on the dashboard: **Hybrid** (default, works), **Brain**, **Manual**.

Failsafes: Arduino stops motors if no `M,` for 200 ms; Mac sends 0,0 if
telemetry is older than 300 ms; Pi sends `M,0,0` on WebSocket drop.

## Offline plots (legacy)

```bash
python -m mac.offline
```
