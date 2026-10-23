"""Single-instance asynchronous looping alarm using Windows winsound."""
from __future__ import annotations

import math
import os
import tempfile
import threading
import wave
from typing import Optional

try:
    import winsound
except ImportError:  # Keep import errors clear if launched outside Windows.
    winsound = None


class AlarmController:
    """Play a generated looping beep asynchronously; safe to start/stop repeatedly."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._active = False
        self._wav_path: Optional[str] = None
        self._error: Optional[str] = None
        self._create_tone()

    @property
    def active(self) -> bool:
        with self._lock:
            return self._active

    @property
    def error(self) -> Optional[str]:
        return self._error

    def _create_tone(self) -> None:
        if winsound is None:
            self._error = "Windows audio (winsound) is unavailable on this platform."
            return
        try:
            fd, path = tempfile.mkstemp(prefix="sleepguard_alarm_", suffix=".wav")
            os.close(fd)
            sample_rate = 22050
            duration = 0.55
            samples = int(sample_rate * duration)
            with wave.open(path, "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(sample_rate)
                frames = bytearray()
                for i in range(samples):
                    t = i / sample_rate
                    # Two short tones separated by a brief gap, repeated by PlaySound.
                    envelope = 0.0 if 0.30 <= t < 0.36 else 1.0
                    frequency = 1050 if t < 0.30 else 850
                    value = int(10500 * envelope * math.sin(2 * math.pi * frequency * t))
                    frames.extend(int(value).to_bytes(2, "little", signed=True))
                wav.writeframes(frames)
            self._wav_path = path
        except (OSError, wave.Error) as exc:
            self._error = f"Could not prepare alarm audio: {exc}"

    def start(self) -> None:
        """Start alarm if not already active; returns without waiting for playback."""
        with self._lock:
            if self._active:
                return
            if winsound is None or not self._wav_path or not os.path.exists(self._wav_path):
                self._error = self._error or "Alarm audio is not available."
                return
            try:
                winsound.PlaySound(
                    self._wav_path,
                    winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_LOOP,
                )
                self._active = True
                self._error = None
            except (RuntimeError, OSError) as exc:
                self._error = f"Alarm playback failed: {exc}"
                self._active = False

    def stop(self) -> None:
        """Stop playback immediately and idempotently."""
        with self._lock:
            if winsound is not None:
                try:
                    winsound.PlaySound(None, winsound.SND_PURGE)
                except (RuntimeError, OSError) as exc:
                    self._error = f"Could not stop alarm cleanly: {exc}"
            self._active = False

    def close(self) -> None:
        self.stop()
        path = self._wav_path
        self._wav_path = None
        if path:
            try:
                os.remove(path)
            except FileNotFoundError:
                pass
            except OSError:
                # Windows may briefly retain the file handle; do not crash shutdown.
                pass
