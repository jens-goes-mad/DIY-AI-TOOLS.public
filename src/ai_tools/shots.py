"""`ai-tools shots`: a screenshot of every mark in the recording -- for an
app's online documentation, made by the same run as its video.

A mark is a rectangle the app draws around an element; recording.marks.csv
(written by the app, docs/interface.md) says when each one was on screen.
Each becomes out/<name>-<nnn>.<lang>.jpg next to the video (nnn: the mark's
place in the script, from 001): the recording's frame from the middle of
that time, in the recording's own resolution -- the window as it looked,
mark included. The picture is the same in every language (the recording
is language-free); <lang> only names it like the video it belongs to.
"""

import sys
from pathlib import Path

from . import timeline
from .render import FPS, _run

# The app fades a mark in over 200 ms (its demo-runner's .demo-mark): never
# take a frame from before it is fully drawn.
FADE_IN_MS = 250
JPEG_QUALITY = 2  # ffmpeg -q:v, 2 = best .. 31
SEEK_BACK_S = 2.0  # see shots()


def shot_ms(mark: timeline.Gap) -> float:
    """When to take a mark's screenshot: the middle of its time on screen,
    but after its fade-in -- and never after it is gone."""
    return min(mark.end_ms, max(mark.start_ms + FADE_IN_MS, (mark.start_ms + mark.end_ms) / 2))


def shot_name(tutorial: str, number: int, lang: str) -> str:
    """out/'s file name of the `number`-th mark (from 1), like the video's."""
    return f"{tutorial}-{number:03d}.{lang}.jpg"


def shots(directory: Path, lang: str = "en") -> list[Path]:
    directory = Path(directory)
    marks_csv = directory / "recording.marks.csv"
    if not marks_csv.exists():
        raise SystemExit(f"{marks_csv} not found -- record again with an app that writes it")
    marks = timeline.read_times(marks_csv)
    out = directory / "out"
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob(f"{directory.name}-[0-9][0-9][0-9].{lang}.jpg"):  # no stale shots of removed marks
        old.unlink()
    written = []
    for number, mark in enumerate(marks, start=1):
        jpg = out / shot_name(directory.name, number, lang)
        # The recording only has a frame where the window changed, and a seek
        # lands on the first frame AFTER the time -- often the one where the
        # mark is already gone. So: seek a bit earlier, turn that into a
        # constant frame rate (like the render, holding each frame until the
        # next), and take the frame on screen at the time itself.
        at = shot_ms(mark) / 1000
        back = min(at, SEEK_BACK_S)
        _run(["-ss", f"{at - back:.3f}", "-i", str(directory / "recording.mov"),
              "-vf", f"fps={FPS}", "-ss", f"{back:.3f}",
              "-frames:v", "1", "-q:v", str(JPEG_QUALITY), str(jpg)])
        print(f"{mark.id}: {shot_ms(mark) / 1000:.2f} s -> {jpg.name}", file=sys.stderr)
        written.append(jpg)
    print(f"{len(written)} screenshots in {out}")
    return written
