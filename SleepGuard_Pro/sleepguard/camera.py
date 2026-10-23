"""Camera capture and eye detection worker."""
from __future__ import annotations

import platform
import queue
import threading
import time
import traceback
from dataclasses import dataclass
from typing import Optional

import cv2

from .config import AppConfig
from .detector import EyeDetector, EyeResult


@dataclass
class FramePacket:
    frame_bgr: object
    eye: EyeResult
    width: int
    height: int
    fps: float
    timestamp: float


@dataclass
class WorkerMessage:
    kind: str
    message: str


class CameraWorker:
    """Owns the camera and detector on a background thread; UI receives latest frames."""

    def __init__(self, config: AppConfig, resolution: tuple[int, int],
                 threshold: float) -> None:
        self.config = config
        self.requested_resolution = resolution
        self.threshold = threshold
        self.frames: queue.Queue[FramePacket] = queue.Queue(maxsize=1)
        self.messages: queue.Queue[WorkerMessage] = queue.Queue()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._cap = None
        self._actual_resolution = (0, 0)

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="SleepGuardCamera", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=3.0)
        # The worker normally releases it in finally. This handles an early-init edge case.
        if self._cap is not None and (thread is None or not thread.is_alive()):
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None

    def _open_camera(self):
        backend = cv2.CAP_DSHOW if platform.system() == "Windows" else cv2.CAP_ANY
        cap = cv2.VideoCapture(self.config.camera_index, backend)
        if not cap.isOpened():
            cap.release()
            raise RuntimeError(
                "Cannot open webcam. Check Windows Camera permissions, close apps using "
                "the camera, and verify that the built-in camera is enabled."
            )
        try:
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass

        modes = [self.requested_resolution]
        for mode in ((1280, 720), (640, 480)):
            if mode not in modes:
                modes.append(mode)
        actual = None
        for w, h in modes:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
            # Read frames to let drivers apply the requested mode.
            for _ in range(3):
                ok, frame = cap.read()
                if ok and frame is not None:
                    got = (int(frame.shape[1]), int(frame.shape[0]))
                    if got[0] >= w * 0.95 and got[1] >= h * 0.95:
                        actual = got
                        break
            if actual:
                break
        # If no requested mode was matched, report the actual first readable frame size.
        if actual is None:
            ok, frame = cap.read()
            if not ok or frame is None:
                cap.release()
                raise RuntimeError("Webcam opened but did not deliver a video frame.")
            actual = (int(frame.shape[1]), int(frame.shape[0]))
        return cap, actual

    def _publish_frame(self, packet: FramePacket) -> None:
        try:
            self.frames.put_nowait(packet)
        except queue.Full:
            try:
                self.frames.get_nowait()
            except queue.Empty:
                pass
            try:
                self.frames.put_nowait(packet)
            except queue.Full:
                pass

    def _run(self) -> None:
        detector = None
        try:
            self._cap, self._actual_resolution = self._open_camera()
            self.messages.put(WorkerMessage(
                "status",
                f"Camera connected: {self._actual_resolution[0]} × {self._actual_resolution[1]}",
            ))
            detector = EyeDetector(
                threshold=self.threshold,
                min_detection_confidence=self.config.min_face_detection_confidence,
                min_tracking_confidence=self.config.min_face_tracking_confidence,
            )
            samples = 0
            fps_started = time.perf_counter()
            fps = 0.0
            while not self._stop.is_set():
                ok, frame = self._cap.read()
                if not ok or frame is None:
                    self.messages.put(WorkerMessage(
                        "error", "Camera frame read failed; webcam may have disconnected."
                    ))
                    break
                # Mirror the preview to feel natural for a built-in webcam.
                frame = cv2.flip(frame, 1)
                eye, annotated = detector.process(frame)
                samples += 1
                elapsed = time.perf_counter() - fps_started
                if elapsed >= 1.0:
                    fps = samples / elapsed
                    samples = 0
                    fps_started = time.perf_counter()
                h, w = annotated.shape[:2]
                self._publish_frame(FramePacket(
                    frame_bgr=annotated, eye=eye, width=w, height=h,
                    fps=fps, timestamp=time.perf_counter(),
                ))
        except Exception as exc:
            detail = f"{type(exc).__name__}: {exc}"
            self.messages.put(WorkerMessage("error", detail))
            self.messages.put(WorkerMessage("traceback", traceback.format_exc()))
        finally:
            if detector is not None:
                try:
                    detector.close()
                except Exception as exc:
                    self.messages.put(WorkerMessage("error", f"Detector cleanup failed: {exc}"))
            if self._cap is not None:
                try:
                    self._cap.release()
                except Exception as exc:
                    self.messages.put(WorkerMessage("error", f"Camera cleanup failed: {exc}"))
                self._cap = None
            self.messages.put(WorkerMessage("stopped", "Camera worker stopped."))
