"""VoxSlide AI — Central Configuration"""

from pathlib import Path

from version import __version__


class Config:
    APP_NAME = "VoxSlide AI"
    # Version lives in version.py — change it there only.
    VERSION = __version__

    # ── Auto-update (GitHub Releases) ─────────────────────────
    # Set these to your public GitHub repository that hosts Releases.
    # Example: https://github.com/ahmadships/voxslide-ai/releases
    GITHUB_OWNER = "ahmadships"
    GITHUB_REPO = "voxslide-ai"
    # Preferred installer asset name uploaded to each Release
    UPDATE_ASSET_NAME = "VoxSlideAI_Setup.exe"
    # Set True to disable update checks (also: VOXSLIDE_SKIP_UPDATE=1)
    SKIP_UPDATE_CHECK = False

    GOOGLE_LANGUAGE = "en-US"
    ENERGY_THRESHOLD = 300
    SESSION_LIMIT_MINUTES = 10
    TRIGGER_NEXT = ["next", "next slide", "go next", "forward", "advance"]
    TRIGGER_PREV = ["back", "previous", "go back", "previous slide", "rewind"]

    PRO_KEYS_FILE = Path.home() / ".voxslide_license"
    PRO_COMMANDS_FILE = Path.home() / ".voxslide_commands.json"

    # Colors — VoxSlide brand theme (matches marketing site)
    COLOR_BG = "#0A0E14"
    COLOR_SURFACE = "#131A24"
    COLOR_SURFACE_RAISED = "#161D29"
    COLOR_BORDER = "#232B38"

    # Primary accent — lime/chartreuse (CTAs, active/success states)
    COLOR_LIME = "#D4F542"
    COLOR_LIME_HOVER = "#C0E12E"
    COLOR_LIME_TEXT = "#0A0E14"   # dark text used on top of lime fills

    # Secondary accents
    COLOR_CYAN = "#4DD8E8"
    COLOR_CYAN_HOVER = "#38C2D2"
    COLOR_CORAL = "#E85D4D"
    COLOR_CORAL_HOVER = "#D24B3C"

    # Legacy aliases kept so nothing else in the codebase breaks —
    # mapped onto the new palette instead of the old blue/red/green set.
    COLOR_BLUE = COLOR_LIME
    COLOR_BLUE_HOVER = COLOR_LIME_HOVER
    COLOR_RED = COLOR_CORAL
    COLOR_RED_HOVER = COLOR_CORAL_HOVER
    COLOR_GREEN = COLOR_LIME
    COLOR_ORANGE = COLOR_CORAL

    COLOR_GRAY = "#7A8699"
    COLOR_GOLD = COLOR_LIME
    COLOR_LOG_BG = "#0A0F1A"
    COLOR_LOG_TEXT = "#4ADE80"
