import sys
import time
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.music_engine import MusicEngine

def verify():
    print("🔎 Verifying Music Engine...")
    
    try:
        music = MusicEngine()
        print("✅ MusicEngine initialized.")
        
        # Test 1: Audio Device Discovery
        device_id = music.find_device()
        if not device_id:
             print("❌ No Spotify Device Found! Start Raspotify.")
             sys.exit(1)
        print(f"✅ Device Found: {device_id}")
        
        # Test 2: Pause (Check Control)
        print("🎵 Testing Pause...")
        music.pause()
        print("✅ Pause Command Sent.")
        
        # Test 3: Search (Check API)
        print("🎵 Testing Search & Play...")
        query = "Never Gonna Give You Up"
        if music.search_and_play(query, type='track'):
            print("✅ Playback Started.")
        else:
            print("❌ Search/Play Failed.")
            sys.exit(1)
            
        print("⏳ Letting it play for 5 seconds...")
        time.sleep(5)
        
        print("🎵 Testing Stop...")
        music.pause()
        print("✅ Verify Complete.")
        
    except Exception as e:
        print(f"❌ Verification Failed with Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    verify()
