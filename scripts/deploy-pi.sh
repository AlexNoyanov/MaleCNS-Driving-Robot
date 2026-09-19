#!/bin/bash
# Push robot code from this Mac to the Pi, enable boot start, restart the agent.
#   ./scripts/deploy-pi.sh
#   ./scripts/deploy-pi.sh --flash
#   ./scripts/deploy-pi.sh --copy-key
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
SSH_WRAP="$REPO/scripts/pi-ssh"
FLASH=0
COPY_KEY=0

while [ $# -gt 0 ]; do
  case "$1" in
    --flash) FLASH=1 ;;
    --copy-key) COPY_KEY=1 ;;
    -h|--help)
      echo "Usage: $0 [--flash] [--copy-key]"
      echo "  --flash     compile and avrdude the Uno after copy"
      echo "  --copy-key  install this Mac's SSH public key on the Pi"
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
  shift
done

# shellcheck disable=SC1091
[ -f "$REPO/scripts/deploy-pi.env" ] && source "$REPO/scripts/deploy-pi.env"
# shellcheck disable=SC1091
[ -f "$REPO/deploy-pi.env" ] && source "$REPO/deploy-pi.env"

PI_HOST="${PI_HOST:-192.168.1.133}"
PI_USER="${PI_USER:-ynoyanov}"
PI_DIR="${PI_DIR:-/home/${PI_USER}/Work/AI-Brains/MaleCNS-Driving-Robot}"
MAC_PORT="${MAC_PORT:-8000}"
TARGET="${PI_USER}@${PI_HOST}"

if [ -z "${MAC_HOST:-}" ]; then
  for iface in en0 en1; do
    MAC_HOST="$(ipconfig getifaddr "$iface" 2>/dev/null || true)"
    [ -n "$MAC_HOST" ] && break
  done
fi
if [ -z "${MAC_HOST:-}" ]; then
  MAC_HOST="$(networksetup -getinfo Wi-Fi 2>/dev/null | awk -F': ' '/^IP address: /{print $2; exit}' || true)"
fi
if [ -z "${MAC_HOST:-}" ]; then
  echo "Could not detect this Mac's LAN IP. Set MAC_HOST=192.168.x.x" >&2
  exit 1
fi

if [ -n "${PI_PASSWORD:-}" ] && ! command -v sshpass >/dev/null 2>&1; then
  echo "Installing sshpass (one-time, for password SSH)…"
  if command -v brew >/dev/null 2>&1; then
    brew install hudochenkov/sshpass/sshpass 2>/dev/null \
      || brew install esolitos/ipa/sshpass \
      || brew install sshpass
  else
    echo "Install sshpass or run: $0 --copy-key  (after adding a key by hand)" >&2
    exit 1
  fi
fi

chmod +x "$SSH_WRAP" "$REPO/firmware/arduino_robot/flash.sh" "$REPO/pi/install-autostart.sh"
export PI_PASSWORD="${PI_PASSWORD:-}"

pi_ssh() { "$SSH_WRAP" "$TARGET" "$@"; }

echo "Mac LAN  $MAC_HOST:$MAC_PORT"
echo "Pi       $TARGET:$PI_DIR"

if [ "$COPY_KEY" = 1 ]; then
  KEY=""
  for cand in "$HOME/.ssh/id_ed25519.pub" "$HOME/.ssh/id_rsa.pub"; do
    [ -f "$cand" ] && KEY="$cand" && break
  done
  if [ -z "$KEY" ]; then
    echo "Creating ~/.ssh/id_ed25519…"
    mkdir -p "$HOME/.ssh"
    ssh-keygen -t ed25519 -N "" -f "$HOME/.ssh/id_ed25519"
    KEY="$HOME/.ssh/id_ed25519.pub"
  fi
  echo "Installing $(basename "$KEY") on the Pi…"
  cat "$KEY" | pi_ssh "mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && sort -u -o ~/.ssh/authorized_keys ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
  echo "Key installed. Later deploys can omit PI_PASSWORD."
fi

echo "Copying pi/, firmware/, shared/…"
pi_ssh "mkdir -p '$PI_DIR/pi' '$PI_DIR/firmware/arduino_robot' '$PI_DIR/shared'"
RSH="$SSH_WRAP"
rsync -az -e "$RSH" \
  "$REPO/pi/robot_agent.py" \
  "$REPO/pi/install-autostart.sh" \
  "$REPO/pi/fly-brain-robot.service" \
  "$TARGET:$PI_DIR/pi/"
rsync -az -e "$RSH" \
  "$REPO/firmware/arduino_robot/arduino_robot.ino" \
  "$REPO/firmware/arduino_robot/Makefile" \
  "$REPO/firmware/arduino_robot/flash.sh" \
  "$TARGET:$PI_DIR/firmware/arduino_robot/"
rsync -az -e "$RSH" \
  "$REPO/shared/__init__.py" \
  "$REPO/shared/protocol.py" \
  "$TARGET:$PI_DIR/shared/"
rsync -az -e "$RSH" \
  "$REPO/requirements-pi.txt" \
  "$TARGET:$PI_DIR/"

echo "Enabling boot service + restarting agent…"
pi_ssh "export PI_DIR=$(printf %q "$PI_DIR") MAC_HOST=$(printf %q "$MAC_HOST") PI_PASSWORD=$(printf %q "${PI_PASSWORD:-}"); bash -s" <<'REMOTE'
set -euo pipefail
cd "$PI_DIR"
chmod +x pi/install-autostart.sh firmware/arduino_robot/flash.sh
if [ -n "${PI_PASSWORD:-}" ]; then
  printf '%s\n' "$PI_PASSWORD" | sudo -S -v
fi
sudo ./pi/install-autostart.sh "$MAC_HOST"
REMOTE

if [ "$FLASH" = 1 ]; then
  echo "Flashing Arduino…"
  pi_ssh "export PI_DIR=$(printf %q "$PI_DIR") PI_PASSWORD=$(printf %q "${PI_PASSWORD:-}"); bash -s" <<'REMOTE'
set -euo pipefail
cd "$PI_DIR"
if [ -n "${PI_PASSWORD:-}" ]; then
  printf '%s\n' "$PI_PASSWORD" | sudo -S -v
fi
./firmware/arduino_robot/flash.sh
REMOTE
fi

echo
echo "Deployed. Agent → ws://$MAC_HOST:$MAC_PORT/robot"
echo "Logs:  $SSH_WRAP $TARGET 'journalctl -u fly-brain-robot -n 30 --no-pager'"
