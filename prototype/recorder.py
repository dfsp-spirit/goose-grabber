"""Recording side of the prototype: timestamp CSVs + video writers.

Writer priority:
  1. H.264 in MP4 via a bundled/system ``ffmpeg`` subprocess (near-lossless,
     CRF ~ 15)  -- the format we want to quality-test tomorrow.
  2. Motion-JPEG in AVI via OpenCV  -- automatic fallback if ffmpeg is missing
     or cannot encode libx264.

The CSV is the source of truth: row N == video frame N == timestamp N,
because we write the CSV row and the video frame in the same loop.
"""
from __future__ import annotations

import csv
import os
import shutil
import subprocess
from typing import Optional, Tuple

from clock import Sample, now


class FrameCSV:
    def __init__(self, path: str):
        self._path = path
        self._fh = open(path, "w", newline="")
        self._w = csv.writer(self._fh)
        self._w.writerow(["frame_idx", "mono_ns", "epoch_ns", "iso_utc"])
        self._fh.flush()

    def write(self, frame_idx: int, s: Sample) -> None:
        self._w.writerow([frame_idx, s.mono_ns, s.epoch_ns, s.iso_utc])
        self._fh.flush()

    def close(self) -> None:
        self._fh.close()


class EventCSV:
    def __init__(self, path: str):
        self._fh = open(path, "w", newline="")
        self._w = csv.writer(self._fh)
        self._w.writerow(["seq", "event", "detail", "mono_ns", "epoch_ns", "iso_utc"])
        self._fh.flush()
        self._seq = 0

    def write(self, event: str, detail: str = "") -> None:
        s = now()
        self._w.writerow([self._seq, event, detail, s.mono_ns, s.epoch_ns, s.iso_utc])
        self._seq += 1
        self._fh.flush()

    def close(self) -> None:
        self._fh.close()


class H264Writer:
    """Feed raw BGR frames to ffmpeg/libx264 -> MP4 (yuv420p, faststart)."""

    def __init__(self, path: str, width: int, height: int, fps: float,
                 crf: int = 15, ffmpeg: str = "ffmpeg"):
        cmd = [
            ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            "-f", "rawvideo", "-pix_fmt", "bgr24",
            "-s", f"{width}x{height}", "-r", str(fps),
            "-i", "-",
            "-an",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf),
            "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            str(path),
        ]
        self._proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    def write(self, frame) -> None:
        if self._proc.stdin is None or self._proc.poll() is not None:
            raise RuntimeError("ffmpeg/libx264 exited early")
        self._proc.stdin.write(frame.tobytes())

    def close(self) -> None:
        if self._proc is None:
            return
        try:
            if self._proc.stdin is not None:
                self._proc.stdin.close()
            self._proc.wait(timeout=15)
        except Exception:
            try:
                self._proc.kill()
            except Exception:
                pass
        self._proc = None  # type: ignore[assignment]


class MJPGWriter:
    """OpenCV Motion-JPEG fallback (frame-independent, widely supported)."""

    def __init__(self, path: str, width: int, height: int, fps: float):
        import cv2
        fourcc = cv2.VideoWriter_fourcc(*"MJPG")
        self._vw = cv2.VideoWriter(str(path), fourcc, fps, (width, height))
        if not self._vw.isOpened():
            raise RuntimeError(f"cv2 MJPG writer could not open {path}")

    def write(self, frame) -> None:
        self._vw.write(frame)

    def close(self) -> None:
        self._vw.release()


def ffmpeg_has_libx264(ffmpeg: str) -> bool:
    try:
        out = subprocess.run([ffmpeg, "-hide_banner", "-encoders"],
                             capture_output=True, text=True, timeout=15).stdout
        return "libx264" in out
    except Exception:
        return False


def open_video_writer(stem: str, width: int, height: int, fps: float,
                      crf: int = 15) -> Tuple[object, str, str]:
    """Return (writer, kind, path). kind is 'h264' or 'mjpeg'."""
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg and ffmpeg_has_libx264(ffmpeg):
        try:
            mp4 = f"{stem}.mp4"
            return H264Writer(mp4, width, height, fps, crf=crf, ffmpeg=ffmpeg), "h264", mp4
        except Exception as exc:  # pragma: no cover
            print(f"  [warn] H.264 via ffmpeg failed ({exc}); falling back to MJPG/AVI")
    avi = f"{stem}.avi"
    return MJPGWriter(avi, width, height, fps), "mjpeg", avi


def csv_sidecar_for(video_path: str) -> Optional[str]:
    """frames.csv lives next to the video with the same stem."""
    base, _ = os.path.splitext(video_path)
    cand = f"{base}.csv"
    return cand if os.path.isfile(cand) else None
