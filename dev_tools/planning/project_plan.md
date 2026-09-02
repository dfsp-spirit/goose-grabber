
## Project Plan

> **Status: architecture proposal — not yet implemented.** This document summarizes the design discussions so far and is meant to be reviewed with the PI before we build.

### Goal & context

- The goose-grabber app runs on a **control computer in the scanner suite** and records video of the **participant's arm** (in the MRI scanner, fixed in place) for later **goosebump detection**.
- The camera is inside the scanner room; the app computer is outside. The camera is an **MRC Systems "12M" MR-compatible camera** (Heidelberg), digitized via a **Terratec Grabster AV350MX** USB grabber. Manual specs (confirmed): **color CMOS sensor 1/4" (active area 4.1×3.1 mm)**; output is an **analog composite video signal — PAL at 50 Hz field frequency (≈ 25 fps, interlaced) or NTSC at 60 Hz**. So the camera's native output is analog, VGA-class video; the AV350 is the correct digitizer (not a downgrade of any digital HD signal), and the 12M's premium is MR compatibility, not resolution.
- Frame **timestamps must align with trial events** (e.g., when a scary image was shown) logged on the stimulus computer. Both computers are connected over a network cable and **time-synced via a local NTP server** (the local NTP server runs on a Windows box in the lab).
- The lab currently owns a plain **12M** (no integrated LED); illumination is provided by **custom lab-built LEDs**. The PI plans to **order new / more cameras soon** — an opportunity to align the order with the study's needs (see *New camera order* below).
- End users (researchers / MRI operators) are **not technical**, and the app must run on **both Windows and Linux**.

### ⚠️ Open questions for the PI (before building)

1. **Camera & grabber quality — resolved.** Confirmed from the 12M manual: **color CMOS sensor, 1/4" (active area 4.1×3.1 mm)**; output is an **analog composite PAL video signal (50 Hz field frequency, ≈25 fps interlaced) or NTSC (60 Hz)**. So the AV350 digitizer is appropriate — it does *not* degrade a digital HD signal (there is none); VGA-class analog is the camera's native output.
   - *Current unit: plain **12M** (no integrated LED), lit by **custom lab-built LEDs** → the 12M vs 12M-i question is moot for today. However, the PI plans to order new cameras soon — see the camera-requirements checklist below.*
   - *Strategic note: if HD skin imaging were ever wanted, that means MRC's **HighResolution** camera (GigE Vision) → a network-camera capture path, entirely different from the USB grabber → out of scope for this app. Given the lab's HiSpeed experience (below), any MRC GigE route is a serious integration project — weigh it carefully before the PI orders.*
2. **Expected session length** (we assume long, 30–60+ min continuous runs) and frame rate.
3. **Who runs the app** and on which OS day-to-day (Windows and Linux are both first-class; we will test both).
4. **Analysis workflow**: confirm that extracting high-quality frames from a recorded video file is acceptable (vs. needing individual image files per frame).
5. **Multi-camera in the scanner?** This study previously ran *outside* the MRI scanner with **5 cameras at once** (2 arms, 2 legs, 1 neck). The PI says only **1** will be used in the scanner — this may be forced by MRI cabling/shielding rather than a real preference. → *Ask PI: could it ever be >1 in the scanner, and (if relevant) how was the outside 5-camera rig wired (one PC? how many USB grabbers/cards)?*

### New camera order (PI plans to buy more soon)

**Why it matters now:** the camera's output interface is a **fork in the app architecture**. Ordering more **12M** cameras keeps the analog-composite / USB-grabber capture path (this plan). Ordering MRC's HD **HighResolution** camera (or any digital/network camera) means **GigE Vision network capture** instead of USB grabbers — a different capture layer. We should know which way the PI is going *before* we finalize the capture code.

**Reality check from the lab (why analog/USB is the pragmatic default):** the lab already runs an MRC **HiSpeed** (GigE Vision) in another project, and it is a beast to handle: legacy C++ SDK/toolchain, C-style code, no OpenCV out of the box, and throughput that can saturate a 1 Gb link — running several is not realistic. MRC's **HighResolution** is HD at *moderate* frame rates (unlike HiSpeed's kHz rates), but it presumably shares the same SDK/integration burden. Implication: for multi-camera or easy-integration needs, the low-friction path is **analog-composite 12M-style cameras** (in-bore) or **standard USB3/UVC industrial cameras** (bench/outside; OpenCV-friendly out of the box) — not MRC's GigE line. If HD in the scanner ever becomes essential, budget for a dedicated integration effort, not a drop-in.

**Checklist to raise with the PI** (what "the right camera" means for goosebump detection in the scanner):
- **Color** — needed for skin tone/texture; rules out MRC's monochrome **HiSpeed**.
- **Resolution** — as high as MR-compatibility and bore space allow. VGA analog (12M) is a hard ceiling for subtle-skin detail; MRC's **HighResolution** (e.g., 1280×960/1280×720) would materially help detection.
- **Progressive scan (non-interlaced)** — cleaner frames than the 12M's interlaced PAL.
- **Frame rate** ≥ 25 fps, ideally 50–60 fps — better temporal resolution for aligning stimulus-onset events to frames.
- **Global shutter** — preferable (motion robustness; the arm is fixed, so less critical).
- **Lens / working distance** — close-focus lens + magnification for a small arm field of view.
- **Lighting** — lab LEDs exist, so an integrated-LED model is optional (only for reproducibility across sessions).
- **Interface decision (explicit)** — analog composite (keeps USB-grabber app) *vs* GigE Vision (network capture).
- **Intended deployment** — in-bore MR-compatible (MR constraints, waveguide cabling) *vs* bench/outside-scanner (unconstrained: any good USB3/industrial camera works, and need not be an MRC).
- **If >1 camera**: order identical models; verify how many MR-compatible cables can run through the waveguide.

**Action:** talk to the PI *before they place the order*. If HD/GigE is a real possibility, we should prototype/assess the GigE Vision capture path separately before building the app's capture layer around analog USB grabbers.

### Camera buying options (summary)

Two very different buying contexts — **in-bore (MR-compatible)** and **bench / outside-scanner (no MR constraints)** — each with its own sensible options. Frame the PI discussion around *which deployment(s) the new order is for* and *how many*.

| If the need is… | Buy | Capture path | Effort |
|---|---|---|---|
| More of the same, in-bore, for reliability/multi-cam | **MRC 12M** (analog composite) | USB grabber (this app) | Low — drop-in, already proven |
| In-bore with reproducible built-in lighting | **MRC 12M-i** | USB grabber (this app) | Low (moot if custom LEDs stay in use) |
| Genuine HD skin imaging, in-bore | **MRC HighResolution** (GigE Vision) | GigE Vision SDK — different from this app | **High — spike/prototype first** |
| Bench / outside-scanner rig (e.g., the 5-cam physiology rig) | **Standard USB3/UVC cameras** (need not be MRC) | UVC/USB3 (this app, N-camera-ready) | Low — OpenCV-friendly out of the box |

**Option A — more MRC 12M (recommended default for in-bore):** keeps the proven analog-composite/USB-grabber path, identical models for uniform processing, easy multi-cam (one grabber per camera, one USB controller per grabber as already done). Cost: stays VGA-analog-interlaced — fine if the PI accepts that ceiling for goosebump detection. Budget per analog camera also includes a **USB grabber + a PCIe USB controller card** once >1–2 grabbers share a PC.

**Option B — MRC HighResolution (only if there is a real HD requirement):** would genuinely help subtle skin detection (HD, progressive, global shutter, color). But per the lab's HiSpeed experience the MRC GigE line is a heavy integration (legacy C++ SDK, C-style code, no OpenCV, high throughput) and is **not a drop-in** for this app. If the PI wants it, treat it as a separate mini-project: run a capture spike first, then decide.

**Option C — bench/outside rig:** no MR constraints, so **don't buy MRC** — standard USB3 UVC cameras give far better resolution/fps per euro and work with this app's capture layer directly. USB3 bandwidth (~10× USB2) means many cameras per PC with far less controller juggling than the analog rig.

**Things to pin down before ordering** (ties into the checklist above): number of cameras; which deployment(s); in-bore cable count through the waveguide (limits how many MR-compatible cameras are physically feasible); and confirmation that the app's capture path (analog/USB vs anything GigE) matches the order.

### Decisions made so far

| Topic | Decision |
|---|---|
| Language | **Python** (not C++/Rust because that would be more effort, especially packaging, with little gain as we dont need super high performance (no live image detection during camera stream)) |
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

Interlacing note: the 12M outputs PAL at 50 Hz *field* rate (≈25 fps interlaced frames). Because the participant's arm is fixed in the scanner, motion/combing artifacts are negligible, so **no deinterlacing is planned** (can be added as an option if ever needed).

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
- The previous 5-cam rig is confirmed: a **dedicated recording workstation with many USB controllers, one camera per controller** — consistent with the bandwidth rules above.
- *Still to determine:* what UVC formats the AV350 exposes (YUYV vs MJPEG).

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

1. **Quality/format validation** on real hardware (does the AV350 + chosen codec preserve goosebumps on the MRC 12M's VGA analog feed? — do this *before* committing the format).
2. Core capture → record → CSV pipeline with `--simulate` mode.
3. PySide6 GUI (camera picker, session index, preview, status, record start/stop, event marker).
4. Session/event handling + `session.json`.
5. GitHub Actions build of Windows + Linux binaries; first release to a guinea-pig user.
6. Optional future: stimulus computer sends a one-byte UDP event packet at stimulus onset for sub-ms alignment (beyond wall-clock merge).
