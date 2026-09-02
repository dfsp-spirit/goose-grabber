# goose-grabber prototype

**Throwaway.** Minimal, no-Qt prototype to validate at the brain imaging center:
pick the right camera **by image**, record H.264 video + a per-frame timestamp
CSV, and later extract frames from the encoded video at good quality.

Planned scope: **1 camera**, no session UI, no packaging. The full-featured app
is planned separately (see `dev_tools/planning/project_plan.md`).

## What it does

1. Enumerates cameras (Linux: from `/sys/class/video4linux`).
2. If several are found (AV350 + laptop cam …) it shows a **live preview window
   per camera** — click the window with the right image (or press its index).
3. Live preview with an on-screen HUD (never written into the saved frames).
4. Records **from selection until you quit** into:

```
recordings/run_<timestamp>/
  video.mp4            H.264, CRF ~15 (near-lossless)      [or video.avi = MJPG fallback]
  frames.csv           one row per frame: frame_idx, mono_ns, epoch_ns, iso_utc
  events.csv           'm' key = mark event (great for the sync test)
  ref_frames/          raw PNG every N frames (pre-encode, for quality comparison)
  meta.txt             camera + encode info
```

CSV row N == video frame N == timestamp N (written in the same loop), so the
CSV is the source of truth.

## Setup & run

```bash
cd prototype
uv sync                 # create .venv, install opencv-python + numpy
uv run python grabber.py --help
uv run python grabber.py                     # pick by image (needs a display)
uv run python grabber.py --camera 0          # skip picker, use /dev/video0
```

Keys: `m` = mark event · `q`/`ESC` = stop & quit.

### H.264 vs fallback

H.264/MP4 is used when a system `ffmpeg` with `libx264` is available
(`sudo apt install ffmpeg` on Debian/Ubuntu if not). Otherwise it falls back to
Motion-JPEG/AVI and prints a warning. MJPG is lower quality / much bigger files,
so for tomorrow's test install ffmpeg if possible.

## Extract frames from the recorded video

```bash
./extract_frames.sh video.mp4 100 200        # frames 100..200 -> frames_video/ next to the video
./extract_frames.sh video.mp4 100            # to the end
./extract_frames.sh video.mp4 100 200 -o out # custom output dir
```

- Output PNGs land in a `frames_<video-stem>/` folder **next to the video** (or `-o`).
- Each exported PNG also carries its frame's timestamps as **PNG text metadata** (keys `goosegrabber.frame_idx/epoch_ns/mono_ns/iso_utc`) — a portable annotation only; the CSV stays the canonical source of truth.

- Frame N == row N of `frames.csv` (recorded order).
- Output is lossless PNG (a good choice for goosebump analysis).
- If `frames.csv` sits next to the video it prints the UTC time of the first and
  last exported frame — handy for the sync check.
- `extract_frames.sh` runs through `uv`; if you prefer, call
  `uv run python extract_frames.py …` directly.

## Quality / sync test idea for tomorrow

1. Point the camera at something with a clock/stopwatch (or any event you can
   time visually).
2. Record; press `m` at the moment of a visible event.
3. Stop. Open `events.csv`: read the `epoch_ns` of your mark.
4. `./extract_frames.sh recordings/run_*/video.mp4 <row-of-mark> <row-of-mark>`
   and check the extracted PNG shows the event — this validates the
   timestamp↔frame mapping end-to-end.
5. For encode quality: compare `ref_frames/frame_*.png` (raw, pre-encode) with
   the extracted PNGs of the same index.

## Notes / simplifications vs. the full app

- Pure OpenCV (HighGUI), no Qt. Multi-window picker is clunky but fine for now.
- No session numbers / no GUI controls — recording is continuous once a camera
  is selected.
- Single camera only; the full app will be N-camera (this code is the seed).
- Timestamps: monotonic + UTC epoch ns per frame (two-clock scheme from the plan).
