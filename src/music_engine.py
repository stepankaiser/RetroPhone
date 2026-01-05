import time
import spotipy
import os
import subprocess
from spotipy.oauth2 import SpotifyOAuth
from .config import SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET, SPOTIPY_REDIRECT_URI

import random

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
        self.is_playing = False # Track state

    def start_embedded_player(self):
        """Starts the embedded librespot player as a subprocess."""
        print("🚀 Starting Embedded Librespot Player (RetroRadio)...")
        try:
            # Kill existing
            os.system("killall librespot 2>/dev/null")
            time.sleep(2)
            
            # Creds
            creds_path = os.path.expanduser("~/RetroPhone/credentials.json")
            if not os.path.exists(creds_path):
                print("⚠️ No credentials.json found! Player might fail.")
                
            # Cache to Disk (SD Card has 10GB free, /tmp RAM was filling up)
            cache_dir = os.path.expanduser("~/RetroPhone/spotify_cache")
            os.system(f"mkdir -p {cache_dir}")
            if os.path.exists(creds_path):
                os.system(f"cp {creds_path} {cache_dir}/credentials.json")

            # Dynamic Name to avoid Avahi/mDNS Collisions
            device_name = f"RetroRadio-{random.randint(1000, 9999)}"
            print(f"   (Using Device Name: {device_name})")

            cmd = [
                "/usr/bin/librespot",
                "--name", device_name,
                "--device", "plughw:0,0", # Exclusive hardware access (Most reliable for Pi Headphone Jack)
                "--backend", "alsa",
                "--bitrate", "320",
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

    def set_volume(self, volume=100):
        if self.device_id:
            try:
                self.sp.volume(volume, device_id=self.device_id)
            except:
                pass

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

    def search_and_play(self, query, type='playlist', retry=True):
        """Search Spotify and play the first result."""
        if not self.device_id: self.find_device()
        
        try:
            # SEARCH STEP (Does not need device ID usually, but good check)
            print(f"🔎 Music Search: '{query}'")
            results = self.sp.search(q=query, limit=1, type=type)
        
            if not results:
                print("❌ Search returned no results.")
                return False

            uri = None
            if type == 'playlist':
                 try: uri = results['playlists']['items'][0]['uri']
                 except: pass
            elif type == 'track':
                 try: uri = results['tracks']['items'][0]['uri']
                 except: pass
            elif type == 'album':
                 try: uri = results['albums']['items'][0]['uri']
                 except: pass
            elif type == 'artist':
                 try: uri = results['artists']['items'][0]['uri']
                 except: pass

            if uri:
                self.set_volume(100) # This might fail if device is dead
                if type == 'playlist' or type == 'album' or type == 'artist':
                    self.sp.start_playback(device_id=self.device_id, context_uri=uri)
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
