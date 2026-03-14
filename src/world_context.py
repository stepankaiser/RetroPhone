import time
import threading
import requests
from datetime import datetime

try:
    from .config import WEATHER_LOCATION
except ImportError:
    WEATHER_LOCATION = "Tallinn"


class WorldContext:
    """
    Fetches and caches real-world context (weather, historical events)
    for DJ prompt injection. Lightweight, thread-safe, failure-tolerant.
    """

    WEATHER_TTL = 3600       # 1 hour
    HISTORY_TTL = 86400      # 24 hours
    REQUEST_TIMEOUT = 10     # seconds (Pi 3 WiFi can be slow)

    LANG_MAP = {
        "EN": "en",
        "CZ": "cs",
    }

    SEASONS = {
        "EN": {
            12: "winter", 1: "winter", 2: "winter",
            3: "spring", 4: "spring", 5: "spring",
            6: "summer", 7: "summer", 8: "summer",
            9: "autumn", 10: "autumn", 11: "autumn",
        },
        "CZ": {
            12: "zima", 1: "zima", 2: "zima",
            3: "jaro", 4: "jaro", 5: "jaro",
            6: "leto", 7: "leto", 8: "leto",
            9: "podzim", 10: "podzim", 11: "podzim",
        },
    }

    def __init__(self, location=None):
        self.location = location or WEATHER_LOCATION or "Tallinn"

        # Cache storage
        self._weather_cache = None       # (timestamp, weather_string)
        self._history_cache = {}         # (lang, month, day) -> (timestamp, events_list)

        # Lock for thread-safe cache access
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_weather(self):
        """
        Returns a string like '12°C, partly cloudy' or '' on error.
        Cached for 1 hour.
        """
        with self._lock:
            if self._weather_cache is not None:
                ts, cached_value = self._weather_cache
                if time.time() - ts < self.WEATHER_TTL:
                    return cached_value

        # Fetch outside the lock to avoid blocking other threads
        weather_str = self._fetch_weather()

        with self._lock:
            self._weather_cache = (time.time(), weather_str)

        return weather_str

    def get_historical_event(self, month, day, decade, language="EN"):
        """
        Returns a historical event close to the given decade for this date.
        Cached for 24 hours per (lang, month, day). Returns '' on error.
        """
        lang = self.LANG_MAP.get(language, "en")
        cache_key = (lang, month, day)

        with self._lock:
            if cache_key in self._history_cache:
                ts, cached_events = self._history_cache[cache_key]
                if time.time() - ts < self.HISTORY_TTL:
                    return self._pick_event(cached_events, decade)

        # Fetch outside the lock
        events = self._fetch_history(month, day, lang)

        with self._lock:
            self._history_cache[cache_key] = (time.time(), events)

        return self._pick_event(events, decade)

    def get_season(self, month, language="EN"):
        """Returns the current season name for the given month."""
        season_map = self.SEASONS.get(language, self.SEASONS["EN"])
        return season_map.get(month, "unknown")

    def get_dj_context(self, year, language="EN"):
        """
        Combine weather + historical event into a ready-to-inject context dict.
        Returns dict with keys: weather, event, season.
        """
        now = datetime.now()
        month = now.month
        day = now.day
        decade = (year // 10) * 10

        weather = self.get_weather()
        event = self.get_historical_event(month, day, decade, language)
        season = self.get_season(month, language)

        return {
            "weather": weather,
            "event": event,
            "season": season,
        }

    # ------------------------------------------------------------------
    # Private: Fetching
    # ------------------------------------------------------------------

    def _fetch_weather(self):
        """Fetch current weather from wttr.in. Returns string or ''."""
        try:
            url = f"https://wttr.in/{self.location}?format=j1"
            resp = requests.get(url, timeout=self.REQUEST_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()

            condition = data["current_condition"][0]
            temp_c = condition["temp_C"]
            desc = condition["weatherDesc"][0]["value"]

            return f"{temp_c}\u00b0C, {desc.lower()}"
        except Exception as e:
            print(f"\U0001f30d WorldContext weather error: {e}")
            return ""

    def _fetch_history(self, month, day, lang):
        """
        Fetch historical events from Wikimedia 'On This Day' API.
        Returns a list of (year, text) tuples, or [] on error.
        """
        try:
            url = (
                f"https://api.wikimedia.org/feed/v1/wikipedia/"
                f"{lang}/onthisday/all/{month:02d}/{day:02d}"
            )
            headers = {
                "User-Agent": "RetroPhone/1.0 (hobbyist project; no contact)",
            }
            resp = requests.get(url, headers=headers, timeout=self.REQUEST_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()

            events = []
            for item in data.get("events", []):
                event_year = item.get("year")
                event_text = item.get("text", "")
                if event_year is not None and event_text:
                    events.append((int(event_year), event_text))

            return events
        except Exception as e:
            print(f"\U0001f30d WorldContext history error: {e}")
            return []

    # ------------------------------------------------------------------
    # Private: Selection
    # ------------------------------------------------------------------

    def _pick_event(self, events, decade):
        """
        Pick the event closest to the given decade from a list of
        (year, text) tuples. Returns the text string, or '' if none.
        """
        if not events:
            return ""

        try:
            # Target the middle of the decade (e.g. 1955 for the 1950s)
            target = decade + 5

            best = min(events, key=lambda e: abs(e[0] - target))
            return f"In {best[0]}: {best[1]}"
        except Exception:
            return ""
