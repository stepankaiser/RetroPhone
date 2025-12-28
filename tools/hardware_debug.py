import RPi.GPIO as GPIO
import time
import sys

# Constants
HOOK_PIN = 22
DIAL_PIN = 27

def main():
    GPIO.setmode(GPIO.BCM)
    # Enable Pull-Up (Input floats high, switch connects to Ground)
    GPIO.setup(HOOK_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(DIAL_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    print("========================================")
    print("      RETRO PHONE HARDWARE DEBUGPER     ")
    print("========================================")
    print(f"Monitoring HOOK (Pin {HOOK_PIN}) and DIAL (Pin {DIAL_PIN})")
    print("Values: 0 = Low (Grounded/Closed), 1 = High (Open)")
    print("----------------------------------------")
    print("Press CTRL+C to stop.")
    
    last_hook = -1
    last_dial = -1
    
    try:
        while True:
            hook_val = GPIO.input(HOOK_PIN)
            dial_val = GPIO.input(DIAL_PIN)
            
            # Print state slightly differently to visualize noise
            state_str = f"In-Call: {'YES' if hook_val == 0 else 'NO '} (Pin={hook_val}) | Dial Pulse: {dial_val}"
            
            # Smart Print: Only if changed? No, user wants to see noise.
            # But let's limit speed to readable
            sys.stdout.write(f"\r{state_str}   ")
            sys.stdout.flush()
            
            time.sleep(0.05)
            
    except KeyboardInterrupt:
        print("\nStopping...")
        GPIO.cleanup()

if __name__ == "__main__":
    main()
