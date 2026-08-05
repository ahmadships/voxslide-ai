"""VoxSlide AI — Pro License Management

License keys are bound to a single device fingerprint (MAC + hostname
hash). Reactivating a valid key on a different device returns
"WRONG_DEVICE" so the UI can point the user at WhatsApp support.
"""

import hashlib
import platform
import uuid
from pathlib import Path

from config import Config


# Result codes returned by `activate()`.
STATUS_OK = "OK"
STATUS_INVALID = "INVALID"
STATUS_WRONG_DEVICE = "WRONG_DEVICE"

# Support contact for stuck / wrong-device activations.
SUPPORT_WHATSAPP = "+92-343-5050786"

# File storing the device fingerprint the key was first activated on.
DEVICE_ID_FILE = Path.home() / ".voxslide_device"


def _device_id() -> str:
    """Stable fingerprint: SHA-256 of (MAC address + hostname), 16 hex chars."""
    raw = f"{uuid.getnode()}-{platform.node()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _load_bound_device() -> str | None:
    """Return the device fingerprint the active key is bound to, or None."""
    if not DEVICE_ID_FILE.exists():
        return None
    try:
        return DEVICE_ID_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return None


def _hash_key(key: str) -> str:
    """SHA-256 of the uppercase, stripped key — keeps plaintext keys out of the binary."""
    return hashlib.sha256(key.upper().strip().encode()).hexdigest()


class LicenseManager:
    # Pre-hashed valid keys. The plaintext keys are never embedded in the
    # compiled exe — only their SHA-256 digests are.
    VALID_KEY_HASHES = [
        _hash_key("VOXS-K9X2-M7QP-4WR8"),
        _hash_key("VOXS-J3HT-N6YL-9BZ5"),
        _hash_key("VOXS-R8DM-X4KQ-2FN7"),
        _hash_key("VOXS-W5PG-H9TJ-6LCV"),
        _hash_key("VOXS-A2NR-Q7XB-8DKM"),
        _hash_key("VOXS-T6YH-F3WQ-5JPX"),
        _hash_key("VOXS-B4KC-L8NM-7GRZ"),
        _hash_key("VOXS-E9QX-V2HF-3YTW"),
        _hash_key("VOXS-G7MJ-P5RK-4DNB"),
        _hash_key("VOXS-Z3WL-C6XT-9HQV"),
    ]

    @staticmethod
    def activate(key: str) -> str:
        """Validate `key`, bind it to this device on first activation.

        Returns one of:
          - "OK"            — key is valid and (now) bound to this device.
          - "INVALID"       — key is not in VALID_KEY_HASHES.
          - "WRONG_DEVICE"  — key is valid but already bound to another device.
        """
        key_hash = _hash_key(key)
        if key_hash not in LicenseManager.VALID_KEY_HASHES:
            return STATUS_INVALID

        bound = _load_bound_device()
        if bound is not None and bound != _device_id():
            return STATUS_WRONG_DEVICE

        try:
            Config.PRO_KEYS_FILE.write_text(key.strip().upper(), encoding="utf-8")
            DEVICE_ID_FILE.write_text(_device_id(), encoding="utf-8")
        except OSError:
            raise
        return STATUS_OK

    @staticmethod
    def is_pro() -> bool:
        if not Config.PRO_KEYS_FILE.exists():
            return False
        try:
            key = Config.PRO_KEYS_FILE.read_text(encoding="utf-8").strip().upper()
        except OSError:
            return False
        return _hash_key(key) in LicenseManager.VALID_KEY_HASHES
