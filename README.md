
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

![Uploading IMG_3170 copy.jpg…]()


Follow **[docs/WIRING.md](docs/WIRING.md)** for the **L298N/L298D** pinout on this acrylic 2WD chassis
(4×AA pack → driver motor power, Arduino → IN1–IN4, Pi USB → Arduino only).

Flash [`firmware/arduino_robot/arduino_robot.ino`](firmware/arduino_robot/arduino_robot.ino)
with Arduino IDE. Serial monitor at 115200 should print `S,<front>,<left>,<right>`.
Type `M,180,180` (from the Pi later) to spin both wheels forward — **jack the wheels up first**.

## 2. Brain + dashboard

### Docker (any Mac / Linux)

Needs [Docker Desktop](https://www.docker.com/products/docker-desktop/) or Engine.
The image is the idle CNS demo (and the brain the Pi talks to). No neuPrint token.

```bash
cd Brain-AI
docker compose up --build
```

Open http://127.0.0.1:8000 — 3D fly CNS, spike raster, approaching-wall idle demo.

From another machine on the LAN, use `http://<this-host-ip>:8000`. Point the Pi at
that same IP (`MAC_HOST` in `scripts/deploy-pi.env`, then `./scripts/deploy-pi.sh`).

Fake closed loop (no hardware):

```bash
docker compose --profile sim up --build
```

Stop with Ctrl-C, or `docker compose down`.

### Local venv (Python 3.10+)

```bash
cd Brain-AI
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-mac.txt
python -m mac.server
```

Open http://127.0.0.1:8000 — same dashboard as Docker, no container.

Optional richer 3D (one-time, needs `NEUPRINT_TOKEN`):

```bash
export NEUPRINT_TOKEN="…"
python scripts/cache_skeletons.py
```

Without a token, `scripts/cache_skeletons.py` still writes a local procedural CNS.

## 3. Raspberry Pi 4

Same Wi-Fi as the Mac. USB from Pi → Arduino. USB camera or CSI ribbon.

From **this Mac** (no interactive SSH):

```bash
./scripts/deploy-pi.sh              # copy code, enable boot start, restart agent
./scripts/deploy-pi.sh --flash      # same, then flash the Uno
./scripts/deploy-pi.sh --host 192.168.1.140   # if the Pi got a new DHCP address
```

Defaults: `ynoyanov@192.168.1.133`, repo `~/Work/AI-Brains/MaleCNS-Driving-Robot`.
Override in `scripts/deploy-pi.env` (gitignored; copy from `scripts/deploy-pi.env.example`).

On the Mac: `python -m mac.server` (listens on `0.0.0.0:8000`). The Pi opens
`ws://<mac>:8000/robot`.

First-time packages on the Pi (once):

```bash
sudo apt install python3-picamera2 python3-serial python3-pip gcc-avr avr-libc avrdude arduino-core-avr arduino-mk
pip3 install -r requirements-pi.txt --break-system-packages
```

Do **not** use `arduino-cli` on this Pi. `./scripts/deploy-pi.sh --flash` uses Debian `avrdude`.

If the Mac’s IP changes, run `./scripts/deploy-pi.sh` again (it writes `MAC_HOST`).

```bash
./scripts/pi-ssh ynoyanov@192.168.1.133 'journalctl -u fly-brain-robot -f'
```

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
