import time
import sys
import os

# Ensure we can import src
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.music_engine import MusicEngine

def test_long_playback():
    print("🧪 Initializing Manual Playback Test...")
    engine = MusicEngine()
    
    # 1. FIND THE DEVICE
    # We expect the service (retrophone.service) to be running librespot
    print("🔎 Finding active RetroRadio...")
    # strict_retro=False allows us to find it even if name changed slightly, 
    # but we really want the one playing.
    device_id = engine.find_device(force_refresh=True)
    
    if not device_id:
        print("❌ Could not find device! Is the service running?")
        return

    # 2. PLAY TRACK
    # Rick Astley - Never Gonna Give You Up (Universally Available)
    song_uri = "spotify:track:4cOdK2wGLETKBW3PvgPWqT" 
    
    # Wait for player to be fully ready
    time.sleep(5)
    
    print(f"▶️ Playing 'Never Gonna Give You Up' on device {device_id}...")
    
    engine.play_track(song_uri)
    
    print("⏱️ Monitoring playback for 3 minutes...")
    print("   (Monitor will report status every 10s. Watch for 'SKIP' warnings)")
    
    start_time = time.time()
    last_progress = -1
    skip_count = 0
    
    # Loop for 180 seconds (3 mins)
    for i in range(180):
        try:
            current = engine.sp.current_playback()
            
            if current and current['is_playing']:
                progress_ms = current['progress_ms']
                track_name = current['item']['name']
                
                # Check for skipping (progress shouldn't jump backward significantly)
                # Allow small jitter, but a jump of > 2s backwards or reset to 0 is bad.
                if last_progress > 0 and progress_ms < (last_progress - 2000):
                     print(f"⚠️ DETECTED SKIP! Progress jumped from {last_progress}ms to {progress_ms}ms")
                     skip_count += 1
                
                last_progress = progress_ms
                
                # Print status every 10 seconds
                if i % 10 == 0:
                     print(f"   [{i}s] 🎶 Playing: {track_name} ({progress_ms/1000:.1f}s)")
            else:
                # Could be paused or buffering
                print(f"   [{i}s] ⚠️ Not playing (Paused or Buffering?)")
                
        except Exception as e:
            print(f"   Error checking status: {e}")
            
        time.sleep(1)

    print("-" * 40)
    if skip_count == 0:
        print("✅ TEST PASSED: No skips detected over 3 minutes.")
    else:
        print(f"❌ TEST FAILED: {skip_count} skips detected.")

if __name__ == "__main__":
    test_long_playback()
