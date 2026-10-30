"""The story overlay as an ASS subtitle file, burned in by ffmpeg (libass).

Per story: an orange box (STATE.md D12: rgb(255,140,0) at 80% opacity, 90%
of the width, centred vertically) for the whole freeze, and on top of it the
sentence being spoken, black, centred.

Lines are wrapped here, not by libass (WrapStyle 2 = no automatic wrapping),
with the same font's real glyph widths -- so the box can be sized to its
story's longest sentence and never changes size while the sentences change.
"""

from dataclasses import dataclass
from typing import Callable

FONT_NAME = "DejaVu Sans"
FONT_FILE = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

BOX_ASS_COLOUR = "&H33008CFF"   # &HAABBGGRR: alpha 0x33 = 80% opaque, BGR 00 8C FF = orange
TEXT_ASS_COLOUR = "&H00000000"  # black, opaque
FADE_MS = 150


@dataclass(frozen=True)
class Layout:
    width: int
    height: int

    @property
    def font_size(self) -> int:
        return round(self.height * 0.042)

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


def _time(ms: float) -> str:
    cs = max(0, round(ms / 10))
    h, rest = divmod(cs, 360000)
    m, rest = divmod(rest, 6000)
    s, cs = divmod(rest, 100)
    return f"{h}:{m:02}:{s:02}.{cs:02}"


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "(").replace("}", ")")


@dataclass(frozen=True)
class StoryOverlay:
    start_ms: float                          # the freeze
    end_ms: float
    cues: list[tuple[float, float, str]]     # sentences in output time


def build(layout: Layout, stories: list[StoryOverlay], measure: Callable[[str], float]) -> str:
    inner = layout.box_w - 2 * layout.pad_x
    events = []
    for story in stories:
        wrapped = [(a, b, wrap(text, inner, measure)) for a, b, text in story.cues]
        lines = max((len(w) for _, _, w in wrapped), default=1)
        box_h = round(lines * layout.line_height + 2 * layout.pad_y)
        box_y = round((layout.height - box_h) / 2)
        events.append(
            f"Dialogue: 0,{_time(story.start_ms)},{_time(story.end_ms)},Box,,0,0,0,,"
            f"{{\\an7\\pos({layout.box_x},{box_y})\\p1\\fad({FADE_MS},{FADE_MS})}}"
            f"m 0 0 l {layout.box_w} 0 {layout.box_w} {box_h} 0 {box_h}{{\\p0}}"
        )
        for a, b, w in wrapped:
            events.append(
                f"Dialogue: 1,{_time(a)},{_time(b)},Text,,0,0,0,,"
                f"{{\\an5\\pos({layout.width // 2},{layout.height // 2})}}" + "\\N".join(_escape(x) for x in w)
            )
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {layout.width}
PlayResY: {layout.height}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Box,{FONT_NAME},{layout.font_size},{BOX_ASS_COLOUR},{BOX_ASS_COLOUR},&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1
Style: Text,{FONT_NAME},{layout.font_size},{TEXT_ASS_COLOUR},{TEXT_ASS_COLOUR},&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,5,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    return header + "\n".join(events) + "\n"
