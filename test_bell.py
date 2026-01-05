import RPi.GPIO as GPIO
import time

# --- KONFIGURACE ---
# Piny, které vedou do IN1 a IN2 na červeném modulu
IN1_PIN = 23
IN2_PIN = 24

# Rychlost kmitání (v sekundách). 
# Pokud zvonek jen "bzučí", zvyšte číslo (např. 0.04).
# Pokud je moc pomalý, snižte číslo (např. 0.025).
SPEED = 0.1  # ZVÝŠENO z 0.03 pro test

# --- NASTAVENÍ ---
GPIO.setmode(GPIO.BCM)
GPIO.setup(IN1_PIN, GPIO.OUT)
GPIO.setup(IN2_PIN, GPIO.OUT)

# Ujistit se, že je na začátku ticho
GPIO.output(IN1_PIN, GPIO.LOW)
GPIO.output(IN2_PIN, GPIO.LOW)

def ring_bell(duration=2):
    print(f"🔔 Zvoním po dobu {duration} sekund...")
    end_time = time.time() + duration
    
    try:
        while time.time() < end_time:
            # ÚDER TAM (Polarita + / -)
            GPIO.output(IN1_PIN, GPIO.HIGH)
            GPIO.output(IN2_PIN, GPIO.LOW)
            time.sleep(SPEED)
            
            # ÚDER ZPĚT (Polarita - / +)
            GPIO.output(IN1_PIN, GPIO.LOW)
            GPIO.output(IN2_PIN, GPIO.HIGH)
            time.sleep(SPEED)

    finally:
        # Vždy vypnout proud po zazvonění! (Aby se cívky nehřály)
        GPIO.output(IN1_PIN, GPIO.LOW)
        GPIO.output(IN2_PIN, GPIO.LOW)
        print("🔕 Ticho.")

# --- HLAVNÍ SMYČKA ---
print("--- TEST ZVONKU ---")
print("Ujistěte se, že máte zapnuté napájení (Step-Up).")
print("Stiskněte ENTER pro zazvonění, Ctrl+C pro konec.")

try:
    while True:
        input("Stiskni ENTER...")
        ring_bell(duration=2) # Zvoní 2 sekundy

except KeyboardInterrupt:
    print("\nUkončuji...")
    GPIO.cleanup()
