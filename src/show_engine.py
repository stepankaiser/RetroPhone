import time
import random
import threading
from .config import (
    FEATURE_FLAGS, SHOW_DJ_BREAK_INTERVAL, SHOW_JINGLE_INTERVAL,
    SHOW_BELL_ENABLED, DECADE_VOICES, DECADE_DJ_NAMES
)


class ShowEngine:
    """
    Orchestrates a full radio show experience.
    Manages the lifecycle: IDLE -> INTRO -> PLAYING -> DJ_BREAK -> PLAYING -> OUTRO
    Coordinates DJ breaks, jingles, proactive bell ringing, and show state.
    """

    def __init__(self, brain, audio, music, phone):
        self.brain = brain
        self.audio = audio
        self.music = music
        self.phone = phone

        self.is_active = False
        self.current_year = None
        self.current_language = "EN"
        self.songs_played = 0
        self.show_phase = "IDLE"  # IDLE, INTRO, PLAYING, DJ_BREAK, OUTRO

        # Internal state
        self._original_track_callback = None
        self._bell_timer = None
        self._pending_bell_content = None

    def start_show(self, year, language="EN"):
        """Begin a full radio show for the given decade."""
        if not FEATURE_FLAGS.get("show_mode"):
            return

        self.is_active = True
        self.current_year = year
        self.current_language = language
        self.songs_played = 0
        self.show_phase = "PLAYING"

        # Take over the track change callback
        self._original_track_callback = self.music.on_track_change
        self.music.on_track_change = self._on_song_end

        # Schedule first bell event
        if SHOW_BELL_ENABLED:
            self._schedule_bell()

        print(f"📻 SHOW MODE STARTED ({year}s)")

    def end_show(self):
        """DJ signs off and show ends."""
        if not self.is_active:
            return

        self.show_phase = "OUTRO"
        print(f"📻 SHOW ENDING ({self.songs_played} songs played)")

        # Generate sign-off
        try:
            dj_name = self.brain.get_dj_name(self.current_year, self.current_language)
            voice_data = self.brain.get_voice_for_year(self.current_year)

            if self.current_language == "EN":
                signoff = f"That's all from {dj_name}! Thanks for tuning in to the {self.current_year}s. Until next time!"
            else:
                signoff = f"To je vse od {dj_name}! Dekuji ze jste poslouchali. Nashledanou!"

            self.music.set_volume(30)
            time.sleep(0.3)
            self.audio.speak(signoff, voice_id=voice_data['id'],
                           voice_settings=voice_data['settings'],
                           model_id=voice_data['model'], year=self.current_year)
            self.music.set_volume(100)
        except Exception as e:
            print(f"   (Sign-off error: {e})")

        # Restore original callback
        self.music.on_track_change = self._original_track_callback
        self._cancel_bell()
        self.is_active = False
        self.show_phase = "IDLE"

    def _on_song_end(self, old_track, new_track):
        """Called when a song finishes during an active show."""
        if not self.is_active:
            return

        self.songs_played += 1
        print(f"📻 Show: Song #{self.songs_played} ended ({old_track['name']})")

        # Don't do breaks if user is on the phone
        if self.phone and self.phone.is_off_hook:
            return

        # Jingle check (every SHOW_JINGLE_INTERVAL songs)
        if self.songs_played % SHOW_JINGLE_INTERVAL == 0:
            self._play_jingle()
            return  # Jingle replaces the DJ break for this transition

        # DJ break check (every SHOW_DJ_BREAK_INTERVAL songs)
        if self.songs_played % SHOW_DJ_BREAK_INTERVAL == 0:
            self._do_dj_break(old_track, new_track)
            return

        # Also forward to original callback if it exists (for the random DJ breaks from Phase 3)
        if self._original_track_callback:
            self._original_track_callback(old_track, new_track)

    def _do_dj_break(self, old_track, new_track):
        """Pause Spotify, DJ talks through home speakers, resume."""
        self.show_phase = "DJ_BREAK"
        try:
            voice_data = self.brain.get_voice_for_year(self.current_year)
            commentary = self.brain.generate_dj_commentary(
                old_track, new_track, self.current_year, self.current_language
            )
            if commentary:
                # Pause Spotify to release ALSA device
                self.music.pause()
                time.sleep(0.5)
                # Speak through HOME AUDIO (room speakers)
                self.audio.speak(commentary, voice_id=voice_data['id'],
                               voice_settings=voice_data['settings'],
                               model_id=voice_data['model'], year=self.current_year,
                               device="home")
                time.sleep(0.3)
                # Resume playback
                try:
                    self.music.sp.start_playback(device_id=self.music.device_id)
                except Exception as e:
                    print(f"   (Resume error: {e})")
        except Exception as e:
            print(f"   (Show DJ break error: {e})")
            try:
                self.music.sp.start_playback(device_id=self.music.device_id)
            except Exception:
                pass
        self.show_phase = "PLAYING"

    def _play_jingle(self):
        """Play the era-specific station jingle through home speakers."""
        try:
            decade_key = int(str(self.current_year)[:3] + "0")
            jingle_name = f"jingle_{decade_key}"
            self.music.pause()
            time.sleep(0.3)
            self.audio.play_sound(jingle_name, block=True, year=self.current_year, device="home")
            time.sleep(0.2)
            try:
                self.music.sp.start_playback(device_id=self.music.device_id)
            except Exception as e:
                print(f"   (Resume after jingle error: {e})")
            print(f"📻 Played jingle for {decade_key}s")
        except Exception as e:
            print(f"   (Jingle error: {e})")
            try:
                self.music.sp.start_playback(device_id=self.music.device_id)
            except Exception:
                pass

    def _schedule_bell(self):
        """Schedule a proactive bell ring for a special event."""
        if not SHOW_BELL_ENABLED or not self.is_active:
            return

        # Ring bell after a random interval (8-15 songs worth of time, ~30-60 min)
        delay = random.randint(180, 600)  # 3-10 minutes
        self._bell_timer = threading.Timer(delay, self._ring_bell_event)
        self._bell_timer.daemon = True
        self._bell_timer.start()

    def _cancel_bell(self):
        """Cancel any pending bell event."""
        if self._bell_timer:
            self._bell_timer.cancel()
            self._bell_timer = None

    def _ring_bell_event(self):
        """Ring the bell to get the user's attention for a special segment."""
        if not self.is_active:
            return
        # Quiet hours: no bell between 22:00 and 08:00
        from datetime import datetime
        hour = datetime.now().hour
        if hour >= 22 or hour < 8:
            self._schedule_bell()  # Try again later
            return
        # Only ring if handset is on hook
        if self.phone and self.phone.is_off_hook:
            # Reschedule for later
            self._schedule_bell()
            return

        event_type = random.choice(["dedication", "breaking_news"])
        dj_name = self.brain.get_dj_name(self.current_year, self.current_language)

        if event_type == "dedication":
            self._pending_bell_content = (
                f"Hey caller! {dj_name} here. This next one is dedicated to you!"
                if self.current_language == "EN"
                else f"Ahoj volajici! Tady {dj_name}. Dalsi pisnicka je venovana vam!"
            )
        else:
            self._pending_bell_content = (
                f"Breaking news on the {self.current_year}s airwaves! Pick up if you want the scoop!"
                if self.current_language == "EN"
                else f"Mimoradna zprava z roku {self.current_year}! Zdvihnete sluchatko!"
            )

        print(f"🔔 BELL RING EVENT: {event_type}")
        try:
            self.phone.ring_bell(duration=1.5)
        except Exception as e:
            print(f"   (Bell ring error: {e})")

        # Schedule next bell
        self._schedule_bell()

    def get_pending_bell_content(self):
        """Get and clear any pending bell content (called when user picks up after bell)."""
        content = self._pending_bell_content
        self._pending_bell_content = None
        return content
