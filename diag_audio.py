"""Diagnostic script - list every audio device and test recording."""
import sys
import sounddevice as sd

B = "=" * 70
D = "-" * 50

print(B)
print("VoxSlide AI - Audio Diagnostic")
print(B)
print(f"Python:       {sys.version}")
print(f"PortAudio:    {sd.get_portaudio_version()}")
print(f"sounddevice:  {sd.__version__}")
print()

# 1. Default devices
print("DEFAULT DEVICES")
print(D)
try:
    inp = sd.default.device[0]
    out = sd.default.device[1]
    print(f"  Default input index:  {inp}")
    print(f"  Default output index: {out}")
    if inp >= 0:
        info = sd.query_devices(inp)
        print(f"    name     = {info['name']}")
        print(f"    channels = in={info['max_input_channels']}  out={info['max_output_channels']}")
        print(f"    rate     = {info['default_samplerate']}")
    else:
        print("  (no default input device set)")
except Exception as e:
    print(f"  ERROR: {e}")
print()

# 2. All host APIs
print("HOST APIs")
print(D)
try:
    for i, api in enumerate(sd.query_hostapis()):
        print(f"  [{i}] {api['name']}  (devices: {api['device_count']})")
except Exception as e:
    print(f"  ERROR: {e}")
print()

# 3. All devices, full table
print("ALL DEVICES")
print(D)
try:
    devices = sd.query_devices()
    for i, d in enumerate(devices):
        marker = ""
        if d.get("max_input_channels", 0) > 0:
            marker += " MIC"
        if d.get("max_output_channels", 0) > 0:
            marker += " OUT"
        print(f"  [{i:2}]{marker}  {d['name']}")
        print(f"         host_api={d['hostapi']}  in_ch={d['max_input_channels']}  out_ch={d['max_output_channels']}  rate={d['default_samplerate']}")
except Exception as e:
    print(f"  ERROR: {e}")
print()

# 4. Try to open the default input device
print("OPEN DEFAULT INPUT")
print(D)
try:
    info = sd.query_devices(kind="input")
    print(f"  Opened: {info['name']}")
    print(f"  Channels in: {info['max_input_channels']}")
    print(f"  Default rate: {info['default_samplerate']}")
except Exception as e:
    print(f"  FAILED to open default input: {e}")
print()

# 5. Try a 1-second test recording
print("1-SECOND TEST RECORDING @ 16 kHz mono int16")
print(D)
try:
    rec = sd.rec(16000, samplerate=16000, channels=1, dtype="int16", blocking=True)
    print(f"  Recorded shape: {rec.shape}, dtype={rec.dtype}")
    print(f"  Min={int(rec.min())}, max={int(rec.max())}, mean={rec.mean():.1f}")
    print("  SUCCESS - microphone is functional")
except Exception as e:
    print(f"  FAILED: {e}")

print()
print(B)
print("Diagnostic complete")
