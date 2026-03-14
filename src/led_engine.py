import time
import threading
from .config import FEATURE_FLAGS

try:
    from rpi_ws281x import PixelStrip, Color
    LED_AVAILABLE = True
except ImportError:
    LED_AVAILABLE = False


class LEDEngine:
    """Controls a WS2812B 60-LED RGB strip via GPIO 10 (SPI MOSI).

    GPIO 18 (default PWM) is unavailable because it conflicts with audio PWM
    on the Raspberry Pi 3, so we use SPI instead. Make sure SPI is enabled
    in raspi-config.

    All visual effects run in daemon threads so they never block the main loop.
    If rpi_ws281x is not installed or the feature flag is disabled, every
    method becomes a silent no-op.
    """

    LED_COUNT = 60
    LED_PIN = 10          # GPIO 10 (SPI MOSI)
    LED_FREQ_HZ = 800000
    LED_DMA = 10
    LED_BRIGHTNESS = 50   # 0-255 (keep low to avoid power issues)
    LED_INVERT = False
    LED_CHANNEL = 0

    # Color palette for each decade (R, G, B)
    DECADE_COLORS = {
        1900: (255, 180, 50),   # Warm amber (gaslight era)
        1910: (200, 150, 50),   # Dim amber (wartime)
        1920: (255, 215, 0),    # Gold (jazz age, art deco)
        1930: (180, 130, 80),   # Sepia (golden era, cinema)
        1940: (80, 120, 80),    # Military green (WWII)
        1950: (255, 50, 100),   # Hot pink (rock n roll, diners)
        1960: (255, 100, 0),    # Orange (psychedelic, counterculture)
        1970: (255, 140, 0),    # Amber/orange (disco)
        1980: (0, 255, 255),    # Cyan/neon (synthwave, neon lights)
        1990: (0, 200, 100),    # Green (grunge, Matrix)
        2000: (0, 100, 255),    # Blue (Y2K, digital)
        2010: (255, 255, 255),  # White (clean, modern)
        2020: (100, 50, 255),   # Purple (vaporwave, LED culture)
    }

    def __init__(self):
        self._enabled = False
        self._strip = None
        self._current_color = (0, 0, 0)
        self._stop_event = threading.Event()
        self._effect_thread = None
        self._warned = False

        if not FEATURE_FLAGS.get("led_strip", True):
            self._debug_once("LED strip disabled by feature flag")
            return

        if not LED_AVAILABLE:
            self._debug_once("rpi_ws281x not installed — LED strip disabled")
            return

        try:
            self._strip = PixelStrip(
                self.LED_COUNT,
                self.LED_PIN,
                self.LED_FREQ_HZ,
                self.LED_DMA,
                self.LED_INVERT,
                self.LED_BRIGHTNESS,
                self.LED_CHANNEL,
            )
            self._strip.begin()
            self._enabled = True
            print("[LEDEngine] Initialized — 60 LEDs on GPIO 10 (SPI)")
        except Exception as e:
            self._debug_once(f"LED strip init failed: {e}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_decade(self, year: int):
        """Set all LEDs to the decade's color with a smooth ~1 s crossfade."""
        if not self._enabled:
            return

        decade = self._year_to_decade(year)
        target = self.DECADE_COLORS.get(decade, (255, 255, 255))

        self._stop_current_effect()

        def _fade():
            start = self._current_color
            steps = 50
            duration = 1.0
            step_delay = duration / steps

            for i in range(1, steps + 1):
                if self._stop_event.is_set():
                    return
                t = i / steps
                r = int(start[0] + (target[0] - start[0]) * t)
                g = int(start[1] + (target[1] - start[1]) * t)
                b = int(start[2] + (target[2] - start[2]) * t)
                self._fill((r, g, b))
                time.sleep(step_delay)

            self._current_color = target

        self._run_effect(_fade)

    def pulse(self, color=None, duration: float = 2.0):
        """Breathing / pulse effect. Runs continuously until stopped.

        One full breath cycle takes ``duration`` seconds.
        """
        if not self._enabled:
            return

        self._stop_current_effect()
        base = color or self._current_color
        if base == (0, 0, 0):
            base = (255, 255, 255)

        def _pulse_loop():
            import math
            steps = 60
            step_delay = duration / steps

            while not self._stop_event.is_set():
                for i in range(steps):
                    if self._stop_event.is_set():
                        return
                    # Sine wave: 0 -> 1 -> 0 over one cycle
                    brightness = (math.sin(2 * math.pi * i / steps - math.pi / 2) + 1) / 2
                    # Clamp to a minimum of ~10 % so LEDs never fully go dark
                    brightness = 0.1 + brightness * 0.9
                    r = int(base[0] * brightness)
                    g = int(base[1] * brightness)
                    b = int(base[2] * brightness)
                    self._fill((r, g, b))
                    time.sleep(step_delay)

        self._run_effect(_pulse_loop)

    def on_air_flash(self, duration: float = 0.5):
        """Quick red flash — call this when the user goes 'live on air'."""
        if not self._enabled:
            return

        self._stop_current_effect()
        saved = self._current_color

        def _flash():
            steps = 4
            half = duration / (2 * steps)
            red = (255, 0, 0)

            for _ in range(steps):
                if self._stop_event.is_set():
                    break
                self._fill(red)
                time.sleep(half)
                self._fill((0, 0, 0))
                time.sleep(half)

            # Restore previous color
            self._fill(saved)
            self._current_color = saved

        self._run_effect(_flash)

    def vu_meter(self, level: float):
        """Show *level* (0.0 -- 1.0) as a bar graph across the strip.

        ``level = 0.5`` lights 30 of 60 LEDs. Lit LEDs are green at the low
        end, yellow in the middle, and red at the top.
        """
        if not self._enabled:
            return

        level = max(0.0, min(1.0, level))
        lit = int(level * self.LED_COUNT)

        for i in range(self.LED_COUNT):
            if i < lit:
                frac = i / self.LED_COUNT
                if frac < 0.6:
                    c = Color(0, 255, 0)      # Green
                elif frac < 0.8:
                    c = Color(255, 200, 0)    # Yellow
                else:
                    c = Color(255, 0, 0)      # Red
            else:
                c = Color(0, 0, 0)
            self._strip.setPixelColor(i, c)
        self._strip.show()

    def rainbow_sweep(self, duration: float = 3.0):
        """Full rainbow sweep across the strip — great for startup or discover mode."""
        if not self._enabled:
            return

        self._stop_current_effect()

        def _rainbow():
            steps = 256
            step_delay = duration / steps

            for j in range(steps):
                if self._stop_event.is_set():
                    return
                for i in range(self.LED_COUNT):
                    hue = (i * 256 // self.LED_COUNT + j) & 255
                    r, g, b = self._wheel(hue)
                    self._strip.setPixelColor(i, Color(r, g, b))
                self._strip.show()
                time.sleep(step_delay)

            # After the sweep, restore current color
            self._fill(self._current_color)

        self._run_effect(_rainbow)

    def off(self):
        """Turn all LEDs off immediately."""
        if not self._enabled:
            return

        self._stop_current_effect()
        self._fill((0, 0, 0))
        self._current_color = (0, 0, 0)

    def cleanup(self):
        """Clean shutdown — turn off LEDs and release resources."""
        self._stop_current_effect()
        if self._enabled:
            self._fill((0, 0, 0))
        self._enabled = False
        print("[LEDEngine] Cleaned up")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fill(self, color: tuple):
        """Set every pixel to *color* (R, G, B) and show."""
        if not self._strip:
            return
        c = Color(color[0], color[1], color[2])
        for i in range(self.LED_COUNT):
            self._strip.setPixelColor(i, c)
        self._strip.show()

    def _stop_current_effect(self):
        """Signal the running effect thread to stop, then wait for it."""
        self._stop_event.set()
        if self._effect_thread and self._effect_thread.is_alive():
            self._effect_thread.join(timeout=3.0)
        self._stop_event.clear()

    def _run_effect(self, target):
        """Launch *target* in a daemon thread, tracking it for later cancellation."""
        self._effect_thread = threading.Thread(target=target, daemon=True)
        self._effect_thread.start()

    def _debug_once(self, msg: str):
        """Print a debug message the first time only."""
        if not self._warned:
            print(f"[LEDEngine] {msg}")
            self._warned = True

    @staticmethod
    def _year_to_decade(year: int) -> int:
        """Round a year down to its decade (e.g. 1967 -> 1960)."""
        return (year // 10) * 10

    @staticmethod
    def _wheel(pos: int) -> tuple:
        """Generate an RGB tuple for a position 0-255 around the color wheel."""
        if pos < 85:
            return (pos * 3, 255 - pos * 3, 0)
        elif pos < 170:
            pos -= 85
            return (255 - pos * 3, 0, pos * 3)
        else:
            pos -= 170
            return (0, pos * 3, 255 - pos * 3)
