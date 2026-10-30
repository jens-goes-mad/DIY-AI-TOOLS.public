"""Subtitle files: per-story WebVTT (one cue per sentence, `<id>-<n>`, times
from the start of that story's narration), reading them back, and the
video's merged SRT."""

import re


def timestamp(ms: float) -> str:
    total = max(0, round(ms))
    h, rest = divmod(total, 3_600_000)
    m, rest = divmod(rest, 60_000)
    s, millis = divmod(rest, 1000)
    return f"{h:02}:{m:02}:{s:02}.{millis:03}"


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build(story_id: str, cues: list[tuple[float, float, str]]) -> str:
    """`cues`: (start_ms, end_ms, text) in order."""
    blocks = [
        f"{story_id}-{n}\n{timestamp(start)} --> {timestamp(end)}\n{_escape(text)}"
        for n, (start, end, text) in enumerate(cues, start=1)
    ]
    return "\n\n".join(["WEBVTT", *blocks]) + "\n"


_TIMING = re.compile(r"^(\d+):(\d{2}):(\d{2})\.(\d{3}) --> (\d+):(\d{2}):(\d{2})\.(\d{3})")


def _ms(h, m, s, millis) -> int:
    return ((int(h) * 60 + int(m)) * 60 + int(s)) * 1000 + int(millis)


def parse(text: str) -> list[tuple[float, float, str]]:
    """The cues of a file build() wrote: (start_ms, end_ms, text)."""
    cues = []
    for block in text.replace("\r\n", "\n").split("\n\n")[1:]:
        lines = [line for line in block.split("\n") if line]
        timing = next((i for i, line in enumerate(lines) if _TIMING.match(line)), None)
        if timing is None:
            continue
        g = _TIMING.match(lines[timing]).groups()
        body = "\n".join(lines[timing + 1:]).replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
        cues.append((_ms(*g[:4]), _ms(*g[4:]), body))
    return cues


def srt(cues: list[tuple[float, float, str]]) -> str:
    """SRT of (start_ms, end_ms, text) -- the whole video's subtitles."""
    def stamp(ms: float) -> str:
        return timestamp(ms).replace(".", ",")
    return "\n".join(f"{n}\n{stamp(a)} --> {stamp(b)}\n{t}\n" for n, (a, b, t) in enumerate(cues, start=1))
