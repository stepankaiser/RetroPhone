import wave
import math
import struct
import random
import os

def generate_tone(filename, frequency=440, duration=10.0, volume=0.5, rate=44100, interrupted=False):
    print(f"Generating {filename} ({frequency}Hz, Interrupted={interrupted})...")
    with wave.open(filename, 'w') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(rate)
        
        data = []
        # Generate full duration
        total_samples = int(rate * duration)
        
        # Interrupted Pattern: 0.5s ON, 0.5s OFF (Total 1s cycle)
        period_samples = int(rate * 1.0) 
        on_samples = int(rate * 0.5) 
        
        for i in range(total_samples):
            # If interrupted, check cycle
            is_silence = False
            if interrupted:
                cycle_pos = i % period_samples
                if cycle_pos > on_samples:
                    is_silence = True
            
            if is_silence:
                value = 0
            else:
                # Sine wave
                value = int(volume * 32767.0 * math.sin(2.0 * math.pi * frequency * i / rate))
                
            data.append(struct.pack('<h', value))
            
        wav_file.writeframes(b''.join(data))

def generate_static(filename, duration=2.0, volume=0.3, rate=44100):
    print(f"Generating {filename} (Static)...")
    with wave.open(filename, 'w') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(rate)
        
        data = []
        for i in range(int(rate * duration)):
            # White noise
            value = int(random.uniform(-1, 1) * volume * 32767.0)
            data.append(struct.pack('<h', value))
            
        wav_file.writeframes(b''.join(data))

def generate_click(filename, duration=0.05, volume=0.8, rate=44100):
    print(f"Generating {filename} (Click)...")
    with wave.open(filename, 'w') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(rate)
        
        data = []
        # Short burst
        for i in range(int(rate * duration)):
            if i < 100: # intense start
                value = int(volume * 32767.0)
            else:
                value = 0
            data.append(struct.pack('<h', value))
        wav_file.writeframes(b''.join(data))

def main():
    sounds_dir = "sounds"
    if not os.path.exists(sounds_dir):
        os.makedirs(sounds_dir)
    
    # Generate Files
    # 425Hz Interrupted (0.5s ON, 0.5s OFF) for 10 seconds
    generate_tone(os.path.join(sounds_dir, "dial_tone.wav"), frequency=425, duration=10.0, interrupted=True) 
    generate_static(os.path.join(sounds_dir, "static_short.wav"), duration=0.5)
    generate_static(os.path.join(sounds_dir, "static_long.wav"), duration=2.0)
    generate_click(os.path.join(sounds_dir, "click.wav"))
    
    print("Done generating sounds.")

if __name__ == "__main__":
    main()
