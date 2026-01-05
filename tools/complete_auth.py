import sys
import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.config import SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET, SPOTIPY_REDIRECT_URI

def complete_auth(url):
    cache_path = os.path.expanduser("~/RetroPhone/.cache")
    print(f"📂 Using Cache Path: {cache_path}")
    
    auth_manager = SpotifyOAuth(
        client_id=SPOTIPY_CLIENT_ID,
        client_secret=SPOTIPY_CLIENT_SECRET,
        redirect_uri=SPOTIPY_REDIRECT_URI,
        scope="user-modify-playback-state user-read-playback-state",
        open_browser=False,
        cache_path=cache_path
    )
    
    try:
        # Parse the code from the URL
        code = auth_manager.parse_response_code(url)
        if not code:
            print("❌ No code found in URL")
            sys.exit(1)
            
        print(f"🔑 Code extracted: {code[:10]}...")
        
        # Get Token (this writes .cache)
        token_info = auth_manager.get_access_token(code)
        
        if token_info:
            print("✅ Token acquired and saved to .cache!")
        else:
            print("❌ Failed to get token.")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 complete_auth.py <redirect_url>")
        sys.exit(1)
    
    complete_auth(sys.argv[1])
