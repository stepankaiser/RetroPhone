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

# Spotify tool definitions for the Conversational AI agent
AGENT_TOOL_DEFINITIONS = [
    {
        "name": "play_music",
        "description": (
            "Search and play music on Spotify. Use when the user asks for a "
            "specific song, artist, album, or playlist."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (artist name, song title, etc.)",
                },
                "type": {
                    "type": "string",
                    "enum": ["track", "artist", "album", "playlist"],
                    "description": "Type of music to search for",
                },
            },
            "required": ["query", "type"],
        },
    },
    {
        "name": "play_era_playlist",
        "description": (
            "Play the default playlist for the current radio era/decade. "
            "Use when user says 'play music', 'spin the records', 'yes', etc."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "pause_music",
        "description": "Pause current music playback.",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
]


# ---------------------------------------------------------------------------
# HandsetAudioInterface
# ---------------------------------------------------------------------------

class HandsetAudioInterface(AudioInterface if ELEVENLABS_CONV_AVAILABLE else object):
    """
    Custom AudioInterface that routes audio through the USB audio device
    (phone handset) on the Raspberry Pi.

    - Mic input:  read from USB device (card 1) at 16kHz mono float32
    - Speaker output: write to USB device (card 1) at 16kHz mono float32
    """

    SAMPLE_RATE = 16000
    CHANNELS = 1
    FORMAT = pyaudio.paFloat32 if PYAUDIO_AVAILABLE else None
    CHUNK_SIZE = 800  # 50ms at 16kHz

    def __init__(self):
        self._pa = None
        self._input_stream = None
        self._output_stream = None
        self._input_callback = None
        self._running = False
        self._read_thread = None

    def start(self, input_callback):
        """
        Start audio capture and playback.

        Args:
            input_callback: Callable that receives mic audio data (bytes).
                            Called repeatedly with float32 PCM chunks.
        """
        if not PYAUDIO_AVAILABLE:
            raise RuntimeError("PyAudio is not installed")

        self._input_callback = input_callback
        self._pa = pyaudio.PyAudio()
        self._running = True

        input_idx = self._find_usb_device(is_input=True)
        output_idx = self._find_usb_device(is_input=False)

        logger.info(
            "HandsetAudio: input_device=%s, output_device=%s",
            input_idx, output_idx,
        )

        # Input stream (mic)
        self._input_stream = self._pa.open(
            format=self.FORMAT,
            channels=self.CHANNELS,
            rate=self.SAMPLE_RATE,
            input=True,
            input_device_index=input_idx,
            frames_per_buffer=self.CHUNK_SIZE,
        )

        # Output stream (handset speaker)
        self._output_stream = self._pa.open(
            format=self.FORMAT,
            channels=self.CHANNELS,
            rate=self.SAMPLE_RATE,
            output=True,
            output_device_index=output_idx,
            frames_per_buffer=self.CHUNK_SIZE,
        )

        # Read mic in a background thread and feed to callback
        self._read_thread = threading.Thread(
            target=self._mic_read_loop, daemon=True
        )
        self._read_thread.start()

    def stop(self):
        """Stop audio streams and release resources."""
        self._running = False

        if self._read_thread:
            self._read_thread.join(timeout=2.0)
            self._read_thread = None

        for stream in (self._input_stream, self._output_stream):
            if stream:
                try:
                    stream.stop_stream()
                    stream.close()
                except Exception:
                    pass
        self._input_stream = None
        self._output_stream = None

        if self._pa:
            try:
                self._pa.terminate()
            except Exception:
                pass
            self._pa = None

    def output(self, audio_data):
        """
        Write agent audio response to the handset speaker.

        Args:
            audio_data: bytes of float32 PCM audio at 16kHz mono.
        """
        if self._output_stream and self._running:
            try:
                self._output_stream.write(audio_data)
            except Exception as e:
                logger.warning("HandsetAudio output error: %s", e)

    def interrupt(self):
        """
        Called when the user interrupts the agent (barge-in).
        Flush any buffered output audio.
        """
        if self._output_stream and self._running:
            try:
                # Stop and restart the output stream to clear its buffer
                self._output_stream.stop_stream()
                self._output_stream.start_stream()
            except Exception as e:
                logger.warning("HandsetAudio interrupt error: %s", e)

    def _mic_read_loop(self):
        """Continuously read mic data and pass to input_callback."""
        while self._running and self._input_stream:
            try:
                data = self._input_stream.read(
                    self.CHUNK_SIZE, exception_on_overflow=False
                )
                if self._input_callback and data:
                    self._input_callback(data)
            except Exception as e:
                if self._running:
                    logger.warning("HandsetAudio mic read error: %s", e)
                break

    def _find_usb_device(self, is_input=True):
        """Find the USB audio device index for PyAudio."""
        if not self._pa:
            return None

        for i in range(self._pa.get_device_count()):
            info = self._pa.get_device_info_by_index(i)
            name_lower = info["name"].lower()
            if is_input and info["maxInputChannels"] > 0:
                if "usb" in name_lower:
                    return i
            elif not is_input and info["maxOutputChannels"] > 0:
                if "usb" in name_lower:
                    return i

        # Fallback to default
        logger.warning(
            "HandsetAudio: USB %s device not found, using default",
            "input" if is_input else "output",
        )
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

    def __init__(self, elevenlabs_api_key=None, music_engine=None):
        api_key = elevenlabs_api_key or ELEVENLABS_API_KEY

        self.client = ElevenLabs(api_key=api_key) if ELEVENLABS_CONV_AVAILABLE else None
        self.music_engine = music_engine

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
            # Build tool configs for the agent
            tools = []
            for tool_def in AGENT_TOOL_DEFINITIONS:
                tools.append({
                    "type": "client",
                    "name": tool_def["name"],
                    "description": tool_def["description"],
                    "parameters": tool_def["parameters"],
                })

            agent = self.client.conversational_ai.agents.create(
                name="RetroRadio DJ",
                conversation_config={
                    "tts": {
                        "voice_id": "JBFqnCBsd6RMkjVDRZzb",  # Default (George)
                        "model_id": "eleven_flash_v2_5",
                    },
                    "agent": {
                        "prompt": {
                            "prompt": "You are a retro radio DJ. Greet the listener warmly.",
                            "llm": "gpt-4o",
                        },
                        "first_message": "Welcome to RetroRadio!",
                        "language": "en",
                    },
                },
                tools=tools,
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
            # Create audio interface
            self._audio_interface = HandsetAudioInterface()

            # Register client-side tools
            client_tools = ClientTools()
            client_tools.register(
                "play_music",
                lambda parameters: self._handle_tool_call("play_music", parameters),
            )
            client_tools.register(
                "play_era_playlist",
                lambda parameters: self._handle_tool_call("play_era_playlist", parameters),
            )
            client_tools.register(
                "pause_music",
                lambda parameters: self._handle_tool_call("pause_music", parameters),
            )

            # Build the DJ greeting
            decade = int(str(year)[:3] + "0")
            lang_code = "cs" if language == "CZ" else "en"
            if language == "CZ":
                first_message = f"Vitejte v nasem radiu z roku {year}! Co pro vas mohu udelat?"
            else:
                first_message = f"You're tuned in to {year}! What can I spin for you?"

            # Build per-session overrides
            overrides = {
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

            # Create the Conversation instance
            self.conversation = Conversation(
                client=self.client,
                agent_id=agent_id,
                audio_interface=self._audio_interface,
                client_tools=client_tools,
                callback_agent_response=self._on_agent_response,
                callback_user_transcript=self._on_user_transcript,
            )

            # Start the session (NON-BLOCKING -- runs in background)
            self.conversation.start_session(overrides=overrides)

            logger.info(
                "Conversational session started: year=%s, voice=%s",
                year, voice_id,
            )
            return True

        except Exception as e:
            logger.error("Failed to start conversational session: %s", e)
            self._cleanup()
            return False

    def end_session(self):
        """End the current session cleanly."""
        if self.conversation:
            try:
                self.conversation.end_session()
            except Exception as e:
                logger.warning("Error ending conversation session: %s", e)
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
        logger.info("Tool call: %s(%s)", tool_name, parameters)

        if not self.music_engine:
            return "Music engine not available"

        try:
            if tool_name == "play_music":
                query = parameters.get("query", "")
                search_type = parameters.get("type", "playlist")
                success = self.music_engine.search_and_play(
                    query, type=search_type
                )
                if success:
                    return f"Now playing: {query}"
                else:
                    return f"Could not find music matching: {query}"

            elif tool_name == "play_era_playlist":
                from .config import DECADE_PLAYLISTS

                decade = int(str(self._session_year)[:3] + "0")
                playlists = DECADE_PLAYLISTS.get(decade)
                if playlists:
                    lang = self._session_language or "EN"
                    uri = playlists.get(lang, playlists["EN"])
                    if uri.startswith("search:"):
                        search_query = uri.replace("search:", "").strip()
                        self.music_engine.search_and_play(
                            search_query, type="playlist"
                        )
                    else:
                        self.music_engine.play_playlist(uri)
                    return "Playing era playlist"
                else:
                    return f"No playlist configured for decade {decade}"

            elif tool_name == "pause_music":
                self.music_engine.pause()
                return "Music paused"

            else:
                return f"Unknown tool: {tool_name}"

        except Exception as e:
            logger.error("Tool call error (%s): %s", tool_name, e)
            return f"Error: {e}"

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def _on_agent_response(self, text):
        """Called when the agent finishes speaking."""
        logger.info("DJ said: %s", text)

    def _on_user_transcript(self, text):
        """Called when user speech is transcribed."""
        logger.info("User said: %s", text)

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
