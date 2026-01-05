import time
import sys
import threading
from src.phone_interface import PhoneInterface
from src.audio_engine import AudioEngine
from src.music_engine import MusicEngine
from src.brain import Brain
from src.config import DECADE_PLAYLISTS, DECADE_VOICES

# System State
current_language = "EN" # EN or CZ
current_year = None
phone = None # Global reference for hangup checks

# Initialize Modules
print("Initializing Audio Engine...")
audio = AudioEngine()
print("Initializing Brain...")
brain = Brain()
print("Initializing Music Engine...")
music = MusicEngine()

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

        # Always Play Dial Tone
        audio.play_sound("dial_tone", block=False)
    else:
        print("\n📞 HANDSET REPLACED")
        # Stop Handset Audio (Host/DialTone), but KEEP MUSIC PLAYING (Radio Mode)
        print("   (Silencing handset...)")
        audio.stop_audio()
        # music.pause() # DISABLED for Continuous Playback

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
        
        audio.play_sound("dial_tone")
        time.sleep(1)
        audio.play_sound("click")
        
        op_voice = DECADE_VOICES["OPERATOR"]
        intro_text = "Operator here. How may I help?" if current_language == "EN" else "Tady centrála. Jak vám mohu pomoci?"
        audio.speak(intro_text, voice_id=op_voice['id'], voice_settings=op_voice['settings'], model_id=op_voice['model'])
        
        while True: # Interaction Loop
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
                
                # INTENT CHECK (Added for Music Support)
                intent = brain.classify_intent(query)
                print(f"   🧠 Intent Classified: {intent}")
                
                if intent == "MUSIC":
                    print("   (Operator: Music request detected...)")
                    # Operator confirms
                    confirm_txt = "Connecting you to that station now." if current_language == "EN" else "Přepojuji vás."
                    audio.speak(confirm_txt, voice_id=op_voice['id'], voice_settings=op_voice['settings'], model_id=op_voice['model'])
                    
                    # Execute Search
                    search_query, search_type = brain.get_music_search_query(query, 1950, current_language) # Default to 1950s context for Operator
                    if search_query:
                        print(f"   (Operator Search: {search_query} | Type: {search_type})")
                        music.search_and_play(search_query, type=search_type.lower() if search_type != "DEFAULT" else 'playlist')
                        return # Exit Operator
                
                response = brain.ask_operator(query, language=current_language)
                audio.speak(response, voice_id=op_voice['id'], voice_settings=op_voice['settings'], model_id=op_voice['model'])
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
    
    if target_year:
        print(f"   >>> TRAVELING TO {target_year}s ({current_language})...")
        current_year = target_year
        
        # Pause Music (Only if NOT direct play, to avoid race condition)
        if not direct_play:
            print("   (Stopping current music [Async]...)")
            def pause_worker():
                try:
                    music.pause()
                except:
                    pass
            threading.Thread(target=pause_worker, daemon=True).start()

        start_music = False # Default

        if not direct_play:
            # ... (Rest of Host Logic) ...
            # --- FULL EXPERIENCE (HOST + CHAT) ---

            # Get Voice Data (Dict)
            print(f"   (Selecting Voice for {target_year}...)")
            voice_data = brain.get_voice_for_year(target_year)
            
            # Static (Threaded to cover latency)
            print("   (Playing Time Travel Static...)")
            stop_static = threading.Event()
            
            def play_static_loop():
                # Loop static until event is set
                while not stop_static.is_set():
                    audio.play_sound("static_long", block=True)
            
            # Start static in background
            static_thread = threading.Thread(target=play_static_loop, daemon=True)
            static_thread.start()
            
            # Host Intro (Latency here)
            print("   (Generating Host Intro...)")
            intro = brain.get_host_intro(target_year, language=current_language)
            
            # Stop Static & Speak
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
                
                # Check intent with AI (Semantic Understanding)
                intent = brain.classify_intent(cmd)
                print(f"   🧠 Intent Classified: {intent}")
                
                if intent == "MUSIC":
                    print("   (Music request detected. Exiting chat...)")
                    
                    # DIRECT SEARCH (Smart Brain handles context now)
                    print("   (Passing request to Smart Brain...)")
                    music_query = cmd
                        
                    start_music = True
                    break
                
                # Otherwise, treat as a chat question
                print("   (Chatting with Host...)")
                response = brain.chat_with_host(cmd, target_year, language=current_language)
                last_host_response = response
                audio.speak(response, voice_id=voice_data['id'], voice_settings=voice_data['settings'], model_id=voice_data['model'], year=target_year)
                # Loop continues...
        else:
            # --- DIRECT PLAY (SHORTCUT) ---
            print(f"   (Direct Play: Skipping Host for {target_year}s)")
            start_music = True
            music_query = None

            # Optional: Play short static even for shortcuts?
            # audio.play_sound("static_short") 

        if start_music:
            music_started = False
            
            # 1. Smart Search (if specific request)
            if music_query and len(music_query) > 10:
                print(f"   (Detected Specific Request: '{music_query}')")
                
                # CONFIRMATION: Host acknowledges the request
                confirm_txt = brain.get_dj_confirmation(target_year, music_query, current_language)
                try:
                    print(f"   HOST CONFIRMS: {confirm_txt}")
                    audio.speak(confirm_txt, voice_id=voice_data['id'], voice_settings=voice_data['settings'], model_id=voice_data['model'], year=target_year)
                except Exception as e:
                    print(f"   Confirmation Error: {e}")

                search_query, search_type = brain.get_music_search_query(music_query, target_year, current_language)
                
                if search_query:
                     print(f"   (Smart Search: {search_query} | Type: {search_type})")
                     
                     # Prioritize based on AI Classification
                     if search_type == "TRACK":
                         if music.search_and_play(search_query, type='track'):
                             music_started = True
                         elif music.search_and_play(search_query, type='playlist'):
                             music_started = True
                     elif search_type == "ALBUM":
                         if music.search_and_play(search_query, type='album'):
                             music_started = True
                         elif music.search_and_play(search_query, type='playlist'):
                             music_started = True
                     elif search_type == "ARTIST":
                         if music.search_and_play(search_query, type='artist'):
                             music_started = True
                         elif music.search_and_play(search_query, type='playlist'):
                             music_started = True
                     elif search_type == "PLAYLIST":
                         # Default/Playlist priority
                         if music.search_and_play(search_query, type='playlist'):
                             music_started = True
                         elif music.search_and_play(search_query, type='track'):
                             music_started = True
                     
                     if not music_started:
                         print("   (Specific Search Failed.)")
                         fail_txt = "I couldn't find that specific record, so here is the radio instead."
                         if current_language == "CZ": fail_txt = "Tu skladbu nemohu najít, ale pustím vám rádio."
                         
                         try:
                             audio.speak(fail_txt, voice_id=voice_data['id'], voice_settings=voice_data['settings'], model_id=voice_data['model'], year=target_year)
                         except:
                             pass
                elif search_type == "DEFAULT":
                     print("   (Generic Request -> Playing Default Era Playlist)")
                     # Host confirms generic request
                     confirm_txt = "Coming right up!" if current_language == "EN" else "Už to hraje!"
                     audio.speak(confirm_txt, voice_id=voice_data['id'], voice_settings=voice_data['settings'], model_id=voice_data['model'], year=target_year)
                     # music_started remains False, so it falls through to Era Playlist

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
                    print(f"   (No playlist found for {decade_key}s)")
        
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
    print("      TIME TRAVEL RADIO - v1.0")
    print("========================================")
    
    # --- HARDWARE SETUP ---
    global phone
    phone = PhoneInterface(
        on_hook_change=on_hook_change,
        on_dial_complete=on_dial_complete
    )
    # Start the GPIO polling thread
    phone.start_interface()

    print("SYSTEM READY. Lift handset to begin.")
    
    # --- MAIN LOOP ---
    try:
        while True:
            # check_dial and check_hook are now in the thread!
            
            # Keep main thread alive and responsive to KeyboardInterrupt
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\nStopping...")
        phone.cleanup()
        music.stop()
        GPIO.cleanup()

if __name__ == "__main__":
    main()
