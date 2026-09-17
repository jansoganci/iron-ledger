#!/usr/bin/env bash
# Idempotent bootstrap for the Month Proof Cloud Agent environment.
# Safe to run repeatedly and against cached/snapshot state.
set -euo pipefail

# Always operate from the repository root, regardless of caller CWD.
cd "$(dirname "$0")/.."

# --- System packages -------------------------------------------------------
# Ubuntu's Python 3.12 ships without the venv/ensurepip module or build
# headers; install them once. Guarded so snapshot boots skip apt entirely.
if ! dpkg -s python3.12-venv >/dev/null 2>&1; then
  sudo apt-get update -qq
  sudo apt-get install -y -qq python3.12-venv python3-dev build-essential
fi

# --- Python backend --------------------------------------------------------
# Repo pins Python 3.11 via .python-version; the pinned deps (pandas 2.2.2,
# pandera 0.20.4, pydantic 2.8.2) also support the image's 3.12 toolchain.
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt -r requirements-dev.txt

# --- Node dependencies -----------------------------------------------------
# Root package-lock.json provides `concurrently` for `npm run dev`.
# Use ci so Cloud Agent installs stay locked to committed lockfiles.
npm ci
npm --prefix frontend ci

