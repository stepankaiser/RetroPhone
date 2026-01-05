import RPi.GPIO as GPIO
import time
import threading
from .config import HOOK_PIN, DIAL_PIN, BELL_PINS, BELL_SPEED

class PhoneInterface(threading.Thread):
    def __init__(self, on_hook_change=None, on_dial_complete=None):
        super().__init__()
        self.on_hook_change = on_hook_change
        self.on_dial_complete = on_dial_complete
        
        # Daemon thread to ensure it dies with main program
        self.daemon = True

        # Setup GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(HOOK_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(DIAL_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        
        # Setup Bell (L298N)
        GPIO.setup(BELL_PINS, GPIO.OUT)
        GPIO.output(BELL_PINS, GPIO.LOW)

        # State
        self.last_hook_state = GPIO.input(HOOK_PIN)
        self.is_off_hook = (self.last_hook_state == 0) # Public State

        self.pulse_count = 0
        self.last_pulse_time = 0
        self.dialing_active = False
        self.running = True
        
        # Debounce / Ghost Pulse filtering
        self.off_hook_time = 0
        
        # Buffering State
        self.digit_buffer = []
        self.last_digit_time = 0
        self.digit_timeout = 2.5 

    def run(self):
        print("   (Phone Interface Thread Started: Debounced)")
        
        # Initial State
        self.last_hook_state = GPIO.input(HOOK_PIN)
        self.last_dial_val = GPIO.input(DIAL_PIN)
        
        # Hook Debounce State
        self.hook_stable_start_time = 0
        self.pending_hook_state = self.last_hook_state
        
        # Pulse Counting
        self.pulse_count = 0
        self.last_pulse_time = 0
        # Sync local with public
        self.is_off_hook = (self.last_hook_state == 0)
        
        # Lockout
        self.off_hook_time = 0
        if self.is_off_hook: self.off_hook_time = time.time()
        
        while self.running:
            now = time.time()
            
            # --- 1. HOOK DEBOUNCE (Pin 22) ---
            current_hook = GPIO.input(HOOK_PIN)
            
            if current_hook != self.pending_hook_state:
                # State changed relative to pending? Reset timer.
                self.pending_hook_state = current_hook
                self.hook_stable_start_time = now
            else:
                # State is consistent with pending. Check duration.
                if (now - self.hook_stable_start_time) > 0.2: # 200ms stable
                    if current_hook != self.last_hook_state:
                         # CONFIRMED CHANGE
                         self.last_hook_state = current_hook
                         self.is_off_hook = (current_hook == 0) # 0 = Lifted
                         
                         print(f"   (DEBUG: Hook={current_hook} -> OffHook={self.is_off_hook})")
                         
                         if self.is_off_hook:
                             self.off_hook_time = now
                             # print("\n📞 HANDSET LIFTED") # Handled by main.py
                             if self.on_hook_change: self.on_hook_change(True)
                         else:
                             self.off_hook_time = 0
                             # print("\n📞 HANDSET REPLACED") # Handled by main.py
                             # FLUSH BUFFER ON HANGUP (Submit whatever we have)
                             self._check_buffer_timeout(force=True)
                             
                             if self.on_hook_change: self.on_hook_change(False)
                             self.digit_buffer = []
                             self.pulse_count = 0

            # --- 2. DIAL DETECTION (Pin 27) ---
            if self.is_off_hook:
                # Ghost Lockout (0.8s is enough with good debounce)
                if (now - self.off_hook_time) < 0.8:
                    self.pulse_count = 0
                else:
                    current_dial = GPIO.input(DIAL_PIN)
                    
                    # RISING EDGE (0 -> 1)
                    if current_dial == 1 and self.last_dial_val == 0:
                        # Debounce (25ms)
                        if (now - self.last_pulse_time) > 0.025:
                            self.pulse_count += 1
                            self.last_pulse_time = now
                            # print(f"      (Rise! {self.pulse_count})") # UNCOMMENTED
                    
                    self.last_dial_val = current_dial
                    
                    # Timeout (End of Digit) -> 0.7s
                    if self.pulse_count > 0 and (now - self.last_pulse_time) > 0.7:
                         final_number = self.pulse_count
                         if final_number == 10: final_number = 0
                         
                         print(f"   (Digit Buffered: {final_number})")
                         self.digit_buffer.append(final_number)
                         self.pulse_count = 0
                         self.last_digit_time = now

            # --- 3. BUFFER ---
            self._check_buffer_timeout()
            
            time.sleep(0.001)

    def start_interface(self):
        self.start()

    def _check_buffer_timeout(self, force=False):
        if not self.digit_buffer:
            return

        time_since_digit = time.time() - self.last_digit_time
        
        should_flush = False
        if force:
            should_flush = True
        elif len(self.digit_buffer) >= 4:
            should_flush = True 
        elif time_since_digit > 4.0: 
            should_flush = True 
            
        if should_flush:
            full_number = 0
            for digit in self.digit_buffer:
                full_number = full_number * 10 + digit
            
            if self.on_dial_complete:
                self.on_dial_complete(full_number)
            
            self.digit_buffer = []

    # Legacy Stubs
    def _check_hook(self): pass
    def _check_dial(self): pass

    def ring_bell(self, duration=3.0):
        """
        Rings the mechanical bell for the specified duration (blocking).
        Run this in a separate thread if you don't want to freeze the app.
        """
        print(f"🔔 RINGING BELL for {duration}s...")
        end_time = time.time() + duration
        
        try:
            while time.time() < end_time and self.running:
                # Hammer Strike
                GPIO.output(BELL_PINS[0], GPIO.HIGH)
                GPIO.output(BELL_PINS[1], GPIO.LOW)
                time.sleep(BELL_SPEED)
                
                # Hammer Return
                GPIO.output(BELL_PINS[0], GPIO.LOW)
                GPIO.output(BELL_PINS[1], GPIO.HIGH)
                time.sleep(BELL_SPEED)
        except Exception as e:
            print(f"❌ Bell Error: {e}")
        finally:
            # Silence
            GPIO.output(BELL_PINS, GPIO.LOW)
            print("🔕 Bell Silence")

    def cleanup(self):
        self.running = False
        GPIO.cleanup()
