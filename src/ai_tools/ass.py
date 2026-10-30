"""The story and chapter overlays as an ASS subtitle file, burned in by
ffmpeg (libass).

- A story: an orange box (STATE.md D12: rgb(255,140,0) at 80% opacity, 90%
  of the width, centred vertically, as high as its longest sentence needs),
  the sentence being spoken on top, black, centred.
- A chapter: the same box, but nearly the whole frame (10% margin on every
  side), and larger title text (D22).
- Several pages: each page's box stays while its sentences are spoken; then
  the next page's box flies in from the right, slowing down, going from
  invisible to 80%, while the old one speeds up and flies out to the left.
  The first page fades in, the last fades out (D18, D22).
- Rounded corners optional (the script's "render": {"rounded": true}).

Lines are wrapped here, not by libass (WrapStyle 2 = no automatic wrapping),
with the same font's real glyph widths -- so a story's box can be sized to
its longest sentence and keeps that size while the sentences change.
Movements are one event per video frame: libass only moves linearly, the
eased curves need the frames.
"""

from dataclasses import dataclass
from typing import Callable

FONT_NAME = "DejaVu Sans"
FONT_FILE = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

BOX_COLOUR = "&H008CFF&"      # BGR of rgb(255,140,0)
BOX_ALPHA = 0x33              # 80% opaque
TEXT_COLOUR = "&H000000&"     # black
DEFAULT_FADE_MS = 1000        # box and text fade in/out (owner, 2026-10-30)
FLY_MS = 800                  # a page change
FLY_SHARE = 0.6               # each box moves during this share of it
TITLE_SCALE = 1.8             # chapter text vs story text

Cue = tuple[float, float, str]  # start_ms, end_ms, text -- output time


@dataclass(frozen=True)
class Layout:
    width: int
    height: int

    @property
    def font_size(self) -> int:
        return round(self.height * 0.042)

    @property
    def title_size(self) -> int:
        return round(self.font_size * TITLE_SCALE)

    @property
    def line_height(self) -> float:
        return self.font_size * 1.35

    @property
    def box_x(self) -> int:
        return round(self.width * 0.05)

    @property
    def box_w(self) -> int:
        return round(self.width * 0.90)

    @property
    def pad_x(self) -> int:
        return round(self.font_size * 1.0)

    @property
    def pad_y(self) -> int:
        return round(self.font_size * 0.8)

    @property
    def radius(self) -> int:
        return round(self.font_size * 0.7)

    def chapter_box(self) -> tuple[int, int, int, int]:
        """x, y, w, h: 10% of the frame free on every side."""
        return (round(self.width * 0.1), round(self.height * 0.1),
                round(self.width * 0.8), round(self.height * 0.8))


@dataclass(frozen=True)
class StoryOverlay:
    start_ms: float          # the freeze
    end_ms: float
    pages: list[list[Cue]]   # per page its sentences, as spoken
    kind: str = "story"


def wrap(text: str, max_width: float, measure: Callable[[str], float]) -> list[str]:
    """Greedy word wrap; a word longer than a line gets a line of its own."""
    lines, line = [], ""
    for word in text.split():
        candidate = f"{line} {word}" if line else word
        if line and measure(candidate) > max_width:
            lines.append(line)
            line = word
        else:
            line = candidate
    if line:
        lines.append(line)
    return lines


def pillow_measure(font_size: int) -> Callable[[str], float]:
    from PIL import ImageFont

    font = ImageFont.truetype(FONT_FILE, font_size)
    return font.getlength


def box_path(w: int, h: int, r: int) -> str:
    """An ASS drawing of a w x h rectangle, corners rounded with radius r
    (cubic Béziers, the usual 0.552 circle approximation); r = 0: square."""
    if r <= 0:
        return f"m 0 0 l {w} 0 {w} {h} 0 {h}"
    r = min(r, w // 2, h // 2)
    c = round(r * (1 - 0.5523))
    return (f"m {r} 0 l {w - r} 0 b {w - c} 0 {w} {c} {w} {r} "
            f"l {w} {h - r} b {w} {h - c} {w - c} {h} {w - r} {h} "
            f"l {r} {h} b {c} {h} 0 {h - c} 0 {h - r} "
            f"l 0 {r} b 0 {c} {c} 0 {r} 0")


def _time(ms: float) -> str:
    cs = max(0, round(ms / 10))
    h, rest = divmod(cs, 360000)
    m, rest = divmod(rest, 6000)
    s, cs = divmod(rest, 100)
    return f"{h}:{m:02}:{s:02}.{cs:02}"


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "(").replace("}", ")")


def _transitions(pages: list[list[Cue]]) -> list[tuple[float, float]]:
    """(start, length) of each page change: FLY_MS (or less if the pause is
    shorter), centred in the pause between the pages' speech."""
    out = []
    for page, following in zip(pages, pages[1:]):
        end, start = page[-1][1], following[0][0]
        length = max(1.0, min(FLY_MS, start - end))
        out.append((end + (start - end - length) / 2, length))
    return out


def build(layout: Layout, stories: list[StoryOverlay], measure_for: Callable[[int], Callable[[str], float]],
          fade_ms: int = DEFAULT_FADE_MS, rounded: bool = False, fps: int = 30) -> str:
    """The ASS document. `measure_for(font_size)`: a text-width function."""
    events = []

    def box(layer, start, end, x, y, w, h, alpha=BOX_ALPHA, fade=(0, 0)):
        fad = f"\\fad({fade[0]},{fade[1]})" if any(fade) else ""
        events.append(f"Dialogue: {layer},{_time(start)},{_time(end)},Box,,0,0,0,,"
                      f"{{\\an7\\pos({x},{y})\\p1\\1a&H{alpha:02X}&{fad}}}"
                      f"{box_path(w, h, layout.radius if rounded else 0)}{{\\p0}}")

    def text(style, start, end, cx, cy, lines, alpha=0, fade=(0, 0)):
        fad = f"\\fad({fade[0]},{fade[1]})" if any(fade) else ""
        events.append(f"Dialogue: 1,{_time(start)},{_time(end)},{style},,0,0,0,,"
                      f"{{\\an5\\pos({cx},{cy})\\1a&H{alpha:02X}&{fad}}}" + "\\N".join(_escape(x) for x in lines))

    for story in stories:
        chapter = story.kind == "chapter"
        size = layout.title_size if chapter else layout.font_size
        measure = measure_for(size)
        if chapter:
            x, y, w, h = layout.chapter_box()
            pad = round(layout.pad_x * TITLE_SCALE)
        else:
            x, w, pad = layout.box_x, layout.box_w, layout.pad_x
        wrapped = [[(a, b, wrap(t, w - 2 * pad, measure)) for a, b, t in page] for page in story.pages]
        if not chapter:
            lines = max(len(ls) for page in wrapped for _, _, ls in page)
            h = round(lines * layout.line_height + 2 * layout.pad_y)
            y = round((layout.height - h) / 2)
        cx, cy = round(x + w / 2), round(y + h / 2)
        style = "Title" if chapter else "Text"

        # When each page stands still: the first from the freeze's start, the
        # last until its end; in between, the page changes.
        changes = _transitions(story.pages)
        arrive = [story.start_ms] + [t + length for t, length in changes]
        depart = [t for t, _ in changes] + [story.end_ms]
        last = len(wrapped) - 1
        for k, page in enumerate(wrapped):
            fade_in = fade_ms if k == 0 else 0
            fade_out = fade_ms if k == last else 0
            box(0, arrive[k], depart[k], x, y, w, h, fade=(fade_in, fade_out))
            for i, (a, _, ls) in enumerate(page):
                start = arrive[k] if i == 0 else a
                end = page[i + 1][0] if i + 1 < len(page) else depart[k]
                text(style, start, end, cx, cy, ls,
                     fade=(fade_in if i == 0 else 0, fade_out if i == len(page) - 1 else 0))

        # The page changes, frame by frame: out to the left speeding up, in
        # from the right slowing down and turning from invisible to 80%.
        for k, (t, length) in enumerate(changes):
            frames = max(1, round(length * fps / 1000))
            leaving, coming = wrapped[k][-1][2], wrapped[k + 1][0][2]
            for f in range(frames):
                t0, t1 = t + length * f / frames, t + length * (f + 1) / frames
                p = (f + 0.5) / frames
                # Staggered, so the boxes never overlap: the old one leaves in
                # the first FLY_SHARE of the change, the new one arrives in the
                # last FLY_SHARE; they share only the middle.
                p_out = min(1.0, p / FLY_SHARE)
                p_in = max(0.0, (p - (1 - FLY_SHARE)) / FLY_SHARE)
                out_dx = round(-(x + w) * p_out * p_out)           # ease-in: speeding up
                eased = 1 - (1 - p_in) ** 2                        # ease-out: slowing down
                in_dx = round((layout.width - x) * (1 - eased))
                box(0, t0, t1, x + out_dx, y, w, h)
                text(style, t0, t1, cx + out_dx, cy, leaving)
                box(0, t0, t1, x + in_dx, y, w, h, alpha=round(0xFF - (0xFF - BOX_ALPHA) * eased))
                text(style, t0, t1, cx + in_dx, cy, coming, alpha=round(0xFF * (1 - eased)))

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {layout.width}
PlayResY: {layout.height}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Box,{FONT_NAME},{layout.font_size},&H{BOX_ALPHA:02X}{BOX_COLOUR[2:-1]},&H00000000,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1
Style: Text,{FONT_NAME},{layout.font_size},&H00{TEXT_COLOUR[2:-1]},&H00000000,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,5,0,0,0,1
Style: Title,{FONT_NAME},{layout.title_size},&H00{TEXT_COLOUR[2:-1]},&H00000000,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,0,0,5,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    return header + "\n".join(events) + "\n"
