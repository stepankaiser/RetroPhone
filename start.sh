#!/bin/bash
# Start Time Travel Radio
cd ~/RetroPhone
# Audio Setup (Unmute and Max Vol)
export AUDIODRIVER=alsa # Force ALSA for SoX/mpg123 to suppress Jack errors

# Load Secrets
set -a
source .env
set +a

# Network Boost (Attempt to disable WiFi Power Management)
iwconfig wlan0 power off >/dev/null 2>&1 || true
# Audio Setup: Try setting 'Speaker', 'PCM', and 'Headphone' (suppress errors if not found)
# Card 0 (Jack): Usually 'Headphone' or 'PCM'
amixer -c 0 set PCM 95% unmute >/dev/null 2>&1 || true
# Card 1 (USB Handset): 'Speaker'/'Mic'
amixer -c 1 set Speaker 100% unmute >/dev/null 2>&1 || true
amixer -c 1 set Headphone 100% unmute >/dev/null 2>&1 || true
amixer -c 1 set Mic 100% unmute >/dev/null 2>&1 || true 
amixer -c 1 set 'Auto Gain Control' on >/dev/null 2>&1 || true

# Cleanup previous instances and audio zombies
echo "Cleaning up..."
pkill -f python3 || true
killall -9 aplay mpg123 arecord librespot >/dev/null 2>&1 || true
time sleep 1

# Force Audio Levels

source venv/bin/activate
python3 -u main.py
