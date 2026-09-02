"""goose-grabber PROTOTYPE -- minimal capture + timestamp recording.

Run:  uv sync  (once)   then:  uv run python grabber.py [options]

What it does:
  1. Enumerates cameras. If more than one is found (e.g. AV350 + laptop cam)
     it shows a live preview window per camera; CLICK the window whose image
     is the camera you want (or press its index digit). With exactly one
     camera it auto-selects.
  2. Shows a live preview with an on-screen HUD (never written into the file).
  3. Records continuously from selection until you quit:
       recordings/run_<timestamp>/
         video.mp4 (H.264, crf ~15)   or video.avi (MJPG fallback)
         frames.csv   one row per frame: frame_idx, mono_ns, epoch_ns, iso_utc
         events.csv   'm' marks an event (great for the sync test)
         ref_frames/  raw PNG of every Nth frame (pre-encode, for quality checks)
         meta.txt     camera + encode info

Keys:  m  = mark event       q / ESC  = stop & quit

Frame index in frames.csv == position of that frame in the video file,
so  ./extract_frames.sh video.mp4 100 200  exports exactly rows 100..200.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime

import cv2
import numpy as np  # noqa: F401  (opencv depends on it; keep explicit)

import clock
import devices
import recorder


def _pick_by_image(devs):
    """Show one live window per camera; click a window to select it."""
    opened = []  # (device, cap, window_name)
    for d in devs:
        cap = cv2.VideoCapture(d.index)
        if not cap.isOpened():
            cap.release()
            continue
        win = f"[{d.index}] {d.name or ('/dev/video%d' % d.index)}"
        cv2.namedWindow(win)
        opened.append((d, cap, win))

    if not opened:
        return None

    chosen = {"d": None}

    def make_cb(dev):
        def cb(event, *args):
            if event == cv2.EVENT_LBUTTONDOWN:
                chosen["d"] = dev
        return cb

    for d, _cap, win in opened:
        cv2.setMouseCallback(win, make_cb(d))

    try:
        while chosen["d"] is None:
            for d, cap, win in opened:
                ok, frame = cap.read()
                if not ok:
                    continue
                disp = frame.copy()
                cv2.putText(disp, "click to select", (8, 26),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2, cv2.LINE_AA)
                cv2.imshow(win, disp)
            key = cv2.waitKey(30) & 0xFF
            if key in (27, ord("q")):
                break
            if 48 <= key <= 57:
                digit = key - 48
                for d, _c, _w in opened:
                    if d.index == digit:
                        chosen["d"] = d
    finally:
        for _d, cap, _w in opened:
            cap.release()
        cv2.destroyAllWindows()
    return chosen["d"]


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="goose-grabber prototype")
    p.add_argument("--camera", type=int, default=None,
                   help="use this device index directly (skip the by-image picker)")
    p.add_argument("--out", default="recordings",
                   help="output directory (default: ./recordings)")
    p.add_argument("--crf", type=int, default=15,
                   help="x264 CRF for H.264 mode (default 15, near-lossless)")
    p.add_argument("--ref-every", type=int, default=25,
                   help="save a raw PNG reference frame every N frames (0 = off)")
    p.add_argument("--list", action="store_true", help="list cameras and exit")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)

    devs = devices.list_devices()
    print(f"Found {len(devs)} camera device(s):")
    for d in devs:
        print(f"   [{d.index}] {d.name}  ({d.path})")

    if args.list:
        return 0

    # --- choose a camera ------------------------------------------------
    if args.camera is not None:
        dev = devices.find(devs, args.camera)
        print(f"Using camera [{dev.index}] {dev.name}")
    elif len(devs) == 1:
        dev = devs[0]
        print(f"Only one camera; using [{dev.index}] {dev.name}")
    else:
        print("\nClick the preview window of the camera you want (or press its index).")
        dev = _pick_by_image(devs)
        if dev is None:
            print("No camera selected. Exiting.")
            return 1

    cap = cv2.VideoCapture(dev.index)
    if not cap.isOpened():
        print(f"[error] Could not open camera [{dev.index}] {dev.name}")
        return 1

    # --- output layout --------------------------------------------------
    os.makedirs(args.out, exist_ok=True)
    run_dir = os.path.join(args.out, "run_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
    os.makedirs(run_dir, exist_ok=True)
    ref_dir = os.path.join(run_dir, "ref_frames") if args.ref_every else None
    if ref_dir:
        os.makedirs(ref_dir, exist_ok=True)

    frames_csv = recorder.FrameCSV(os.path.join(run_dir, "frames.csv"))
    events_csv = recorder.EventCSV(os.path.join(run_dir, "events.csv"))

    # Learn the true frame size from one grab, then open the video writer.
    ok, probe = cap.read()
    if not ok:
        print("[error] Could not grab a frame from the camera.")
        return 1
    h, w = probe.shape[:2]
    fps = float(cap.get(cv2.CAP_PROP_FPS))
    if not (fps > 0 and fps <= 120):
        fps = 25.0

    writer, kind, video_name = recorder.open_video_writer(
        os.path.join(run_dir, "video"), w, h, fps, crf=args.crf)
    print(f"\nRecording to: {run_dir}")
    print(f"  mode : {kind}   resolution {w}x{h}   nominal {fps:.0f} fps")
    print("  keys : 'm' mark event   'q'/ESC quit")

    # --- meta -----------------------------------------------------------
    with open(os.path.join(run_dir, "meta.txt"), "w") as fh:
        fh.write(f"camera_index={dev.index}\n")
        fh.write(f"camera_name={dev.name}\n")
        fh.write(f"camera_path={dev.path}\n")
        fh.write(f"mode={kind}\n")
        fh.write(f"crf={args.crf}\n")
        fh.write(f"resolution={w}x{h}\n")
        fh.write(f"nominal_fps={fps}\n")
        fh.write(f"start={clock.iso_utc_now()}\n")

    events_csv.write("recording_started", f"camera=[{dev.index}] {dev.name} mode={kind}")

    # --- main loop ------------------------------------------------------
    win = "goose-grabber (prototype)"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)

    idx = 0
    t_last = time.monotonic()
    fps_ema = 0.0
    n_events = 0
    err: str | None = None

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                time.sleep(0.05)
                continue
            if frame.shape[:2] != (h, w):
                frame = cv2.resize(frame, (w, h))

            s = clock.now()
            writer.write(frame)          # may raise -> caught below
            frames_csv.write(idx, s)     # row idx == video frame idx
            if ref_dir and idx % args.ref_every == 0:
                cv2.imwrite(os.path.join(ref_dir, f"frame_{idx:06d}.png"), frame)
            idx += 1

            now_m = time.monotonic()
            dt = now_m - t_last
            t_last = now_m
            if dt > 0:
                inst = 1.0 / dt
                fps_ema = inst if fps_ema == 0 else 0.9 * fps_ema + 0.1 * inst

            # HUD (preview only -- never in the saved frames)
            disp = frame.copy()
            lines = [
                f"[{dev.index}] {dev.name}",
                f"{kind}  frames={idx}  ~{fps_ema:.1f} fps",
                f"UTC {s.iso_utc}",
            ]
            for i, txt in enumerate(lines):
                cv2.putText(disp, txt, (8, 26 + 24 * i), cv2.FONT_HERSHEY_SIMPLEX,
                            0.6, (0, 255, 0), 2, cv2.LINE_AA)
            cv2.imshow(win, disp)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
            if key == ord("m"):
                n_events += 1
                events_csv.write("mark", f"frame={idx - 1}")
                print(f"  [mark] at frame {idx - 1}  ({s.iso_utc})")

            if cv2.getWindowProperty(win, cv2.WND_PROP_VISIBLE) < 1:
                break
    except KeyboardInterrupt:
        pass
    except Exception as exc:  # e.g. ffmpeg died
        err = str(exc)
        print(f"\n[error] {exc}")
    finally:
        events_csv.write("recording_stopped", f"frames={idx} mode={kind}")
        try:
            writer.close()
        except Exception as exc:
            print(f"[warn] finalizing video failed: {exc}")
        frames_csv.close()
        events_csv.close()
        cap.release()
        cv2.destroyAllWindows()

    print(f"\nDone. {idx} frames -> {run_dir}")
    print(f"  video : {video_name}")
    print(f"  csv   : frames.csv ({idx} rows; row == frame index)")
    if n_events:
        print(f"  events: {n_events} mark(s) in events.csv")
    if err:
        print(f"  note  : recording ended with an error ({err}); CSV rows may exceed video frames.")
    return 0 if not err else 1


if __name__ == "__main__":
    sys.exit(main())
