#!/usr/bin/env bash
set -euo pipefail
sudo apt update
sudo apt install -y python3-venv python3-pip mosquitto mosquitto-clients libegl1 libgl1 libxcb-cursor0
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
sudo systemctl enable --now mosquitto
echo "LifeLane dependencies installed. Timings are for simulation only."
