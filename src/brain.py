from openai import OpenAI
import random
from .config import OPENAI_API_KEY, DECADE_VOICES, DECADE_PLAYLISTS

class Brain:
    def __init__(self):
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.chat_history = [] # Stateful conversation memory
        
        # Persona Prompts
        self.operator_prompt_en = """
        You are 'The Operator', a polite, efficiency-focused switchboard operator from the 1950s. 
        Your accent is neutral and professional (Transatlantic style).
        You help the user with general queries or connecting them to specific music/radio stations.
        Keep answers concise (under 2 sentences).
        Start response with "Operator here." or "Connecting...".
        """
        
        self.operator_prompt_cz = """
        Jste 'Spojovatelka', zdvořilá a efektivní telefonní operátorka z 50. let.
        Pomáháte uživateli s dotazy nebo s přepojením na hudbu/rádio.
        Odpovědi musí být stručné (max 2 věty).
        Začněte odpověď slovy "Tady centrála." nebo "Přepojuji...".
        """

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

    def get_persona_style(self, year, language="EN"):
        """
        Returns specific style/mood instructions for the given year.
        """
        decade = int(str(year)[:3] + "0")
        
        styles = {
            1900: "Edwardian Era / Turn of the Century. Extremely formal, scientific optimism. Vocabulary: 'Splendid', 'Marvelous'.",
            1910: "WWI Era / Industrial. Gritty but resilient. News-focused tone. 'Over there', 'The Great War'.",
            1920: "Jazz age, energetic but polite, 'Old Sport', 'Bee's Knees'. Fast talking.",
            1930: "Great Depression era but hopeful radio voice. Cinematic, storytelling tone.",
            1940: "WWII/Post-War. Transatlantic accent (Mid-Atlantic). Formal, patriotic, serious but warm.",
            1950: "Rock n Roll craze. High energy, rapid fire. Slang: 'Daddy-o', 'Cool', 'Nifty'.",
            1960: "Counter-culture vs Pop. Example: 'Groovy', 'Far out'. smooth or very excited.",
            1970: "Disco & Classic Rock. Laid back, chill, 'cool cat'. Smooth FM radio style.",
            1980: "MTV generation. Hyper-energetic, maybe slightly valley girl or loud DJ. 'Radical', 'Totally'.",
            1990: "Alternative/Pop. Casual, maybe a bit ironic or 'Morning Zoo' crew energy.",
            2000: "Y2K Era / Millennial Pop. Tech optimism, fast-paced, 'Awesome', 'Sweet'.",
            2010: "Social Media Age. Highly curated, energetic, 'Top 40' radio host style.",
            2020: "Present Day. Modern slang, podcast-style conversational tone. 'Vibe', 'Trendy'.",
        }
        
        style = styles.get(decade, "Standard Radio DJ. Professional and charismatic.")
        
        if language == "CZ":
            # Simple mapping to Czech contexts
            cz_styles = {
                1900: "Rakousko-Uhersko, Belle Époque. Velmi formální, uctivá čeština. 'Císař pán', 'Pokrok'.",
                1910: "Válečná léta a vznik Republiky. Vlastenecký, odhodlaný tón. 'Masaryk', 'Legionáři'.",
                1920: "První republika. Spisovná čeština, uctivý tón (Oldřich Nový style).",
                1930: "Doba filmu a swingu. Melodický hlas, elegantní vyjadřování.",
                1940: "Válečná/Poválečná doba. Vážnější, informativní, vlastenecký tón.",
                1950: "Budovatelské nadšení (často hrané) nebo potlačovaný jazz. Oficiální tón.",
                1960: "Uvolnění, divadla malých forem. Hravý, inteligentní humor (Semafor style).",
                1970: "Normalizace, ale v rádiu snaha o 'pohodu'. Klidný, uhlazený hlas.",
                1980: "Diskotéková éra a pop. Dynamičtější, méně formální.",
                1990: "Svoboda, divoká devadesátá. Energický, západní styl moderování. 'Nová éra'.",
                2000: "Vstup do EU, digitální doba. Moderní, civilní projev. SuperStar éra.",
                2010: "Doba sociálních sítí. Rychlý, 'cool' styl komerčních rádií (Evropa 2).",
                2020: "Současnost. Autentický, podcastový styl. Uvolněná čeština.",
            }
            style = cz_styles.get(decade, "Standardní rádiový moderátor.")
            
        return style

    def get_host_intro(self, year, language="EN"):
        """
        Generate a randomized intro for a specific year's radio host. 
        """
        # Clear history on new intro/year change
        self.chat_history = []
        
        style = self.get_persona_style(year, language)
        
        # RANDOMIZATION: Pick a topic to keep it fresh
        topics_en = [
            "breaking news headline",
            "latest technology or invention",
            "fashion trend or celebrity gossip",
            "the weather and general mood in the streets",
            "a new hit song or musical trend",
            "a philosophical thought about this modern era"
        ]
        topics_cz = [
            "hlavní zprávu dne",
            "nejnovější technický vynález nebo trend",
            "módu nebo drby o celebritách",
            "počasí a náladu na ulicích",
            "nový hudební hit nebo styl",
            "filosofickou myšlenku o této moderní době"
        ]
        
        topic = random.choice(topics_en) if language == "EN" else random.choice(topics_cz)
        
        if language == "EN":
            prompt = f"""
            You are a Radio DJ from {year}. 
            Year: {year}.
            **Persona/Style**: {style}
            Context: Talk briefly about: {topic}.
            Goal: Introduce yourself and ask the user: "Shall we spin the records, or do you want to chat more about {year}?"
            Keep it under 3 sentences. Stay strictly in character.
            """
        else:
            prompt = f"""
            Jste rádiový moderátor z roku {year}.
            Rok: {year}.
            **Styl/Osobnost**: {style}
            Kontext: Krátce zmiňte: {topic}.
            Cíl: Uvítejte posluchače a zeptejte se: "Mám pustit hudbu, nebo si chcete povídat o roce {year}?"
            Max 3 věty. Držte se role.
            """

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
        Extracts duration in seconds from user text using LLM.
        Returns: int (seconds) or None if invalid.
        """
        try:
            # Simple prompt to extract integer seconds
            response = self.client.chat.completions.create(
                model="gpt-5.2-2025-12-11", # Fallback to standard model
                messages=[
                    {"role": "system", "content": "You are a time parser. Convert the user's time request into TOTAL SECONDS. Return ONLY the integer number. If no time is found, return 0. Examples: '5 minutes' -> 300, 'one hour' -> 3600, '10 seconds' -> 10, 'Set a timer' -> 0"},
                    {"role": "user", "content": user_text}
                ],
                temperature=0.0
            )
            val = response.choices[0].message.content.strip()
            # Clean non-digits just in case
            val = ''.join(filter(str.isdigit, val))
            if not val: return None
            seconds = int(val)
            return seconds if seconds > 0 else None
        except Exception as e:
            print(f"Time Parse Error: {e}")
            return None


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
        """
        Interactive chat with the Host Persona.
        """
        style = self.get_persona_style(year, language)
        
        if language == "EN":
            prompt = f"""
            You are a Radio DJ from {year}. 
            **Persona/Style**: {style}
            Stay in character. Answer the user's question about the news, culture, or life in {year}.
            Be concise (2 sentences).
            """
        else:
            prompt = f"""
            Jste moderátor z roku {year}.
            **Styl/Osobnost**: {style}
            Zůstaňte v roli. Odpovězte uživateli na dotaz ohledně zpráv, kultury nebo života v roce {year}.
            Stručně (2 věty).
            """
            
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
            
            return reply
        except Exception as e:
             return "Signal lost..."

    def get_music_search_query(self, user_text, year, language="EN"):
        """
        Extracts a music search query AND type (TRACK vs PLAYLIST).
        Uses Chat History to understand context ("Play that", "Play trailer").
        """
        
        # Flatten history for the music librarian prompt
        history_text = "\\n".join([f"{m['role'].upper()}: {m['content']}" for m in self.chat_history[-4:]])
        
        system_prompt = (
            f"You are a music librarian for the year {year}. "
            f"User Language: {language}.\n"
            f"Review the recent conversation context and the user's request to extract a Spotify search query.\n"
            f"--- CONTEXT ---\n{history_text}\n"
            f"--- END CONTEXT ---\n"
            "Format: 'TYPE: Query'\n"
            "Rules:\n"
            "0. If user says generic affirmation like 'Spin the records', 'Play music', 'Yes', 'Lets do it' -> return 'DEFAULT: None'.\n"
            "1. If user asks for a specific song (e.g. 'Play Here in My Heart'), use 'TRACK: Song Artist year:XXXX'.\n"
            "2. If user refers to a song in context (e.g. 'Play that', 'Play the trailer'), resolve it to the full title mentioned in Context.\n"
            "3. If user explicitly asks for an ALBUM (e.g. 'Play album Abbey Road'), use 'ALBUM: Album Name Artist'.\n"
            "4. If user asks for music BY or FROM a specific artist (e.g. 'Play Bing Crosby', 'Songs from Elvis'), use 'ARTIST: Artist Name'.\n"
            "5. If user names a famous entity without identifying type (e.g. 'Play Beatles' vs 'Play Bohemian Rhapsody'), USE YOUR WORLD KNOWLEDGE to infer if it is an ARTIST or TRACK.\n"
            "   - 'Play Beatles' -> 'ARTIST: The Beatles'\n"
            "   - 'Play Bohemian Rhapsody' -> 'TRACK: Bohemian Rhapsody Queen'\n"
            "6. If user asks for a genre, mood, or artist collection (e.g. 'Play Rock', 'Jazz music'), use 'PLAYLIST: Query'. Do NOT use 'year:XXXX' for playlists.\n"
            "7. Limit query to 3-4 keywords.\n"
            "8. IMPORTANT: Correct any spelling errors or typos in proper names to their canonical local form (e.g. 'Vladimir Myšík' -> 'Vladimír Mišík', 'Vteřině' -> 'Vteřiny').\n"
            "Example: 'TRACK: Here in My Heart Al Martino'"
        )
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-5.2-2025-12-11",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_text}
                ],
                max_completion_tokens=50,
                temperature=0.3
            )
            raw_result = response.choices[0].message.content.strip().replace('"', '')
            print(f"🧠 Raw Music Algo: {raw_result}")
            
            # Parse
            if ":" in raw_result:
                parts = raw_result.split(":", 1)
                s_type = parts[0].strip().upper()
                s_query = parts[1].strip()
                if "DEFAULT" in s_type:
                    return None, "DEFAULT"
                return s_query, s_type
            else:
                return raw_result, "PLAYLIST" # Default fallback for unformatted

        except Exception as e:
            print(f"Error generating music query: {e}")
            return f"top hits {year}", "PLAYLIST"

    def get_dj_confirmation(self, year, query, language="EN"):
        """
        Generate a short snippet where the DJ confirms and ANNOUNCES what they are about to play.
        """
        style = self.get_persona_style(year, language)
        prompt = (
            f"You are a Radio DJ from {year}. Style: {style}\n"
            f"User request (Search Term): '{query}'.\n"
            f"Confirm you found it and are playing it now. Mention the artist/song name clearly.\n"
            f"Example: 'The Beatles? Excellent choice. Coming right up!' or 'Streaming that track now.'"
        )
        try:
            response = self.client.chat.completions.create(
                model="gpt-5.2-2025-12-11",
                messages=[{"role": "system", "content": prompt}],
                max_completion_tokens=50,
                temperature=0.7
            )
            content = response.choices[0].message.content
            if not content or not content.strip():
                raise ValueError("Empty response from DJ")
            return content
        except Exception as e:
            fallback = "Coming right up!" if language == "EN" else "Už to hraju!"
            return fallback

    def classify_intent(self, user_text):
        """
        Determine if the user wants to CHAT, PLAY_MUSIC (explicit), or NAVIGATE.
        """
        prompt = (
            f"Classify the following user input into exactly one category:\n"
            f"1. 'MUSIC': User explicitly wants to start playing music NOW (e.g. 'Play X', 'Start music', 'I want to hear X').\n"
            f"2. 'CHAT': User is asking a question, chatting, or asking ABOUT music (e.g. 'What is popular?', 'Who is the singer?', 'Tell me about X').\n"
            f"user_input: '{user_text}'\n"
            f"Return ONLY the category name."
        )
        try:
            response = self.client.chat.completions.create(
                model="gpt-5.2-2025-12-11",
                messages=[{"role": "system", "content": prompt}],
                max_completion_tokens=10,
                temperature=0.0,
                timeout=3.0 # Fast intent check
            )
            return response.choices[0].message.content.strip().upper()
        except:
             return "CHAT"
