#!/usr/bin/env bash
# Extract frames START..END (inclusive) from an encoded video as PNGs.
#
#   ./extract_frames.sh video.mp4 100 200
#   ./extract_frames.sh video.mp4 100 -o ./out
#
# Frame N == row N of the timestamp CSV written next to the video.
set -euo pipefail
cd "$(dirname "$0")"

if command -v uv >/dev/null 2>&1; then
  exec uv run python extract_frames.py "$@"
else
  echo "uv not found; running with python3 (deps must be installed)" >&2
  exec python3 extract_frames.py "$@"
fi
