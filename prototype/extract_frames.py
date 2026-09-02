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

When a timestamp CSV is found next to the video, the frame's timestamps are
also embedded in each PNG as namespaced text metadata (keys
``goosegrabber.frame_idx/epoch_ns/mono_ns/iso_utc``). This is portable
annotation only -- the CSV remains the canonical source of truth.
"""
from __future__ import annotations

import argparse
import csv
import os
import sys

import cv2

try:
    from PIL import Image
    from PIL.PngImagePlugin import PngInfo
    _HAS_PIL = True
except Exception:  # pragma: no cover
    _HAS_PIL = False


_CSV_FIELDS = ("mono_ns", "epoch_ns", "iso_utc")


def _read_csv_rows(path: str):
    """frame_idx -> dict of timestamp fields ({} if unreadable)."""
    rows = {}
    try:
        with open(path, newline="") as fh:
            for row in csv.DictReader(fh):
                try:
                    idx = int(row["frame_idx"])
                except (KeyError, ValueError):
                    continue
                rows[idx] = {k: row.get(k, "") for k in _CSV_FIELDS}
    except OSError:
        return {}
    return rows


def _write_png(path: str, frame_bgr, meta) -> bool:
    """Lossless PNG. If Pillow + per-frame metadata are available, embed the
    timestamps as namespaced PNG text chunks (annotation only).
    Falls back to cv2.imwrite (plain PNG) otherwise."""
    if _HAS_PIL and meta:
        img = Image.fromarray(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
        info = PngInfo()
        for k, v in meta.items():
            info.add_text(f"goosegrabber.{k}", str(v))
        try:
            img.save(path, format="PNG", pnginfo=info)
            return True
        except Exception as exc:  # pragma: no cover
            print(f"  [warn] metadata write failed ({exc}); writing plain PNG")
    return cv2.imwrite(path, frame_bgr)


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
    times = _read_csv_rows(csv_path) if csv_path else {}

    exported = []
    i = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if start <= i and (end is None or i <= end):
                out = os.path.join(outdir, f"frame_{i:05d}.png")
                meta = times.get(i) if times else None
                if not _write_png(out, frame, meta):
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
            t_first = (times.get(first) or {}).get("iso_utc", "?")
            t_last = (times.get(last) or {}).get("iso_utc", "?")
            print(f"  frame {first}  UTC {t_first}")
            print(f"  frame {last}  UTC {t_last}")
            print("  (timestamps also embedded in each PNG as goosegrabber.* metadata)")
        else:
            print("  (no timestamp CSV found next to the video;")
            print("   pass --csv to print UTC times for the exported frames)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
