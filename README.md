# 📞 RetroPhone: Time Travel Radio - System Documentation

## 1. Overview
The **RetroPhone** is an AI-powered "Time Travel Radio" built into a vintage rotary phone. It allows users to lift the handset, chat with simulated "Operator" or radio DJs from different decades (1900s-2020s), and play period-correct music via Spotify.

**Key Features:**
- **Voice Interface:** Powered by OpenAI GPT-5 (Brain) and Whisper (Ear).
- **Audio Output:** Hybrid routing (Music -> Home Audio via Jack, Voice -> Handset via USB).
- **Physical Controls:** Rotary dial to switch "decades" (channels).
- **Self-Healing:** Automatic service recovery and Spotify session management.

---

## 2. Installation & Setup

### Prerequisites
- Raspberry Pi 4 (Recommended) or 3B+.
- Python 3.9+
- Spotify Premium Account.
- OpenAI & ElevenLabs API Keys.

### Installation
1.  **Clone the Repository**:
    ```bash
    git clone https://github.com/yourusername/RetroPhone.git
    cd RetroPhone
    ```

2.  **System Dependencies**:
    ```bash
    sudo apt-get install -y libasound2-dev libspotify-dev sox libsox-fmt-mp3 mpg123
    ```

3.  **Python Environment**:
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```

4.  **Configuration**:
    Copy the example environment file and add your keys:
    ```bash
    cp .env.example .env
    nano .env
    ```

5.  **Service Deployment**:
    ```bash
    sudo cp retrophone.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable retrophone.service
    sudo systemctl start retrophone.service
    ```

## 3. Hardware Configuration

### Connections
*   **Raspberry Pi 4 Model B** (Headless)
*   **Rotary Phone Hook:**
    *   Pin **GPIO 22** (BCM) -> Hook Switch (Normally Closed/Open logic handled in software).
    *   **GND** -> Common Ground.
*   **Rotary Dial:**
    *   Pin **GPIO 27** (BCM) -> Dial Pulse Switch.
    *   **GND** -> Common Ground.
*   **Audio Output 1 (Music):**
    *   **3.5mm Jack (Card 0)** -> Connected to Home Audio Receiver (Yamaha).
    *   Volume: Line Level (95%).
    *   ALSA Device: `plughw:0,0`
*   **Audio Output 2 (Voice):**
    *   **USB Audio Dongle (Card 1)** -> Inside Phone.
    *   Output: Handset Earpiece.
    *   Input: Handset Microphone.
    *   ALSA Device: `plughw:1,0` (Configured in `config.py` as `AUDIO_DEVICE_ID = 1`).

---

## 3. Software Architecture

### Core Modules (`src/`)
*   **`main.py`**: The central loop. Monitors the `PhoneInterface`. If `Off Hook` detected -> Starts `Brain` conversation. If `Dial` detected -> Switches "Channel" (Decade).
*   **`phone_interface.py`**: A threaded hardware monitor for GPIO pins. Debounces signals and exposes `is_off_hook` logic and `dial_count`.
*   **`brain.py`**: The Intelligence.
    *   Uses **OpenAI GPT-5.2** for persona generation ("Operator", "1950s DJ").
    *   Handles **Intent Classification** (Chat vs Music Request).
    *   Generates **Spotify Search Queries** (e.g. "TRACK: song artist").
    *   **Language Aware**: Adapts to Czech (CZ) vs English (EN) contexts, with normalization rules for spelling.
*   **`audio_engine.py`**:
    *   **TTS:** Uses **ElevenLabs** for high-quality voice synthesis and caches standard phrases.
    *   **STT:** Uses **OpenAI Whisper** for transcribing user speech.
    *   **VAD:** (Voice Activity Detection) Detects when user stops speaking using energy thresholds.
*   **`music_engine.py`**:
    *   Wraps **Librespot** (Embedded Spotify Client) and **Spotipy** (Web API).
    *   **Fast Heal**: If playback fails (404), it attempts to refresh the device ID cache first.
    *   **Full Restart**: If Fast Heal fails, it restarts the embedded player subprocess.
    *   **Routing**: Forces music to `plughw:0,0` (Jack).

### Service Management
The application runs as a systemd service for 24/7 reliability.

*   **Service File**: `/etc/systemd/system/retrophone.service`
*   **User**: `pi`
*   **Auto-Restart**: `Restart=always` (5s delay).
*   **Environment**: `PYTHONUNBUFFERED=1` (for log visibility).
*   **Logs**: `journalctl -u retrophone`
*   **Nightly Reboot**: Cron job at 04:00 AM (`sudo systemctl restart retrophone.service`) to clear memory leaks/audio driver quirks.

---

## 4. Configuration (`src/config.py`)

*   **API Keys**: stored in `.env` (recommended) or environment variables.
    *   `OPENAI_API_KEY`
    *   `ELEVENLABS_API_KEY`
    *   `SPOTIPY_CLIENT_ID` / `SPOTIPY_CLIENT_SECRET`
*   **Audio Settings**:
    *   `AUDIO_DEVICE_ID = 1` (USB Handset).
    *   `DEFAULT_VOLUME = 80`.
*   **Decade Mapping**:
    *   Dial `1` -> 1910s ... `9` -> 1990s ... `0` -> Operator.

---

## 5. Maintenance & Troubleshooting

### Common Commands
```bash
# Check Status
sudo systemctl status retrophone.service

# View Logs (Live)
journalctl -u retrophone -f

# View Logs (Last 100 lines)
journalctl -u retrophone -n 100

# Restart Service
sudo systemctl restart retrophone.service
```

### Authentication (Spotify)
If Spotify stops working (Auth Error):
1.  Run `venv/bin/python3 tools/complete_auth.py` manually via SSH.
2.  Follow the URL to re-authenticate.
3.  The service will pick up the new token automatically.

### "Silent Handset"
If the handset is silent but Music plays:
1.  Check `start.sh` mixer settings.
2.  Verify USB Card Index (`aplay -l`). If it moved from Card 1 to 2, update `config.py`.

### "Wrong Music Playing"
1.  Check `src/brain.py` debug logs.
2.  Ensure Brain is correctly identifying the language (`User Language: CZ`).
3.  Check if the artist spelling was corrected by the Brain's generic rule.

---
v1.0 - Dec 2025
