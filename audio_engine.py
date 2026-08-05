"""VoxSlide AI - Audio Engine (Non-blocking background thread)

Uses `speech_recognition.Microphone` (PyAudio) when available, with the
device index resolved by probing inputs via `sounddevice` and matching
by name. Falls back to direct `sounddevice` capture on Python 3.14+
where official PyAudio wheels are not yet published.
"""

import threading
import speech_recognition as sr
import sounddevice as sd
from config import Config
from typing import Callable, Optional, Tuple

try:
    import pyaudio  # noqa: F401
    _PYAUDIO_AVAILABLE = True
except ImportError:
    _PYAUDIO_AVAILABLE = False

SAMPLE_WIDTH = 2
CHANNELS = 1
LISTEN_SECONDS = 4
CALIBRATION_SECONDS = 0.8

# Confirmed working default input from diagnostic (MME HD microphone)
DEFAULT_MIC_INDEX = 1


class AudioEngine:
    def __init__(self, on_heard: Callable[[str], None], on_action: Callable[[str], None]):
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = Config.ENERGY_THRESHOLD
        self.recognizer.dynamic_energy_threshold = False
        self.running = False
        self.on_heard = on_heard
        self.on_action = on_action
        self._thread = None

    def start(self):
        self.running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self.running = False

    def set_threshold(self, value: int):
        self.recognizer.energy_threshold = int(value)

    # ── DEVICE RESOLUTION ─────────────────────────────────────

    def _probe_sounddevice_mic(self) -> Optional[Tuple[int, dict]]:
        """Return (sounddevice_index, info) for the first working input."""
        try:
            devices = sd.query_devices()
        except Exception as e:
            self.on_heard(f"[Error] Cannot enumerate audio devices: {e}")
            return None

        try:
            default_idx = sd.default.device[0]
        except Exception:
            default_idx = -1

        candidates = []
        if default_idx is not None and default_idx >= 0:
            d = devices[default_idx]
            if d.get("max_input_channels", 0) > 0:
                candidates.append(default_idx)
        for i, d in enumerate(devices):
            if i not in candidates and d.get("max_input_channels", 0) > 0:
                candidates.append(i)

        for idx in candidates:
            try:
                info = sd.query_devices(idx, kind="input")
                sd.rec(
                    int(info["default_samplerate"] * 0.1),
                    samplerate=int(info["default_samplerate"]),
                    channels=min(CHANNELS, info["max_input_channels"]),
                    dtype="int16",
                    device=idx,
                    blocking=True,
                )
                return idx, info
            except Exception:
                continue
        return None

    def _resolve_pyaudio_index(self, sd_name: str) -> int:
        """Map a sounddevice mic name to the PyAudio device index."""
        names = sr.Microphone.list_microphone_names()
        sd_key = sd_name.strip().lower()
        for i, name in enumerate(names):
            if sd_key in name.strip().lower() or name.strip().lower() in sd_key:
                return i
        # Same ordering on Windows: default MME mic is usually index 1
        if DEFAULT_MIC_INDEX < len(names):
            return DEFAULT_MIC_INDEX
        return 0

    # ── LISTEN LOOPS ──────────────────────────────────────────

    def _listen_loop(self):
        if _PYAUDIO_AVAILABLE:
            self._listen_with_microphone()
        else:
            self.on_heard("[System] PyAudio unavailable; using sounddevice capture.")
            self._listen_with_sounddevice()

    def _listen_with_microphone(self):
        probed = self._probe_sounddevice_mic()
        if probed is None:
            self.on_heard("[Error] No working microphone found.")
            self.on_action("NO_MIC")
            return

        _, info = probed
        pa_index = self._resolve_pyaudio_index(info["name"])
        self.on_heard(
            f"[System] Mic ready: {info['name']} "
            f"(PyAudio index {pa_index})"
        )

        try:
            microphone = sr.Microphone(device_index=pa_index)
        except Exception as e:
            self.on_heard(f"[Error] Cannot open microphone: {e}")
            self.on_action("NO_MIC")
            return

        try:
            with microphone as source:
                self.on_heard("[System] Calibrating ambient noise...")
                self.recognizer.adjust_for_ambient_noise(source, duration=CALIBRATION_SECONDS)
        except Exception as e:
            self.on_heard(f"[Error] Calibration failed: {e}")
            self.on_action("NO_MIC")
            return

        while self.running:
            try:
                with microphone as source:
                    audio = self.recognizer.listen(
                        source, timeout=None, phrase_time_limit=LISTEN_SECONDS
                    )
                text = self._recognize(audio)
                if text:
                    self._dispatch(text)
            except sr.WaitTimeoutError:
                continue
            except OSError as e:
                self.on_heard(f"[Error] Microphone I/O: {e}")
                self.on_action("NO_MIC")
                return
            except Exception as e:
                self.on_heard(f"[Error] Unexpected: {e}")
                continue

    def _listen_with_sounddevice(self):
        probed = self._probe_sounddevice_mic()
        if probed is None:
            self.on_heard("[Error] No working microphone found.")
            self.on_heard("[Hint] Check Settings -> Sound -> Input device.")
            self.on_action("NO_MIC")
            return

        idx, info = probed
        sample_rate = int(info["default_samplerate"])
        channels = min(CHANNELS, info["max_input_channels"])
        self.on_heard(
            f"[System] Mic ready: {info['name']} "
            f"(@ {sample_rate} Hz, device {idx})"
        )

        self.on_heard("[System] Calibrating ambient noise...")
        try:
            sd.rec(
                int(sample_rate * CALIBRATION_SECONDS),
                samplerate=sample_rate,
                channels=channels,
                dtype="int16",
                device=idx,
                blocking=True,
            )
        except Exception as e:
            self.on_heard(f"[Error] Calibration failed: {e}")
            self.on_action("NO_MIC")
            return

        while self.running:
            try:
                recording = sd.rec(
                    int(sample_rate * LISTEN_SECONDS),
                    samplerate=sample_rate,
                    channels=channels,
                    dtype="int16",
                    device=idx,
                    blocking=True,
                )
                if recording is None or len(recording) == 0:
                    continue

                mono = recording[:, 0] if recording.ndim == 2 else recording
                audio = sr.AudioData(mono.tobytes(), sample_rate, SAMPLE_WIDTH)
                text = self._recognize(audio)
                if text:
                    self._dispatch(text)

            except sd.PortAudioError as e:
                self.on_heard(f"[Error] PortAudio: {e}")
                self.on_action("NO_MIC")
                return
            except Exception as e:
                msg = str(e)
                if "NumPy" in msg or "numpy" in msg:
                    self.on_heard("[Error] NumPy is required. Run: pip install numpy")
                else:
                    self.on_heard(f"[Error] Unexpected: {e}")
                continue

    def _recognize(self, audio: sr.AudioData) -> Optional[str]:
        try:
            return (
                self.recognizer.recognize_google(audio, language=Config.GOOGLE_LANGUAGE)
                .lower()
                .strip()
            )
        except sr.UnknownValueError:
            return None
        except sr.RequestError as e:
            self.on_heard(f"[Error] Speech API unavailable: {e}")
            return None

    def _dispatch(self, text: str):
        self.on_heard(text)
        if any(t in text for t in Config.TRIGGER_NEXT):
            self.on_action("NEXT")
        elif any(t in text for t in Config.TRIGGER_PREV):
            self.on_action("PREV")
