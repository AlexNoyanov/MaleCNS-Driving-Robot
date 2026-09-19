#!/bin/bash
# Install systemd unit so the Pi agent starts on boot.
#   sudo ./pi/install-autostart.sh 192.168.1.47
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "Run with sudo: sudo $0 <MAC_LAN_IP>"
  exit 1
fi

MAC_HOST="${1:-${MAC_HOST:-}}"
MAC_PORT="${MAC_PORT:-8000}"
if [ -z "$MAC_HOST" ]; then
  echo "Usage: sudo $0 <MAC_LAN_IP>"
  echo "Example: sudo $0 192.168.1.47"
  exit 1
fi

REPO="$(cd "$(dirname "$0")/.." && pwd)"
USER_NAME="${SUDO_USER:-ynoyanov}"
UNIT_SRC="$REPO/pi/fly-brain-robot.service"
UNIT_DST=/etc/systemd/system/fly-brain-robot.service

sed -e "s|__USER__|${USER_NAME}|g" -e "s|__REPO__|${REPO}|g" "$UNIT_SRC" > "$UNIT_DST"

cat > /etc/default/fly-brain-robot <<EOF
MAC_HOST=${MAC_HOST}
MAC_PORT=${MAC_PORT}
EOF

chmod +x "$REPO/firmware/arduino_robot/flash.sh"
usermod -aG dialout,video "$USER_NAME" || true

systemctl daemon-reload
systemctl enable fly-brain-robot
systemctl restart fly-brain-robot
systemctl --no-pager --full status fly-brain-robot || true

echo
echo "Agent starts on boot and connects to ws://${MAC_HOST}:${MAC_PORT}/robot"
echo "Change Mac IP later:  sudo nano /etc/default/fly-brain-robot && sudo systemctl restart fly-brain-robot"
echo "Logs:  journalctl -u fly-brain-robot -f"
