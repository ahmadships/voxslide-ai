"""VoxSlide AI — Free-tier session cooldown tracking.

Persists the timestamp of the last ended free-tier session and exposes
cooldown queries. Pro users skip this entirely (callers gate on
`LicenseManager.is_pro()`).
"""

import json
import time
from pathlib import Path

# 1 hour between free-tier sessions (user-configurable).
COOLDOWN_SECONDS = 3600

# JSON file in the user's home dir. Survives app restarts.
STATE_FILE = Path.home() / ".voxslide_session.json"


class SessionManager:
    """Static helpers for free-tier session cooldowns."""

    @staticmethod
    def record_session_end() -> None:
        """Stamp the current time as the end of the last free session."""
        payload = {"last_end_ts": time.time()}
        try:
            STATE_FILE.write_text(json.dumps(payload), encoding="utf-8")
        except OSError:
            # Disk full / perms issue — don't crash the app, the cooldown
            # simply won't persist this run.
            pass

    @staticmethod
    def is_in_cooldown() -> bool:
        """True if a free-tier session ended less than COOLDOWN_SECONDS ago."""
        return SessionManager.cooldown_remaining() > 0

    @staticmethod
    def cooldown_remaining() -> int:
        """Seconds until the next free session is allowed (0 if not in cooldown)."""
        if not STATE_FILE.exists():
            return 0
        try:
            data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            last_end = float(data.get("last_end_ts", 0))
        except (OSError, ValueError, json.JSONDecodeError, TypeError):
            return 0
        if last_end <= 0:
            return 0
        elapsed = time.time() - last_end
        return max(0, int(COOLDOWN_SECONDS - elapsed))
