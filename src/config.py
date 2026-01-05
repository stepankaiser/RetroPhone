import os

# --- HARDWARE CONFIGURATION ---
HOOK_PIN = 22
DIAL_PIN = 27
BELL_PINS = (23, 24)
BELL_SPEED = 0.1 # Seconds (0.1 verified good for mechanical hammer)

# --- AUDIO CONFIGURATION ---
# Volume settings, device IDs, etc.
DEFAULT_VOLUME = 80
AUDIO_DEVICE_ID = 1 # USB Audio (Conversation Mic/Speaker)

# MUSIC ROUTING NOTE:
# For now (testing): Music also goes to USB (Card 2).
# Production: Music will go to Headphone Jack (Card 1 or 0).
# This is controlled by /etc/raspotify/conf, NOT this file.

# --- API KEYS ---
# SECURITY WARNING: Never commit actual keys to GitHub!
# Load from Environment Variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "your_openai_key_here")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "your_elevenlabs_key_here")

# Spotify Credentials
SPOTIPY_CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID", "your_spotify_client_id")
SPOTIPY_CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET", "your_spotify_client_secret")
SPOTIPY_REDIRECT_URI = "http://localhost:8888/callback"
# --- VOICES (ElevenLabs IDs) ---
# You can find new voices at https://elevenlabs.io/app/voice-lab
# Mapping: Decade -> Voice ID
# --- VOICES (ElevenLabs IDs) ---
# Mapping: Decade -> { 'id': str, 'settings': dict, 'model': str }
DECADE_VOICES = {
    # Default / Operator (Professional, Transatlantic vibe)
    "OPERATOR": { 
        "id": "JBFqnCBsd6RMkjVDRZzb", # George
        "settings": {"stability": 0.8, "similarity_boost": 0.75, "style": 0.0},
        "model": "eleven_turbo_v2_5"
    },
    
    # 1910: Mechanical Age (Old British, Unstable)
    1910: {
        "id": "JBFqnCBsd6RMkjVDRZzb", # Old/Mature British (George)
        "settings": {"stability": 0.25, "similarity_boost": 0.95, "style": 0.0},
        "model": "eleven_multilingual_v2" # v1/v2 for glitchiness
    },
    # 1920: Birth of Broadcasting (Formal, Tenor, Slow)
    1900: { "id": "JBFqnCBsd6RMkjVDRZzb", "settings": {"stability": 0.50, "similarity_boost": 0.80, "style": 0.10}, "model": "eleven_turbo_v2_5"},
    1920: {
        "id": "JBFqnCBsd6RMkjVDRZzb", # George (Formal)
        "settings": {"stability": 0.50, "similarity_boost": 0.80, "style": 0.10},
        "model": "eleven_turbo_v2_5"
    },
    # 1930: Golden Era (Fast Newsman, Staccato, High Drama)
    1930: {
        "id": "TxGEqnHWrfWFTfGW9XjX", # Josh (Deep/Narrator)
        "settings": {"stability": 0.65, "similarity_boost": 0.75, "style": 0.45},
        "model": "eleven_turbo_v2_5"
    },
    # 1940: War News (Authoritative, Steady, Fatherly)
    1940: {
        "id": "JBFqnCBsd6RMkjVDRZzb", # George
        "settings": {"stability": 0.80, "similarity_boost": 0.75, "style": 0.30},
        "model": "eleven_turbo_v2_5"
    },
    # 1950: Rock n Roll (Excited, High Energy, Smile)
    1950: {
        "id": "ErXwobaYiN019PkySvjV", # Antoni (Bold/Excited)
        "settings": {"stability": 0.40, "similarity_boost": 0.75, "style": 0.70},
        "model": "eleven_turbo_v2_5"
    },
    # 1960: Pirate Radio (Raspy, Wild, Unstable)
    1960: {
        "id": "ErXwobaYiN019PkySvjV", # Antoni (Pushed)
        "settings": {"stability": 0.25, "similarity_boost": 0.50, "style": 0.90},
        "model": "eleven_turbo_v2_5"
    },
    # 1970: FM Cool (Smooth, Deep, Laid back)
    1970: {
        "id": "TxGEqnHWrfWFTfGW9XjX", # Josh (Deep/Smooth)
        "settings": {"stability": 0.85, "similarity_boost": 0.75, "style": 0.20},
        "model": "eleven_turbo_v2_5"
    },
    # 1980: Voice of God (Deep Promo, Perfect, Robotic)
    1980: {
        "id": "TxGEqnHWrfWFTfGW9XjX", # Josh (Epic)
        "settings": {"stability": 0.95, "similarity_boost": 1.00, "style": 0.0},
        "model": "eleven_turbo_v2_5"
    },
    # 1990: Morning Zoo (Casual, Sarcastic, Noisy)
    1990: {
        "id": "21m00Tcm4TlvDq8ikWAM", # Rachel (Conversational)
        "settings": {"stability": 0.50, "similarity_boost": 0.75, "style": 0.60},
        "model": "eleven_turbo_v2_5"
    },
    # 2000: Top 40 (Cheerful, Corporate, Clean)
    2000: {
        "id": "21m00Tcm4TlvDq8ikWAM", # Rachel
        "settings": {"stability": 0.70, "similarity_boost": 0.75, "style": 0.40},
        "model": "eleven_turbo_v2_5"
    },
    # 2010: Social Media Age (Fast, Curated)
    2010: {
        "id": "MF3mGyEYCl7XYWbV9V6O", # Elli (Younger)
        "settings": {"stability": 0.50, "similarity_boost": 0.75, "style": 0.50},
        "model": "eleven_turbo_v2_5"
    },
    # 2020: Podcast (Vocal Fry, Raw, Conversational)
    2020: {
        "id": "21m00Tcm4TlvDq8ikWAM", # Rachel/Patrick
        "settings": {"stability": 0.40, "similarity_boost": 0.40, "style": 0.0},
        "model": "eleven_turbo_v2_5"
    }
}

# --- SPOTIFY PLAYLISTS ---
# Format: { Decade_Int: {"EN": "spotify:playlist:...", "CZ": "spotify:playlist:..."} }
DECADE_PLAYLISTS = {
    1900: {"EN": "search:Classical 1900s", "CZ": "search:Klasická hudba"}, 
    1910: {"EN": "search:1910s Music", "CZ": "search:Hudba 1910"}, 
    1920: {"EN": "search:1920s Jazz", "CZ": "search:1920s Jazz"}, 
    1930: {"EN": "search:1930s Jazz", "CZ": "search:1930s Jazz"}, 
    1940: {"EN": "search:1940s Big Band", "CZ": "search:1940s Music"}, 
    1950: {"EN": "search:1950s Rock n Roll", "CZ": "search:1950s Rock n Roll"}, 
    1960: {"EN": "search:1960s Golden Oldies", "CZ": "search:1960s Music"}, 
    1970: {"EN": "search:1970s Classic Rock", "CZ": "search:1970s Music"}, 
    1980: {"EN": "spotify:playlist:37i9dQZF1DX4UtSsGT1Sbe", "CZ": "spotify:playlist:37i9dQZF1DX4UtSsGT1Sbe"}, # All Out 80s (Seems OK)
    1990: {"EN": "spotify:playlist:37i9dQZF1DXbTxeAdrVG2l", "CZ": "spotify:playlist:37i9dQZF1DXbTxeAdrVG2l"}, # All Out 90s (Seems OK)
    2000: {"EN": "spotify:playlist:37i9dQZF1DX4o1oenSJRJd", "CZ": "spotify:playlist:37i9dQZF1DX4o1oenSJRJd"}, # All Out 00s (Seems OK)
    2010: {"EN": "spotify:playlist:37i9dQZF1DX5Ejj0EkURtP", "CZ": "spotify:playlist:37i9dQZF1DX5Ejj0EkURtP"}, # All Out 10s (Seems OK)
    2020: {"EN": "spotify:playlist:37i9dQZF1DX4JAvqIzK2nW", "CZ": "spotify:playlist:37i9dQZF1DX4JAvqIzK2nW"}, # Today's Top Hits (Seems OK)
}

# --- SOX AUDIO EFFECTS (Post-Production) ---
# Raw Sox effects chains.
# Highpass/Lowpass = EQ Orez
# Overdrive = Distortion/Saturation
# Reverb = Room sound
# Pinknoise = Static overlay (handled by mixing, but we simulate using distortion for now)
DECADE_EFFECTS = {
    # 1910: Mechanical Age (Carbon Mic, Narrow Band)
    1910: "highpass 500 lowpass 2000 overdrive 10", 

    # 1920: Early Broadcast (Slightly better, still narrow)
    1900: "highpass 300 lowpass 3000 overdrive 5",
    1920: "highpass 300 lowpass 3000 overdrive 5",
    
    # 1930: Golden Era (Tube Saturation, Warmth)
    # Bass boost (150-300Hz) simulation via eq
    1930: "highpass 100 lowpass 4500 overdrive 2 bass +3",
    
    # 1940: War (Ribbon Mic, Mid-range punch)
    1940: "highpass 100 lowpass 5000 bass +5 treble -2",
    
    # 1950: Rock n Roll (Spring Reverb, Compression)
    # compand = compressor/expander
    1950: "highpass 50 lowpass 8000 reverb 20 50 100 100 0 0 compand 0.3,1 6:-70,-60,-20 -5 -90 0.2",
    
    # 1960: Pirate (Compressed, AM Radio filter)
    1960: "highpass 200 lowpass 5000 overdrive 2 compand 0.3,1 6:-70,-60,-20 -5 -90 0.2",
    
    # 1970: FM Stereo (Full Range, Smooth)
    # Minimal processing, just warmth
    1970: "bass +2 treble +1",
    
    # 1980: Voice of God (V-Shape EQ, Hard Limit)
    1980: "bass +6 treble +4 compand 0.1,0.3 -60,-60,-30,-10,-20,-8,-10,-2,-5,0,0,0 -8 -90 0.1",
    
    # 1990: Morning Zoo (Dry, Close Mic)
    1990: "treble +2", # Just a bit of crispness
    
    # 2000: Digital (Clean, Gate)
    2000: "silence 1 0.1 1%", # Noise gate effect
    
    # 2010: Modern (Broadcast Processed)
    2010: "bass +3 treble +3 compand 0.3,1 6:-70,-60,-20 -5 -90 0.2",
    
    # 2020: Podcast (Raw, Vocal Fry friendly)
    2020: "", # No processing (Raw)
}

