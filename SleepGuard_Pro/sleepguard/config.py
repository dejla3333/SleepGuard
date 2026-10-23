"""Central application settings."""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class AppConfig:
    app_name: str = "SleepGuard Pro"
    camera_index: int = 0
    # Prefer 1080p; the camera module tries progressively lower modes if needed.
    preferred_resolution: tuple[int, int] = (1920, 1080)
    resolution_modes: dict[str, tuple[int, int]] = field(default_factory=lambda: {
        "1080p (1920 × 1080)": (1920, 1080),
        "720p (1280 × 720)": (1280, 720),
        "480p (640 × 480)": (640, 480),
    })
    default_ear_threshold: float = 0.21
    min_face_detection_confidence: float = 0.5
    min_face_tracking_confidence: float = 0.5
    ui_refresh_ms: int = 25
    preview_max_width: int = 900
    preview_max_height: int = 570
    camera_backend: int = 0  # camera.py selects DirectShow on Windows
