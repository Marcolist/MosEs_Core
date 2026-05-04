#!/usr/bin/env bash
# MosEs Core install script for Raspberry Pi OS / Debian-derived systems.
# Run as root.

set -euo pipefail

INSTALL_DIR=/opt/moses
DATA_DIR=/var/lib/moses
USER_NAME=moses
REPO_URL="${REPO_URL:-https://github.com/marcolist/moses_core.git}"
BRANCH="${BRANCH:-main}"

if [[ $EUID -ne 0 ]]; then
  echo "Please run as root (sudo)." >&2
  exit 1
fi

apt-get update
apt-get install -y python3 python3-venv python3-pip git chromium-browser xserver-xorg xinit x11-xserver-utils

id -u "$USER_NAME" >/dev/null 2>&1 || useradd --system --create-home --shell /bin/bash "$USER_NAME"

mkdir -p "$INSTALL_DIR" "$DATA_DIR"
chown -R "$USER_NAME:$USER_NAME" "$INSTALL_DIR" "$DATA_DIR"

if [[ ! -d "$INSTALL_DIR/.git" ]]; then
  sudo -u "$USER_NAME" git clone --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
else
  sudo -u "$USER_NAME" git -C "$INSTALL_DIR" pull --ff-only
fi

sudo -u "$USER_NAME" python3 -m venv "$INSTALL_DIR/venv"
sudo -u "$USER_NAME" "$INSTALL_DIR/venv/bin/pip" install --upgrade pip
sudo -u "$USER_NAME" "$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt"

install -m 0644 "$INSTALL_DIR/deploy/moses.service" /etc/systemd/system/moses.service
install -m 0644 "$INSTALL_DIR/deploy/moses-kiosk.service" /etc/systemd/system/moses-kiosk.service

systemctl daemon-reload
systemctl enable --now moses.service
systemctl enable moses-kiosk.service

echo "Installed. Open http://$(hostname -I | awk '{print $1}'):8000/admin to configure."
