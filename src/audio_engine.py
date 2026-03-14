import os
import time
import subprocess
from openai import OpenAI
from elevenlabs.client import ElevenLabs
from elevenlabs import save, VoiceSettings
from .config import OPENAI_API_KEY, ELEVENLABS_API_KEY, AUDIO_DEVICE_ID, DEFAULT_VOLUME, DECADE_EFFECTS, FEATURE_FLAGS

# Audio output targets
DEVICE_HANDSET = "handset"   # plughw:1,0 — USB audio (phone handset speaker)
DEVICE_HOME = "home"         # plughw:0,0 — Headphone jack (home audio / room speakers)


class AudioEngine:
    def __init__(self):
        self.openai_client = OpenAI(api_key=OPENAI_API_KEY)
        self.eleven_client = ElevenLabs(api_key=ELEVENLABS_API_KEY)

        self.current_process = None

        self.sounds_dir = os.path.join(os.path.dirname(__file__), "../sounds")
        if not os.path.exists(self.sounds_dir):
            os.makedirs(self.sounds_dir)

        self.temp_audio_path = "/tmp/retro_temp_audio.wav"
        self.temp_speech_path = "/tmp/retro_tts.mp3"
        self.temp_processed_path = "/tmp/retro_tts_processed.mp3"

    def _get_alsa_device(self, target=DEVICE_HANDSET):
        """Get the ALSA device string for the given output target."""
        if target == DEVICE_HOME:
            return "plughw:0,0"
        return f"plughw:{AUDIO_DEVICE_ID},0"

    def stop_audio(self):
        """Stop any currently playing audio."""
        if self.current_process:
            try:
                self.current_process.terminate()
                try:
                    self.current_process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.current_process.kill()
                self.current_process = None
            except Exception as e:
                print(f"Error stopping audio: {e}")

    def play_sound(self, sound_name, block=False, year=None, device=DEVICE_HANDSET):
        """Play a sound effect, optionally with decade-specific vintage processing."""
        # Try .mp3 first (AI-generated jingles), then .wav (synthesized)
        path = os.path.join(self.sounds_dir, f"{sound_name}.mp3")
        if not os.path.exists(path):
            path = os.path.join(self.sounds_dir, f"{sound_name}.wav")
        if not os.path.exists(path):
            print(f"Warning: Sound {sound_name} not found")
            return

        decade = int(str(year)[:3] + "0") if year else None
        if decade and DECADE_EFFECTS.get(decade):
            ext = os.path.splitext(path)[1]
            cached_path = f"/tmp/retro_{sound_name}_{decade}{ext}"
            if not os.path.exists(cached_path):
                cached_path = self._apply_vintage_effects(path, cached_path, year)
            path = cached_path

        self._play_file(path, block=block, device=device)

    def speak(self, text, voice_id="JBFqnCBsd6RMkjVDRZzb", voice_settings=None,
              model_id="eleven_turbo_v2_5", year=None, device=DEVICE_HANDSET):
        """
        Speak text using ElevenLabs TTS.
        Streams directly to player for lowest latency.
        SoX vintage effects are applied in-line via pipe (no temp file needed).
        """
        print(f"🗣️ Speaking ({device}): {text}")
        self.stop_audio()

        try:
            v_settings = None
            if voice_settings:
                v_settings = VoiceSettings(
                    stability=voice_settings.get('stability', 0.5),
                    similarity_boost=voice_settings.get('similarity_boost', 0.75),
                    style=voice_settings.get('style', 0.0),
                    use_speaker_boost=True
                )

            decade = int(str(year)[:3] + "0") if year else None
            effects = DECADE_EFFECTS.get(decade, "") if decade else ""

            tts_kwargs = {
                "text": text,
                "voice_id": voice_id,
                "model_id": model_id,
                "voice_settings": v_settings,
                "optimize_streaming_latency": 3,
            }
            audio_generator = self.eleven_client.text_to_speech.convert(**tts_kwargs)

            if effects:
                # Stream through SoX effects pipeline directly to speaker
                self._stream_with_effects(audio_generator, effects, device)
            else:
                # Stream directly to player (fastest path)
                self._stream_to_player(audio_generator, device)

        except Exception as e:
            print(f"❌ TTS Error: {e}")
            subprocess.run(["espeak", text], stderr=subprocess.DEVNULL)

    def _stream_to_player(self, audio_iter, device=DEVICE_HANDSET):
        """Stream ElevenLabs MP3 chunks directly to mpg123 via stdin."""
        self.stop_audio()
        alsa_dev = self._get_alsa_device(device)
        try:
            self.current_process = subprocess.Popen(
                ["mpg123", "-q", "-a", alsa_dev, "-"],
                stdin=subprocess.PIPE
            )
            for chunk in audio_iter:
                if isinstance(chunk, bytes) and self.current_process.stdin:
                    self.current_process.stdin.write(chunk)
            if self.current_process.stdin:
                self.current_process.stdin.close()
            self.current_process.wait()
            self.current_process = None
        except Exception as e:
            print(f"❌ Stream Error: {e}")

    def _stream_with_effects(self, audio_iter, effects, device=DEVICE_HANDSET):
        """
        Stream ElevenLabs MP3 → SoX (vintage effects) → ALSA speaker.
        All in one pipeline, no temp files. Real-time streaming with effects.
        """
        self.stop_audio()
        alsa_dev = self._get_alsa_device(device)
        sox_env = {**os.environ, "AUDIODRIVER": "alsa"}

        try:
            # Pipeline: stdin (MP3) → sox (decode + effects) → ALSA output
            # sox reads MP3 from stdin (-t mp3 -), applies effects, outputs to ALSA device
            sox_cmd = [
                "sox", "-t", "mp3", "-",       # Read MP3 from stdin
                "-t", "alsa", alsa_dev,         # Output to ALSA device
            ] + effects.split()

            self.current_process = subprocess.Popen(
                sox_cmd, stdin=subprocess.PIPE, env=sox_env,
                stderr=subprocess.DEVNULL
            )

            for chunk in audio_iter:
                if isinstance(chunk, bytes) and self.current_process.stdin:
                    self.current_process.stdin.write(chunk)
            if self.current_process.stdin:
                self.current_process.stdin.close()
            self.current_process.wait()
            self.current_process = None

        except Exception as e:
            print(f"❌ Stream+FX Error: {e}. Falling back to direct stream.")
            # Fallback: stream without effects
            self._stream_to_player(audio_iter, device)

    def _apply_vintage_effects(self, input_path, output_path, year):
        """Apply SoX effects to a file (used for sound effects caching)."""
        decade = int(str(year)[:3] + "0") if year else year
        effects = DECADE_EFFECTS.get(decade)
        if not effects:
            return input_path

        print(f"   🎛️ Applying FX ({year}): {effects}")
        sox_env = {**os.environ, "AUDIODRIVER": "alsa"}
        cmd = ["sox", input_path, output_path] + effects.split()

        try:
            result = subprocess.run(cmd, env=sox_env, capture_output=True, text=True)
            if result.returncode == 0:
                return output_path
            else:
                print(f"   ❌ SoX failed: {result.stderr.strip()}")
                return input_path
        except Exception as e:
            print(f"   ❌ SoX Error: {e}")
            return input_path

    def listen(self, duration=15):
        """
        Smart Listening (VAD):
        - recording starts when you speak (noise > 1%)
        - recording stops when you stop (silence > 2.0s)
        - failsafe timeout
        """
        self.stop_audio()
        time.sleep(0.5)

        print("👂 Listening (Smart VAD)...")

        sox_env = {**os.environ, "AUDIODRIVER": "alsa"}
        cmd = [
            "timeout", str(duration),
            "sox", "-q", "-t", "alsa", f"plughw:{AUDIO_DEVICE_ID},0",
            self.temp_audio_path,
            "silence", "1", "0.1", "1%", "1", "2.0", "1%"
        ]

        subprocess.run(cmd, env=sox_env)

        if not os.path.exists(self.temp_audio_path) or os.path.getsize(self.temp_audio_path) < 100:
            return ""

        print("📝 Transcribing...")
        text = self._transcribe_cloud(self.temp_audio_path)

        hallucinations = [
            "ご視聴ありがとうございました",
            "Thanks for watching",
            "MBC",
            "Amara.org"
        ]
        if any(h in text for h in hallucinations) or len(text) < 2:
            print(f"   (Filtered Hallucination: '{text}')")
            return ""

        print(f"   You said: '{text}'")
        return text

    def _transcribe_cloud(self, audio_path):
        """Transcribe using OpenAI Whisper cloud API, with local fallback."""
        try:
            with open(audio_path, "rb") as audio_file:
                transcription = self.openai_client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    prompt="User is requesting songs by name on a retro radio. Common requests include: 'Play Here by Mumford and Sons', 'Play Bohemian Rhapsody', 'Play a song called...'. Treat short words like 'Here', 'Stay', 'Home' as potential song titles, not filler words. The language is likely English or Czech.",
                    language=None
                )
            return transcription.text.strip()
        except Exception as e:
            print(f"❌ Cloud STT Error: {e}")
            if FEATURE_FLAGS.get("local_whisper"):
                return self._transcribe_local(audio_path)
            return ""

    def _transcribe_local(self, audio_path):
        """Fallback: transcribe using local faster-whisper model."""
        try:
            from faster_whisper import WhisperModel
            if not hasattr(self, '_local_model'):
                print("   (Loading local Whisper model...)")
                self._local_model = WhisperModel("tiny", device="cpu", compute_type="int8")
            segments, _ = self._local_model.transcribe(audio_path)
            text = " ".join(s.text for s in segments).strip()
            print(f"   (Local Whisper: '{text}')")
            return text
        except ImportError:
            print("   (faster-whisper not installed)")
            return ""
        except Exception as e:
            print(f"❌ Local STT Error: {e}")
            return ""

    def _play_file(self, path, block=True, device=DEVICE_HANDSET):
        """Play audio file using aplay (wav) or mpg123 (mp3)."""
        self.stop_audio()
        alsa_dev = self._get_alsa_device(device)

        if path.endswith(".mp3"):
            cmd = ["mpg123", "-q", "-a", alsa_dev, path]
        else:
            cmd = ["aplay", "-q", "-D", alsa_dev, path]

        try:
            self.current_process = subprocess.Popen(cmd)
            if block:
                self.current_process.wait()
                self.current_process = None
        except Exception as e:
            print(f"Error play_file: {e}")
