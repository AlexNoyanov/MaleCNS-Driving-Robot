#!/bin/bash
# Compile and flash the Uno from the Pi. Stop the agent first — it owns /dev/ttyACM0.
#   ./flash.sh
#   ./flash.sh /dev/ttyUSB0
set -euo pipefail

PORT="${1:-/dev/ttyACM0}"
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

as_root() {
  if [ "$(id -u)" -eq 0 ]; then
    "$@"
  elif [ -n "${PI_PASSWORD:-}" ]; then
    printf '%s\n' "$PI_PASSWORD" | sudo -S "$@"
  else
    sudo "$@"
  fi
}

if systemctl is-active --quiet fly-brain-robot 2>/dev/null; then
  echo "Stopping fly-brain-robot so the USB port is free…"
  as_root systemctl stop fly-brain-robot
  RESTART_AGENT=1
else
  RESTART_AGENT=0
  pkill -f robot_agent.py 2>/dev/null || true
fi

sleep 1
if ! [ -e "$PORT" ]; then
  echo "No Arduino at $PORT. Plug USB in and try: ls /dev/ttyACM* /dev/ttyUSB*"
  exit 1
fi

make
HEX="$(ls -1t build-uno/*.hex 2>/dev/null | head -1 || true)"
if [ -z "$HEX" ]; then
  echo "No .hex after make. Is gcc-avr / arduino-mk installed?"
  exit 1
fi

echo "Flashing $HEX → $PORT"
/usr/bin/avrdude -C /etc/avrdude.conf -p atmega328p -c arduino -b 115200 \
  -P "$PORT" -D -U "flash:w:${HEX}:i"

if [ "$RESTART_AGENT" = 1 ]; then
  echo "Starting fly-brain-robot…"
  as_root systemctl start fly-brain-robot
fi
echo "Done."
