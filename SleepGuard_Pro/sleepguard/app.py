
"""Monochrome Tkinter UI for SleepGuard Pro."""
from __future__ import annotations

import queue
import tkinter as tk
from tkinter import ttk
from typing import Optional

import cv2
from PIL import Image, ImageTk

from .alarm import AlarmController
from .camera import CameraWorker, FramePacket
from .config import AppConfig


# Pure black-and-white palette
BLACK = "#000000"
DARK = "#090909"
PANEL = "#111111"
PANEL_ALT = "#181818"
BORDER = "#303030"
WHITE = "#FFFFFF"
SOFT_WHITE = "#E6E6E6"
GRAY = "#999999"
MID_GRAY = "#666666"
RED = "#FF4545"


class SleepGuardApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()

        self.config_data = AppConfig()
        self.title(self.config_data.app_name)
        self.geometry("1280x850")
        self.minsize(1000, 700)
        self.configure(bg=BLACK)

        self.alarm = AlarmController()
        self.worker: Optional[CameraWorker] = None
        self._photo = None
        self._closing = False
        self._monitoring = False
        self._manual_mute = False
        self._last_state = "UNKNOWN"
        self._last_packet: Optional[FramePacket] = None

        self.resolution_var = tk.StringVar(
            value="1080p (1920 × 1080)"
        )
        self.sensitivity_var = tk.DoubleVar(
            value=self.config_data.default_ear_threshold
        )
        self.state_var = tk.StringVar(value="UNKNOWN")
        self.metric_var = tk.StringVar(value="EAR: —")
        self.resolution_status_var = tk.StringVar(
            value="RESOLUTION  /  —"
        )
        self.fps_var = tk.StringVar(value="FPS  /  —")
        self.alarm_var = tk.StringVar(value="ALARM OFF")
        self.status_var = tk.StringVar(
            value="System ready. Start the camera to begin monitoring."
        )
        self.threshold_text_var = tk.StringVar(
            value=f"{self.sensitivity_var.get():.3f}"
        )

        self._setup_style()
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(self.config_data.ui_refresh_ms, self._poll_worker)

    def _setup_style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")

        style.configure(
            "TCombobox",
            fieldbackground=PANEL_ALT,
            background=PANEL_ALT,
            foreground=WHITE,
            arrowcolor=WHITE,
            bordercolor=BORDER,
            lightcolor=BORDER,
            darkcolor=BORDER,
            padding=10,
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", PANEL_ALT)],
            foreground=[("readonly", WHITE)],
            selectbackground=[("readonly", PANEL_ALT)],
            selectforeground=[("readonly", WHITE)],
        )

        style.configure(
            "Horizontal.TScale",
            background=PANEL,
            troughcolor=BORDER,
            bordercolor=PANEL,
            lightcolor=WHITE,
            darkcolor=WHITE,
        )

        style.configure(
            "TButton",
            font=("Segoe UI", 10, "bold"),
            padding=(12, 12),
            borderwidth=1,
            relief="flat",
            focuscolor=PANEL,
        )

        style.configure(
            "Primary.TButton",
            background=WHITE,
            foreground=BLACK,
            bordercolor=WHITE,
        )
        style.map(
            "Primary.TButton",
            background=[
                ("disabled", "#444444"),
                ("pressed", "#CCCCCC"),
                ("active", "#E5E5E5"),
            ],
            foreground=[
                ("disabled", "#AAAAAA"),
                ("!disabled", BLACK),
            ],
        )

        style.configure(
            "Secondary.TButton",
            background=PANEL_ALT,
            foreground=WHITE,
            bordercolor=BORDER,
        )
        style.map(
            "Secondary.TButton",
            background=[
                ("pressed", "#303030"),
                ("active", "#262626"),
            ],
            foreground=[("active", WHITE)],
        )

        style.configure(
            "Danger.TButton",
            background="#292020",
            foreground="#FF7777",
            bordercolor="#633333",
        )
        style.map(
            "Danger.TButton",
            background=[
                ("pressed", "#502222"),
                ("active", "#3A2020"),
            ],
            foreground=[("active", "#FF9999")],
        )

    def _panel(self, parent, **kwargs):
        return tk.Frame(
            parent,
            bg=PANEL,
            highlightbackground=BORDER,
            highlightthickness=1,
            bd=0,
            **kwargs,
        )

    def _label(
        self,
        parent,
        text="",
        *,
        color=WHITE,
        size=10,
        bold=False,
        bg=PANEL,
        **kwargs,
    ):
        return tk.Label(
            parent,
            text=text,
            bg=bg,
            fg=color,
            font=(
                "Segoe UI",
                size,
                "bold" if bold else "normal",
            ),
            **kwargs,
        )

    def _build_ui(self) -> None:
        # Main header
        header = tk.Frame(self, bg=BLACK)
        header.pack(fill="x", padx=28, pady=(24, 20))

        brand = tk.Frame(header, bg=BLACK)
        brand.pack(side="left")

        self._label(
            brand,
            "SLEEPGUARD",
            bg=BLACK,
            size=25,
            bold=True,
        ).pack(anchor="w")

        self._label(
            brand,
            "PRO  /  REAL-TIME EYE MONITORING",
            bg=BLACK,
            color=GRAY,
            size=9,
        ).pack(anchor="w", pady=(3, 0))

        right_header = tk.Frame(header, bg=BLACK)
        right_header.pack(side="right", anchor="center")

        self._label(
            right_header,
            "●  LOCAL PROCESSING",
            bg=BLACK,
            color=SOFT_WHITE,
            size=9,
            bold=True,
        ).pack(anchor="e")

        self._label(
            right_header,
            "VIDEO IS NOT SAVED BY THIS APP",
            bg=BLACK,
            color=MID_GRAY,
            size=8,
        ).pack(anchor="e", pady=(5, 0))

        # Thin divider
        tk.Frame(self, bg=BORDER, height=1).pack(
            fill="x", padx=28, pady=(0, 20)
        )

        # Main content
        content = tk.Frame(self, bg=BLACK)
        content.pack(
            fill="both",
            expand=True,
            padx=28,
            pady=(0, 16),
        )
        content.columnconfigure(0, weight=3)
        content.columnconfigure(1, weight=2)
        content.rowconfigure(0, weight=1)

        # Camera preview panel
        preview_panel = self._panel(content)
        preview_panel.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=(0, 16),
        )
        preview_panel.rowconfigure(1, weight=1)
        preview_panel.columnconfigure(0, weight=1)

        preview_header = tk.Frame(preview_panel, bg=PANEL)
        preview_header.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=20,
            pady=(18, 12),
        )

        self._label(
            preview_header,
            "LIVE CAMERA",
            size=10,
            bold=True,
        ).pack(side="left")

        self._label(
            preview_header,
            "CAM  /  01",
            color=GRAY,
            size=9,
        ).pack(side="right")

        self.preview = tk.Label(
            preview_panel,
            text="CAMERA FEED\n\nStart monitoring to connect your camera",
            bg="#050505",
            fg=GRAY,
            font=("Segoe UI", 12),
            justify="center",
            anchor="center",
            bd=0,
        )
        self.preview.grid(
            row=1,
            column=0,
            sticky="nsew",
            padx=16,
            pady=(0, 14),
        )

        camera_footer = tk.Frame(preview_panel, bg=PANEL)
        camera_footer.grid(
            row=2,
            column=0,
            sticky="ew",
            padx=20,
            pady=(0, 18),
        )

        self._label(
            camera_footer,
            textvariable=self.resolution_status_var,
            color=GRAY,
            size=9,
        ).pack(side="left")

        self._label(
            camera_footer,
            textvariable=self.fps_var,
            color=WHITE,
            size=9,
            bold=True,
        ).pack(side="right")

        # Right-side controls
        side = tk.Frame(content, bg=BLACK)
        side.grid(row=0, column=1, sticky="nsew")
        side.columnconfigure(0, weight=1)

        # Eye state
        state_panel = self._panel(side)
        state_panel.grid(
            row=0,
            column=0,
            sticky="ew",
            pady=(0, 14),
        )

        self._label(
            state_panel,
            "DETECTION STATUS",
            color=GRAY,
            size=9,
            bold=True,
        ).pack(anchor="w", padx=18, pady=(16, 12))

        self.state_badge = tk.Label(
            state_panel,
            textvariable=self.state_var,
            bg="#252525",
            fg=WHITE,
            font=("Segoe UI", 23, "bold"),
            padx=12,
            pady=16,
            bd=0,
        )
        self.state_badge.pack(fill="x", padx=16)

        self._label(
            state_panel,
            textvariable=self.metric_var,
            color=SOFT_WHITE,
            size=10,
            bg=PANEL,
        ).pack(anchor="w", padx=18, pady=(12, 17))

        # Settings
        controls = self._panel(side)
        controls.grid(
            row=1,
            column=0,
            sticky="ew",
            pady=(0, 14),
        )

        self._label(
            controls,
            "MONITOR SETTINGS",
            color=GRAY,
            size=9,
            bold=True,
        ).pack(anchor="w", padx=18, pady=(16, 16))

        self._label(
            controls,
            "Capture resolution",
            size=10,
        ).pack(anchor="w", padx=18)

        self.resolution_combo = ttk.Combobox(
            controls,
            textvariable=self.resolution_var,
            values=list(
                self.config_data.resolution_modes.keys()
            ),
            state="readonly",
        )
        self.resolution_combo.pack(
            fill="x",
            padx=18,
            pady=(7, 16),
        )
        self.resolution_combo.bind(
            "<<ComboboxSelected>>",
            self._resolution_changed,
        )

        slider_header = tk.Frame(controls, bg=PANEL)
        slider_header.pack(fill="x", padx=18)

        self._label(
            slider_header,
            "Eye sensitivity",
            size=10,
        ).pack(side="left")

        self._label(
            slider_header,
            textvariable=self.threshold_text_var,
            color=WHITE,
            size=10,
            bold=True,
        ).pack(side="right")

        self.threshold_slider = ttk.Scale(
            controls,
            from_=0.12,
            to=0.32,
            variable=self.sensitivity_var,
            command=self._sensitivity_changed,
        )
        self.threshold_slider.pack(
            fill="x",
            padx=18,
            pady=(12, 4),
        )

        self._label(
            controls,
            "Lower values are more sensitive.",
            color=GRAY,
            size=8,
            wraplength=330,
            justify="left",
        ).pack(anchor="w", padx=18, pady=(2, 16))

        # Alarm panel
        alarm_panel = self._panel(side)
        alarm_panel.grid(
            row=2,
            column=0,
            sticky="ew",
            pady=(0, 14),
        )

        self._label(
            alarm_panel,
            "AUDIO ALERT",
            color=GRAY,
            size=9,
            bold=True,
        ).pack(anchor="w", padx=18, pady=(14, 8))

        self.alarm_label = tk.Label(
            alarm_panel,
            textvariable=self.alarm_var,
            bg=PANEL,
            fg=GRAY,
            font=("Segoe UI", 13, "bold"),
            anchor="w",
        )
        self.alarm_label.pack(
            fill="x",
            padx=18,
            pady=(0, 12),
        )

        ttk.Button(
            alarm_panel,
            text="MUTE / STOP ALARM",
            style="Secondary.TButton",
            command=self._manual_stop_alarm,
        ).pack(fill="x", padx=16, pady=(0, 16))

        # Camera controls
        buttons = tk.Frame(side, bg=BLACK)
        buttons.grid(row=3, column=0, sticky="ew")
        buttons.columnconfigure(0, weight=1)
        buttons.columnconfigure(1, weight=1)

        self.start_button = ttk.Button(
            buttons,
            text="START CAMERA",
            style="Primary.TButton",
            command=self.start_monitoring,
        )
        self.start_button.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=(0, 6),
        )

        self.stop_button = ttk.Button(
            buttons,
            text="STOP MONITORING",
            style="Danger.TButton",
            command=self.stop_monitoring,
        )
        self.stop_button.grid(
            row=0,
            column=1,
            sticky="ew",
            padx=(6, 0),
        )

        # Bottom status bar
        status_bar = tk.Frame(
            self,
            bg="#101010",
            highlightbackground=BORDER,
            highlightthickness=1,
        )
        status_bar.pack(
            fill="x",
            padx=28,
            pady=(0, 10),
        )

        self._label(
            status_bar,
            "SYSTEM",
            bg="#101010",
            color=WHITE,
            size=9,
            bold=True,
        ).pack(side="left", padx=(14, 12), pady=12)

        self._label(
            status_bar,
            textvariable=self.status_var,
            bg="#101010",
            color=SOFT_WHITE,
            size=9,
            anchor="w",
            justify="left",
            wraplength=900,
        ).pack(
            side="left",
            fill="x",
            expand=True,
            pady=12,
            padx=(0, 12),
        )

        self._label(
            self,
            bg=BLACK,
            color=MID_GRAY,
            size=8,
        ).pack(pady=(0, 10))

    def _resolution_changed(self, _event=None) -> None:
        if self._monitoring:
            self.status_var.set(
                "Stop monitoring before changing camera resolution."
            )
            if self.worker:
                for label, size in (
                    self.config_data.resolution_modes.items()
                ):
                    if size == self.worker.requested_resolution:
                        self.resolution_var.set(label)
                        break

    def _sensitivity_changed(self, _value=None) -> None:
        value = round(float(self.sensitivity_var.get()), 3)
        self.threshold_text_var.set(f"{value:.3f}")

        if self.worker and self.worker.running:
            self.status_var.set(
                "Sensitivity changed. Restart monitoring to apply it."
            )

    def start_monitoring(self) -> None:
        if self._monitoring:
            return

        label = self.resolution_var.get()
        resolution = self.config_data.resolution_modes.get(
            label,
            self.config_data.preferred_resolution,
        )

        self._manual_mute = False
        self._last_state = "UNKNOWN"
        self.alarm.stop()

        self.worker = CameraWorker(
            self.config_data,
            resolution,
            float(self.sensitivity_var.get()),
        )

        self._monitoring = True
        self.status_var.set(
            "Starting camera and initializing eye detector..."
        )
        self.preview.configure(
            text="CONNECTING TO CAMERA...",
            image="",
        )
        self._photo = None
        self.worker.start()

    def stop_monitoring(self) -> None:
        self._monitoring = False
        self.alarm.stop()

        if self.worker:
            self.worker.stop()
            self.worker = None

        self._last_state = "UNKNOWN"
        self.state_var.set("UNKNOWN")
        self.state_badge.configure(bg="#252525", fg=WHITE)
        self.metric_var.set("EAR: —")
        self.fps_var.set("FPS  /  —")
        self.resolution_status_var.set("RESOLUTION  /  —")
        self.alarm_var.set("ALARM OFF")
        self.alarm_label.configure(fg=GRAY)
        self.preview.configure(
            image="",
            text="MONITORING STOPPED",
        )
        self._photo = None
        self.status_var.set(
            "Monitoring stopped. Camera and alarm released."
        )

    def _manual_stop_alarm(self) -> None:
        self._manual_mute = True
        self.alarm.stop()
        self.alarm_var.set("ALARM MUTED")
        self.alarm_label.configure(fg=WHITE)
        self.status_var.set(
            "Alarm muted manually. It will remain muted until "
            "the eye state changes or monitoring is restarted."
        )

    def _set_state(self, state: str) -> None:
        self.state_var.set(state)

        colors = {
            "OPEN": ("#222222", WHITE),
            "CLOSED": ("#401818", "#FF7777"),
            "UNKNOWN": ("#252525", WHITE),
        }
        bg, fg = colors.get(state, colors["UNKNOWN"])
        self.state_badge.configure(bg=bg, fg=fg)

    def _handle_packet(self, packet: FramePacket) -> None:
        self._last_packet = packet
        eye = packet.eye
        old_state = self._last_state
        self._last_state = eye.state

        self._set_state(eye.state)

        if eye.ear_average is None:
            self.metric_var.set(f"EAR: —  |  {eye.message}")
        else:
            self.metric_var.set(
                f"EAR AVG: {eye.ear_average:.3f}   "
                f"L: {eye.ear_left:.3f}   "
                f"R: {eye.ear_right:.3f}"
            )

        self.resolution_status_var.set(
            f"RESOLUTION  /  {packet.width} × {packet.height}"
        )
        self.fps_var.set(f"FPS  /  {packet.fps:.1f}")

        # Preserve the existing alarm behavior.
        if eye.state == "CLOSED":
            if not self._manual_mute:
                self.alarm.start()
        else:
            self.alarm.stop()
            if eye.state == "OPEN":
                self._manual_mute = False

        if self.alarm.active:
            self.alarm_var.set("ALARM PLAYING")
            self.alarm_label.configure(fg="#FF7777")
            self.status_var.set(
                "Eyes detected closed — alarm active."
            )
        elif self._manual_mute and eye.state == "CLOSED":
            self.alarm_var.set("ALARM MUTED")
            self.alarm_label.configure(fg=WHITE)
        else:
            self.alarm_var.set("ALARM OFF")
            self.alarm_label.configure(fg=GRAY)

            if eye.state == "UNKNOWN":
                self.status_var.set(
                    f"Detection unknown: {eye.message}. Alarm stopped safely."
                )
            elif eye.state == "OPEN":
                self.status_var.set("Eyes detected open. Alarm off.")
            elif old_state != "CLOSED":
                self.status_var.set("Eyes detected closed.")

        # Display the most recent camera frame.
        frame = packet.frame_bgr
        max_w = self.config_data.preview_max_width
        max_h = self.config_data.preview_max_height

        scale = min(
            max_w / frame.shape[1],
            max_h / frame.shape[0],
            1.0,
        )

        if scale < 1.0:
            frame = cv2.resize(
                frame,
                (
                    int(frame.shape[1] * scale),
                    int(frame.shape[0] * scale),
                ),
                interpolation=cv2.INTER_AREA,
            )

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(rgb)
        self._photo = ImageTk.PhotoImage(image=image)
        self.preview.configure(image=self._photo, text="")

    def _poll_worker(self) -> None:
        if self._closing:
            return

        worker = self.worker

        if worker:
            # Read worker messages without blocking the UI.
            while True:
                try:
                    message = worker.messages.get_nowait()
                except queue.Empty:
                    break

                if message.kind == "status":
                    self.status_var.set(message.message)

                elif message.kind == "error":
                    self.status_var.set(
                        f"Camera error: {message.message}"
                    )
                    self.alarm.stop()
                    self.alarm_var.set("ALARM OFF")
                    self.alarm_label.configure(fg=GRAY)

                elif message.kind == "traceback":
                    print(
                        "SleepGuard worker traceback:\n",
                        message.message,
                    )

                elif (
                    message.kind == "stopped"
                    and self._monitoring
                ):
                    self._monitoring = False
                    self.alarm.stop()

            latest = None

            while True:
                try:
                    latest = worker.frames.get_nowait()
                except queue.Empty:
                    break

            if latest is not None and self._monitoring:
                self._handle_packet(latest)

            if not worker.running and self._monitoring:
                self._monitoring = False
                self.alarm.stop()

        self.after(
            self.config_data.ui_refresh_ms,
            self._poll_worker,
        )

    def _on_close(self) -> None:
        self._closing = True
        self._monitoring = False
        self.alarm.stop()

        if self.worker:
            self.worker.stop()
            self.worker = None

        self.alarm.close()
        self.destroy()
