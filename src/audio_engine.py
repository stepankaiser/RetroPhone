import os
import time
import subprocess
from openai import OpenAI
from elevenlabs.client import ElevenLabs
from elevenlabs import save, VoiceSettings
from .config import OPENAI_API_KEY, ELEVENLABS_API_KEY, AUDIO_DEVICE_ID, DEFAULT_VOLUME, DECADE_EFFECTS

class AudioEngine:
    def __init__(self):
        # Initialize Clients
        self.openai_client = OpenAI(api_key=OPENAI_API_KEY)
        self.eleven_client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
        
        # Audio Process Tracking
        self.current_process = None
        
        # Paths
        self.sounds_dir = os.path.join(os.path.dirname(__file__), "../sounds")
        if not os.path.exists(self.sounds_dir):
            os.makedirs(self.sounds_dir)
            
        self.temp_audio_path = "/tmp/retro_temp_audio.wav"
        self.temp_speech_path = "/tmp/retro_tts.mp3"
        self.temp_processed_path = "/tmp/retro_tts_processed.mp3"

    def stop_audio(self):
        """Stop any currently playing audio (sound effects/music initiated by this engine)."""
        if self.current_process:
            try:
                self.current_process.terminate()
                try:
                    self.current_process.wait(timeout=2) # Ensure process acts on the signal
                except subprocess.TimeoutExpired:
                    self.current_process.kill() # Force kill if stubborn
                self.current_process = None
            except Exception as e:
                print(f"Error stopping audio: {e}")

    def play_sound(self, sound_name, block=False):
        """
        Play a sound effect.
        :param block: If True, wait for sound to finish. If False, play in background.
        """
        path = os.path.join(self.sounds_dir, f"{sound_name}.wav")
        if os.path.exists(path):
            self._play_file(path, block=block)
        else:
            print(f"Warning: Sound {sound_name} not found at {path}")

    def speak(self, text, voice_id="JBFqnCBsd6RMkjVDRZzb", voice_settings=None, model_id="eleven_turbo_v2_5", year=None):
        print(f"🗣️ Speaking: {text}")
        self.stop_audio() # Stop any background sounds
        
        try:
            # Prepare Settings Object if provided
            v_settings = None
            if voice_settings:
                v_settings = VoiceSettings(
                    stability=voice_settings.get('stability', 0.5),
                    similarity_boost=voice_settings.get('similarity_boost', 0.75),
                    style=voice_settings.get('style', 0.0),
                    use_speaker_boost=True
                )

            # Generate Audio
            audio_generator = self.eleven_client.text_to_speech.convert(
                text=text,
                voice_id=voice_id,
                model_id=model_id,
                voice_settings=v_settings
            )
            save(audio_generator, self.temp_speech_path)
            
            # Post-Production (SoX)
            final_path = self.temp_speech_path
            if year:
                 final_path = self._apply_vintage_effects(self.temp_speech_path, self.temp_processed_path, year)

            self._play_file(final_path, block=True) # Speak is always blocking
            
        except Exception as e:
            print(f"❌ TTS Error: {e}")
            os.system(f"espeak '{text}'")

    def _apply_vintage_effects(self, input_path, output_path, year):
        """Apply SoX effects based on the decade."""
        effects = DECADE_EFFECTS.get(year)
        if not effects:
            return input_path # No effects for this year
            
        print(f"   🎛️ Applying FX ({year}): {effects}")
        # Command: AUDIODRIVER=alsa sox input.mp3 output.mp3 <effects>
        # Note: sox needs libsox-fmt-mp3 for mp3 support
        cmd = f"AUDIODRIVER=alsa sox '{input_path}' '{output_path}' {effects}"
        
        try:
            res = os.system(cmd)
            if res == 0:
                return output_path
            else:
                print("   ❌ SoX failed (check if installed). Playing raw.")
                return input_path
        except Exception as e:
            print(f"   ❌ SoX Error: {e}")
            return input_path

    def listen(self, duration=15):
        """
        Smart Listening (VAD):
        - recording starts when you speak (noise > 1%)
        - recording stops when you stop (silence > 2.0s)
        - failsafe timeout of 15s
        """
        self.stop_audio() # Silence before listening
        time.sleep(0.5) # Give the audio card a moment to release (Race Condition Fix)

        print("👂 Listening (Smart VAD)...")
        
        # VAD Command using SoX
        # 1. silence 1 0.1 1%  -> Remove silence at start until 0.1s of sound > 1%
        # 2. 1 2.0 1%          -> Stop recording after 2.0s of silence < 1%
        # timeout 15           -> Hard limit to prevent hanging
        
        # Explicitly force AUDIODRIVER=alsa to hush Jack errors
        # Fix: AUDIODRIVER=alsa must be BEFORE timeout or passed via env to work
        cmd = (
            f"AUDIODRIVER=alsa timeout {duration} sox -q -t alsa plughw:{AUDIO_DEVICE_ID},0 "
            f"{self.temp_audio_path} silence 1 0.1 1% 1 2.0 1%"
        )
        
        res = os.system(cmd) 
        
        # Check if file exists and has size (timeout might kill it without creating valid header sometimes)
        if not os.path.exists(self.temp_audio_path) or os.path.getsize(self.temp_audio_path) < 100:
             # If SoX failed or timed out with just silence, we might get an empty/truncated file.
             return ""

        # Proceed to Transcribe...

        print("📝 Transcribing...")
        try:
            with open(self.temp_audio_path, "rb") as audio_file:
                transcription = self.openai_client.audio.transcriptions.create(
                    model="whisper-1", 
                    file=audio_file,
                    prompt="User is speaking to a radio host about music, news, life, or the year. The language is likely English or Czech.",
                    language=None # Auto-detect
                )
            text = transcription.text.strip()
            
            # Anti-Hallucination Filters (Whisper bugs on silence)
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
        except Exception as e:
            print(f"❌ STT Error: {e}")
            return ""

    def _play_file(self, path, block=True):
        """Play audio file using aplay (wav) or mpg123 (mp3)."""
        self.stop_audio() # Stop previous
        
        cmd = []
        if path.endswith(".mp3"):
            # Use specific hardware device for Voice/Handset (USB Audio)
            cmd = ["mpg123", "-q", "-a", f"plughw:{AUDIO_DEVICE_ID},0", path]
        else:
            cmd = ["aplay", "-q", "-D", f"plughw:{AUDIO_DEVICE_ID},0", path]
            
        # Unified Process Launch (Allows killing blocking processes too)
        try:
            self.current_process = subprocess.Popen(cmd)
            
            if block:
                self.current_process.wait()
                self.current_process = None # Clear after finish
        except Exception as e:
            print(f"Error play_file: {e}")
