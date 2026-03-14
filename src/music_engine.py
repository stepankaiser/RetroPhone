import time
import spotipy
import os
import subprocess
import shutil
import random
import threading
from spotipy.oauth2 import SpotifyOAuth
from .config import SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET, SPOTIPY_REDIRECT_URI, FEATURE_FLAGS

class MusicEngine:
    def __init__(self):
        cache_path = os.path.expanduser("~/RetroPhone/.cache")
        self.sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
            client_id=SPOTIPY_CLIENT_ID,
            client_secret=SPOTIPY_CLIENT_SECRET,
            redirect_uri=SPOTIPY_REDIRECT_URI,
            scope="user-modify-playback-state user-read-playback-state",
            open_browser=False, # Headless Mode
            cache_path=cache_path
        ))
        self.device_id = None
        self.is_playing = False

        # Playback Monitor (Phase 3)
        self._monitor_thread = None
        self._monitor_running = False
        self.current_track = None      # {id, name, artist, progress_ms, duration_ms}
        self.on_track_change = None    # callback: fn(old_track, new_track)

    def start_embedded_player(self):
        """Starts the embedded librespot player as a subprocess."""
        print("🚀 Starting Embedded Librespot Player (RetroRadio)...")
        try:
            # Kill existing
            subprocess.run(["killall", "librespot"], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
            time.sleep(2)

            # Creds
            creds_path = os.path.expanduser("~/RetroPhone/credentials.json")
            if not os.path.exists(creds_path):
                print("⚠️ No credentials.json found! Player might fail.")

            # Cache to Disk (SD Card has 10GB free, /tmp RAM was filling up)
            cache_dir = os.path.expanduser("~/RetroPhone/spotify_cache")
            os.makedirs(cache_dir, exist_ok=True)
            if os.path.exists(creds_path):
                shutil.copy2(creds_path, os.path.join(cache_dir, "credentials.json"))

            # Dynamic Name to avoid Avahi/mDNS Collisions
            device_name = f"RetroRadio-{random.randint(1000, 9999)}"
            print(f"   (Using Device Name: {device_name})")

            cmd = [
                "/usr/bin/librespot",
                "--name", device_name,
                "--device", "plughw:0,0",
                "--backend", "alsa",
                "--bitrate", "320",
                "--format", "S16",              # 16-bit (Pi 3 headphone jack is PWM, higher won't help)
                "--dither", "tpdf_hp",           # Best dithering algorithm (reduces quantization noise)
                "--enable-volume-normalisation",  # Consistent volume across tracks (real radio feel)
                "--normalisation-method", "dynamic",
                "--normalisation-gain-type", "auto",
                "--normalisation-pregain", "3",   # Slight boost for speaker output
                "--cache", cache_dir,
                "--initial-volume", "90",
                "--zeroconf-port", "5555"
            ]
            
            # Launch in background (DEVNULL to avoid spamming main log, or capture if needed)
            # We let it inherit stdout/stderr for now to see logs in systemd journal
            subprocess.Popen(cmd)
            
            print("⏳ Waiting 10s for Player to Splash...")
            time.sleep(10)
            return True
        except Exception as e:
            print(f"❌ Failed to start player: {e}")
            return False

    def find_device(self, device_name="RetroRadio", force_refresh=False, strict_retro=False):
        """Find the Spotify Connect device ID (Prioritizing RetroRadio)."""
        CACHE_FILE = os.path.expanduser("~/RetroPhone/.spotify_device_id")
        
        # CLEAR CACHE IF FORCED
        if force_refresh and os.path.exists(CACHE_FILE):
             print("🧹 Clearing Device Cache...")
             os.remove(CACHE_FILE)

        try:
            best_device = None
            found_retro = False
            
            # 1. OPTIONAL: Check Cache First (Fast Path)
            if not force_refresh and not strict_retro and os.path.exists(CACHE_FILE):
                with open(CACHE_FILE, "r") as f:
                    cached_id = f.read().strip()
                if cached_id:
                    print(f"💾 Using Cached Device ID: {cached_id}")
                    self.device_id = cached_id
                    return self.device_id

            # 2. SCANNING (Slow Path)
            print("🔎 Scanning for Spotify Devices...")
            devices = self.sp.devices()
            print(f"🔎 Available Devices: {len(devices['devices'])}")
            
            for d in devices['devices']:
                # print(f"   - Name: {d['name']} | ID: {d['id']} | Active: {d['is_active']} | Volume: {d['volume_percent']}")
                d_name = d['name'].lower()
                
                # PRIORITY 1: The Radio itself
                if 'retroradio' in d_name or 'retro' in d_name:
                    best_device = d['id']
                    print(f"🎵 Found Retro Radio: {d['name']}")
                    found_retro = True
                    break 
                
                # PRIORITY 2: Any active device (fallback)
                if d['is_active'] and not strict_retro:
                    best_device = d['id']

            if found_retro and best_device:
                # Save this ID for later
                try:
                    with open(CACHE_FILE, "w") as f:
                        f.write(best_device)
                    print(f"💾 Saved Radio Device ID to cache.")
                except Exception as e:
                    print(f"⚠️ Could not save device ID: {e}")

            # Fallback to first available if nothing else
            if not best_device and devices['devices'] and not strict_retro:
                # STOP! Don't just pick the phone if we haven't tried healing yet.
                if not force_refresh:
                     print("⚠️ Retro Radio not found. Attempting to wake it up...")
                     if self._handle_playback_error("Device not found (Proactive)"):
                         return self.find_device(force_refresh=True)

                best_device = devices['devices'][0]['id']
                print(f"⚠️ Warning: Using Fallback Device: {devices['devices'][0]['name']}")

            self.device_id = best_device
            if best_device:
                 print(f"🎵 Target Device ID: {self.device_id}")
                 
                 # WAKE UP
                 try:
                     self.sp.transfer_playback(device_id=best_device, force_play=False)
                     time.sleep(1)
                 except Exception:
                     pass
            else:
                 print("❌ No Spotify devices found. Starting Player...")
                 self.start_embedded_player()
                 # Try finding one more time after start
                 time.sleep(5)
                 return self.find_device(force_refresh=True)
                 
            return self.device_id
        except Exception as e:
            print(f"❌ Spotify Error: {e}")
            return None

    def _handle_playback_error(self, e):
        """
        If we get a 404/Device Not Found OR 403/Restriction, invalidate cache and retry.
        Returns True if we should retry, False otherwise.
        """
        err_str = str(e)
        if "404" in err_str or "Device not found" in err_str or "No active device" in err_str or "403" in err_str or "Restriction violated" in err_str:
            print(f"⚠️ Playback Error ({err_str[:50]}...). Attempting Fast Heal...")
            
            # STEP 1: FAST HEAL (Refresh Device List)
            # Maybe the device ID just changed (Dynamic Naming)?
            print("   (Refreshing Device List...)")
            new_dev_id = self.find_device(force_refresh=True, strict_retro=True)
            
            if new_dev_id:
                print("   ✅ Fast Heal Successful! Found new Device ID.")
                return True # Retry the command with new ID
            
            # STEP 2: NUCLEAR OPTION (Restart Service)
            print("   ⚠️ Fast Heal Failed. Restarting Embedded Player...")
            
            # 1. Delete Cache (Wait, find_device already cleared it if we forced refresh, but do it again to be safe)
            CACHE_FILE = os.path.expanduser("~/RetroPhone/.spotify_device_id")
            if os.path.exists(CACHE_FILE):
                os.remove(CACHE_FILE)
            
            # 2. Restart EMBEDDED PLAYER (Self Healing)
            self.start_embedded_player()
            
            # 3. Force Find
            print("   (Polling for RetroRadio to announce...)")
            for i in range(10): # Try for 20 seconds
                 dev_id = self.find_device(force_refresh=True, strict_retro=True)
                 if dev_id:
                     print("   ✅ RetroRadio Recovered!")
                     return True
                 time.sleep(2)
            
            return True
        return False

    def start_monitor(self):
        """Start background thread monitoring Spotify playback for song transitions."""
        if not FEATURE_FLAGS.get("playback_monitor"):
            return
        if self._monitor_running:
            return
        self._monitor_running = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        print("🎵 Playback Monitor Started")

    def stop_monitor(self):
        """Stop the playback monitor thread."""
        self._monitor_running = False
        print("🎵 Playback Monitor Stopped")

    def _monitor_loop(self):
        """Poll Spotify every 3 seconds, detect song transitions."""
        last_track_id = None
        while self._monitor_running:
            try:
                playback = self.sp.current_playback()
                if playback and playback.get('is_playing') and playback.get('item'):
                    new_id = playback['item']['id']
                    old_track = self.current_track

                    self.current_track = {
                        'id': new_id,
                        'name': playback['item']['name'],
                        'artist': playback['item']['artists'][0]['name'],
                        'album': playback['item']['album']['name'],
                        'progress_ms': playback['progress_ms'],
                        'duration_ms': playback['item']['duration_ms'],
                    }

                    # Note: audio_features API returns 403 (deprecated by Spotify)
                    # Skip fetching to avoid log spam

                    # Detect song change
                    if last_track_id and new_id != last_track_id and self.on_track_change:
                        try:
                            self.on_track_change(old_track, self.current_track)
                        except Exception as e:
                            print(f"   (Track change callback error: {e})")

                    last_track_id = new_id
                elif not playback or not playback.get('is_playing'):
                    self.is_playing = False
            except Exception as e:
                print(f"   (Monitor poll error: {e})")

            time.sleep(3)

    def stop(self):
        """Stop all playback and clean up embedded player."""
        try:
            self.pause()
        except Exception as e:
            print(f"   (Stop pause error: {e})")
        self.is_playing = False
        subprocess.run(["killall", "librespot"], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)

    def set_volume(self, volume=100):
        if self.device_id:
            try:
                self.sp.volume(volume, device_id=self.device_id)
            except Exception as e:
                print(f"   (Volume error: {e})")

    def play_track(self, uri, retry=True):
        if not self.device_id: self.find_device()
        try:
            self.set_volume(100)
            self.sp.start_playback(device_id=self.device_id, uris=[uri])
            self.is_playing = True
            print(f"▶️ Playing: {uri}")
        except Exception as e:
            print(f"❌ Play Error: {e}")
            if retry and self._handle_playback_error(e):
                 self.play_track(uri, retry=False)

    def play_playlist(self, playlist_uri, retry=True):
        if not self.device_id: self.find_device()
        try:
            self.set_volume(100)
            self.sp.start_playback(device_id=self.device_id, context_uri=playlist_uri)
            self.is_playing = True
            print(f"▶️ Playing Playlist: {playlist_uri}")
        except Exception as e:
            print(f"❌ Play Error: {e}")
            if retry and self._handle_playback_error(e):
                 self.play_playlist(playlist_uri, retry=False)

    def get_track_features(self, track_id):
        """Get audio features for a track (energy, tempo, valence, danceability)."""
        try:
            features = self.sp.audio_features(track_id)
            if features and features[0]:
                f = features[0]
                return {
                    "energy": f.get("energy", 0.5),
                    "tempo": f.get("tempo", 120),
                    "valence": f.get("valence", 0.5),
                    "danceability": f.get("danceability", 0.5),
                }
        except Exception as e:
            print(f"   (Audio features error: {e})")
        return None

    def play_local_phonograph(self, decade):
        """Play a random local recording from the phonograph collection (pre-1930s)."""
        import subprocess as sp_mod
        phono_dir = os.path.expanduser("~/RetroPhone/sounds/phonograph/")
        if not os.path.exists(phono_dir):
            return False
        files = [f for f in os.listdir(phono_dir) if f.endswith(('.wav', '.mp3', '.ogg'))]
        if not files:
            return False
        path = os.path.join(phono_dir, random.choice(files))
        print(f"📻 Playing phonograph: {path}")
        if path.endswith('.mp3'):
            sp_mod.Popen(["mpg123", "-q", "-a", "plughw:0,0", path])
        else:
            sp_mod.Popen(["aplay", "-q", "-D", "plughw:0,0", path])
        self.is_playing = True
        return True

    def search_and_play(self, query, type='playlist', retry=True, year=None):
        """Search Spotify and play the first result. Optional year for era filtering."""
        if not self.device_id: self.find_device()

        try:
            print(f"🔎 Music Search: '{query}' (Type: {type})")

            # Era-filtered search: append year range for better results
            search_q = query
            if year and type in ('track', 'album') and not any(c in query for c in ['year:', 'spotify:']):
                decade = int(str(year)[:3] + "0")
                search_q = f"{query} year:{decade}-{decade + 9}"
                print(f"   (Era-filtered: '{search_q}')")

            results = self.sp.search(q=search_q, limit=5, type=type)

            # If era-filtered search got nothing, retry without filter
            if not results or not self._has_results(results, type):
                if search_q != query:
                    print("   (Era filter returned nothing, trying unfiltered...)")
                    results = self.sp.search(q=query, limit=5, type=type)
            
            if not results or not self._has_results(results, type):
                print("❌ Search returned no results.")
                return False

            uri = None
            if type == 'playlist':
                 try: uri = results['playlists']['items'][0]['uri']
                 except (KeyError, IndexError) as e: print(f"   (Playlist parse: {e})")
            elif type == 'track':
                 try: uri = results['tracks']['items'][0]['uri']
                 except (KeyError, IndexError) as e: print(f"   (Track parse: {e})")
            elif type == 'album':
                 try: uri = results['albums']['items'][0]['uri']
                 except (KeyError, IndexError) as e: print(f"   (Album parse: {e})")
            elif type == 'artist':
                 try: uri = results['artists']['items'][0]['uri']
                 except (KeyError, IndexError) as e: print(f"   (Artist parse: {e})")

            if uri:
                self.set_volume(100) # This might fail if device is dead
                
                if type == 'playlist' or type == 'album' or type == 'artist':
                    self.sp.start_playback(device_id=self.device_id, context_uri=uri)
                elif type == 'track':
                    # SMART RADIO: Build queue from related artists (not just same artist)
                    try:
                        track_info = results['tracks']['items'][0]
                        artist_id = track_info['artists'][0]['id']
                        artist_name = track_info['artists'][0]['name']
                        print(f"   (Building Smart Radio from {artist_name} + related artists...)")

                        # Start with this artist's top tracks
                        top = self.sp.artist_top_tracks(artist_id)
                        queue_uris = [uri]  # Requested track first
                        queue_uris += [t['uri'] for t in top['tracks'] if t['uri'] != uri][:5]

                        # Add tracks from related artists for variety
                        try:
                            related = self.sp.artist_related_artists(artist_id)
                            for rel_artist in related['artists'][:4]:
                                rel_top = self.sp.artist_top_tracks(rel_artist['id'])
                                rel_uris = [t['uri'] for t in rel_top['tracks'][:3]]
                                queue_uris.extend(rel_uris)
                        except Exception as e:
                            print(f"   (Related artists failed: {e})")

                        # Shuffle everything after the first track
                        first = queue_uris[0]
                        rest = queue_uris[1:]
                        random.shuffle(rest)
                        full_queue = [first] + rest[:19]  # Max 20 tracks

                        self.sp.start_playback(device_id=self.device_id, uris=full_queue)
                        print(f"   (Smart Radio: {len(full_queue)} tracks queued)")
                    except Exception as e:
                        print(f"   (Smart Radio Failed: {e}. Playing single track.)")
                        self.sp.start_playback(device_id=self.device_id, uris=[uri])
                else:
                    self.sp.start_playback(device_id=self.device_id, uris=[uri])
                
                self.is_playing = True
                print(f"▶️ Playing Search Result: {uri}")
                return True
            else:
                print("❌ No music found.")
                return False
        except Exception as e:
            print(f"❌ Search/Play Error: {e}")
            if retry and self._handle_playback_error(e):
                return self.search_and_play(query, type=type, retry=False)
            return False

    def _has_results(self, results, type):
        """Check if search results contain at least one item."""
        key_map = {'playlist': 'playlists', 'track': 'tracks', 'album': 'albums', 'artist': 'artists'}
        key = key_map.get(type, type + 's')
        try:
            return bool(results.get(key, {}).get('items'))
        except Exception:
            return False

    def pause(self):
        try:
            print("   (MusicEngine: Sending Pause...)")
            self.sp.pause_playback(device_id=self.device_id)
            self.is_playing = False
        except Exception as e:
            # If pause fails, just ignore it. Music probably isn't playing or device is gone.
            # Do NOT trigger self-healing here, as it blocks the main thread (e.g. Operator dial).
            print(f"   (Pause ignored: {e})")
            self.is_playing = False
