import time
import sys
import threading
import random
from src.phone_interface import PhoneInterface
from src.audio_engine import AudioEngine
from src.music_engine import MusicEngine
from src.brain import Brain
from src.show_engine import ShowEngine
from src.world_context import WorldContext
from src.conversational_engine import ConversationalEngine
from src.led_engine import LEDEngine
from src.preferences import Preferences
from src.config import (DECADE_PLAYLISTS, DECADE_VOICES, FEATURE_FLAGS, DJ_BREAK_PROBABILITY,
                        CLASSICAL_VOICE, CLASSICAL_PERSONA, CLASSICAL_PLAYLISTS)

# Persistent Preferences
prefs = Preferences() if FEATURE_FLAGS.get("persistent_prefs") else None

# System State
current_language = prefs.get("language") if prefs else "EN"
current_year = None
phone = None

# Initialize Modules
print("Initializing Audio Engine...")
audio = AudioEngine()
print("Initializing Brain...")
brain = Brain()
print("Initializing Music Engine...")
music = MusicEngine()
print("Initializing World Context...")
world = WorldContext() if FEATURE_FLAGS.get("world_context") else None
if world:
    brain.set_world_context(world)
print("Initializing LED Engine...")
led = LEDEngine()

# Initialized in main() after phone is ready
show = None
conv_engine = None

# --- DJ BREAK CALLBACK (Phase 3) ---
def on_track_change(old_track, new_track):
    """Called by MusicEngine monitor when song changes."""
    if not FEATURE_FLAGS.get("dj_breaks"):
        return
    if not current_year:
        return
    # Don't interrupt if user is on the phone
    if phone and phone.is_off_hook:
        return
    # Probability gate
    if random.random() > DJ_BREAK_PROBABILITY:
        return

    print(f"🎙️ DJ BREAK: {old_track['name']} -> {new_track['name']}")
    try:
        voice_data = brain.get_voice_for_year(current_year)
        commentary = brain.generate_dj_commentary(old_track, new_track, current_year, current_language)
        if commentary:
            # Pause Spotify (releases ALSA plughw:0,0 so we can use it)
            music.pause()
            time.sleep(0.5)
            # Speak DJ break through HOME AUDIO (room speakers), not handset
            audio.speak(commentary, voice_id=voice_data['id'], voice_settings=voice_data['settings'],
                       model_id=voice_data['model'], year=current_year, device="home")
            time.sleep(0.3)
            # Resume playback
            try:
                music.sp.start_playback(device_id=music.device_id)
            except Exception as e:
                print(f"   (Resume error: {e})")
    except Exception as e:
        print(f"   (DJ Break error: {e})")
        # Try to resume music if something went wrong
        try:
            music.sp.start_playback(device_id=music.device_id)
        except Exception:
            pass

# Wire up the callback
music.on_track_change = on_track_change

def on_hook_change(is_off_hook):
    if is_off_hook:
        print("\n📞 HANDSET LIFTED")

        # Always Pause Music on Pickup (New Interaction)
        print("   (Pausing music for new dial...)")
        try:
            threading.Thread(target=music.pause, daemon=True).start()
        except Exception as e:
            print(f"   (Pause Error: {e})")

        # SAFETY: Ensure Handset Audio is free before playing Dial Tone
        audio.stop_audio()
        time.sleep(0.2)

        # Check for pending bell content first (proactive show event)
        bell_content = show.get_pending_bell_content() if (show and show.is_active) else None
        if bell_content:
            try:
                voice_data = brain.get_voice_for_year(current_year)
                audio.speak(bell_content, voice_id=voice_data['id'], voice_settings=voice_data['settings'], model_id=voice_data['model'], year=current_year)
            except Exception as e:
                print(f"   (Bell content error: {e})")
                audio.play_sound("dial_tone", block=False)
        # Call-in greeting if music was playing and we have a current decade
        elif FEATURE_FLAGS.get("callin_greeting") and music.is_playing and current_year:
            try:
                greeting = brain.get_callin_greeting(current_year, current_language)
                voice_data = brain.get_voice_for_year(current_year)
                audio.speak(greeting, voice_id=voice_data['id'], voice_settings=voice_data['settings'], model_id=voice_data['model'], year=current_year)
            except Exception as e:
                print(f"   (Call-in greeting error: {e})")
                audio.play_sound("dial_tone", block=False)
        else:
            audio.play_sound("dial_tone", block=False)
    else:
        print("\n📞 HANDSET REPLACED")
        print("   (Silencing handset...)")
        audio.stop_audio()
        # End ConvAI session if active (do it in a thread to avoid deadlock)
        if conv_engine and conv_engine.is_active():
            threading.Thread(target=conv_engine.end_session, daemon=True).start()
        # Restore decade LED color (stop on-air flash)
        if current_year:
            led.set_decade(current_year)

def _use_conversational_ai():
    """Check if we should use ElevenLabs Conversational AI."""
    return (FEATURE_FLAGS.get("conversational_ai") and
            not FEATURE_FLAGS.get("legacy_mode") and
            conv_engine and conv_engine.is_available())

def _run_conversational_session(year, language):
    """
    Run an ElevenLabs Conversational AI session. Blocks until hangup.
    Returns True if session ran, False if fallback needed.
    """
    try:
        voice_data = brain.get_voice_for_year(year)
        instructions = brain.build_realtime_instructions(year, language)

        # CRITICAL: Release the ALSA device so ConvAI can open it
        audio.stop_audio()
        time.sleep(0.5)

        if not conv_engine.start_session(year, language, voice_data['id'], instructions):
            return False

        # LED: on-air indicator
        led.on_air_flash()

        # Wait for hangup — poll GPIO directly (phone_interface thread may be starved by ConvAI)
        # Also enforce idle timeout to prevent runaway billing
        import RPi.GPIO as GPIO
        CONVAI_MAX_DURATION = 120  # 5 minutes max per session
        session_start = time.time()
        while conv_engine.is_active():
            hook_val = GPIO.input(22)  # 1 = on hook, 0 = off hook
            if hook_val == 1:
                print("   (ConvAI: Hook-down detected via direct GPIO)")
                break
            if time.time() - session_start > CONVAI_MAX_DURATION:
                print("   (ConvAI: Max session duration reached, ending)")
                break
            time.sleep(0.2)

        conv_engine.end_session()
        return True

    except Exception as e:
        print(f"❌ ConvAI session failed: {e}")
        return False

def _pick_discover_decade():
    """Pick a random decade weighted by user discovery history."""
    all_decades = [1900, 1910, 1920, 1930, 1940, 1950, 1960, 1970, 1980, 1990, 2000, 2010, 2020]
    if not prefs:
        return random.choice(all_decades)

    history = prefs.get("discover_history") or []
    # Build weights: un-tried decades get weight 3, liked get 2, disliked get 0.5
    tried = {h["decade"]: h["liked"] for h in history}
    weights = []
    for d in all_decades:
        if d not in tried:
            weights.append(3.0)  # Never tried — high weight
        elif tried[d]:
            weights.append(2.0)  # Liked — medium weight
        else:
            weights.append(0.5)  # Disliked — low weight

    return random.choices(all_decades, weights=weights, k=1)[0]

def on_dial_complete(number):
    global current_language, current_year
    print(f"\n🔢 DIALED: {number}")
    
    # Stop Dial Tone if it's playing
    audio.stop_audio()
    
    # --- LANGUAGE TOGGLE (9) ---
    if number == 9:
        op_voice = DECADE_VOICES["OPERATOR"]
        if current_language == "EN":
            current_language = "CZ"
            audio.speak("Switching to Czech Mode.", voice_id=op_voice['id'], voice_settings=op_voice['settings'], model_id=op_voice['model'])
        else:
            current_language = "EN"
            audio.speak("Přepínám do angličtiny.", voice_id=op_voice['id'], voice_settings=op_voice['settings'], model_id=op_voice['model'])
        print(f"   >>> LANGUAGE SET TO: {current_language}")
        if prefs:
            prefs.set("language", current_language)
        return

    # --- DISCOVER MODE (99) ---
    if number == 99 and FEATURE_FLAGS.get("discover_mode"):
        print("🎲 DISCOVER MODE!")
        decade = _pick_discover_decade()
        target_year = decade
        current_year = target_year
        led.set_decade(target_year)
        led.rainbow_sweep(duration=2.0)

        voice_data = brain.get_voice_for_year(target_year)
        dj_name = brain.get_dj_name(target_year, current_language)

        # Use ConvAI if available
        if _use_conversational_ai():
            audio.play_sound("click")
            _run_conversational_session(target_year, current_language)
        else:
            intro = f"Surprise! You've landed in the {target_year}s with {dj_name}! Let's see what we've got..."
            audio.speak(intro, voice_id=voice_data['id'], voice_settings=voice_data['settings'], model_id=voice_data['model'], year=target_year)

        # Start music for this decade
        decade_key = int(str(target_year)[:3] + "0")
        playlists = DECADE_PLAYLISTS.get(decade_key)
        if playlists:
            uri = playlists.get(current_language, playlists["EN"])
            if uri.startswith("search:"):
                music.search_and_play(uri.replace("search:", "").strip(), type='playlist')
            else:
                music.play_playlist(uri)

        # Save to discover history (assume liked unless they hang up fast)
        if prefs:
            history = prefs.get("discover_history") or []
            history.append({"decade": decade, "liked": True})
            prefs.set("discover_history", history[-50:])  # Keep last 50

        if show and FEATURE_FLAGS.get("show_mode"):
            if show.is_active:
                show.end_show()
            show.start_show(target_year, current_language)
        return

    # --- SECRET MODE: TIMER (666) ---
    if number == 666:
        print("😈 TIMER MODE ACTIVATED")
        handle_timer_mode()
        return

    # --- OPERATOR (0) ---
    if number == 0:
        print("   >>> CONNECTING TO OPERATOR...")
        music.pause()
        audio.play_sound("click", block=True)

        # Try ConvAI (Phase 11) — Operator gets special modern instructions
        if _use_conversational_ai():
            print("   (Using ElevenLabs ConvAI for Operator)")
            try:
                # Pick a random voice personality for the Operator
                random_voice = brain.pick_random_operator_voice()
                op_instructions = brain.build_operator_instructions(
                    current_language, voice_style=random_voice["style"])
                audio.stop_audio()
                time.sleep(0.5)
                if conv_engine.start_session(None, current_language, random_voice['id'], op_instructions):
                    led.on_air_flash()
                    # Poll hook directly + timeout to prevent runaway billing
                    import RPi.GPIO as GPIO
                    CONVAI_MAX_DURATION = 120  # 5 min max
                    session_start = time.time()
                    while conv_engine.is_active():
                        hook_val = GPIO.input(22)
                        if hook_val == 1:
                            print("   (ConvAI: Hook-down detected via direct GPIO)")
                            break
                        if time.time() - session_start > CONVAI_MAX_DURATION:
                            print("   (ConvAI: Max session duration reached)")
                            break
                        time.sleep(0.2)
                    conv_engine.end_session()
                    return
            except Exception as e:
                print(f"   (ConvAI Operator failed: {e})")
            print("   (ConvAI failed, falling back to legacy)")

        op_voice = DECADE_VOICES["OPERATOR"]
        intro_text = "Operator here. How may I help?" if current_language == "EN" else "Tady centrála. Jak vám mohu pomoci?"
        audio.speak(intro_text, voice_id=op_voice['id'], voice_settings=op_voice['settings'], model_id=op_voice['model'])

        while True: # Legacy Interaction Loop
            # HANGUP CHECK
            if phone and not phone.is_off_hook:
                 print("   (Operator: Hung up)")
                 break

            query = audio.listen(duration=8)
            
            # HANGUP CHECK (Post-listen)
            if phone and not phone.is_off_hook:
                 print("   (Operator: Hung up)")
                 break

            if query:
                print(f"   User asked: {query}")

                # SINGLE GPT CALL: Classify intent + extract query + DJ confirmation
                search_query, search_type, confirm_txt = brain.classify_and_extract(query, 1950, current_language)
                print(f"   🧠 Result: {search_type} | {search_query}")

                if search_type == "CHAT":
                    # Not a music request — answer as Operator
                    response = brain.ask_operator(query, language=current_language)
                    audio.speak(response, voice_id=op_voice['id'], voice_settings=op_voice['settings'], model_id=op_voice['model'])
                elif search_type == "DEFAULT" or not search_query:
                    # Generic request — no specific search
                    pass
                else:
                    # MUSIC REQUEST
                    print("   (Operator: Music request detected...)")

                    # 1. SPEAK CONFIRMATION (already generated)
                    if confirm_txt:
                        try:
                            audio.speak(confirm_txt, voice_id=op_voice['id'], voice_settings=op_voice['settings'], model_id=op_voice['model'])
                        except Exception as e: print(f"   (Confirm error: {e})")

                    # 2. CORRECTION WINDOW
                    correction = audio.listen(duration=2.5)
                    if correction and len(correction) > 2:
                        negatives = ["no", "stop", "wait", "wrong", "ne", "špatně"]
                        if any(w in correction.lower() for w in negatives):
                            apology = "Apologies. Who did you want?" if current_language == "EN" else "Omlouvám se. Koho?"
                            audio.speak(apology, voice_id=op_voice['id'], voice_settings=op_voice['settings'], model_id=op_voice['model'])
                            new_q = audio.listen(duration=5)
                            if new_q:
                                search_query, search_type, confirm_txt = brain.classify_and_extract(new_q, 1950, current_language)
                                if confirm_txt:
                                    audio.speak(confirm_txt, voice_id=op_voice['id'], voice_settings=op_voice['settings'], model_id=op_voice['model'])

                    # 3. EXECUTE PLAY
                    print(f"   (Operator Search: {search_query} | Type: {search_type})")
                    type_map = {"TRACK": "track", "ALBUM": "album", "ARTIST": "artist"}
                    music.search_and_play(search_query, type=type_map.get(search_type, "playlist"))
                    return # Exit Operator
            else:
                 audio.speak("I didn't hear anything. Disconnecting." if current_language == "EN" else "Nemohu vás momentálně spojit.",
                             voice_id=op_voice['id'], voice_settings=op_voice['settings'], model_id=op_voice['model'])
                 break
        return

    # --- TIME TRAVEL (Handle both single digit decade and 4 digit year) --
    target_year = None
    direct_play = False

    if 1 <= number <= 8:
        # User dialed decade shortcut (1-8) -> Direct Play
        target_year = 1900 + (number * 10)
        direct_play = True
    elif 1900 <= number <= 2030:
        # User dialed exact year
        target_year = number
    elif 100 <= number < 1900:
        # Classical era — anything before 1900
        print(f"   >>> CLASSICAL ERA ({number})")
        current_year = number
        led.set_decade(1900)

        if _use_conversational_ai():
            audio.play_sound("click", block=True)
            cp = CLASSICAL_PERSONA
            dj_name = cp["dj_name"].get(current_language, "Maestro")
            instr = brain.build_realtime_instructions(1900, current_language)
            # Override with classical context
            instr = f"""You are {dj_name}, the host of {cp['station']} in {cp['city']}.
{cp['world']}
Your catchphrase: "{cp['catchphrase']}"
Style: {cp['style_en' if current_language == 'EN' else 'style_cz']}
{cp['forbidden']}
The caller dialed year {number}. Talk about music and life around that time.
TOOLS: Use play_music to find classical music, use play_era_playlist for a classical playlist.
Keep responses SHORT (1-2 sentences). Language: {'English' if current_language == 'EN' else 'Czech'}."""

            audio.stop_audio()
            time.sleep(0.5)
            if conv_engine.start_session(number, current_language, CLASSICAL_VOICE['id'], instr):
                led.on_air_flash()
                import RPi.GPIO as GPIO
                CONVAI_MAX_DURATION = 120
                session_start = time.time()
                while conv_engine.is_active():
                    if GPIO.input(22) == 1:
                        print("   (ConvAI: Hook-down detected)")
                        break
                    if time.time() - session_start > CONVAI_MAX_DURATION:
                        break
                    time.sleep(0.2)
                conv_engine.end_session()

        # Play classical playlist
        uri = CLASSICAL_PLAYLISTS.get(current_language, CLASSICAL_PLAYLISTS["EN"])
        music.play_playlist(uri)
        return

    if target_year:
        print(f"   >>> TRAVELING TO {target_year}s ({current_language})...")

        # Cross-decade handoff: previous DJ says goodbye
        if current_year and current_year != target_year and not direct_play:
            try:
                handoff = brain.generate_handoff(current_year, target_year, current_language)
                if handoff:
                    old_voice = brain.get_voice_for_year(current_year)
                    audio.speak(handoff, voice_id=old_voice['id'], voice_settings=old_voice['settings'],
                               model_id=old_voice['model'], year=current_year)
            except Exception as e:
                print(f"   (Handoff error: {e})")

        current_year = target_year
        if prefs:
            prefs.set("last_decade", int(str(target_year)[:3] + "0"))
        led.set_decade(target_year)
        
        # Pause Music (Only if NOT direct play, to avoid race condition)
        if not direct_play:
            print("   (Stopping current music [Async]...)")
            def pause_worker():
                try:
                    music.pause()
                except Exception as e:
                    print(f"   (Async pause error: {e})")
            threading.Thread(target=pause_worker, daemon=True).start()

        start_music = False # Default
        music_search_query = None
        music_search_type = "DEFAULT"
        music_confirm_txt = None
        voice_data = brain.get_voice_for_year(target_year)  # Always needed for fallback messages

        if not direct_play:
            # Try Realtime API first (Phase 5)
            if _use_conversational_ai():
                print(f"   (Using ElevenLabs ConvAI for {target_year})")
                audio.play_sound("click")
                if _run_conversational_session(target_year, current_language):
                    return
                print("   (ConvAI failed, falling back to legacy)")

            # --- LEGACY: FULL EXPERIENCE (HOST + CHAT) ---
            print(f"   (Voice selected for {target_year})")
            
            # Play era jingle + static while generating intro
            print("   (Playing Time Travel Transition...)")
            stop_static = threading.Event()
            decade_key = int(str(target_year)[:3] + "0")

            def play_transition_loop():
                # Play jingle first, then loop static until event is set
                jingle_name = f"jingle_{decade_key}"
                audio.play_sound(jingle_name, block=True, year=target_year)
                while not stop_static.is_set():
                    audio.play_sound("static_long", block=True, year=target_year)

            static_thread = threading.Thread(target=play_transition_loop, daemon=True)
            static_thread.start()

            # Host Intro (Latency here — jingle covers it)
            print("   (Generating Host Intro...)")
            intro = brain.get_host_intro(target_year, language=current_language)

            # Stop transition & Speak
            stop_static.set()
            audio.stop_audio()
            time.sleep(0.5)
            
            print(f"   HOST SAYS: {intro}")
            audio.speak(intro, voice_id=voice_data['id'], voice_settings=voice_data['settings'], model_id=voice_data['model'], year=target_year)
            
            # Interactive Conversation Loop
            in_chat_mode = True
            music_query = None
            last_host_response = intro # Keep track of context

            while in_chat_mode:
                # HANGUP CHECK
                if phone and not phone.is_off_hook:
                    print("   (Host: Hung up)")
                    break

                # Listen for user input
                cmd = audio.listen(duration=8) 
                
                # HANGUP CHECK (Post-listen)
                if phone and not phone.is_off_hook:
                    print("   (Host: Hung up)")
                    break

                if not cmd:
                    # Silence -> Assume user wants music now
                    print("   (Silence detected. Starting music...)")
                    start_music = True
                    break
                    
                print(f"   User said: {cmd}")

                # SINGLE GPT CALL: Classify + extract in one shot
                search_query, search_type, confirm_txt = brain.classify_and_extract(cmd, target_year, current_language)
                print(f"   🧠 Result: {search_type} | {search_query}")

                if search_type == "CHAT":
                    # Chat question — talk to host
                    print("   (Chatting with Host...)")
                    response = brain.chat_with_host(cmd, target_year, language=current_language)
                    last_host_response = response
                    audio.speak(response, voice_id=voice_data['id'], voice_settings=voice_data['settings'], model_id=voice_data['model'], year=target_year)
                    # Loop continues...
                else:
                    # Music request (specific, default, or generic)
                    print("   (Music request detected. Exiting chat...)")
                    music_query = cmd
                    # Pass pre-extracted results forward
                    music_search_query = search_query
                    music_search_type = search_type
                    music_confirm_txt = confirm_txt
                    start_music = True
                    break
        else:
            # --- DIRECT PLAY (SHORTCUT) ---
            print(f"   (Direct Play: Skipping Host for {target_year}s)")
            start_music = True
            music_query = None

            # Optional: Play short static even for shortcuts?
            # audio.play_sound("static_short") 

        if start_music:
            music_started = False

            # Use pre-extracted results from classify_and_extract
            search_query = music_search_query
            search_type = music_search_type
            confirm_txt = music_confirm_txt

            # 1. Smart Search (if specific request with pre-extracted query)
            if search_query and search_type not in ("DEFAULT", "CHAT"):
                print(f"   (Specific Request: '{search_query}' | Type: {search_type})")

                # A. SPEAK CONFIRMATION (already generated by classify_and_extract)
                if confirm_txt:
                    try:
                        print(f"   HOST CONFIRMS: {confirm_txt}")
                        audio.speak(confirm_txt, voice_id=voice_data['id'], voice_settings=voice_data['settings'], model_id=voice_data['model'], year=target_year)
                    except Exception as e:
                        print(f"   Confirmation Error: {e}")

                # B. CORRECTION WINDOW
                correction = audio.listen(duration=2.5)

                if correction and len(correction) > 2:
                    negatives = ["no", "stop", "wait", "wrong", "not that", "change", "ne", "špatně", "počkej"]
                    if any(w in correction.lower() for w in negatives):
                        print(f"   (Correction Detected: '{correction}')")
                        apology = "Apologies. Who did you want to hear?" if current_language == "EN" else "Omlouvám se. Koho chcete slyšet?"

                        try:
                            audio.speak(apology, voice_id=voice_data['id'], voice_settings=voice_data['settings'], model_id=voice_data['model'], year=target_year)
                        except Exception as e: print(f"   (Apology error: {e})")

                        new_query = audio.listen(duration=5)
                        if new_query:
                            print(f"   (New Query: '{new_query}')")
                            search_query, search_type, confirm_txt = brain.classify_and_extract(new_query, target_year, current_language)
                            if confirm_txt:
                                try:
                                    audio.speak(confirm_txt, voice_id=voice_data['id'], voice_settings=voice_data['settings'], model_id=voice_data['model'], year=target_year)
                                except Exception as e: print(f"   (Confirm error: {e})")

                # C. EXECUTE PLAY
                if search_query:
                    print(f"   (Smart Search: {search_query} | Type: {search_type})")
                    type_map = {"TRACK": "track", "ALBUM": "album", "ARTIST": "artist", "PLAYLIST": "playlist"}
                    sp_type = type_map.get(search_type, "playlist")
                    if music.search_and_play(search_query, type=sp_type):
                        music_started = True
                    elif sp_type != "playlist" and music.search_and_play(search_query, type='playlist'):
                        music_started = True

                    if not music_started:
                        print("   (Specific Search Failed.)")
                        fail_txt = "I couldn't find that specific record, so here is the radio instead."
                        if current_language == "CZ": fail_txt = "Tu skladbu nemohu najít, ale pustím vám rádio."
                        try:
                            audio.speak(fail_txt, voice_id=voice_data['id'], voice_settings=voice_data['settings'], model_id=voice_data['model'], year=target_year)
                        except Exception as e: print(f"   (Fail msg error: {e})")

            elif search_type == "DEFAULT":
                print("   (Generic Request -> Playing Default Era Playlist)")
                confirm_txt = "Coming right up!" if current_language == "EN" else "Už to hraje!"
                audio.speak(confirm_txt, voice_id=voice_data['id'], voice_settings=voice_data['settings'], model_id=voice_data['model'], year=target_year)

            # 2. Fallback to Era Playlist
            if not music_started:
                decade_key = int(str(target_year)[:3] + "0")
                playlists = DECADE_PLAYLISTS.get(decade_key)
                
                if playlists:
                    uri = playlists.get(current_language, playlists["EN"])
                    print(f"   >>> PLAYING DEFAULT ERA PLAYLIST: {uri}")
                    
                    if uri.startswith("search:"):
                        query = uri.replace("search:", "").strip()
                        music.search_and_play(query, type='playlist')
                    else:
                        music.play_playlist(uri)
                else:
                    # Phonograph fallback for pre-1930s decades
                    if decade_key <= 1920 and FEATURE_FLAGS.get("phonograph_mode"):
                        print(f"   (Trying phonograph mode for {decade_key}s...)")
                        if not music.play_local_phonograph(decade_key):
                            print(f"   (No phonograph recordings found for {decade_key}s)")
                    else:
                        print(f"   (No playlist found for {decade_key}s)")

            # Start show mode after music begins playing
            if show and FEATURE_FLAGS.get("show_mode"):
                if show.is_active:
                    show.end_show()
                show.start_show(target_year, current_language)

        return


# =========================================
# TIMER MODE (666)
# =========================================
def handle_timer_mode():
    """
    Operator asks for duration, sets a background timer to ring the bell.
    """
    op_voice = DECADE_VOICES["OPERATOR"]
    
    # 1. Intro
    # audio.SPEAK_lock.acquire() # Locked internally by speak now? No, but let's be safe or just call speak. 
    # Actually speak() handles locking usually.
    audio.speak("Timer mode. How long should I set it for?", voice_id=op_voice['id'], voice_settings=op_voice['settings'], model_id=op_voice['model'])
    
    # 2. Listen
    user_text = audio.listen(duration=5)
    
    if not user_text:
        audio.speak("I didn't hear a duration. Timer cancelled.", voice_id=op_voice['id'], voice_settings=op_voice['settings'], model_id=op_voice['model'])
        return

    # 3. Parse
    seconds = brain.extract_timer_duration(user_text)
    
    if seconds:
        print(f"⏰ Setting Timer: {seconds}s")
        audio.speak(f"Setting timer for {seconds} seconds.", voice_id=op_voice['id'], voice_settings=op_voice['settings'], model_id=op_voice['model'])
        
        # 4. Start Thread
        def timer_callback():
            print(f"⏰ TIMER EXPIRED ({seconds}s)")
            phone.ring_bell(duration=2.0)
        
        t = threading.Timer(seconds, timer_callback)
        t.daemon = True # Ensure it dies if app dies
        t.start()
        
    else:
        audio.speak("I couldn't understand the time. Please try again.", voice_id=op_voice['id'], voice_settings=op_voice['settings'], model_id=op_voice['model'])

def main():
    print("========================================")
    print("      TIME TRAVEL RADIO - v3.0")
    print("========================================")

    # --- HARDWARE SETUP ---
    global phone
    phone = PhoneInterface(
        on_hook_change=on_hook_change,
        on_dial_complete=on_dial_complete
    )
    phone.start_interface()

    # --- INITIALIZE SHOW ENGINE ---
    global show
    show = ShowEngine(brain, audio, music, phone)

    # --- INITIALIZE CONVERSATIONAL AI ENGINE ---
    global conv_engine
    if FEATURE_FLAGS.get("conversational_ai"):
        conv_engine = ConversationalEngine(music_engine=music, world_context=world)
        print(f"🎙️ ConvAI: {'Available' if conv_engine.is_available() else 'Not available (missing deps)'}")

    # --- PRE-START SPOTIFY PLAYER ---
    print("Starting Spotify player...")
    # Always start our own librespot first — don't use MacBook/phone as fallback
    music.start_embedded_player()
    music.find_device(force_refresh=True, strict_retro=True)

    # --- START PLAYBACK MONITOR ---
    music.start_monitor()

    # --- LED STARTUP EFFECT ---
    led.rainbow_sweep(duration=2.0)

    print("SYSTEM READY. Lift handset to begin.")

    # --- MAIN LOOP ---
    try:
        while True:
            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\nStopping...")
        if conv_engine and conv_engine.is_active():
            conv_engine.end_session()
        if show and show.is_active:
            show.end_show()
        music.stop_monitor()
        phone.cleanup()
        music.stop()
        led.off()
        led.cleanup()

if __name__ == "__main__":
    main()
