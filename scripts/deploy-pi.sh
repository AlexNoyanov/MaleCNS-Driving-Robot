#!/bin/bash
# From this Mac: copy robot code to the Pi, enable boot start, restart the agent.
#   ./scripts/deploy-pi.sh
#   ./scripts/deploy-pi.sh --flash
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
SSH_WRAP="$REPO/scripts/pi-ssh"
FLASH=0
COPY_KEY=0

while [ $# -gt 0 ]; do
  case "$1" in
    --flash) FLASH=1 ;;
    --copy-key) COPY_KEY=1 ;;
    --host)
      shift
      PI_HOST_OVERRIDE="${1:-}"
      [ -n "$PI_HOST_OVERRIDE" ] || { echo "--host needs an IP or hostname" >&2; exit 1; }
      ;;
    -h|--help)
      echo "Usage: $0 [--flash] [--copy-key] [--host IP]"
      echo "  --flash     also compile and avrdude the Uno"
      echo "  --copy-key  one-time: install this Mac's SSH public key on the Pi"
      echo "  --host IP   Pi address if DHCP changed (default 192.168.1.133)"
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

PI_HOST="${PI_HOST_OVERRIDE:-${PI_HOST:-192.168.1.133}}"
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
  echo "Could not detect this Mac's LAN IP. Set MAC_HOST=192.168.x.x in scripts/deploy-pi.env" >&2
  exit 1
fi

if [ -n "${PI_PASSWORD:-}" ] && ! command -v sshpass >/dev/null 2>&1; then
  echo "Installing sshpass (one-time)…"
  brew install hudochenkov/sshpass/sshpass 2>/dev/null \
    || brew install esolitos/ipa/sshpass \
    || brew install sshpass
fi

chmod +x "$SSH_WRAP" "$REPO/firmware/arduino_robot/flash.sh" "$REPO/pi/install-autostart.sh"
export PI_PASSWORD="${PI_PASSWORD:-}"

pi_ssh() { "$SSH_WRAP" "$TARGET" "$@"; }

echo "Mac LAN  $MAC_HOST:$MAC_PORT"
echo "Pi       $TARGET:$PI_DIR"

echo "Waiting for SSH…"
ok=0
for i in $(seq 1 20); do
  if "$SSH_WRAP" -o ConnectTimeout=4 "$TARGET" true 2>/dev/null; then
    ok=1
    break
  fi
  echo "  not up yet ($i/20)"
  sleep 1
done
if [ "$ok" != 1 ]; then
  echo "No SSH at $TARGET. Power the Pi and wait for Wi-Fi." >&2
  exit 1
fi

if [ "$COPY_KEY" = 1 ]; then
  KEY=""
  for cand in "$HOME/.ssh/id_ed25519.pub" "$HOME/.ssh/id_rsa.pub"; do
    [ -f "$cand" ] && KEY="$cand" && break
  done
  if [ -z "$KEY" ]; then
    mkdir -p "$HOME/.ssh"
    ssh-keygen -t ed25519 -N "" -f "$HOME/.ssh/id_ed25519"
    KEY="$HOME/.ssh/id_ed25519.pub"
  fi
  echo "Installing SSH public key on the Pi…"
  cat "$KEY" | pi_ssh "mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && sort -u -o ~/.ssh/authorized_keys ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
fi

echo "Copying pi/, firmware/, shared/…"
pi_ssh "mkdir -p '$PI_DIR/pi' '$PI_DIR/firmware' '$PI_DIR/shared'"
rsync -az -e "$SSH_WRAP" --exclude '__pycache__' --exclude '*.pyc' \
  "$REPO/pi/" "$TARGET:$PI_DIR/pi/"
rsync -az -e "$SSH_WRAP" --exclude 'build-uno' \
  "$REPO/firmware/" "$TARGET:$PI_DIR/firmware/"
rsync -az -e "$SSH_WRAP" --exclude '__pycache__' --exclude '*.pyc' \
  "$REPO/shared/" "$TARGET:$PI_DIR/shared/"
rsync -az -e "$SSH_WRAP" \
  "$REPO/requirements-pi.txt" \
  "$TARGET:$PI_DIR/"

echo "Enabling boot service + restarting agent…"
# sudo -S reads the password from stdin; install script must run as root.
pi_ssh "cd $(printf %q "$PI_DIR") && chmod +x pi/install-autostart.sh firmware/arduino_robot/flash.sh && printf '%s\n' $(printf %q "${PI_PASSWORD:-}") | sudo -S ./pi/install-autostart.sh $(printf %q "$MAC_HOST")"

if [ "$FLASH" = 1 ]; then
  echo "Flashing Arduino…"
  # Run as the Pi user so build-uno is not root-owned; flash.sh sudo's systemctl.
  pi_ssh "cd $(printf %q "$PI_DIR") && PI_PASSWORD=$(printf %q "${PI_PASSWORD:-}") ./firmware/arduino_robot/flash.sh"
fi

echo
echo "--- agent ---"
pi_ssh "systemctl --no-pager --full status fly-brain-robot | head -20; echo; journalctl -u fly-brain-robot -n 15 --no-pager" || true
echo
echo "Deployed. Agent → ws://$MAC_HOST:$MAC_PORT/robot"
echo "Again later:  ./scripts/deploy-pi.sh"
echo "With firmware: ./scripts/deploy-pi.sh --flash"
