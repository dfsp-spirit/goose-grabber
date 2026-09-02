
## Project Plan

> **Status: architecture proposal — not yet implemented.** This document summarizes the design discussions so far and is meant to be reviewed with the PI before we build.

### Goal & context

- The goose-grabber app runs on a **control computer in the scanner suite** and records video of the **participant's arm** (in the MRI scanner, fixed in place) for later **goosebump detection**.
- The camera is inside the scanner room; the app computer is outside. The video signal currently reaches the computer via a **Terratec Grabster AV350MX** USB analog grabber (composite/S-Video → ~640×480, 25 fps).
- Frame **timestamps must align with trial events** (e.g., when a scary image was shown) logged on the stimulus computer. Both computers are connected over a network cable and **time-synced via a local NTP server** (the local NTP server runs on a Windows box in the lab).
- End users (researchers / MRI operators) are **not technical**, and the app must run on **both Windows and Linux**.

### ⚠️ Open questions for the PI (before building)

1. **Camera & grabber quality.** The actual camera may be an expensive MR-compatible camera (possibly a "MRC Heidelberg" MRI camera). If so, we need its exact model and output interface, because:
   - The AV350MX is a cheap **analog composite** grabber. Going analog → 640×480 interlaced PAL almost certainly **degrades the camera's native output** (resolution, interlacing, added noise) and may be the wrong capture path entirely.
   - If the camera has a native **digital output** (SDI / HDMI / DVI / USB3 / FireWire), capturing that directly would preserve far more quality for subtle goosebump detection.
   - → *Ask PI: exact camera model, its output connector/format, and whether the AV350 path is actually required or just what was on hand.*
2. **Expected session length** (we assume long, 30–60+ min continuous runs) and frame rate.
3. **Who runs the app** and on which OS day-to-day (Windows and Linux are both first-class; we will test both).
4. **Analysis workflow**: confirm that extracting high-quality frames from a recorded video file is acceptable (vs. needing individual image files per frame).
5. **Multi-camera in the scanner?** This study previously ran *outside* the MRI scanner with **5 cameras at once** (2 arms, 2 legs, 1 neck). The PI says only **1** will be used in the scanner — this may be forced by MRI cabling/shielding rather than a real preference. → *Ask PI: could it ever be >1 in the scanner, and (if relevant) how was the outside 5-camera rig wired (one PC? how many USB grabbers/cards)?*

### Decisions made so far

| Topic | Decision |
|---|---|
| Language | **Python** (maintained by a scientific programmer; not C++/Rust) |
| Distribution | **PyInstaller** → single Windows `.exe` + Linux binary; **built automatically by GitHub Actions** on tag/release (no per-OS manual build) |
| GUI | **PySide6 (Qt), single window**: camera picker, editable session index, large live preview with fullscreen toggle, status banner |
| Camera selection | **By name, never by index** (indices shift on plug/unplug). Windows: DirectShow enumeration; Linux: V4L2/sysfs. Selection persisted; guardrails/warning so the built-in laptop camera can never silently replace the AV350 |
| Recording format | **One video file per session + a per-frame CSV sidecar** (not thousands of PNGs). Default: **near-lossless H.264 (CRF ≈ 15) in MKV via a bundled ffmpeg binary** (small files, frame-extractable). Fallback: Motion-JPEG in AVI (no extra dependency) |
| Timestamps | Two clocks per frame recorded in CSV: `monotonic_ns` (stable, detects dropped frames) + `epoch_ns` (**UTC wall clock, NTP-synced**, integer — merges cleanly with stimulus logs). Timestamps are written to the CSV / preview **only — never burned into saved frames** |
| Sync | CSV row N == video frame N == timestamp N (written in the same loop) → CSV is the source of truth for timing |
| Sessions / events | Editable, persisted session index (auto-increments); folder-per-session; keypresses & markers logged as timestamped events in `events.csv`; per-session `session.json` header |
| Logging | `goose-grabber.log` next to output for support ("send me the log") |
| Development | `--simulate` mode (synthetic frames) so the app can be developed/demoed without the hardware |

### Recording format & storage (estimate at 640×480, 25 fps, 60-min run)

| Format | ≈ size per 60-min run | Per-frame fidelity | Notes |
|---|---|---|---|
| Raw uncompressed | ~55–80 GB | exact | impractical |
| FFV1 lossless | ~30–70 GB | exact | wasteful on noisy analog source |
| PNG per frame | ~20–40 GB + ~90k files | exact | file-count & write-speed problems |
| **MJPG (q≈90) in AVI** | ~15–35 GB | high, frame-independent | zero extra deps; fallback mode |
| **H.264 CRF≈15 in MKV** (default) | ~2–5 GB | visually lossless | requires bundled ffmpeg |

Rationale: the source (analog composite) is the quality ceiling, so true lossless wastes disk encoding source noise. Goosebumps are luminance/texture, which near-lossless H.264 preserves well; any frame can be extracted from the MKV later at full stored quality. **Validate early** with a real recording that goosebumps survive the chosen codec before finalizing.

### Multi-camera ready (1..N)

> The app must support **any number of cameras (1..N)** without a redesign — the current plan assumes one camera; the outside-scanner version of this study used 5. A single-camera deployment is just the N=1 case. This is a modest generalization *now* (loop over a list, tile the preview) versus a rewrite of capture, UI, and file naming later.

**Architecture is camera-list based — nothing is ever hard-coded to "the" camera:**

- **Config**: `cameras: [ {device, label, …}, … ]` (a list; today it holds one entry).
- **Capture/recording**: one worker thread **per camera** (OpenCV `read()` is blocking, so cameras must not share a thread). Each worker has its own ffmpeg subprocess + `frames.csv`. All sample the **same shared clock** → frames across cameras are inherently aligned (no per-camera sync needed).
- **Files per session** (one session groups all cameras):
  ```
  session_NNN/
    session.json            # lists each camN → device + human label
    events.csv              # shared: keypresses/markers belong to the session
    cam0_video.mkv, cam0_frames.csv   # e.g. "arm-L"
    cam1_video.mkv, cam1_frames.csv   # e.g. "arm-R"
    ...
  ```
- **Preview**: single window, **tile grid** (1 cam = one tile = today's UI). Each tile carries an editable label ("ARM L", "NECK") so an operator always knows which feed is which. Same fullscreen toggle + status banner.
- **Session index & events stay single** — one session = one participant/run, grouped across cameras.

**Hardware feasibility — multiple USB grabbers on one PC (not one PC per camera):**

- One **USB 2.0 host controller** carries roughly **~20–24 MB/s** of isochronous video traffic total, shared by all devices on it. A single AV350 at 640×480@25 in uncompressed **YUYV is ≈15 MB/s** — two such streams already exceed one controller.
- ⇒ Multi-cam rig rules of thumb: **(1) spread grabbers across USB controllers** (different physical port groups / add-on controllers), not just across ports; **(2) use the grabber's MJPEG mode** if exposed (device-compressed, ~0.5–2 MB/s per noisy analog stream — many cheap grabbers only sustain full 25 fps in MJPEG anyway); **(3) a powered USB hub adds no bandwidth** (everything on it shares its single upstream link).
- Realistic outcome: **3 grabbers on one modern desktop = doable**; **5 = a stretch but feasible** with controller spreading and/or MJPEG mode.
- **Disk/CPU are not the bottleneck**: H.264 CRF≈15 at VGA is ~2–5 GB/hr *per camera* → 5 cams ≈ 10–25 GB/hr of sequential writes (trivial for an SSD). One veryfast H.264 encode at VGA is cheap; 5 concurrent encodes are fine.
- **Sync favors one PC over one-PC-per-camera**: all cameras share the same clock, so no cross-machine NTP between cameras is ever needed.
- *To determine:* what UVC formats the AV350 exposes (YUYV vs MJPEG), and how the previous 5-cam rig was actually wired (ask the lab tech / inspect the old data files).

### Proposed code layout

```
goose-grabber/
├─ goose_grabber/
│  ├─ __main__.py        # python -m goose_grabber entry point (CLI args, --simulate)
│  ├─ config.py          # app config (cameras list, output dir, session index, writer, codec…) JSON
│  ├─ clock.py           # monotonic + NTP wall-clock sampling (UTC epoch ns)
│  ├─ devices.py         # cross-platform camera enumeration (DirectShow / V4L2)
│  ├─ capture.py         # camera wrapper + SimulatedCamera
│  ├─ recorders.py       # FrameWriter: FFmpegWriter (MKV/H.264), MJPEGWriter (AVI)
│  ├─ index_writer.py    # frames.csv + events.csv writers (flushed)
│  ├─ session.py         # session folders, session.json, index handling
│  ├─ controller.py      # state machine: idle ↔ recording; wires cameras→recorders→CSVs
│  ├─ ui.py              # PySide6 main window + tile-grid preview + capture worker threads
│  └─ logging_setup.py
├─ tests/                # unit tests for pure logic (clock, config, csv, session)
├─ goose-grabber.spec    # PyInstaller spec (bundles ffmpeg + app)
├─ pyproject.toml / requirements.txt
├─ .github/workflows/build.yml   # builds Windows .exe + Linux binary, attaches to release
└─ README.md
```

### Proposed milestones (for review)

1. **Quality/format validation** on real hardware (does the AV350 + chosen codec preserve goosebumps? — do this *before* committing the format) — depends on the PI's camera answer.
2. Core capture → record → CSV pipeline with `--simulate` mode.
3. PySide6 GUI (camera picker, session index, preview, status, record start/stop, event marker).
4. Session/event handling + `session.json`.
5. GitHub Actions build of Windows + Linux binaries; first release to a guinea-pig user.
6. Optional future: stimulus computer sends a one-byte UDP event packet at stimulus onset for sub-ms alignment (beyond wall-clock merge).
