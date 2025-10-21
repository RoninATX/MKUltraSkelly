#!/usr/bin/env bash
set -euo pipefail

log() {
  echo "[bootstrap] $*"
}

declare -a SUDO=()
if [[ $EUID -ne 0 ]]; then
  if command -v sudo >/dev/null 2>&1; then
    SUDO=(sudo)
  else
    log "This script requires administrative privileges. Please run as root or install sudo."
    exit 1
  fi
fi

run_as_root() {
  if ((${#SUDO[@]})); then
    "${SUDO[@]}" "$@"
  else
    "$@"
  fi
}
export DEBIAN_FRONTEND="${DEBIAN_FRONTEND:-noninteractive}"
APT_PACKAGES=(bluez bluez-tools bluetooth python3 python3-venv python3-pip python3-dev git)

log "Updating apt package index"
run_as_root apt-get update
log "Upgrading installed packages"
run_as_root apt-get upgrade -y
log "Installing required packages: ${APT_PACKAGES[*]}"
run_as_root apt-get install -y "${APT_PACKAGES[@]}"

if command -v systemctl >/dev/null 2>&1; then
  log "Enabling and starting bluetooth.service"
  if ! run_as_root systemctl enable bluetooth.service; then
    log "Unable to enable bluetooth.service; continuing"
  fi
  if ! run_as_root systemctl start bluetooth.service; then
    log "Unable to start bluetooth.service; continuing"
  fi
else
  log "systemctl not available; skipping Bluetooth service configuration"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_DIR="${REPO_DIR:-$DEFAULT_REPO_DIR}"
REPO_URL="${REPO_URL:-}"

if [[ -d "$REPO_DIR/.git" ]]; then
  log "Updating repository in $REPO_DIR"
  git -C "$REPO_DIR" pull --ff-only
else
  if [[ -z "$REPO_URL" ]]; then
    log "REPO_URL not set and $REPO_DIR is not a Git repository."
    log "Set REPO_URL to clone the project into $REPO_DIR."
    exit 1
  fi
  log "Cloning repository from $REPO_URL into $REPO_DIR"
  git clone "$REPO_URL" "$REPO_DIR"
fi

PYTHON_BIN="${PYTHON_BIN:-python3}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  log "Python binary '$PYTHON_BIN' not found on PATH"
  exit 1
fi

VENV_PATH="${VENV_PATH:-$REPO_DIR/.venv}"
log "Creating virtual environment at $VENV_PATH"
"$PYTHON_BIN" -m venv "$VENV_PATH"
# shellcheck disable=SC1090
source "$VENV_PATH/bin/activate"
log "Upgrading pip"
pip install --upgrade pip
if [[ -f "$REPO_DIR/requirements.txt" ]]; then
  log "Installing Python dependencies from requirements.txt"
  pip install -r "$REPO_DIR/requirements.txt"
else
  log "requirements.txt not found; skipping Python dependency installation"
fi
deactivate

log "Bootstrap complete"
