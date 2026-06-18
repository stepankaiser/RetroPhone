#!/usr/bin/env python3
"""
Re-authorize Spotify on a machine WITH a browser (e.g. your Mac), then copy the
resulting token cache to the headless Pi.

Why this exists: Spotify refresh tokens now expire after 6 months — absolute,
NOT extended by use (policy effective 2026-07-20). The Pi runs headless with
open_browser=False, so it cannot complete an OAuth sign-in on its own. The token
cache is just a JSON blob keyed to the same client_id, so we generate it here
(where there is a browser) and scp it to the Pi.

Usage (from the repo root, on a machine with a browser):
    python3 -m venv venv && venv/bin/pip install spotipy
    venv/bin/python tools/reauth_local.py
Then run the printed scp + restart commands when you're on the Pi's network.

Prerequisite: the Spotify dashboard must list the redirect URI
http://127.0.0.1:8888/callback (Spotify no longer accepts 'localhost').
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _load_env(path):
    """Minimal .env loader that tolerates this repo's `export VAR=val` style."""
    if not os.path.exists(path):
        return
    for line in open(path):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.replace("export ", "").strip()
        os.environ.setdefault(key, val.strip().strip('"').strip("'"))


_load_env(os.path.join(ROOT, ".env"))

import spotipy
from spotipy.oauth2 import SpotifyOAuth
from src.config import SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET, SPOTIPY_REDIRECT_URI

# Must match the scopes the radio uses (music_engine.py) so the token is usable.
SCOPE = "user-modify-playback-state user-read-playback-state"
CACHE_OUT = os.path.join(ROOT, ".cache.new")


def main():
    print(f"Redirect URI: {SPOTIPY_REDIRECT_URI}")
    if "localhost" in SPOTIPY_REDIRECT_URI:
        print("STOP: Spotify no longer accepts 'localhost' redirect URIs.")
        print("      Set SPOTIPY_REDIRECT_URI = http://127.0.0.1:8888/callback in")
        print("      src/config.py AND add it in the Spotify dashboard, then re-run.")
        sys.exit(1)

    auth = SpotifyOAuth(
        client_id=SPOTIPY_CLIENT_ID,
        client_secret=SPOTIPY_CLIENT_SECRET,
        redirect_uri=SPOTIPY_REDIRECT_URI,
        scope=SCOPE,
        open_browser=True,     # spotipy opens the browser and runs a local server
        cache_path=CACHE_OUT,  # on 127.0.0.1:<port> to capture the redirect code
    )

    print("Opening your browser to authorize — approve the request in Spotify...")
    sp = spotipy.Spotify(auth_manager=auth)  # triggers OAuth, writes CACHE_OUT
    try:
        who = sp.me()
        print(f"Authorized as: {who.get('display_name') or who.get('id')}")
    except Exception as e:
        print(f"(Authorized, but the /me check failed — token still written: {e})")

    if not os.path.exists(CACHE_OUT):
        print("ERROR: token cache was not written. Re-run and finish the browser step.")
        sys.exit(1)

    print()
    print(f"Fresh token cache written: {CACHE_OUT}")
    print("Deploy it to the Pi (run these when on the Pi's network):")
    print(f"    scp {CACHE_OUT} pi@radio.local:~/RetroPhone/.cache")
    print("    ssh pi@radio.local 'sudo systemctl restart retrophone'")
    print()
    print("This token is valid for ~6 months. Re-run before it lapses to avoid downtime.")


if __name__ == "__main__":
    main()
