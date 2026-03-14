from openai import OpenAI
import random
import re
import json
import os
from .config import (OPENAI_API_KEY, DECADE_VOICES, DECADE_PLAYLISTS, DECADE_DJ_NAMES,
                     DECADE_PERSONAS, FEATURE_FLAGS, OPERATOR_VOICE_POOL)

CHAT_HISTORY_DIR = os.path.expanduser("~/RetroPhone/chat_history/")
CHAT_HISTORY_MAX_TURNS = 20


class Brain:
    def __init__(self):
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.chat_history = []
        self._current_history_year = None
        
        # Persona Prompts (legacy — used when ConvAI is off)
        self.operator_prompt_en = """You are 'The Operator', a polite, efficiency-focused switchboard operator.
You help the user with general queries or connecting them to music/radio stations.
Keep answers concise (under 2 sentences). Start with "Operator here." """

        self.operator_prompt_cz = """Jste 'Spojovatelka', zdvorila telefoni operatorka.
Pomaháte s dotazy nebo s prepojenim na hudbu/radio.
Strucne (max 2 vety). Zacnete "Tady centrala." """

    def ask_operator(self, query, language="EN"):
        """
        Ask the Operator a question.
        """
        system_prompt = self.operator_prompt_en if language == "EN" else self.operator_prompt_cz
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-5.2-2025-12-11", # The Ultimate Upgrade
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query}
                ],
                max_completion_tokens=150,
                timeout=5.0 # Prevent hanging on bad network
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"🧠 Brain Error: {e}")
            return "I am unable to connect you at this time." if language == "EN" else "Nemohu vás momentálně spojit."

    def get_voice_for_year(self, year):
        # Round to decade (e.g. 1955 -> 1950)
        decade = int(str(year)[:3] + "0")
        voice = DECADE_VOICES.get(decade, DECADE_VOICES[1900]) # Default fallback
        print(f"🧠 Selected Voice for {year}: {voice}")
        return voice

    def _get_decade(self, year):
        """Convert year to decade key."""
        return int(str(year)[:3] + "0")

    def get_persona(self, year, language="EN"):
        """Get full persona data for a decade."""
        decade = self._get_decade(year)
        return DECADE_PERSONAS.get(decade, DECADE_PERSONAS.get(1950, {}))

    def get_persona_style(self, year, language="EN"):
        """Returns style instructions for the given year."""
        persona = self.get_persona(year, language)
        style_key = "style_cz" if language == "CZ" else "style_en"
        style = persona.get(style_key, persona.get("style_en", "Standard Radio DJ."))
            
        return style

    def get_dj_name(self, year, language="EN"):
        """Get the DJ name for a specific decade."""
        decade = int(str(year)[:3] + "0")
        names = DECADE_DJ_NAMES.get(decade, {"EN": "DJ RetroRadio", "CZ": "DJ RetroRadio"})
        return names.get(language, names["EN"])

    def get_callin_greeting(self, year, language="EN"):
        """Get a short call-in greeting for when user lifts handset during music."""
        dj_name = self.get_dj_name(year, language)
        style = self.get_persona_style(year, language)
        decade = int(str(year)[:3] + "0")

        greetings_en = {
            1900: f"Good day! You've reached {dj_name}. How may I assist you?",
            1910: f"You're on the wire with {dj_name}! What's the word?",
            1920: f"Well hello there, old sport! {dj_name} speaking. What'll it be?",
            1930: f"This is {dj_name} coming at you live! What's your pleasure?",
            1940: f"You're on the air with {dj_name}. Go ahead, caller.",
            1950: f"Hey daddy-o! {dj_name} here. What's your request?",
            1960: f"Far out! {dj_name} on the line. Lay it on me!",
            1970: f"Hey cool cat, you're live with {dj_name}. What's your groove?",
            1980: f"You're on the air with {dj_name}! What's your totally rad request?",
            1990: f"Yo! {dj_name} here. What do you wanna hear?",
            2000: f"Hey! You're live with {dj_name}. What's your request?",
            2010: f"OMG you're on with {dj_name}! What are we playing?",
            2020: f"What's up! {dj_name} here. What's the vibe?",
        }
        greetings_cz = {
            1900: f"Dobry den! U aparatu {dj_name}. Cim mohu slouzit?",
            1910: f"Tady {dj_name}! Co si prejete?",
            1920: f"U aparatu {dj_name}. Co vam smim pustit?",
            1930: f"Tady {dj_name}, mluvte!",
            1940: f"Volate do studia, tady {dj_name}. Posloucham.",
            1950: f"Ahoj! Tady {dj_name}. Co si prejete slyset?",
            1960: f"Nazdar! {dj_name} u mikrofonu. Co zahrajeme?",
            1970: f"Cau! Tady {dj_name}. Jaky bude vas priklad?",
            1980: f"Jste ve vysitani s {dj_name}! Co chcete slyset?",
            1990: f"Cus! Tady {dj_name}. Co pustíme?",
            2000: f"Ahoj! Volate do studia {dj_name}. Jaky mate prani?",
            2010: f"Jste na lince s {dj_name}! Co hrajeme?",
            2020: f"Cau! Tady {dj_name}. Co je za vibe?",
        }

        greetings = greetings_cz if language == "CZ" else greetings_en
        return greetings.get(decade, f"You're on the air with {dj_name}!")

    def _save_history(self, year):
        """Save chat history to disk for persistence across sessions."""
        if not FEATURE_FLAGS.get("persistent_history"):
            return
        try:
            os.makedirs(CHAT_HISTORY_DIR, exist_ok=True)
            path = os.path.join(CHAT_HISTORY_DIR, f"{year}.json")
            with open(path, 'w') as f:
                json.dump(self.chat_history[-CHAT_HISTORY_MAX_TURNS:], f)
        except Exception as e:
            print(f"   (History save error: {e})")

    def _load_history(self, year):
        """Load chat history from disk."""
        if not FEATURE_FLAGS.get("persistent_history"):
            return []
        try:
            path = os.path.join(CHAT_HISTORY_DIR, f"{year}.json")
            if os.path.exists(path):
                with open(path, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"   (History load error: {e})")
        return []

    def get_host_intro(self, year, language="EN"):
        """
        Generate a randomized intro for a specific year's radio host.
        """
        # Load or clear history based on year change
        if self._current_history_year != year:
            self.chat_history = self._load_history(year)
            self._current_history_year = year
        else:
            self.chat_history = []

        dj_name = self.get_dj_name(year, language)
        persona = self.get_persona(year, language)
        style = self.get_persona_style(year, language)
        station = persona.get("station", "KRET Radio")
        city = persona.get("city", "the studio")
        catchphrase = persona.get("catchphrase", "")
        world = persona.get("world", "")
        forbidden = persona.get("forbidden", "")

        # Get world context (weather + historical event) if available
        world_ctx = ""
        if hasattr(self, '_world_context') and self._world_context:
            ctx = self._world_context.get_dj_context(year, language)
            if ctx.get("weather"):
                world_ctx += f"\nCurrent weather in the listener's city: {ctx['weather']}."
            if ctx.get("event"):
                world_ctx += f"\nHistorical context: {ctx['event']}."

        topics_en = ["breaking news", "latest invention", "fashion or celebrity gossip",
                      "the weather and mood in the streets", "a new hit song", "a philosophical thought"]
        topics_cz = ["hlavni zpravu dne", "nejnovejsi vynalaz", "modu nebo drby",
                      "pocasi a naladu na ulicich", "novy hudebni hit", "filosofickou myslenku"]
        topic = random.choice(topics_en) if language == "EN" else random.choice(topics_cz)

        if language == "EN":
            prompt = f"""You are {dj_name}, broadcasting live on {station} from {city} in {year}.
Year: {year}. {world}
Your catchphrase: "{catchphrase}"
Persona/Style: {style}
{world_ctx}

RULES:
- You are LIVE ON AIR. Never acknowledge being AI, a simulation, or a phone system.
- You genuinely live in {year}. {forbidden}
- Use verbal tics, filler words, and era-appropriate slang naturally.

Context: Mention {topic} briefly.
Goal: Introduce yourself as {dj_name} on {station} and ask: "Shall we spin the records, or do you want to chat?"
Max 3 sentences. Punchy — this is live radio."""
        else:
            prompt = f"""Jste {dj_name}, vysilate zive na {station} z {city} v roce {year}.
Rok: {year}. {world}
Vase heslo: "{catchphrase}"
Styl: {style}
{world_ctx}

PRAVIDLA:
- Jste V ZIVEM VYSILANI. Nikdy nezminejte AI, simulaci, ani telefonni system.
- Zijete v roce {year}. {forbidden}

Kontext: Kratce zmiňte {topic}.
Cil: Predstavte se jako {dj_name} na {station} a zeptejte se: "Mam pustit hudbu, nebo si chcete povidat?"
Max 3 vety. Strucne — jste v zivem vysilani."""

        try:
            # Fallback (which shouldn't happen now we verified the model)
            response = self.client.chat.completions.create(
                model="gpt-5.2-2025-12-11",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": "Intro the show!"}
                ],
                max_completion_tokens=200,
                timeout=6.0
            )
            content = response.choices[0].message.content
            # Init History
            self.chat_history.append({"role": "assistant", "content": content})
            return content
        except Exception as e:
            print(f"❌ Intro Error: {e}") # Debug log
            return f"Welcome to {year}."

    def extract_timer_duration(self, user_text):
        """
        Extracts duration in seconds from user text using regex.
        Returns: int (seconds) or None if invalid.
        """
        WORD_NUMS = {
            "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
            "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
            "fifteen": 15, "twenty": 20, "thirty": 30, "forty": 40,
            "forty-five": 45, "half": 0.5, "quarter": 0.25,
            # Czech
            "jedna": 1, "dva": 2, "tri": 3, "ctyri": 4, "pet": 5,
            "deset": 10, "patnact": 15, "dvacet": 20, "tricet": 30,
            "pul": 0.5,
        }

        text = user_text.lower().strip()
        total = 0.0
        handled = set()

        # Handle "half an hour", "pul hodiny"
        m = re.search(r'half\s+an?\s+hour|pul\s+hodin', text)
        if m:
            total += 1800
            handled.add(m.span())

        # Handle "a quarter hour"
        m = re.search(r'quarter\s+(of\s+an?\s+)?hour', text)
        if m:
            total += 900
            handled.add(m.span())

        # Match numeric + unit patterns
        pattern = r'(\d+(?:\.\d+)?|' + '|'.join(re.escape(w) for w in WORD_NUMS) + r')\s*(hours?|hodin[yu]?|minutes?|mins?|minut[yu]?|seconds?|secs?|sekund[yu]?|vter[iy]n[yu]?)'
        for match in re.finditer(pattern, text):
            # Skip if this span overlaps with a handled special case
            if any(h[0] <= match.start() < h[1] for h in handled):
                continue
            val_str, unit = match.groups()
            value = WORD_NUMS.get(val_str, None)
            if value is None:
                try:
                    value = float(val_str)
                except ValueError:
                    continue
            if any(u in unit for u in ['hour', 'hodin']):
                total += value * 3600
            elif any(u in unit for u in ['min', 'minut']):
                total += value * 60
            else:
                total += value

        return int(total) if total > 0 else None


    def extract_contextual_search(self, user_text, context_text, year):
        """
        If user says 'Play it' or 'Play that', extract the song from context.
        """
        prompt = (
            f"User Command: '{user_text}'.\n"
            f"Previous Host Output: '{context_text}'.\n"
            f"Goal: The user wants to play a song mentioned by the host. Extract the Song Title and Artist.\n"
            f"ROBUSTNESS 1: Treat words like 'stone', 'sound', 'soon', 'this' as meaning 'song'.\n"
            f"ROBUSTNESS 2: Phonetic correction (e.g. 'Trailer' -> 'Thriller').\n"
            f"Return ONLY the Spotify Search Query (e.g. 'Bohemian Rhapsody Queen year:{year}')."
            f"If no song is found in context, return 'False'."
        )
        try:
            response = self.client.chat.completions.create(
                model="gpt-5.2-2025-12-11",
                messages=[{"role": "system", "content": prompt}],
                max_completion_tokens=30,
                timeout=4.0
            )
            result = response.choices[0].message.content.strip()
            if "False" in result: return None
            return result.replace('"', '')
        except:
             return None

    def chat_with_host(self, query, year, language="EN"):
        """Interactive chat with the Host Persona."""
        dj_name = self.get_dj_name(year, language)
        persona = self.get_persona(year, language)
        style = self.get_persona_style(year, language)
        station = persona.get("station", "KRET Radio")
        forbidden = persona.get("forbidden", "")

        if language == "EN":
            prompt = f"""You are {dj_name}, broadcasting on {station} in {year}.
Style: {style}
You are LIVE ON AIR. Never break character. {forbidden}
Answer the caller's question about news, culture, or life in {year}.
Be concise (2 sentences). Use era-appropriate language."""
        else:
            prompt = f"""Jste {dj_name}, vysilate na {station} v roce {year}.
Styl: {style}
Jste v zivem vysilani. {forbidden}
Odpovezte volajicimu na dotaz o zprávách, kulture nebo zivote v roce {year}.
Strucne (2 vety)."""
            
        try:
            # Construct messages with history
            messages = [{"role": "system", "content": prompt}]
            # Add up to last 4 turns of history to keep context but save tokens
            messages.extend(self.chat_history[-4:]) 
            messages.append({"role": "user", "content": query})

            response = self.client.chat.completions.create(
                model="gpt-5.2-2025-12-11", 
                messages=messages,
                max_completion_tokens=150,
                timeout=5.0
            )
            
            reply = response.choices[0].message.content
            # Update History
            self.chat_history.append({"role": "user", "content": query})
            self.chat_history.append({"role": "assistant", "content": reply})
            self._save_history(year)

            return reply
        except Exception as e:
             return "Signal lost..."

    def classify_and_extract(self, user_text, year, language="EN"):
        """
        Single GPT call that classifies intent AND extracts search query + DJ confirmation.
        Returns: (search_query, search_type, confirmation_text)
        - CHAT:    (None, "CHAT", None)
        - DEFAULT: (None, "DEFAULT", None)
        - MUSIC:   ("query", "TRACK"/"ARTIST"/"ALBUM"/"PLAYLIST", "DJ confirmation line")
        """

        # Flatten history for context
        history_text = "\\n".join([f"{m['role'].upper()}: {m['content']}" for m in self.chat_history[-4:]])
        dj_name = self.get_dj_name(year, language)
        style = self.get_persona_style(year, language)

        system_prompt = (
            f"You are {dj_name}, a music librarian AND Radio DJ for the year {year}. "
            f"DJ Style: {style}\n"
            f"User Language: {language}.\n"
            f"Review the context and the user's request. First classify intent, then extract search info.\n"
            f"--- CONTEXT ---\n{history_text}\n"
            f"--- END CONTEXT ---\n"
            "STEP 1 — Classify:\n"
            "- If user is asking a question, chatting, or asking ABOUT music (not requesting playback) -> return 'CHAT: None'\n"
            "- If user says generic affirmation like 'Spin the records', 'Play music', 'Yes', 'Lets do it' -> return 'DEFAULT: None'\n"
            "- Otherwise, user wants music -> continue to Step 2.\n"
            "\n"
            "STEP 2 — Extract search query (only if music request):\n"
            "1. If user asks for a specific song (e.g. 'Play Here in My Heart'), use 'TRACK: Song Artist'.\n"
            "2. If user refers to a song in context (e.g. 'Play that', 'Play the trailer'), resolve it to the full title mentioned in Context.\n"
            "3. If user explicitly asks for an ALBUM (e.g. 'Play album Abbey Road'), use 'ALBUM: Album Name Artist'.\n"
            "4. If user asks for music BY or FROM a specific artist (e.g. 'Play Bing Crosby', 'Songs from Elvis'), use 'ARTIST: Artist Name'.\n"
            "5. If user names a famous entity without identifying type, USE YOUR WORLD KNOWLEDGE to infer ARTIST or TRACK.\n"
            "   CRITICAL: If the user explicitly states a song title (e.g. 'the song called X', 'play X from Y'),\n"
            "   you MUST use that EXACT title, even if you don't recognize it. NEVER substitute a different song.\n"
            "   Example: 'Play Here from Mumford and Sons' -> 'TRACK: Here Mumford Sons' (NOT 'I Will Wait').\n"
            "6. If user asks for a genre, mood, or artist collection, use 'PLAYLIST: Query'.\n"
            "7. Limit query to 3-4 keywords.\n"
            "8. Correct spelling errors in proper names to their canonical form.\n"
            "\n"
            "STEP 3 — DJ Confirmation (only if music request):\n"
            f"Write a 1-sentence confirmation in the DJ style of {year}. Mention the artist/song.\n"
            "If it's a track, mention you'll keep the vibe going with similar tracks.\n"
            "\n"
            "OUTPUT FORMAT (exactly):\n"
            "TYPE: Query | CONFIRM: DJ confirmation sentence\n"
            "Examples:\n"
            "- 'TRACK: Here Mumford Sons | CONFIRM: Mumford and Sons? I'll spin that and keep the hits coming!'\n"
            "- 'ARTIST: The Beatles | CONFIRM: The Beatles, far out! Let me drop the needle on their grooviest cuts.'\n"
            "- 'CHAT: None'\n"
            "- 'DEFAULT: None'"
        )

        try:
            response = self.client.chat.completions.create(
                model="gpt-5.2-2025-12-11",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_text}
                ],
                max_completion_tokens=80,
                temperature=0.3
            )
            raw_result = response.choices[0].message.content.strip().replace('"', '')
            print(f"🧠 Raw AI: {raw_result}")

            # Parse: "TYPE: Query | CONFIRM: text" or "CHAT: None" or "DEFAULT: None"
            if ":" not in raw_result:
                return raw_result, "PLAYLIST", None

            # Split on | to separate search from confirmation
            confirm_text = None
            search_part = raw_result
            if "|" in raw_result:
                parts = raw_result.split("|", 1)
                search_part = parts[0].strip()
                confirm_part = parts[1].strip()
                if confirm_part.upper().startswith("CONFIRM:"):
                    confirm_text = confirm_part.split(":", 1)[1].strip()

            # Parse search part: "TYPE: Query"
            type_parts = search_part.split(":", 1)
            s_type = type_parts[0].strip().upper()
            s_query = type_parts[1].strip() if len(type_parts) > 1 else None

            if "CHAT" in s_type:
                return None, "CHAT", None
            if "DEFAULT" in s_type:
                return None, "DEFAULT", None

            return s_query, s_type, confirm_text

        except Exception as e:
            print(f"Error in classify_and_extract: {e}")
            return f"top hits {year}", "PLAYLIST", None

    def generate_dj_commentary(self, previous_track, next_track, year, language="EN"):
        """
        Generate between-song DJ commentary for home audio broadcast.
        previous_track: {name, artist, ...} | next_track: {name, artist, ...} or None
        """
        dj_name = self.get_dj_name(year, language)
        persona = self.get_persona(year, language)
        style = self.get_persona_style(year, language)
        station = persona.get("station", "KRET Radio")
        catchphrase = persona.get("catchphrase", "")

        prev_info = f'"{previous_track["name"]}" by {previous_track["artist"]}' if previous_track else "that last tune"
        next_info = f'Coming up: "{next_track["name"]}" by {next_track["artist"]}.' if next_track else ""

        # Include track features if available
        features_info = ""
        if previous_track and previous_track.get("energy"):
            e = previous_track["energy"]
            features_info = f" (Energy: {'high' if e > 0.7 else 'mellow' if e < 0.4 else 'medium'})"

        if language == "EN":
            prompt = f"""You are {dj_name} on {station}, live from {year}. Style: {style}
You just played {prev_info}{features_info}. {next_info}
Give a brief DJ break (1-2 sentences). Comment on the song, the artist, or drop a fun fact about {year}.
Stay in character. Under 30 words. End with your catchphrase if it fits naturally: "{catchphrase}" """
        else:
            prompt = f"""Jste {dj_name} na {station}, zive z roku {year}. Styl: {style}
Prave jste hrali {prev_info}. {next_info}
Kratky komentar (1-2 vety). Zustaňte v roli. Max 30 slov."""

        try:
            response = self.client.chat.completions.create(
                model="gpt-5.2-2025-12-11",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": "DJ break!"}
                ],
                max_completion_tokens=60,
                timeout=5.0,
                temperature=0.7
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"DJ Commentary Error: {e}")
            return None

    def generate_handoff(self, from_year, to_year, language="EN"):
        """Generate a cross-decade DJ handoff — previous DJ passes to next."""
        from_dj = self.get_dj_name(from_year, language)
        to_dj = self.get_dj_name(to_year, language)
        from_style = self.get_persona_style(from_year, language)

        if language == "EN":
            prompt = f"""You are {from_dj}, a Radio DJ from {from_year}. Style: {from_style}
Sign off and hand over to {to_dj} from {to_year}. One sentence. Stay in character."""
        else:
            prompt = f"""Jste {from_dj}, moderator z roku {from_year}. Styl: {from_style}
Rozlucte se a predejte slovo {to_dj} z roku {to_year}. Jedna veta. Zustaňte v roli."""

        try:
            response = self.client.chat.completions.create(
                model="gpt-5.2-2025-12-11",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": "Sign off!"}
                ],
                max_completion_tokens=60,
                timeout=5.0
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"Handoff Error: {e}")
            return None

    def set_world_context(self, world_context):
        """Set the WorldContext instance for weather/history injection."""
        self._world_context = world_context

    def pick_random_operator_voice(self):
        """Pick a random voice from the operator pool. Returns dict with id, name, style."""
        choice = random.choice(OPERATOR_VOICE_POOL)
        print(f"   Operator voice: {choice['name']} ({choice['style']})")
        return choice

    def build_operator_instructions(self, language="EN", voice_style=None):
        """Build system instructions for the Operator ConvAI session — modern, news-aware."""
        lang_name = "English" if language == "EN" else "Czech"

        # Get real-time context
        ctx_block = ""
        if hasattr(self, '_world_context') and self._world_context:
            op_ctx = self._world_context.get_operator_context(language)
            ctx_block = f"""
CURRENT INFORMATION:
- Date: {op_ctx['date']}, Time: {op_ctx['time']}
- Location: {op_ctx['location']}
- Weather: {op_ctx['weather']}
{op_ctx['news']}"""

        # Random voice personality twist
        personality = ""
        if voice_style:
            personality = f"\nYour PERSONALITY for this call: You speak like a {voice_style}. Stay in this character throughout — it's what makes you memorable and fun!"

        if language == "EN":
            return f"""You are The Operator — a friendly, knowledgeable concierge for RetroPhone Time Travel Radio.
You know EVERYTHING about the modern world.{personality}

You can:
- Answer questions about current events, news, weather, anything
- Play music for the caller (use the play_music tool)
- Play a curated radio station (use the play_era_playlist tool)
- Help the caller navigate decades (tell them to dial 1-8 for different eras)
- Chat about anything — you're smart, witty, and helpful
{ctx_block}

STYLE:
- Start with "Operator here." or a warm greeting
- Be concise but informative (2-3 sentences max)
- You CAN discuss current events, politics, sports, technology — you're modern and aware
- If they ask about news or what's happening, reference the headlines above
- If they ask about weather, tell them the real weather
- Language: {lang_name}

TOOLS:
- play_music: search and play a specific song, artist, or genre
- play_era_playlist: play the default playlist for a decade
- pause_music: pause current playback"""
        else:
            return f"""Jste Operatorka — prateltska, vzdelana concierge pro RetroPhone.
Mluvite s vrelosti operatorky z 50. let, ale vite VSE o modernim svete.
{ctx_block}

STYL:
- Zacnete "Tady centrala." nebo pratelskym pozdravem
- Strucne ale informativne (2-3 vety)
- Muzete diskutovat aktualni udalosti, pocasi, cokoliv
- Jazyk: {lang_name}

NASTROJE:
- play_music: hledani a prehrani hudby
- play_era_playlist: pustit radio daneho desetileti
- pause_music: pozastavit prehravani"""

    def build_realtime_instructions(self, year, language="EN"):
        """Build system instructions for ElevenLabs Conversational AI or Realtime API."""
        dj_name = self.get_dj_name(year, language)
        persona = self.get_persona(year, language)
        style = self.get_persona_style(year, language)
        station = persona.get("station", "KRET Radio")
        city = persona.get("city", "the studio")
        catchphrase = persona.get("catchphrase", "")
        world = persona.get("world", "")
        forbidden = persona.get("forbidden", "")
        lang_name = "English" if language == "EN" else "Czech"

        # Inject world context if available
        world_ctx = ""
        if hasattr(self, '_world_context') and self._world_context:
            ctx = self._world_context.get_dj_context(year, language)
            if ctx.get("weather"):
                world_ctx += f"\nThe listener's weather right now: {ctx['weather']}. You can mention it naturally."
            if ctx.get("event"):
                world_ctx += f"\nFun fact for today: {ctx['event']}"

        return f"""You are {dj_name}, broadcasting live on {station} from {city} in {year}.
{world}
Your catchphrase: "{catchphrase}"
Style: {style}
{world_ctx}

A listener just called in on a vintage rotary telephone. You are LIVE ON AIR.

RULES:
- Never acknowledge being AI, a simulation, or a phone system. You are a REAL DJ.
- You genuinely live in {year}. {forbidden}
- Use era-appropriate slang, filler words, and verbal tics naturally.
- Keep responses SHORT (1-2 sentences) — this is live radio, keep it punchy!
- Language: {lang_name}

TOOLS:
- If they want a specific song/artist, use play_music
- If they say "play music", "spin the records", or just want tunes, use play_era_playlist
- If they want to pause, use pause_music

Be warm, be fun, be {dj_name}. {catchphrase}"""
