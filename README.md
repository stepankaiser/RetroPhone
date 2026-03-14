# RetroPhone: Time Travel Radio v3.0

An AI-powered "Time Travel Radio" built into a real 1930s rotary phone. Lift the handset, dial a decade, and talk to a live DJ from that era — then listen to the music on your home speakers.

## What It Does

- **Dial 0**: Call the Operator (1950s switchboard style)
- **Dial 1-8**: Jump to a decade (1910s-1980s) — DJ introduces the era, plays music
- **Dial 1900-2030**: Exact year time travel with full DJ experience
- **Dial 9**: Toggle English / Czech
- **Dial 99**: Discover Mode — random decade, learns your taste
- **Dial 666**: Timer mode (ring the bell after N minutes)

## Architecture

```
HOME AUDIO (plughw:0,0 — headphone jack):    HANDSET (plughw:1,0 — USB audio):
├── Spotify music via librespot               ├── Mic input from handset
├── DJ breaks between songs                   ├── DJ voice during phone calls
├── Era-specific jingles                      └── Dial tone & click sounds
└── Phonograph playback (pre-1930s)

LED STRIP (GPIO 10 — SPI):
├── Decade-specific color glow
├── Pulse effect during DJ breaks
└── On-air flash when handset lifted
```

## Core Technologies

| Component | Service | Purpose |
|-----------|---------|---------|
| **Conversation** | ElevenLabs Conversational AI | Real-time voice chat with DJ (sub-500ms latency) |
| **DJ Voices** | ElevenLabs TTS (14 voices) | Unique voice per decade |
| **Intelligence** | OpenAI GPT-5.2 | Persona generation, intent classification |
| **Speech-to-Text** | OpenAI Whisper | Voice transcription (legacy pipeline) |
| **Music** | Spotify + Librespot | Search, playback, smart radio queues |
| **Weather** | wttr.in | Real weather in DJ commentary |
| **History** | Wikimedia API | "On this day" events for DJ context |
| **Visual** | WS2812B LED strip | Decade colors, VU meter, on-air indicator |

## Hardware

- **Raspberry Pi 3 Model B** (headless, WiFi)
- **1930s Rotary Phone** (hook switch, rotary dial, mechanical bell)
- **USB Audio Dongle** (inside phone — mic + earpiece)
- **3.5mm Jack** → Home audio system
- **WS2812B 60-LED Strip** (GPIO 10 via SPI)
- **L298N Motor Driver** (GPIO 23+24 for mechanical bell)

### GPIO Pin Map

| Pin | Function |
|-----|----------|
| GPIO 22 | Hook switch (pull-up) |
| GPIO 27 | Rotary dial pulse (pull-up) |
| GPIO 23 | Bell motor IN1 |
| GPIO 24 | Bell motor IN2 |
| GPIO 10 | WS2812B LED data (SPI MOSI) |

## Installation

### Prerequisites
- Raspberry Pi 3/4/5 with Raspberry Pi OS
- Python 3.9+
- Spotify Premium account
- OpenAI API key
- ElevenLabs API key (Starter tier or above)

### Setup

```bash
# Clone
git clone https://github.com/yourusername/RetroPhone.git
cd RetroPhone

# System dependencies
sudo apt-get install -y libasound2-dev sox libsox-fmt-mp3 mpg123 portaudio19-dev

# Enable SPI (for LED strip)
sudo raspi-config nonint do_spi 0

# Python environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configuration
cp .env.example .env
nano .env  # Add your API keys

# Generate AI jingles (uses ElevenLabs Sound Effects API)
python3 tools/generate_jingles.py

# Deploy as service
sudo cp retrophone.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable retrophone.service
sudo systemctl start retrophone.service
```

### Optional: Phonograph Mode
For authentic pre-1930s audio, add public domain recordings to `sounds/phonograph/`. The system will play these when Spotify has limited results for early decades.

## Source Modules

| Module | Purpose |
|--------|---------|
| `main.py` | Event loop, dial routing, show orchestration |
| `src/config.py` | All configuration: voices, personas, playlists, feature flags |
| `src/brain.py` | LLM intelligence: DJ personas, intent classification, prompts |
| `src/audio_engine.py` | TTS streaming, STT, sound playback, dual audio routing |
| `src/music_engine.py` | Spotify search/play, smart radio, playback monitor |
| `src/conversational_engine.py` | ElevenLabs Conversational AI (real-time voice) |
| `src/show_engine.py` | Radio show lifecycle (DJ breaks, jingles, bell events) |
| `src/world_context.py` | Weather + historical events API |
| `src/led_engine.py` | WS2812B LED strip control |
| `src/phone_interface.py` | GPIO: hook switch, rotary dial, bell motor |
| `src/preferences.py` | Persistent user preferences |

## Feature Flags (`src/config.py`)

```python
FEATURE_FLAGS = {
    "streaming_tts": True,          # Stream TTS directly (no temp file)
    "callin_greeting": True,        # DJ greets when you pick up during music
    "playback_monitor": True,       # Track what's playing for DJ commentary
    "dj_breaks": True,              # DJ talks between songs on home audio
    "show_mode": True,              # Full radio show orchestration
    "conversational_ai": True,      # ElevenLabs real-time voice (default ON)
    "legacy_mode": False,           # Force old listen->think->speak pipeline
    "world_context": True,          # Weather + history in DJ prompts
    "led_strip": True,              # WS2812B LED feedback
    "phonograph_mode": True,        # Local audio for pre-1930s
    "discover_mode": True,          # Random decade on dial 99
    "persistent_prefs": True,       # Remember language/decade across reboots
    "persistent_history": True,     # DJ remembers conversations
}
```

## 14 Unique DJ Voices

Every decade has its own ElevenLabs voice and rich persona:

| Decade | DJ Name | Station | Voice |
|--------|---------|---------|-------|
| Operator | — | — | Daniel "Steady Broadcaster" |
| 1900s | Professor Whitmore | The Marconi Hour | Bill "Wise, Mature" |
| 1910s | Sergeant Broadcast | Trench Radio | Harry "Fierce Warrior" |
| 1920s | Slick Eddie | KRET Speakeasy Radio | Eric "Smooth, Trustworthy" |
| 1930s | Silver Screen Stan | Golden Age Radio Theater | Brian "Deep, Resonant" |
| 1940s | Captain Airwave | Armed Forces Radio | George "Warm Storyteller" |
| 1950s | Wolfman Jack Jr. | K-R-E-T Rock Radio | Charlie "Confident, Energetic" |
| 1960s | Sunshine Sam | Radio RETRO Pirate FM | Callum "Husky Trickster" |
| 1970s | Smooth Barry | KRET-FM Smooth Sounds | Roger "Laid-Back, Resonant" |
| 1980s | Thunder Mike | POWER-RET FM | Adam "Dominant, Firm" |
| 1990s | DJ Xtreme | The Morning Zoo on KRET | Chris "Charming, Down-to-Earth" |
| 2000s | Ryan Fresh | HitMix KRET | Jessica "Playful, Bright" |
| 2010s | Hashtag Hannah | KRET Digital | Lily "Velvety Actress" |
| 2020s | Vibe Check | The RETRO Pod | Laura "Enthusiast, Quirky" |

## Troubleshooting

```bash
# Check status
sudo systemctl status retrophone

# Live logs
journalctl -u retrophone -f

# Restart
sudo systemctl restart retrophone

# Spotify re-auth
cd ~/RetroPhone && source venv/bin/activate
python3 tools/complete_auth.py

# Test hardware
python3 tools/hardware_debug.py    # GPIO pins
python3 tools/verify_spotify.py    # Spotify connection
python3 tools/find_audio_index.py  # Audio devices
```

## Version History

- **v3.0** (Mar 2026) — ElevenLabs Conversational AI, 14 unique voices, rich personas, weather/history context, smart Spotify, LED strip, discover mode, phonograph mode, AI-generated jingles
- **v2.0** (Mar 2026) — DJ names, streaming TTS, song-aware breaks, show mode, cross-decade handoff
- **v1.0** (Dec 2025) — Initial release: rotary phone, decade DJs, Spotify integration
