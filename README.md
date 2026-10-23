# SleepGuard Pro

A Windows desktop study-assistance prototype that monitors eye openness using a webcam and facial landmarks. Frames are processed locally; this application does not save or upload camera frames.

## Features

- Tkinter/ttk dark UI with teal accents.
- Built-in webcam index 0 by default.
- Requests a selected resolution (1080p, 720p, or 480p), then reports the actual frame dimensions.
- Background capture and inference worker; UI consumes only the newest queued frame to reduce stale-frame latency.
- Eye Aspect Ratio (EAR) for both eyes.
- Asynchronous looping Windows WAV alarm; repeated start requests do not create extra playback loops.
- Manual mute, safe stop on unknown face state, and cleanup on stop/window close.
- Diagnostic values: left EAR, right EAR, average EAR, state, actual resolution, FPS.

## Requirements

- Windows 10/11, 64-bit.
- CPython 3.12, 64-bit recommended.
- A webcam and working audio output.

Pinned package versions are selected for the CPython 3.12 Windows wheel ecosystem:
- `mediapipe==0.10.21`
- `opencv-python==4.10.0.84`
- `numpy==1.26.4`
- `Pillow==11.1.0`

MediaPipe's old `solutions.face_mesh` API is marked legacy by upstream, although it is present in the pinned release. It is used here to keep installation self-contained without requiring the user to download a separate `.task` model. For a long-lived production product, migrate to the maintained MediaPipe Tasks Face Landmarker API and distribute its model asset with the application.

## Installation (PowerShell or Command Prompt)

Open a terminal in the `SleepGuard_Pro` folder:

```powershell
py -3.12 --version
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main.py
```

If PowerShell blocks activation, either run this once for the current user if permitted:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Or use Command Prompt instead:

```bat
py -3.12 -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main.py
```

Do not install `opencv-python-headless` alongside `opencv-python`. They both provide the `cv2` module and can conflict.

## How to use

1. Sit facing the camera in even, front-facing light. Keep both eyes visible and remove anything that obscures the eye region.
2. Choose a capture resolution before starting. The app requests that mode but displays the dimensions actually delivered by the camera.
3. Click **START CAMERA**.
4. Watch the left/right EAR values while your eyes are open. Typical values vary by person, camera angle, lighting, and landmark quality.
5. To calibrate, try a threshold between `0.18` and `0.25`. Raise the threshold if normal open eyes are mistakenly classified as closed; lower it if normal open eyes trigger the alarm. Use small changes.
6. Test eye closure and reopening. Alarm playback starts when a processed valid frame classifies both eyes as closed, and stops on an open or unknown state.
7. **MUTE / STOP ALARM** silences the current closure event until the eyes are detected open again. Restart monitoring to clear mute immediately.
8. Click **STOP MONITORING** when finished.

## Algorithm

For each eye, six facial landmarks represent the eye corners and two pairs of upper/lower eyelid points. The Eye Aspect Ratio is:

`EAR = (distance(p2,p6) + distance(p3,p5)) / (2 × distance(p1,p4))`

When the eye is open, vertical eyelid distances are generally larger relative to eye width. When it closes, EAR generally decreases. SleepGuard calculates EAR for each eye and classifies `CLOSED` only when both values are below the configured threshold. If either eye is above threshold, the state is `OPEN`. If no face or reliable eye landmarks are available, the state is `UNKNOWN`; the alarm is stopped rather than treating unknown data as closed.

This is a heuristic, not a universal biological measurement. Head pose, glasses, low light, camera placement, facial differences, and brief blinks can cause false results. There is intentionally no programmed minimum closure duration, so blinks may trigger the alarm. Adding a debounce would reduce blink alarms but would violate the requested no-delay behavior.

## Testing checklist

- [ ] Start camera with the laptop built-in webcam.
- [ ] Stop monitoring and confirm camera indicator/resource is released.
- [ ] Test 1080p, 720p, and 480p; compare the displayed actual resolution with the selected mode.
- [ ] With eyes open, confirm state usually reads `OPEN`.
- [ ] Close both eyes briefly; confirm state changes to `CLOSED`.
- [ ] Confirm the alarm starts on the first processed closed-eye frame.
- [ ] Reopen eyes; confirm the alarm stops.
- [ ] Move out of frame; confirm state becomes `UNKNOWN` and the alarm stops.
- [ ] Trigger alarm and use **MUTE / STOP ALARM**; confirm sound stops.
- [ ] Test in dim and bright light; note misclassifications and tune threshold.
- [ ] Deny camera permission or open another app that owns the webcam; confirm an error is shown.
- [ ] Unplug/disable the camera while running; confirm the worker exits and audio stops.
- [ ] Close the window during monitoring; confirm the application exits and audio stops.

## Troubleshooting

### `No matching distribution found` or installation failure
Confirm the interpreter is 64-bit Python 3.12:
```powershell
python -c "import sys, platform; print(sys.version); print(platform.architecture())"
```
Use a fresh virtual environment and install only the pinned requirements. MediaPipe wheel availability varies by Python version and architecture.

### Camera cannot open
- Windows Settings → Privacy & security → Camera: allow camera access and desktop apps.
- Close Teams, Zoom, browsers, Camera app, or other applications using the webcam.
- Check Device Manager for a disabled or missing camera device.
- If your built-in camera is not index 0, change `camera_index` in `sleepguard/config.py` to `1` and restart.

### Actual resolution is lower than requested
The webcam driver may not support the requested dimensions or may return a different mode. The app reports the frame's actual dimensions rather than assuming the request succeeded. Try 720p or 480p.

### Alarm does not play
Check Windows output volume and output device. `winsound` is Windows-specific. The app generates a local WAV tone at startup; if audio initialization fails, inspect the status/console output.

### EAR state is inaccurate
Improve frontal lighting, position the camera near eye level, avoid strong backlighting, and ensure both eyes are visible. Adjust sensitivity in small increments. The value is diagnostic, not a medical measurement.

### Low FPS
Try 720p or 480p, close other camera applications, and ensure the laptop is not in a power-saving mode. FPS depends on the webcam, CPU, lighting, and model runtime.

## Known limitations and safety

- This is a study-assistance prototype, not a medical device and not a reliable guarantee against falling asleep.
- Eye closure alone cannot distinguish a normal blink, looking down, fatigue, or sleep.
- No intentional closure timer is used. Consequently, a short blink can sound the alarm.
- An `UNKNOWN` state stops the alarm for safety; therefore this application cannot guarantee a warning if tracking fails.
- It is not intended for driving or other safety-critical activities. Do not rely on it instead of adequate sleep and breaks.
