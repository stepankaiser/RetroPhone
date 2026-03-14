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

def generate_jingle(filename, decade, duration=3.0, volume=0.4, rate=44100):
    """Generate an era-specific radio jingle/station ID."""
    print(f"Generating jingle for {decade}s -> {filename}...")
    with wave.open(filename, 'w') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(rate)

        data = []
        total_samples = int(rate * duration)

        for i in range(total_samples):
            t = i / rate
            value = 0.0

            if decade <= 1910:
                # Gramophone crackle: filtered noise + scratchy warble
                noise = random.uniform(-1, 1) * 0.15
                warble = math.sin(2 * math.pi * 300 * t + math.sin(2 * math.pi * 5 * t) * 3) * 0.3
                crackle = (random.random() > 0.98) * random.uniform(-1, 1) * 0.6
                value = (noise + warble + crackle) * volume
                # Fade envelope
                env = min(t / 0.3, 1.0) * min((duration - t) / 0.5, 1.0)
                value *= env

            elif decade == 1920:
                # Jazz-age piano sting: quick arpeggiated tones
                notes = [262, 330, 392, 523]  # C major arpeggio
                note_dur = duration / len(notes)
                note_idx = min(int(t / note_dur), len(notes) - 1)
                freq = notes[note_idx]
                local_t = t - note_idx * note_dur
                env = max(0, 1.0 - local_t / note_dur) * min(local_t / 0.01, 1.0)
                value = math.sin(2 * math.pi * freq * t) * env * volume
                # Add slight honky-tonk detune
                value += math.sin(2 * math.pi * (freq * 1.005) * t) * env * volume * 0.3

            elif decade == 1930:
                # Golden age orchestral swell
                freq = 220 + 220 * (t / duration)  # Rising pitch
                env = math.sin(math.pi * t / duration)  # Smooth swell
                value = math.sin(2 * math.pi * freq * t) * env * volume
                value += math.sin(2 * math.pi * freq * 1.5 * t) * env * volume * 0.3  # Fifth

            elif decade == 1940:
                # Shortwave radio tuning sweep
                sweep_freq = 400 + 1600 * math.sin(2 * math.pi * 0.5 * t)
                static_mix = random.uniform(-1, 1) * 0.2
                signal = math.sin(2 * math.pi * sweep_freq * t) * 0.5
                env = min(t / 0.2, 1.0) * min((duration - t) / 0.3, 1.0)
                value = (signal + static_mix) * volume * env

            elif decade == 1950:
                # Rock n roll guitar riff: power chord stab
                freqs = [110, 165, 220]  # A power chord
                stab_len = 0.15
                num_stabs = 4
                stab_period = duration / num_stabs
                local_t = t % stab_period
                if local_t < stab_len:
                    env = max(0, 1.0 - local_t / stab_len)
                    for f in freqs:
                        value += math.sin(2 * math.pi * f * t) * env
                    # Add overdrive
                    value = max(-1, min(1, value * 2)) * volume * 0.6
                else:
                    value = 0

            elif decade == 1960:
                # Pirate radio burst: distorted signal + static
                freq = 800 + 200 * math.sin(2 * math.pi * 3 * t)
                signal = math.sin(2 * math.pi * freq * t)
                signal = max(-0.6, min(0.6, signal * 3))  # Hard clip
                static = random.uniform(-1, 1) * 0.25
                env = min(t / 0.1, 1.0) * min((duration - t) / 0.2, 1.0)
                value = (signal + static) * volume * env

            elif decade == 1970:
                # Smooth FM ident: warm sine sweep with chorus
                freq = 440 + 220 * math.sin(2 * math.pi * 0.3 * t)
                value = math.sin(2 * math.pi * freq * t) * 0.5
                value += math.sin(2 * math.pi * (freq * 1.002) * (t + 0.01)) * 0.3  # Chorus
                env = math.sin(math.pi * t / duration)
                value *= volume * env

            elif decade == 1980:
                # Synth stab: detuned saw + gated reverb
                freq = 440
                saw1 = (2 * (freq * t % 1) - 1)
                saw2 = (2 * ((freq * 1.01) * t % 1) - 1)  # Detuned
                value = (saw1 + saw2) * 0.3
                # Gate pattern
                gate = 1.0 if (t * 8) % 1 < 0.6 else 0.0
                env = min(t / 0.05, 1.0) * min((duration - t) / 0.1, 1.0)
                value *= volume * gate * env

            elif decade == 1990:
                # Morning zoo air horn + scratch
                if t < 0.4:
                    # Air horn
                    value = math.sin(2 * math.pi * 880 * t) * 0.6
                    value += math.sin(2 * math.pi * 1108 * t) * 0.4  # Major third
                    env = min(t / 0.02, 1.0) * min((0.4 - t) / 0.1, 1.0)
                    value *= volume * env
                elif t < 1.0:
                    # Record scratch simulation
                    scratch_t = t - 0.4
                    freq = 200 + 600 * abs(math.sin(2 * math.pi * 4 * scratch_t))
                    value = math.sin(2 * math.pi * freq * t) * 0.3
                    noise = random.uniform(-1, 1) * 0.15
                    value = (value + noise) * volume
                else:
                    value = 0

            elif decade == 2000:
                # Digital whoosh: filtered sweep
                freq = 100 + 2000 * (t / duration) ** 2
                value = math.sin(2 * math.pi * freq * t) * 0.5
                env = (t / duration) ** 0.5 * min((duration - t) / 0.3, 1.0)
                value *= volume * env

            elif decade == 2010:
                # EDM riser: building synth
                freq = 200 * (2 ** (t / duration))  # Exponential rise
                value = math.sin(2 * math.pi * freq * t) * 0.4
                # Add sub
                value += math.sin(2 * math.pi * 60 * t) * 0.3
                env = (t / duration) * min((duration - t) / 0.1, 1.0)
                value *= volume * env

            elif decade >= 2020:
                # Podcast chime: clean bell tones
                notes = [523, 659, 784, 1047]  # C5 major
                for j, freq in enumerate(notes):
                    onset = j * 0.4
                    if t >= onset:
                        local_t = t - onset
                        env = max(0, math.exp(-local_t * 3))
                        value += math.sin(2 * math.pi * freq * local_t) * env * 0.25
                value *= volume

            # Clamp
            sample = int(max(-32767, min(32767, value * 32767)))
            data.append(struct.pack('<h', sample))

        wav_file.writeframes(b''.join(data))


def main():
    sounds_dir = "sounds"
    if not os.path.exists(sounds_dir):
        os.makedirs(sounds_dir)

    # Generate core sound effects
    generate_tone(os.path.join(sounds_dir, "dial_tone.wav"), frequency=425, duration=10.0, interrupted=True)
    generate_static(os.path.join(sounds_dir, "static_short.wav"), duration=0.5)
    generate_static(os.path.join(sounds_dir, "static_long.wav"), duration=2.0)
    generate_click(os.path.join(sounds_dir, "click.wav"))

    # Generate era-specific jingles
    decades = [1900, 1910, 1920, 1930, 1940, 1950, 1960, 1970, 1980, 1990, 2000, 2010, 2020]
    for decade in decades:
        generate_jingle(os.path.join(sounds_dir, f"jingle_{decade}.wav"), decade, duration=3.0)

    print("Done generating all sounds.")

if __name__ == "__main__":
    main()
