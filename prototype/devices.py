"""Camera device enumeration (Linux-first, generic probe fallback).

OpenCV only knows integer indices; we additionally try to resolve human
readable names from the kernel on Linux so the user can recognise the AV350
vs. a laptop webcam.
"""
from __future__ import annotations

import glob
import os
import sys
from dataclasses import dataclass
from typing import List


@dataclass
class Device:
    index: int   # integer index passed to cv2.VideoCapture
    name: str    # human readable name (best effort)
    path: str = ""  # linux: /dev/videoN


def _v4l2_devices() -> List[Device]:
    devs: List[Device] = []
    for p in sorted(glob.glob("/sys/class/video4linux/video*")):
        idx = int(os.path.basename(p)[len("video"):])
        node = f"/dev/video{idx}"
        if not os.path.exists(node):
            continue
        try:
            with open(os.path.join(p, "name")) as fh:
                name = fh.read().strip()
        except OSError:
            name = "Unknown"
        devs.append(Device(index=idx, name=name, path=node))
    return devs


def _probe_devices(limit: int = 8) -> List[Device]:
    """Generic fallback: probe indices until one fails to open."""
    try:
        import cv2
    except Exception:  # pragma: no cover
        return []
    devs: List[Device] = []
    for i in range(limit):
        cap = cv2.VideoCapture(i)
        if cap is not None and cap.isOpened():
            cap.release()
            devs.append(Device(index=i, name=f"Camera {i}"))
        else:
            if cap is not None:
                cap.release()
            break
    return devs


def list_devices() -> List[Device]:
    devs = _v4l2_devices() if sys.platform.startswith("linux") else []
    if not devs:
        devs = _probe_devices()
    return devs


def find(devs: List[Device], index: int) -> Device:
    for d in devs:
        if d.index == index:
            return d
    return Device(index=index, name=f"Camera {index}")
