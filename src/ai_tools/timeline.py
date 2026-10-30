"""Where everything goes in the rendered video (RFC-001, "The freeze").

The recording has a 1 s gap per story (recording.csv). The output plays the
recording up to a gap, holds one frame from the middle of the gap for the
narration (plus a lead and a tail), then plays on from the gap's end.

Everything is planned in whole frames of a constant-rate copy of the
recording, so the times computed here are exactly the times in the video --
no rounding drift over many cuts.
"""

import csv
from dataclasses import dataclass
from pathlib import Path

LEAD_MS = 400   # box up before the voice starts
TAIL_MS = 700   # box stays after the voice ends


@dataclass(frozen=True)
class Gap:
    id: str
    start_ms: float
    end_ms: float


@dataclass(frozen=True)
class Clip:
    """Frames [first, first + count) of the recording, played as they are."""
    first: int
    count: int


@dataclass(frozen=True)
class Still:
    """Frame `frame` of the recording, held for `count` frames."""
    frame: int
    count: int
    story_id: str


@dataclass(frozen=True)
class Placed:
    """A story in the output: its freeze and when its voice starts (ms)."""
    story_id: str
    start_ms: float
    end_ms: float
    voice_ms: float


def read_gaps(path: Path) -> list[Gap]:
    """recording.csv (docs/interface.md), checked: ids unique, gaps in order
    and not overlapping."""
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    gaps = [Gap(r["id"], float(r["start_ms"]), float(r["end_ms"])) for r in rows]
    for prev, gap in zip(gaps, gaps[1:]):
        if gap.start_ms < prev.end_ms:
            raise ValueError(f"{path}: story {gap.id} starts before {prev.id} ends")
    if len({g.id for g in gaps}) != len(gaps):
        raise ValueError(f"{path}: a story id is listed twice")
    return gaps


def plan(gaps: list[Gap], narration_ms: dict[str, float], total_frames: int, fps: int,
         lead_ms: float = LEAD_MS, tail_ms: float = TAIL_MS) -> tuple[list, list[Placed], int]:
    """The pieces of the output in order (Clip / Still), each story's place
    in it, and the output's length in frames. `narration_ms`: per story id."""
    def frame(ms: float) -> int:
        return min(total_frames, max(0, round(ms * fps / 1000)))

    def ms(frames: int) -> float:
        return frames * 1000 / fps

    pieces, placed = [], []
    cursor = 0  # next recording frame to play
    out = 0     # output frames so far
    for gap in gaps:
        if gap.id not in narration_ms:
            raise ValueError(f"story {gap.id} is in the recording but has no narration")
        start, end = frame(gap.start_ms), frame(gap.end_ms)
        if start > cursor:
            pieces.append(Clip(cursor, start - cursor))
            out += start - cursor
        hold = max(1, round((lead_ms + narration_ms[gap.id] + tail_ms) * fps / 1000))
        pieces.append(Still(min(total_frames - 1, (start + end) // 2), hold, gap.id))
        placed.append(Placed(gap.id, ms(out), ms(out + hold), ms(out) + lead_ms))
        out += hold
        cursor = max(cursor, end)
    if total_frames > cursor:
        pieces.append(Clip(cursor, total_frames - cursor))
        out += total_frames - cursor
    return pieces, placed, out
