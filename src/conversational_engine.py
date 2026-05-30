"""
ConversationalEngine: Real-time voice conversation using ElevenLabs Conversational AI SDK.

Uses the ElevenLabs Conversation class with a custom AudioInterface to route
mic input and speaker output through the USB audio device (phone handset),
while the agent handles turn detection, STT, LLM, and TTS internally.

Requires: elevenlabs>=2.27.0, pyaudio (+ portaudio19-dev on Pi)

Hardware mapping:
  Card 0 (plughw:0,0): bcm2835 Headphones -> home audio speakers
  Card 1 (plughw:1,0): USB Audio Device   -> phone handset (mic + speaker)
"""

import os
import json
import struct
import time
import threading
import logging

try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False

try:
    from elevenlabs.client import ElevenLabs
    from elevenlabs.conversational_ai.conversation import Conversation, ClientTools, AudioInterface
    ELEVENLABS_CONV_AVAILABLE = True
except ImportError:
    ELEVENLABS_CONV_AVAILABLE = False

from .config import ELEVENLABS_API_KEY, AUDIO_DEVICE_ID, FEATURE_FLAGS

logger = logging.getLogger(__name__)

# Agent ID cache file
AGENT_ID_CACHE = os.path.expanduser("~/.retro_agent_id")


# ---------------------------------------------------------------------------
# EchoGateAudioInterface — prevents feedback loop in handset
# ---------------------------------------------------------------------------

class EchoGateAudioInterface:
    """
    Wraps DefaultAudioInterface with echo suppression.

    The old phone handset has the mic and speaker very close together.
    When the agent speaks, the mic picks up the audio and feeds it back,
    creating an infinite echo loop ("Ahoy!" → mic hears "Ahoy!" → repeats).

    Fix: suppress mic input for a short window after each audio output chunk.
    This is a simple "echo gate" — mic is muted while speaker is active.
    """

    def __init__(self):
        from elevenlabs.conversational_ai.default_audio_interface import DefaultAudioInterface
        self._inner = DefaultAudioInterface()
        self._is_outputting = False
        self._output_end_time = 0
        self._gate_delay = 1.5  # Keep mic muted for 1.5s after last output chunk
        # The output queue adds latency — audio plays ~1-2s after output() is called,
        # so we need a long tail to cover the actual speaker playback time

    def start(self, input_callback):
        """Start with a wrapped input callback that gates echo."""
        self._real_callback = input_callback

        def gated_callback(audio_data):
            # Suppress mic input while agent is speaking (+ gate_delay after)
            now = time.time()
            if now < self._output_end_time:
                # Send silence instead of actual mic data to prevent echo
                silence = b'\x00' * len(audio_data)
                self._real_callback(silence)
            else:
                self._is_outputting = False
                self._real_callback(audio_data)

        self._inner.start(gated_callback)

    def stop(self):
        self._inner.stop()

    def output(self, audio):
        self._is_outputting = True
        self._inner.output(audio)
        # Estimate when this audio chunk finishes playing:
        # Each chunk is PCM 16-bit mono at 16kHz = 2 bytes per sample
        # So len(audio) bytes = len(audio)/2 samples = len(audio)/2/16000 seconds
        chunk_duration = len(audio) / 2 / 16000
        # Gate extends to: now + queue_buffer_time + chunk_play_time + safety margin
        self._output_end_time = time.time() + chunk_duration + self._gate_delay

    def interrupt(self):
        self._is_outputting = False
        self._output_end_time = 0  # Immediately unmute mic on interruption
        self._inner.interrupt()


# Spotify tool definitions — embedded in agent.prompt.tools at creation time.
# These tell the LLM what tools exist. ClientTools handles local execution.
AGENT_TOOLS_CONFIG = [
    {
        "type": "client",
        "name": "play_music",
        "description": "Search Spotify and play music. Use when the user asks for a specific song, artist, album, or genre. Always use this when the user names a song or artist.",
        "expects_response": True,
        "response_timeout_secs": 15,
        "parameters": {
            "type": "object",
            "description": "Spotify search parameters",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "What to search for (song name, artist name, album, genre, etc.)"
                },
                "search_type": {
                    "type": "string",
                    "description": "Type of search",
                    "enum": ["track", "artist", "album", "playlist"]
                }
            },
            "required": ["query", "search_type"]
        }
    },
    {
        "type": "client",
        "name": "play_era_playlist",
        "description": "Play the default radio playlist for the current era/decade. Use for generic music requests like 'play music', 'spin the records', 'play something', 'yes'.",
        "expects_response": True,
        "response_timeout_secs": 10,
        "parameters": {
            "type": "object",
            "description": "No parameters needed",
            "properties": {}
        }
    },
    {
        "type": "client",
        "name": "pause_music",
        "description": "Pause the currently playing music. Use when user says 'stop', 'pause', 'quiet'.",
        "expects_response": True,
        "response_timeout_secs": 5,
        "parameters": {
            "type": "object",
            "description": "No parameters needed",
            "properties": {}
        }
    },
    {
        "type": "client",
        "name": "queue_song",
        "description": "Add a song to the playback queue WITHOUT interrupting what's currently playing. Use when the user wants to queue a song for later, or asks to play multiple songs in a row (queue the second, third, etc. songs). Example: 'play X and then Y' — play X with play_music, then queue Y with queue_song.",
        "expects_response": True,
        "response_timeout_secs": 10,
        "parameters": {
            "type": "object",
            "description": "Song to add to queue",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Song name and artist to search for"
                }
            },
            "required": ["query"]
        }
    },
    {
        "type": "client",
        "name": "search_spotify",
        "description": "Search Spotify WITHOUT playing. Returns a list of results so you can discuss options with the listener before playing. Use when the user wants to browse, explore, or choose from options. Example: 'What albums does Bruce Springsteen have?' or 'Find me some jazz playlists'.",
        "expects_response": True,
        "response_timeout_secs": 10,
        "parameters": {
            "type": "object",
            "description": "Spotify search parameters",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "What to search for"
                },
                "search_type": {
                    "type": "string",
                    "description": "Type of search",
                    "enum": ["track", "artist", "album", "playlist"]
                }
            },
            "required": ["query", "search_type"]
        }
    },
    {
        "type": "client",
        "name": "now_playing",
        "description": "Get information about what's currently playing on Spotify. Use when user asks 'what's playing?', 'who is this?', 'what song is this?'.",
        "expects_response": True,
        "response_timeout_secs": 5,
        "parameters": {
            "type": "object",
            "description": "No parameters needed",
            "properties": {}
        }
    },
    {
        "type": "client",
        "name": "skip_track",
        "description": "Skip to the next track. Use when user says 'next', 'skip', 'next song'.",
        "expects_response": True,
        "response_timeout_secs": 5,
        "parameters": {
            "type": "object",
            "description": "No parameters needed",
            "properties": {}
        }
    },
    {
        "type": "client",
        "name": "get_weather",
        "description": "Get the current weather in the listener's city. Use when user asks about weather.",
        "expects_response": True,
        "response_timeout_secs": 5,
        "parameters": {
            "type": "object",
            "description": "No parameters needed",
            "properties": {}
        }
    },
    {
        "type": "client",
        "name": "get_news",
        "description": "Get today's top news headlines. Use when user asks about news, current events, or what's happening in the world.",
        "expects_response": True,
        "response_timeout_secs": 5,
        "parameters": {
            "type": "object",
            "description": "No parameters needed",
            "properties": {}
        }
    },
]


# ---------------------------------------------------------------------------
# HandsetAudioInterface
# ---------------------------------------------------------------------------

class HandsetAudioInterface(AudioInterface if ELEVENLABS_CONV_AVAILABLE else object):
    """
    Custom AudioInterface that routes audio through the USB audio device
    (phone handset) on the Raspberry Pi.

    Mirrors DefaultAudioInterface exactly but targets USB device (card 1).
    ElevenLabs ConvAI expects: paInt16, 16kHz, mono.
    The USB device runs at 44100Hz natively — PyAudio/ALSA handles resampling.
    """

    INPUT_FRAMES_PER_BUFFER = 4000   # 250ms @ 16kHz
    OUTPUT_FRAMES_PER_BUFFER = 1000  # 62.5ms @ 16kHz

    def __init__(self):
        if not PYAUDIO_AVAILABLE:
            raise RuntimeError("PyAudio is not installed")
        self._pyaudio_module = pyaudio

    def start(self, input_callback):
        """Start audio capture and playback on USB handset."""
        import queue as queue_mod
        self.input_callback = input_callback
        self.output_queue = queue_mod.Queue()
        self.should_stop = threading.Event()
        self.output_thread = threading.Thread(target=self._output_thread)

        self.p = self._pyaudio_module.PyAudio()

        # Find USB audio device
        usb_idx = self._find_usb_device()
        logger.info("HandsetAudio: using device index %s", usb_idx)

        # Input stream — use callback mode like DefaultAudioInterface
        self.in_stream = self.p.open(
            format=self._pyaudio_module.paInt16,
            channels=1,
            rate=16000,
            input=True,
            input_device_index=usb_idx,
            stream_callback=self._in_callback,
            frames_per_buffer=self.INPUT_FRAMES_PER_BUFFER,
            start=True,
        )

        # Output stream
        self.out_stream = self.p.open(
            format=self._pyaudio_module.paInt16,
            channels=1,
            rate=16000,
            output=True,
            output_device_index=usb_idx,
            frames_per_buffer=self.OUTPUT_FRAMES_PER_BUFFER,
            start=True,
        )

        self.output_thread.start()

    def stop(self):
        """Stop audio streams and release resources."""
        self._running = False

        if self._read_thread:
            self._read_thread.join(timeout=2.0)
            self._read_thread = None

    def stop(self):
        """Stop audio streams and clean up."""
        self.should_stop.set()
        self.output_thread.join()
        self.in_stream.stop_stream()
        self.in_stream.close()
        self.out_stream.close()
        self.p.terminate()

    def output(self, audio: bytes):
        """Buffer agent audio for playback."""
        self.output_queue.put(audio)

    def interrupt(self):
        """Clear output buffer (user is interrupting the agent)."""
        try:
            while True:
                _ = self.output_queue.get(block=False)
        except Exception:
            pass

    def _output_thread(self):
        """Background thread that writes buffered audio to the speaker."""
        while not self.should_stop.is_set():
            try:
                audio = self.output_queue.get(timeout=0.25)
                self.out_stream.write(audio)
            except Exception:
                pass

    def _in_callback(self, in_data, frame_count, time_info, status):
        """PyAudio callback — forward mic data to ElevenLabs SDK."""
        if self.input_callback:
            self.input_callback(in_data)
        return (None, self._pyaudio_module.paContinue)

    def _find_usb_device(self):
        """Find the USB audio device index for PyAudio."""
        for i in range(self.p.get_device_count()):
            info = self.p.get_device_info_by_index(i)
            if "usb" in info["name"].lower() and info["maxInputChannels"] > 0:
                return i
        logger.warning("HandsetAudio: USB device not found, using default")
        return None


# ---------------------------------------------------------------------------
# ConversationalEngine
# ---------------------------------------------------------------------------

class ConversationalEngine:
    """
    Real-time voice conversation engine using ElevenLabs Conversational AI SDK.

    Creates an ElevenLabs agent on first use, then starts non-blocking
    conversation sessions with per-decade voice and prompt overrides.
    Tool calls for Spotify control are handled via ClientTools.
    """

    def __init__(self, elevenlabs_api_key=None, music_engine=None, world_context=None):
        api_key = elevenlabs_api_key or ELEVENLABS_API_KEY

        self.client = ElevenLabs(api_key=api_key) if ELEVENLABS_CONV_AVAILABLE else None
        self.music_engine = music_engine
        self.world_context = world_context

        self.agent_id = None
        self.conversation = None
        self._audio_interface = None

        # Session context (set by start_session)
        self._session_year = None
        self._session_language = None

    @staticmethod
    def is_available():
        """Check if all required dependencies are installed."""
        return PYAUDIO_AVAILABLE and ELEVENLABS_CONV_AVAILABLE

    # ------------------------------------------------------------------
    # Agent management
    # ------------------------------------------------------------------

    def ensure_agent(self):
        """
        Create the base agent via API if not already created.
        Caches the agent_id to ~/.retro_agent_id for reuse across restarts.

        Returns:
            str: The agent_id, or None on failure.
        """
        # Already loaded
        if self.agent_id:
            return self.agent_id

        # Try loading from cache
        if os.path.exists(AGENT_ID_CACHE):
            try:
                with open(AGENT_ID_CACHE, "r") as f:
                    cached_id = f.read().strip()
                if cached_id:
                    self.agent_id = cached_id
                    logger.info("Loaded cached agent_id: %s", cached_id)
                    return self.agent_id
            except Exception as e:
                logger.warning("Could not read agent cache: %s", e)

        # Create new agent
        if not self.client:
            logger.error("ElevenLabs client not available")
            return None

        try:
            from elevenlabs import ConversationalConfig
            from elevenlabs.types import (
                AgentPlatformSettingsRequestModel,
                ConversationInitiationClientDataConfigInput,
                ConversationConfigClientOverrideConfigInput,
                AgentConfigOverrideConfig,
                PromptAgentApiModelOverrideConfig,
                TtsConversationalConfigOverrideConfig,
            )

            # Create agent with:
            # 1. Spotify + world tools (so LLM knows it can call them)
            # 2. Override permissions for prompt, first_message, language, AND voice_id
            agent = self.client.conversational_ai.agents.create(
                name="RetroRadio DJ v3",
                conversation_config=ConversationalConfig(
                    tts={
                        "voice_id": "JBFqnCBsd6RMkjVDRZzb",
                        # Keep flash_v2 (NOT _v2_5): EL rejects v2.5 TTS for English-base
                        # agents ("English Agents must use turbo or flash v2"). flash_v2 is
                        # the lowest-latency model allowed and already handles CZ overrides.
                        "model_id": "eleven_flash_v2",
                    },
                    agent={
                        "prompt": {
                            "prompt": "You are a radio DJ. Help the listener find music to play.",
                            "llm": "gpt-5.5",  # was gpt-4o; live agent updated to match (May 2026)
                            "tools": AGENT_TOOLS_CONFIG,
                        },
                        "first_message": "Welcome to RetroRadio!",
                        "language": "en",
                    },
                    # Enable Czech as an additional language (dial-9 CZ mode). EL then
                    # uses the multilingual v2.5 TTS for 'cs' while English stays on v2,
                    # giving proper Czech pronunciation. Empty overrides => inherit base;
                    # start_session() already supplies the CZ first_message + decade voice.
                    language_presets={"cs": {"overrides": {}}},
                ),
                platform_settings=AgentPlatformSettingsRequestModel(
                    overrides=ConversationInitiationClientDataConfigInput(
                        conversation_config_override=ConversationConfigClientOverrideConfigInput(
                            agent=AgentConfigOverrideConfig(
                                prompt=PromptAgentApiModelOverrideConfig(prompt=True),
                                first_message=True,
                                language=True,
                            ),
                            tts=TtsConversationalConfigOverrideConfig(
                                voice_id=True,
                            ),
                        ),
                    ),
                ),
            )

            self.agent_id = agent.agent_id
            logger.info("Created new agent: %s", self.agent_id)

            # Cache to disk
            try:
                with open(AGENT_ID_CACHE, "w") as f:
                    f.write(self.agent_id)
            except Exception as e:
                logger.warning("Could not cache agent_id: %s", e)

            return self.agent_id

        except Exception as e:
            logger.error("Agent creation failed: %s", e)
            return None

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def start_session(self, year, language, voice_id, system_instructions):
        """
        Start a non-blocking conversation session with per-decade overrides.

        Args:
            year: The target decade year (e.g. 1970).
            language: "EN" or "CZ".
            voice_id: ElevenLabs voice ID for this decade.
            system_instructions: Full system prompt for the DJ persona.

        Returns:
            True if session started, False on failure (caller should fall
            back to legacy pipeline).
        """
        if not self.is_available():
            logger.warning("ConversationalEngine: dependencies not available")
            return False

        # Ensure agent exists
        agent_id = self.ensure_agent()
        if not agent_id:
            logger.error("No agent_id available, cannot start session")
            return False

        # End any existing session
        self.end_session()

        self._session_year = year
        self._session_language = language

        try:
            from elevenlabs.conversational_ai.default_audio_interface import DefaultAudioInterface
            self._audio_interface = DefaultAudioInterface()

            # Register ALL client-side tool handlers (must match AGENT_TOOLS_CONFIG names)
            client_tools = ClientTools()
            for tool_def in AGENT_TOOLS_CONFIG:
                tool_name = tool_def["name"]
                client_tools.register(
                    tool_name,
                    lambda params, tn=tool_name: self._handle_tool_call(tn, params),
                )

            # Build the greeting
            decade = int(str(year)[:3] + "0") if year else None
            lang_code = "cs" if language == "CZ" else "en"
            if not year:
                # Operator — modern greeting
                if language == "CZ":
                    first_message = "Tady centrala. Jak vam mohu pomoci?"
                else:
                    first_message = "Operator here. How can I help you today?"
            elif language == "CZ":
                first_message = f"Vitejte v nasem radiu z roku {year}! Co pro vas mohu udelat?"
            else:
                first_message = f"You're tuned in to {year}! What can I spin for you?"

            # Per-session overrides: prompt + first_message + language + voice
            from elevenlabs.conversational_ai.conversation import ConversationInitiationData

            config = ConversationInitiationData(
                conversation_config_override={
                    "agent": {
                        "prompt": {
                            "prompt": system_instructions,
                        },
                        "first_message": first_message,
                        "language": lang_code,
                    },
                    "tts": {
                        "voice_id": voice_id,
                    },
                }
            )

            self.conversation = Conversation(
                client=self.client,
                agent_id=agent_id,
                requires_auth=False,
                audio_interface=self._audio_interface,
                config=config,
                client_tools=client_tools,
                callback_agent_response=self._on_agent_response,
                callback_user_transcript=self._on_user_transcript,
            )

            # Start the session (NON-BLOCKING -- runs in background)
            self.conversation.start_session()

            print(f"🎙️ ConvAI: Session started (year={year}, voice={voice_id[:12]}...)")
            return True

        except Exception as e:
            logger.error("Failed to start conversational session: %s", e)
            self._cleanup()
            return False

    def end_session(self):
        """End the current session cleanly."""
        print("🎙️ ConvAI: Ending session...")
        conv = self.conversation
        self.conversation = None  # Mark inactive FIRST to stop hangup loop
        if conv:
            try:
                conv.end_session()
                print("🎙️ ConvAI: Session ended")
            except Exception as e:
                print(f"🎙️ ConvAI: End session error (ignored): {e}")
        self._cleanup()

    def wait_for_session_end(self):
        """
        Block until the current session ends (agent disconnects or error).
        Useful for callers that need synchronous behavior.
        """
        if self.conversation:
            try:
                self.conversation.wait_for_session_end()
            except Exception as e:
                logger.warning("Error waiting for session end: %s", e)

    def is_active(self):
        """Check if a conversation session is currently running."""
        return self.conversation is not None

    # ------------------------------------------------------------------
    # Tool call handling
    # ------------------------------------------------------------------

    def _handle_tool_call(self, tool_name, parameters):
        """
        Handle Spotify tool calls from the agent.

        Args:
            tool_name: Name of the tool being called.
            parameters: Dict of parameters from the agent.

        Returns:
            str: Result message to send back to the agent.
        """
        print(f"🎙️ TOOL: {tool_name}({parameters})")

        if not self.music_engine:
            print("🎙️ TOOL: Music engine not available!")
            return "Music engine not available"

        try:
            if tool_name == "play_music":
                query = parameters.get("query", "")
                search_type = parameters.get("search_type", parameters.get("type", "track"))
                year = self._session_year

                print(f"🎙️ Spotify: Searching '{query}' as {search_type}")
                success = self.music_engine.search_and_play(query, type=search_type, year=year)

                if success:
                    # Get track info to feed back to the DJ
                    time.sleep(1)
                    track = self.music_engine.current_track
                    if track:
                        return f"Now playing: {track.get('name', query)} by {track.get('artist', 'unknown')}. Music is coming through the speakers."
                    return f"Now playing: {query}. Music is coming through the speakers."
                else:
                    return f"Could not find '{query}' on Spotify. Try a different search."

            elif tool_name == "play_era_playlist":
                from .config import DECADE_PLAYLISTS

                decade = int(str(self._session_year)[:3] + "0") if self._session_year else 1950
                playlists = DECADE_PLAYLISTS.get(decade)
                if playlists:
                    lang = self._session_language or "EN"
                    uri = playlists.get(lang, playlists["EN"])
                    if uri.startswith("search:"):
                        self.music_engine.search_and_play(uri.replace("search:", "").strip(), type="playlist")
                    else:
                        self.music_engine.play_playlist(uri)
                    return f"Playing the {decade}s radio playlist. Music is coming through the speakers."
                return "Could not find a playlist for this era."

            elif tool_name == "queue_song":
                query = parameters.get("query", "")
                print(f"🎙️ Spotify QUEUE: '{query}'")
                try:
                    results = self.music_engine.sp.search(q=query, limit=1, type="track")
                    tracks = results.get("tracks", {}).get("items", [])
                    if tracks:
                        track = tracks[0]
                        track_uri = track["uri"]
                        track_name = track["name"]
                        artist_name = track["artists"][0]["name"]
                        self.music_engine.sp.add_to_queue(uri=track_uri, device_id=self.music_engine.device_id)
                        return f"Queued: {track_name} by {artist_name}. It will play after the current song."
                    return f"Could not find '{query}' to queue."
                except Exception as e:
                    return f"Queue error: {e}"

            elif tool_name == "search_spotify":
                query = parameters.get("query", "")
                search_type = parameters.get("search_type", "track")
                print(f"🎙️ Spotify SEARCH: '{query}' as {search_type}")
                try:
                    results = self.music_engine.sp.search(q=query, limit=5, type=search_type)
                    key_map = {"track": "tracks", "artist": "artists", "album": "albums", "playlist": "playlists"}
                    items = results.get(key_map.get(search_type, "tracks"), {}).get("items", [])
                    if not items:
                        return f"No {search_type}s found for '{query}'."

                    result_lines = []
                    for i, item in enumerate(items[:5], 1):
                        name = item.get("name", "?")
                        if search_type == "track":
                            artist = item["artists"][0]["name"] if item.get("artists") else "?"
                            result_lines.append(f"{i}. {name} by {artist}")
                        elif search_type == "album":
                            artist = item["artists"][0]["name"] if item.get("artists") else "?"
                            year = item.get("release_date", "?")[:4]
                            result_lines.append(f"{i}. {name} by {artist} ({year})")
                        elif search_type == "artist":
                            genres = ", ".join(item.get("genres", [])[:2]) or "various"
                            result_lines.append(f"{i}. {name} ({genres})")
                        else:
                            owner = item.get("owner", {}).get("display_name", "?")
                            result_lines.append(f"{i}. {name} by {owner}")

                    return f"Found {len(items)} {search_type}s: " + "; ".join(result_lines) + ". Which one would you like to hear?"
                except Exception as e:
                    return f"Search error: {e}"

            elif tool_name == "pause_music":
                self.music_engine.pause()
                return "Music paused."

            elif tool_name == "now_playing":
                try:
                    playback = self.music_engine.sp.current_playback()
                    if playback and playback.get("item"):
                        item = playback["item"]
                        name = item["name"]
                        artist = item["artists"][0]["name"]
                        album = item["album"]["name"]
                        progress = playback["progress_ms"] // 1000
                        duration = item["duration_ms"] // 1000
                        return f"Currently playing: '{name}' by {artist} from the album '{album}'. {progress}s into {duration}s total."
                    return "Nothing is currently playing."
                except Exception as e:
                    return f"Could not get playback info: {e}"

            elif tool_name == "skip_track":
                try:
                    self.music_engine.sp.next_track(device_id=self.music_engine.device_id)
                    time.sleep(1)
                    track = self.music_engine.current_track
                    if track:
                        return f"Skipped! Now playing: {track.get('name', '?')} by {track.get('artist', '?')}."
                    return "Skipped to the next track."
                except Exception as e:
                    return f"Could not skip: {e}"

            elif tool_name == "get_weather":
                if self.world_context:
                    weather = self.world_context.get_weather()
                    location = self.world_context.location
                    return f"Current weather in {location}: {weather}" if weather else "Weather data not available."
                return "Weather service not configured."

            elif tool_name == "get_news":
                if self.world_context:
                    headlines = self.world_context.get_news(5)
                    if headlines:
                        news_text = "; ".join(headlines[:5])
                        return f"Today's top headlines: {news_text}"
                    return "No news available right now."
                return "News service not configured."

            else:
                return f"Unknown tool: {tool_name}"

        except Exception as e:
            print(f"🎙️ Tool error: {e}")
            return f"Sorry, there was a problem: {e}"

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def _on_agent_response(self, text):
        """Called when the agent finishes speaking."""
        print(f"🎙️ AGENT: {text}")

    def _on_user_transcript(self, text):
        """Called when user speech is transcribed."""
        print(f"🎙️ USER: {text}")

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def _cleanup(self):
        """Release all resources."""
        self.conversation = None

        if self._audio_interface:
            try:
                self._audio_interface.stop()
            except Exception:
                pass
            self._audio_interface = None
