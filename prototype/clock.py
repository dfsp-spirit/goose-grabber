"""Two-clock sampling for the prototype.

Every sample records BOTH:
  - ``mono_ns``   : time.monotonic_ns()  -> never jumps, good for deltas /
                    detecting dropped frames.
  - ``epoch_ns``  : time.time_ns()       -> NTP-synced UTC wall clock; this is
                    what aligns with the stimulus computer's trial logs.

Storing epoch ns as an integer avoids all timezone/format ambiguity later.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class Sample:
    mono_ns: int   # time.monotonic_ns() at sample time
    epoch_ns: int  # time.time_ns() at sample time (UTC)

    @property
    def iso_utc(self) -> str:
        return datetime.fromtimestamp(self.epoch_ns / 1e9, tz=timezone.utc).isoformat()


def now() -> Sample:
    """Sample both clocks back-to-back. The sub-100 us gap between them is
    negligible for ms-level work."""
    mono = time.monotonic_ns()
    epoch = time.time_ns()
    return Sample(mono_ns=mono, epoch_ns=epoch)


def iso_utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
