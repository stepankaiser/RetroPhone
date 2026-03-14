import os

# ============================================================
# FEATURE FLAGS — Toggle features on/off
# ============================================================
FEATURE_FLAGS = {
    "streaming_tts": True,          # Stream ElevenLabs TTS directly to player
    "callin_greeting": True,        # DJ greets caller when handset lifted during music
    "playback_monitor": True,       # Background thread monitoring Spotify playback
    "dj_breaks": True,              # Proactive DJ commentary between songs
    "show_mode": True,              # Full radio show orchestration
    "conversational_ai": True,      # ElevenLabs Conversational AI (default ON)
    "legacy_mode": False,           # Force legacy listen->classify->speak pipeline
    "persistent_prefs": True,       # Remember user preferences across sessions
    "persistent_history": True,     # Remember chat history across sessions
    "local_whisper": False,         # Local Whisper as offline fallback
    "world_context": True,          # Weather + historical events in DJ prompts
    "led_strip": True,              # WS2812B LED strip visual feedback
    "phonograph_mode": True,        # Local audio for pre-1930s decades
    "discover_mode": True,          # Random decade discovery (dial 99)
}

# ============================================================
# SHOW MODE CONFIGURATION
# ============================================================
DJ_BREAK_PROBABILITY = 0.3
SHOW_DJ_BREAK_INTERVAL = 3
SHOW_JINGLE_INTERVAL = 6
SHOW_BELL_ENABLED = True

# ============================================================
# WORLD CONTEXT
# ============================================================
WEATHER_LOCATION = os.getenv("WEATHER_LOCATION", "Tallinn")

# ============================================================
# HARDWARE CONFIGURATION
# ============================================================
HOOK_PIN = 22
DIAL_PIN = 27
BELL_PINS = (23, 24)
BELL_SPEED = 0.1
LED_PIN = 10  # GPIO 10 (SPI MOSI) for WS2812B — GPIO 18 conflicts with audio PWM

# ============================================================
# AUDIO CONFIGURATION
# ============================================================
DEFAULT_VOLUME = 80
AUDIO_DEVICE_ID = 1  # USB Audio card (Handset mic + speaker)

# ============================================================
# API KEYS
# ============================================================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "your_openai_key_here")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "your_elevenlabs_key_here")
SPOTIPY_CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID", "your_spotify_client_id")
SPOTIPY_CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET", "your_spotify_client_secret")
SPOTIPY_REDIRECT_URI = "http://localhost:8888/callback"

# ============================================================
# DJ NAMES — Each decade has a named personality (EN + CZ)
# ============================================================
DECADE_DJ_NAMES = {
    1900: {"EN": "Professor Whitmore", "CZ": "Profesor Bily"},
    1910: {"EN": "Sergeant Broadcast", "CZ": "Rotmistr Novak"},
    1920: {"EN": "Slick Eddie", "CZ": "Elegantni Eduard"},
    1930: {"EN": "Silver Screen Stan", "CZ": "Pan Redaktor"},
    1940: {"EN": "Captain Airwave", "CZ": "Kapitan Vlna"},
    1950: {"EN": "Wolfman Jack Jr.", "CZ": "Vlcak Honza"},
    1960: {"EN": "Sunshine Sam", "CZ": "Slunickovy Sam"},
    1970: {"EN": "Smooth Barry", "CZ": "Klidny Bara"},
    1980: {"EN": "Thunder Mike", "CZ": "Hromovy Mikes"},
    1990: {"EN": "DJ Xtreme", "CZ": "DJ Extrem"},
    2000: {"EN": "Ryan Fresh", "CZ": "Rysacek"},
    2010: {"EN": "Hashtag Hannah", "CZ": "Hashtag Hanka"},
    2020: {"EN": "Vibe Check", "CZ": "Kontrola Vibi"},
}

# ============================================================
# VOICES — 14 distinct ElevenLabs voices (one per decade + operator)
# ============================================================
DECADE_VOICES = {
    "OPERATOR": {
        "id": "onwK4e9ZLuTAKqWW03F9",  # Daniel — "Steady Broadcaster"
        "settings": {"stability": 0.85, "similarity_boost": 0.80, "style": 0.0},
        "model": "eleven_turbo_v2_5"
    },
    1900: {
        "id": "pqHfZKP75CvOlQylNhV4",  # Bill — "Wise, Mature, Balanced"
        "settings": {"stability": 0.70, "similarity_boost": 0.80, "style": 0.10},
        "model": "eleven_turbo_v2_5"
    },
    1910: {
        "id": "SOYHLrjzK2X1ezoPC6cr",  # Harry — "Fierce Warrior"
        "settings": {"stability": 0.30, "similarity_boost": 0.90, "style": 0.10},
        "model": "eleven_multilingual_v2"
    },
    1920: {
        "id": "cjVigY5qzO86Huf0OWal",  # Eric — "Smooth, Trustworthy"
        "settings": {"stability": 0.55, "similarity_boost": 0.80, "style": 0.20},
        "model": "eleven_turbo_v2_5"
    },
    1930: {
        "id": "nPczCjzI2devNBz1zQrb",  # Brian — "Deep, Resonant, Comforting"
        "settings": {"stability": 0.65, "similarity_boost": 0.75, "style": 0.45},
        "model": "eleven_turbo_v2_5"
    },
    1940: {
        "id": "JBFqnCBsd6RMkjVDRZzb",  # George — "Warm, Captivating Storyteller"
        "settings": {"stability": 0.80, "similarity_boost": 0.75, "style": 0.30},
        "model": "eleven_turbo_v2_5"
    },
    1950: {
        "id": "IKne3meq5aSn9XLyUdCD",  # Charlie — "Deep, Confident, Energetic"
        "settings": {"stability": 0.40, "similarity_boost": 0.75, "style": 0.70},
        "model": "eleven_turbo_v2_5"
    },
    1960: {
        "id": "N2lVS1w4EtoT3dr4eOWO",  # Callum — "Husky Trickster"
        "settings": {"stability": 0.25, "similarity_boost": 0.60, "style": 0.85},
        "model": "eleven_turbo_v2_5"
    },
    1970: {
        "id": "CwhRBWXzGAHq8TQ4Fs17",  # Roger — "Laid-Back, Casual, Resonant"
        "settings": {"stability": 0.80, "similarity_boost": 0.75, "style": 0.20},
        "model": "eleven_turbo_v2_5"
    },
    1980: {
        "id": "pNInz6obpgDQGcFmaJgB",  # Adam — "Dominant, Firm"
        "settings": {"stability": 0.90, "similarity_boost": 0.95, "style": 0.10},
        "model": "eleven_turbo_v2_5"
    },
    1990: {
        "id": "iP95p4xoKVk53GoZ742B",  # Chris — "Charming, Down-to-Earth"
        "settings": {"stability": 0.50, "similarity_boost": 0.75, "style": 0.55},
        "model": "eleven_turbo_v2_5"
    },
    2000: {
        "id": "cgSgspJ2msm6clMCkdW9",  # Jessica — "Playful, Bright, Warm"
        "settings": {"stability": 0.65, "similarity_boost": 0.75, "style": 0.40},
        "model": "eleven_turbo_v2_5"
    },
    2010: {
        "id": "pFZP5JQG7iQjIQuC4Bku",  # Lily — "Velvety Actress"
        "settings": {"stability": 0.50, "similarity_boost": 0.75, "style": 0.50},
        "model": "eleven_turbo_v2_5"
    },
    2020: {
        "id": "FGY2WhTYpPnrIDTdsKH5",  # Laura — "Enthusiast, Quirky Attitude"
        "settings": {"stability": 0.40, "similarity_boost": 0.50, "style": 0.30},
        "model": "eleven_turbo_v2_5"
    },
}

# ============================================================
# DECADE PERSONAS — Rich world-building for immersive DJ prompts
# ============================================================
DECADE_PERSONAS = {
    1900: {
        "station": "The Marconi Hour",
        "city": "London",
        "catchphrase": "Marvelous, simply marvelous!",
        "world": "The Edwardian era. Motorcars are a curiosity, electric lights are spreading, Marconi's wireless is a scientific miracle.",
        "forbidden": "Never mention radio stations, TV, jazz, or anything after 1909.",
        "style_en": "Extremely formal, scientific optimism, Received Pronunciation. 'Splendid', 'Marvelous', 'I say'.",
        "style_cz": "Rakousko-Uhersko, Belle Epoque. Velmi formalni, uctiva cestina. 'Cisar pan', 'Pokrok'.",
    },
    1910: {
        "station": "Trench Radio",
        "city": "the Western Front",
        "catchphrase": "Keep your heads down and your spirits up!",
        "world": "The Great War rages in Europe. Soldiers listen on field wireless sets. Ragtime plays in dance halls back home.",
        "forbidden": "Never mention WWII, radio stations, or anything after 1919.",
        "style_en": "Gritty but resilient, clipped military diction. 'Over there', 'carry on', 'chin up'.",
        "style_cz": "Valecna leta a vznik Republiky. Vlastenecky, odhodlany ton. 'Masaryk', 'Legionari'.",
    },
    1920: {
        "station": "KRET Speakeasy Radio",
        "city": "New York",
        "catchphrase": "The bee's knees, old sport!",
        "world": "Prohibition is on but jazz clubs are hopping. Flappers dance the Charleston. Radio is brand new.",
        "forbidden": "Never mention TV, WWII, or anything after 1929. Alcohol is officially illegal.",
        "style_en": "Fast-talking, energetic, Gatsby-era. 'Old sport', 'the cat's meow', 'ritzy'.",
        "style_cz": "Prvni republika. Spisovna cestina, uctivy ton (Oldrich Novy style).",
    },
    1930: {
        "station": "Golden Age Radio Theater",
        "city": "Hollywood",
        "catchphrase": "Stay tuned, folks!",
        "world": "The Great Depression hits hard, but radio is America's escape. Fireside chats, big band swing.",
        "forbidden": "Never mention TV, WWII outcome, or anything after 1939.",
        "style_en": "Cinematic, storytelling, Transatlantic accent. Warm despite hard times.",
        "style_cz": "Doba filmu a swingu. Melodicky hlas, elegantni vyjadrovani.",
    },
    1940: {
        "station": "Armed Forces Radio",
        "city": "London",
        "catchphrase": "This is your Captain on the airwaves.",
        "world": "World War II defines everything. Rationing, air raids, V-mail. Radio is the lifeline for news and morale.",
        "forbidden": "Never mention the war's outcome, Cold War, or anything after 1949.",
        "style_en": "Authoritative, steady, fatherly. Mid-Atlantic accent. Edward R. Murrow gravitas.",
        "style_cz": "Valecna/Povalecna doba. Vaznejsi, informativni, vlastenecky ton.",
    },
    1950: {
        "station": "K-R-E-T Rock Radio",
        "city": "Memphis",
        "catchphrase": "Keep it rockin', daddy-o!",
        "world": "Rock and roll explodes! Elvis is king, diners have jukeboxes, teens cruise in hot rods.",
        "forbidden": "Never mention Beatles, Vietnam, hippies, or anything after 1959. Rock is BRAND NEW.",
        "style_en": "High-energy, rapid-fire, excitable. 'Daddy-o', 'cool', 'dig it', 'nifty'.",
        "style_cz": "Budovatelske nadseni nebo potlacovany jazz. Dynamicky ton.",
    },
    1960: {
        "station": "Radio RETRO Pirate FM",
        "city": "a ship off the coast",
        "catchphrase": "Broadcasting from international waters, baby!",
        "world": "Counterculture, Beatlemania, flower power. You broadcast illegally from a ship.",
        "forbidden": "Never mention punk, disco, or anything after 1969.",
        "style_en": "Wild, rebellious, breathless. 'Groovy', 'far out', 'peace and love, cats'.",
        "style_cz": "Uvolneni, divadla malych forem. Hravy, inteligentni humor (Semafor style).",
    },
    1970: {
        "station": "KRET-FM Smooth Sounds",
        "city": "San Francisco",
        "catchphrase": "Keep it mellow, keep it real.",
        "world": "FM radio is the new frontier. Album rock, disco at Studio 54. Vinyl is king.",
        "forbidden": "Never mention MTV, CDs, digital music, or anything after 1979.",
        "style_en": "Laid-back, smooth, philosophical. 'Cool cat', 'right on', 'far out'. Speaks slowly.",
        "style_cz": "Normalizace, ale v radiu snaha o 'pohodu'. Klidny, uhlazeny hlas.",
    },
    1980: {
        "station": "POWER-RET FM",
        "city": "Los Angeles",
        "catchphrase": "TOTALLY RADICAL!",
        "world": "MTV launched! Synthesizers rule, hair metal is huge, Cold War at its peak. Neon and Walkmans.",
        "forbidden": "Never mention internet, grunge, or anything after 1989. Berlin Wall is still standing.",
        "style_en": "HYPER-energetic, booming. 'Radical', 'totally', 'awesome', 'bodacious'.",
        "style_cz": "Diskotekova era a pop. Dynamictejsi, mene formalni.",
    },
    1990: {
        "station": "The Morning Zoo on KRET",
        "city": "Seattle",
        "catchphrase": "Whatever, dude. Here's the music.",
        "world": "Grunge killed hair metal. Internet is dial-up. Friends is on TV. Alternative and hip-hop rising.",
        "forbidden": "Never mention smartphones, social media, streaming, or anything after 1999.",
        "style_en": "Casual, ironic, Gen-X sarcasm. 'Whatever', 'as if', 'all that and a bag of chips'.",
        "style_cz": "Svoboda, divoka devadesata. Energicky, zapadni styl moderovani.",
    },
    2000: {
        "station": "HitMix KRET",
        "city": "Miami",
        "catchphrase": "That's what I'm talking about!",
        "world": "Y2K didn't end the world. iPods are new. Reality TV and pop princesses dominate.",
        "forbidden": "Never mention smartphones, Instagram, TikTok, or anything after 2009.",
        "style_en": "Cheerful, corporate-polished. 'Awesome', 'sweet', 'OMG'. Pop radio energy.",
        "style_cz": "Vstup do EU, digitalni doba. Moderni, civilni projev. SuperStar era.",
    },
    2010: {
        "station": "KRET Digital",
        "city": "Brooklyn",
        "catchphrase": "Follow us, like us, stream us!",
        "world": "Smartphones everywhere, Instagram filters, streaming killed the CD. EDM festivals dominate.",
        "forbidden": "Never mention COVID, TikTok virality, or anything after 2019.",
        "style_en": "Curated, social-media-aware. 'Literally', 'I can't even', 'this is everything'.",
        "style_cz": "Doba socialnich siti. Rychly, 'cool' styl komercnich radii.",
    },
    2020: {
        "station": "The RETRO Pod",
        "city": "your living room",
        "catchphrase": "That's the vibe.",
        "world": "Pandemic changed everything. Podcasts are the new radio. TikTok makes songs viral. Vinyl comeback.",
        "forbidden": "Never mention future events. You think old-school radio was better.",
        "style_en": "Conversational, authentic, podcast-style. 'Vibe', 'no cap', 'hits different'.",
        "style_cz": "Soucasnost. Autenticky, podcastovy styl. Uvolnena cestina.",
    },
}

# ============================================================
# SPOTIFY PLAYLISTS — Default fallback per decade
# ============================================================
DECADE_PLAYLISTS = {
    1900: {"EN": "search:Classical 1900s", "CZ": "search:Klasicka hudba"},
    1910: {"EN": "search:1910s Music Ragtime", "CZ": "search:Hudba 1910"},
    1920: {"EN": "search:1920s Jazz Charleston", "CZ": "search:1920s Jazz"},
    1930: {"EN": "search:1930s Big Band Swing", "CZ": "search:1930s Swing"},
    1940: {"EN": "search:1940s Big Band Andrews Sisters", "CZ": "search:1940s Music"},
    1950: {"EN": "search:1950s Rock n Roll Elvis", "CZ": "search:1950s Rock n Roll"},
    1960: {"EN": "search:1960s Classic Rock Beatles", "CZ": "search:1960s Music"},
    1970: {"EN": "search:1970s Classic Rock Disco", "CZ": "search:1970s Music"},
    1980: {"EN": "spotify:playlist:37i9dQZF1DX4UtSsGT1Sbe", "CZ": "spotify:playlist:37i9dQZF1DX4UtSsGT1Sbe"},
    1990: {"EN": "spotify:playlist:37i9dQZF1DXbTxeAdrVG2l", "CZ": "spotify:playlist:37i9dQZF1DXbTxeAdrVG2l"},
    2000: {"EN": "spotify:playlist:37i9dQZF1DX4o1oenSJRJd", "CZ": "spotify:playlist:37i9dQZF1DX4o1oenSJRJd"},
    2010: {"EN": "spotify:playlist:37i9dQZF1DX5Ejj0EkURtP", "CZ": "spotify:playlist:37i9dQZF1DX5Ejj0EkURtP"},
    2020: {"EN": "spotify:playlist:37i9dQZF1DX4JAvqIzK2nW", "CZ": "spotify:playlist:37i9dQZF1DX4JAvqIzK2nW"},
}

# ============================================================
# SOX AUDIO EFFECTS — Vintage post-processing per decade
# ============================================================
DECADE_EFFECTS = {
    1900: "highpass 300 lowpass 3000 overdrive 5",
    1910: "highpass 500 lowpass 2000 overdrive 10",
    1920: "highpass 300 lowpass 3000 overdrive 5",
    1930: "highpass 100 lowpass 4500 overdrive 2 bass +3",
    1940: "highpass 100 lowpass 5000 bass +5 treble -2",
    1950: "highpass 50 lowpass 8000 reverb 20 50 100 100 0 0 compand 0.3,1 6:-70,-60,-20 -5 -90 0.2",
    1960: "highpass 200 lowpass 5000 overdrive 2 compand 0.3,1 6:-70,-60,-20 -5 -90 0.2",
    1970: "bass +2 treble +1",
    1980: "bass +6 treble +4 compand 0.1,0.3 -60,-60,-30,-10,-20,-8,-10,-2,-5,0,0,0 -8 -90 0.1",
    1990: "treble +2",
    2000: "silence 1 0.1 1%",
    2010: "bass +3 treble +3 compand 0.3,1 6:-70,-60,-20 -5 -90 0.2",
    2020: "",
}
