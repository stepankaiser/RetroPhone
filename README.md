# RetroPhone: Time Travel Radio

> **A real 1930s rotary phone transformed into an AI-powered time travel radio.** Lift the handset, dial a year, and have a real-time voice conversation with a DJ from that era — complete with era-appropriate music from Spotify, live weather, and historical events from the day you're calling.

Built on Raspberry Pi 3 with ElevenLabs Conversational AI, OpenAI GPT, and Spotify.

---

## How It Works

Pick up the handset on a real vintage rotary phone. Dial a number. A DJ from that era answers — in character, with a unique voice, broadcasting from a fictional radio station. Ask for music, chat about life in that year, or just listen.

| Dial | What Happens |
|------|-------------|
| **0** | Call the Operator — a modern concierge with a random personality each call (pirate, cowboy, wrestling announcer...). Knows today's weather, news, and can play anything on Spotify. |
| **1-8** | Decade shortcut — instant music from 1910s through 1980s |
| **1900-2030** | Dial an exact year — full DJ experience with era persona |
| **100-1899** | Classical era — Maestro Bradford hosts from Vienna's Royal Concert Hall |
| **99** | Discover Mode — random decade, learns your taste over time |
| **9** | Toggle English / Czech |
| **666** | Timer — ring the bell after N minutes |

### The Radio Model

```
HOME SPEAKERS (3.5mm jack)          PHONE HANDSET (USB audio)
├── Spotify music                   ├── Your voice (mic)
├── Phonograph playback (pre-1930)  └── DJ voice (speaker)
└── DJ breaks between songs
```

Music plays on your home audio system. The phone is just for calling in — like a real radio station.

---

## 14 DJ Personalities

Every decade has its own named DJ with a unique ElevenLabs voice, fictional station, catchphrase, and era-specific knowledge. The DJs never break character and don't know anything beyond their time period.

| Decade | DJ | Station | Catchphrase |
|--------|-----|---------|-------------|
| 1900s | Professor Whitmore | The Marconi Hour | *"Marvelous, simply marvelous!"* |
| 1910s | Sergeant Broadcast | Trench Radio | *"Keep your heads down and spirits up!"* |
| 1920s | Slick Eddie | KRET Speakeasy Radio | *"The bee's knees, old sport!"* |
| 1930s | Silver Screen Stan | Golden Age Radio Theater | *"Stay tuned, folks!"* |
| 1940s | Captain Airwave | Armed Forces Radio | *"This is your Captain on the airwaves."* |
| 1950s | Wolfman Jack Jr. | K-R-E-T Rock Radio | *"Keep it rockin', daddy-o!"* |
| 1960s | Sunshine Sam | Radio RETRO Pirate FM | *"Broadcasting from international waters, baby!"* |
| 1970s | Smooth Barry | KRET-FM Smooth Sounds | *"Keep it mellow, keep it real."* |
| 1980s | Thunder Mike | POWER-RET FM | *"TOTALLY RADICAL!"* |
| 1990s | DJ Xtreme | The Morning Zoo on KRET | *"Whatever, dude."* |
| 2000s | Ryan Fresh | HitMix KRET | *"That's what I'm talking about!"* |
| 2010s | Hashtag Hannah | KRET Digital | *"Follow us, like us, stream us!"* |
| 2020s | Vibe Check | The RETRO Pod | *"That's the vibe."* |
| Classical | Maestro Bradford | The Royal Concert Hall | *"Exquisite. Simply exquisite."* |

The **Operator** (dial 0) is special — a modern, all-knowing concierge who randomly picks a different voice personality each call from a pool of 12 characters including a grumpy Italian grandpa, a pirate, a wrestling announcer, a demon, and a cowboy. Same knowledge, different personality every time.

---

## What the DJ Can Do

The DJs aren't just voice personas — they have real tools:

| Tool | Example |
|------|---------|
| **Play music** | *"Play Born to Run by Springsteen"* → searches Spotify and plays |
| **Queue songs** | *"Play X and then queue Y"* → plays first, queues second |
| **Search & browse** | *"What albums does Radiohead have?"* → lists options, lets you pick |
| **Now playing** | *"What's this song?"* → tells you track name, artist, album |
| **Skip track** | *"Next!"* → skips to next song |
| **Pause** | *"Stop the music"* → pauses playback |
| **Weather** | *"What's the weather?"* → live data from wttr.in |
| **News** | *"What's happening in the world?"* → top BBC headlines |
| **Era playlist** | *"Spin the records!"* → plays curated decade playlist |

---

## Tech Stack

| Layer | Technology | Role |
|-------|-----------|------|
| **Real-time voice** | [ElevenLabs Conversational AI](https://elevenlabs.io/conversational-ai) | Sub-second voice conversation with custom voices, turn detection, interruption support |
| **Intelligence** | [OpenAI GPT](https://openai.com) | DJ personas, intent classification, era-specific knowledge |
| **Music** | [Spotify](https://developer.spotify.com) + [Librespot](https://github.com/librespot-org/librespot) | Search, playback, queue management. 320kbps with volume normalization |
| **Weather** | [wttr.in](https://wttr.in) | Live weather injected into DJ prompts (no API key needed) |
| **History** | [Wikimedia API](https://api.wikimedia.org) | "On this day" events filtered to each decade |
| **Hardware** | [Raspberry Pi 3](https://www.raspberrypi.com) | GPIO for rotary dial, hook switch, and bell motor |

### Audio Architecture

- **Home speakers** (Pi headphone jack → amplifier): All music and DJ breaks
- **Phone handset** (USB audio dongle inside phone): Voice conversation only
- **Librespot**: Embedded Spotify Connect player, 320kbps, volume normalization, tpdf_hp dithering

---

## Hardware

### What You Need

- Raspberry Pi 3/4/5 with Raspberry Pi OS
- A rotary phone (any vintage phone with a hook switch and rotary dial)
- USB audio dongle (inside the phone — connects to handset mic + earpiece)
- 3.5mm cable to home audio system
- L298N motor driver (optional — for mechanical bell)
- Spotify Premium account
- ElevenLabs API key (Starter tier or above)
- OpenAI API key

### Wiring

| Wire | Pi GPIO | Function |
|------|---------|----------|
| Hook switch | GPIO 22 (pull-up) | Detects handset lift/replace |
| Rotary dial pulse | GPIO 27 (pull-up) | Counts dial pulses |
| Bell motor IN1 | GPIO 23 | Mechanical bell strike |
| Bell motor IN2 | GPIO 24 | Mechanical bell return |

---

## Installation

```bash
# Clone
git clone https://github.com/stepankaiser/RetroPhone.git
cd RetroPhone

# System dependencies
sudo apt-get install -y libasound2-dev sox libsox-fmt-mp3 mpg123 portaudio19-dev

# Python environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configuration
cp .env.example .env
nano .env  # Add your API keys: OPENAI_API_KEY, ELEVENLABS_API_KEY, SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET

# Generate AI sound effects (uses ElevenLabs Sound Effects API)
python3 tools/generate_jingles.py

# Deploy as systemd service (auto-start on boot)
sudo cp retrophone.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable retrophone.service
sudo systemctl start retrophone.service
```

### Optional: Phonograph Mode

For pre-1930s decades, Spotify has limited content. Add public domain recordings to `sounds/phonograph/` or generate them:

```bash
python3 tools/generate_jingles.py  # Also generates phonograph audio via ElevenLabs Sound Effects API
```

---

## Project Structure

```
RetroPhone/
├── main.py                        # Main event loop and dial routing
├── start.sh                       # Service startup (ALSA setup, cleanup)
├── retrophone.service             # systemd unit file
├── requirements.txt
├── .env.example
│
├── src/
│   ├── config.py                  # Voices, personas, playlists, feature flags
│   ├── brain.py                   # LLM prompts, DJ personas, intent classification
│   ├── audio_engine.py            # TTS streaming, STT, SoX vintage effects
│   ├── music_engine.py            # Spotify search/play/queue, playback monitor
│   ├── conversational_engine.py   # ElevenLabs ConvAI (real-time voice sessions)
│   ├── phone_interface.py         # GPIO: hook switch, rotary dial, bell
│   ├── world_context.py           # Weather (wttr.in) + historical events (Wikimedia)
│   ├── show_engine.py             # Radio show lifecycle (DJ breaks, jingles)
│   ├── led_engine.py              # WS2812B LED strip control
│   └── preferences.py             # Persistent user preferences (JSON)
│
├── sounds/
│   ├── dial_tone.wav              # Classic 425Hz interrupted tone
│   ├── click.wav                  # Connection click
│   ├── static_*.wav               # Time-travel transition effects
│   ├── jingle_*.mp3               # AI-generated era-specific jingles
│   └── phonograph/                # Pre-1930s public domain recordings
│
└── tools/
    ├── generate_jingles.py        # Generate jingles via ElevenLabs Sound Effects
    ├── sound_generator.py         # Synthesize dial tones, static, clicks
    ├── verify_spotify.py          # Test Spotify connection
    ├── hardware_debug.py          # GPIO pin monitor
    ├── find_audio_index.py        # ALSA device discovery
    └── complete_auth.py           # Spotify OAuth helper
```

---

## Configuration

All behavior is controlled via feature flags in `src/config.py`:

```python
FEATURE_FLAGS = {
    "conversational_ai": True,   # ElevenLabs real-time voice (the main experience)
    "streaming_tts": True,       # Stream TTS directly to speaker (low latency)
    "callin_greeting": True,     # DJ greets when you pick up during music
    "playback_monitor": True,    # Track what Spotify is playing
    "world_context": True,       # Weather + historical events in DJ prompts
    "phonograph_mode": True,     # Local audio fallback for pre-1930s
    "discover_mode": True,       # Random decade exploration (dial 99)
    "persistent_prefs": True,    # Remember language across reboots
    "persistent_history": True,  # DJ remembers conversations per decade
    "dj_breaks": False,          # DJ commentary between songs
    "show_mode": False,          # Full radio show (jingles, bell events)
    "led_strip": False,          # WS2812B LED strip (needs Pi 4+ for audio compatibility)
    "legacy_mode": False,        # Force old sequential pipeline (Whisper→GPT→ElevenLabs TTS)
}
```

---

## How It's Built

### Real-Time Voice (ElevenLabs Conversational AI)

The core experience uses ElevenLabs' Conversational AI SDK. A single WebSocket session handles speech-to-text, LLM reasoning, and text-to-speech in one pipeline — giving sub-second voice response latency. The agent is created via API with 9 client-side tools for Spotify control, weather, and news.

Each call starts a new session with per-decade overrides for voice, prompt, first message, and language. The DJ's system prompt includes the station name, era context, catchphrase, current weather, and a historical event from today's date in that decade.

### Legacy Pipeline (Fallback)

If ConvAI is unavailable, the system falls back to a sequential pipeline: SoX VAD recording → OpenAI Whisper STT → GPT classification/response → ElevenLabs TTS streaming → SoX vintage audio effects → speaker output. This adds 4-8 seconds of latency but works offline from ElevenLabs' ConvAI service.

### Vintage Audio Effects

Each decade has a SoX effects chain that simulates the audio technology of the time:
- 1910s: narrow bandwidth + heavy overdrive (carbon microphone)
- 1930s: tube warmth + bass boost (golden age radio)
- 1950s: spring reverb + compression (rock n roll AM radio)
- 1980s: V-shaped EQ + hard limiting (voice of God FM promos)
- 2020s: no processing (raw podcast quality)

---

## Troubleshooting

```bash
sudo systemctl status retrophone      # Check service status
journalctl -u retrophone -f           # Live logs
sudo systemctl restart retrophone     # Restart

# Spotify re-authentication
cd ~/RetroPhone && source venv/bin/activate
python3 tools/complete_auth.py

# Hardware diagnostics
python3 tools/hardware_debug.py       # GPIO pin states
python3 tools/verify_spotify.py       # Spotify connection test
python3 tools/find_audio_index.py     # Audio device discovery
```

---

## Version History

| Version | Date | Highlights |
|---------|------|------------|
| **v3.0** | Mar 2026 | ElevenLabs Conversational AI, 14 unique community voices, 9 Spotify/weather/news tools, random operator personalities, classical era, queue support, discover mode, world context |
| **v2.0** | Mar 2026 | DJ names, streaming TTS, song-aware DJ breaks, show mode, cross-decade handoff, LED strip support |
| **v1.0** | Dec 2025 | Initial release: rotary phone integration, decade DJs, Spotify playback, bilingual (EN/CZ) |

---

## License

MIT

---

*Built with a 1930s phone, a Raspberry Pi, and a mass of AI magic.*
