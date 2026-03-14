"""
Generate era-specific radio jingles using ElevenLabs Sound Effects API.
Falls back to synthesized jingles from sound_generator.py if API unavailable.

Usage: python3 tools/generate_jingles.py
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

SOUNDS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sounds")

JINGLE_PROMPTS = {
    1900: "Gentle classical music box melody, Edwardian era, music box chime, warm and nostalgic, 4 seconds",
    1910: "Military bugle call transitioning to ragtime piano, brass, patriotic, 4 seconds",
    1920: "Upbeat 1920s jazz jingle, Charleston rhythm, piano and clarinet, speakeasy vibe, 4 seconds",
    1930: "Golden age radio orchestral fanfare, dramatic strings, 1930s movie opening, warm, 4 seconds",
    1940: "1940s big band swing jingle, brass section, energetic, wartime radio bumper, 4 seconds",
    1950: "1950s rock and roll jingle, electric guitar riff, upbeat drums, diner jukebox feel, 4 seconds",
    1960: "1960s psychedelic rock jingle, fuzzy guitar, groovy beat, pirate radio station bumper, 4 seconds",
    1970: "1970s smooth FM radio jingle, funky bass line, wah guitar, disco strings, laid back, 4 seconds",
    1980: "1980s synth pop jingle, electronic drums, neon synthesizer arpeggio, power chord, energetic, 4 seconds",
    1990: "1990s alternative rock radio jingle, grunge guitar, punchy drums, morning zoo bumper, 4 seconds",
    2000: "2000s pop radio jingle, digital production, cheerful, top 40 station ID, clean, 4 seconds",
    2010: "2010s EDM drop jingle, building synth riser, electronic, modern radio station, 4 seconds",
    2020: "Podcast intro chime, clean bell tones, minimalist, modern, calming, lo-fi, 4 seconds",
}


def generate_with_elevenlabs():
    """Try to generate jingles using ElevenLabs Sound Effects API."""
    try:
        from elevenlabs.client import ElevenLabs

        api_key = os.getenv("ELEVENLABS_API_KEY")
        if not api_key:
            print("No ELEVENLABS_API_KEY found. Skipping API generation.")
            return False

        client = ElevenLabs(api_key=api_key)
        success_count = 0

        for decade, prompt in JINGLE_PROMPTS.items():
            output_path = os.path.join(SOUNDS_DIR, f"jingle_{decade}.mp3")

            # Skip if already exists
            if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
                print(f"   Skipping {decade}s (already exists)")
                success_count += 1
                continue

            print(f"   Generating {decade}s jingle...")
            try:
                result = client.text_to_sound_effects.convert(
                    text=prompt,
                    duration_seconds=4.0,
                )
                # result is an iterator of bytes
                with open(output_path, 'wb') as f:
                    for chunk in result:
                        f.write(chunk)
                print(f"   ✅ {decade}s -> {output_path}")
                success_count += 1
            except Exception as e:
                print(f"   ❌ {decade}s failed: {e}")

        return success_count > 0

    except ImportError:
        print("elevenlabs package not installed.")
        return False
    except Exception as e:
        print(f"ElevenLabs generation failed: {e}")
        return False


def generate_synthesized_fallback():
    """Fall back to the synthesized jingles from sound_generator.py."""
    print("\nFalling back to synthesized jingles...")
    try:
        # Import the existing generator
        tools_dir = os.path.dirname(os.path.abspath(__file__))
        sys.path.insert(0, tools_dir)
        from sound_generator import generate_jingle

        decades = [1900, 1910, 1920, 1930, 1940, 1950, 1960, 1970, 1980, 1990, 2000, 2010, 2020]
        for decade in decades:
            output_path = os.path.join(SOUNDS_DIR, f"jingle_{decade}.wav")
            if not os.path.exists(output_path):
                generate_jingle(output_path, decade, duration=3.0)
            else:
                print(f"   Skipping {decade}s (already exists)")
        return True
    except Exception as e:
        print(f"Synthesized generation failed: {e}")
        return False


def main():
    os.makedirs(SOUNDS_DIR, exist_ok=True)

    print("=== RetroPhone Jingle Generator ===")
    print(f"Output: {SOUNDS_DIR}\n")

    print("Trying ElevenLabs Sound Effects API...")
    if not generate_with_elevenlabs():
        generate_synthesized_fallback()

    print("\nDone! Jingles ready in sounds/")


if __name__ == "__main__":
    main()
