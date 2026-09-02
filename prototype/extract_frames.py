"""Extract a range of frames from an encoded video as PNG files.

Usage:
    uv run python extract_frames.py VIDEO START [END] [-o OUTDIR] [--csv frames.csv]

    VIDEO             recorded video (video.mp4 or video.avi)
    START, END        frame range, INCLUSIVE. Frame N == row N of the
                      timestamp CSV (i.e. recorded frame order).
                      END may be omitted or -1 to mean "until the end".
    -o OUTDIR         where the PNGs go (default: ./frames_<video-stem>)
    --csv FILE        optional timestamp CSV; prints the UTC time of the first
                      and last exported frame (auto-detected if it sits next
                      to the video with the same stem).

Files are written as frame_00000.png ... frame_000NN.png (lossless PNG).
"""
from __future__ import annotations

import argparse
import csv
import os
import sys

import cv2


def _read_csv_times(path: str):
    times = {}
    try:
        with open(path, newline="") as fh:
            for row in csv.DictReader(fh):
                try:
                    times[int(row["frame_idx"])] = row.get("iso_utc", "")
                except (KeyError, ValueError):
                    continue
    except OSError:
        return {}
    return times


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Export frames N..M from an encoded video as PNG")
    p.add_argument("video")
    p.add_argument("start", type=int)
    p.add_argument("end", type=int, nargs="?", default=-1)
    p.add_argument("-o", "--outdir", default=None)
    p.add_argument("--csv", default=None)
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        print(f"[error] cannot open video: {args.video}")
        return 1

    start, end = args.start, args.end
    if end < 0:
        end = None
    if end is not None and end < start:
        print("[error] END must be >= START")
        return 1

    stem = os.path.splitext(os.path.basename(args.video))[0]
    video_dir = os.path.dirname(os.path.abspath(args.video))
    outdir = args.outdir or os.path.join(video_dir, f"frames_{stem}")
    os.makedirs(outdir, exist_ok=True)

    # Auto-locate the timestamp CSV next to the video (same stem, or frames.csv).
    csv_path = args.csv
    if csv_path is None:
        base, _ = os.path.splitext(args.video)
        for cand in (f"{base}.csv", os.path.join(video_dir, "frames.csv")):
            if os.path.isfile(cand):
                csv_path = cand
                break
    times = _read_csv_times(csv_path) if csv_path else {}

    exported = []
    i = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if start <= i and (end is None or i <= end):
                out = os.path.join(outdir, f"frame_{i:05d}.png")
                if not cv2.imwrite(out, frame):
                    print(f"[error] failed to write {out}")
                    return 1
                exported.append((i, out))
            if end is not None and i >= end:
                break
            i += 1
    finally:
        cap.release()

    print(f"Exported {len(exported)} frame(s) to {outdir}/")
    if exported:
        first, _ = exported[0]
        last, _ = exported[-1]
        if times:
            t_first = times.get(first, "?")
            t_last = times.get(last, "?")
            print(f"  frame {first}  UTC {t_first}")
            print(f"  frame {last}  UTC {t_last}")
        else:
            print("  (no timestamp CSV found next to the video;")
            print("   pass --csv to print UTC times for the exported frames)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
