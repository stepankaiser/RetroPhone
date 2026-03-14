"""
Persistent user preferences for RetroPhone.
Stores language, last decade, and volume across sessions.
"""

import json
import os

PREFS_PATH = os.path.expanduser("~/RetroPhone/user_prefs.json")


class Preferences:
    DEFAULTS = {
        "language": "EN",
        "last_decade": None,
        "volume": 100,
    }

    def __init__(self):
        self.data = self._load()

    def _load(self):
        """Load preferences from disk, merging with defaults."""
        try:
            if os.path.exists(PREFS_PATH):
                with open(PREFS_PATH, 'r') as f:
                    saved = json.load(f)
                return {**self.DEFAULTS, **saved}
        except Exception as e:
            print(f"   (Prefs load error: {e})")
        return dict(self.DEFAULTS)

    def save(self):
        """Persist preferences to disk."""
        try:
            os.makedirs(os.path.dirname(PREFS_PATH), exist_ok=True)
            with open(PREFS_PATH, 'w') as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            print(f"   (Prefs save error: {e})")

    def get(self, key):
        return self.data.get(key, self.DEFAULTS.get(key))

    def set(self, key, value):
        self.data[key] = value
        self.save()
