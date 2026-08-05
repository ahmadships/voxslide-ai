"""VoxSlide AI — Central Configuration"""

from pathlib import Path


class Config:
    APP_NAME = "VoxSlide AI"
    VERSION = "1.0.0"
    GOOGLE_LANGUAGE = "en-US"
    ENERGY_THRESHOLD = 300
    SESSION_LIMIT_MINUTES = 10
    TRIGGER_NEXT = ["next", "next slide", "go next", "forward", "advance"]
    TRIGGER_PREV = ["back", "previous", "go back", "previous slide", "rewind"]

    PRO_KEYS_FILE = Path.home() / ".voxslide_license"
    PRO_COMMANDS_FILE = Path.home() / ".voxslide_commands.json"

    # Colors
    COLOR_BG = "#0F172A"
    COLOR_SURFACE = "#1E293B"
    COLOR_BORDER = "#334155"
    COLOR_BLUE = "#2563EB"
    COLOR_BLUE_HOVER = "#1D4ED8"
    COLOR_RED = "#DC2626"
    COLOR_RED_HOVER = "#B91C1C"
    COLOR_GREEN = "#22C55E"
    COLOR_ORANGE = "#F97316"
    COLOR_GRAY = "#64748B"
    COLOR_GOLD = "#F59E0B"
    COLOR_LOG_BG = "#0A0F1E"
    COLOR_LOG_TEXT = "#4ADE80"
