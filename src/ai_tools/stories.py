"""The stories of a tutorial script (docs/interface.md): ids, texts, sentences.

The script is the app's demo script; only its `story` steps matter here. Ids
follow the app's rule exactly: an explicit `id`, else `story-<n>` with n
counting stories from 1 -- so a row in the recording's CSV and a file here
always name the same story.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path

SCRIPT_VERSION = 1
ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


class ScriptError(ValueError):
    pass


@dataclass(frozen=True)
class Story:
    id: str
    text: str


# --- Pause markers -----------------------------------------------------------
#
# In a story's text: [pause] (PAUSE_DEFAULT_MS), [pause 2s], [pause 1.5s],
# [pause 500ms]. Silence in the narration at that point; neither spoken nor
# shown. Any other [...] is an error, so a typo is reported instead of read
# aloud.

PAUSE_DEFAULT_MS = 700
PAUSE_MAX_MS = 10_000
_MARKER = re.compile(r"\[([^\[\]]*)\]")
_PAUSE = re.compile(r"^\s*pause(?:\s+(\d+(?:\.\d+)?)\s*(ms|s))?\s*$", re.IGNORECASE)


@dataclass(frozen=True)
class Pause:
    ms: float


@dataclass(frozen=True)
class Speech:
    text: str


def _pause_ms(marker: str) -> float:
    match = _PAUSE.match(marker)
    if not match:
        raise ScriptError(f'unknown marker "[{marker}]" -- markers are [pause], [pause 2s], [pause 500ms]')
    value, unit = match.groups()
    ms = PAUSE_DEFAULT_MS if value is None else float(value) * (1000 if unit.lower() == "s" else 1)
    if ms > PAUSE_MAX_MS:
        raise ScriptError(f"[{marker}]: at most {PAUSE_MAX_MS // 1000} s")
    return ms


def parts(sentence: str) -> list[Pause | Speech]:
    """A sentence as speech and pauses, in order (empty speech dropped). A
    piece that is only punctuation ("Last [pause].") joins the speech before
    it -- nothing to synthesize on its own, and no "Last ." on screen."""
    items: list[Pause | Speech] = []

    def add(text: str) -> None:
        text = " ".join(text.split())
        if not text:
            return
        if not any(c.isalnum() for c in text):
            last = next((i for i in range(len(items) - 1, -1, -1) if isinstance(items[i], Speech)), None)
            if last is not None:
                items[last] = Speech(items[last].text + text)
            return
        items.append(Speech(text))

    start = 0
    for match in _MARKER.finditer(sentence):
        add(sentence[start:match.start()])
        items.append(Pause(_pause_ms(match.group(1))))
        start = match.end()
    add(sentence[start:])
    return items


# --- Pronunciation lexicon ---------------------------------------------------
#
# A JSON object word -> how to say it: a respelling the TTS reads right
# ("Combis": "Kombies") or raw phonemes ("Kronos": "[[kɹˈəʊnɒs]]", Piper's
# espeak IPA). Whole words, case-sensitive, longest first; applied to what
# is spoken only -- the subtitles keep the real spelling.

def read_lexicon(path: Path) -> dict[str, str]:
    try:
        lexicon = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise ScriptError(f"{path}: {e}") from e
    if not isinstance(lexicon, dict) or not all(isinstance(k, str) and k.strip() and isinstance(v, str) and v.strip()
                                                for k, v in lexicon.items()):
        raise ScriptError(f'{path}: wants a JSON object of "word": "how to say it"')
    return lexicon


def spoken(text: str, lexicon: dict[str, str]) -> str:
    """`text` with every lexicon word replaced by its pronunciation."""
    if not lexicon:
        return text
    words = sorted(lexicon, key=len, reverse=True)
    pattern = re.compile(r"(?<![\w-])(" + "|".join(re.escape(w) for w in words) + r")(?![\w-])")
    return pattern.sub(lambda m: lexicon[m.group(1)], text)


def shown(sentence: str) -> str:
    """The sentence as spoken and shown: markers out, spaces tidied."""
    return " ".join(item.text for item in parts(sentence) if isinstance(item, Speech))


def read_stories(path: Path) -> list[Story]:
    """The stories of the script at `path`, in script order."""
    try:
        script = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise ScriptError(f"{path}: {e}") from e
    if not isinstance(script, dict) or script.get("version") != SCRIPT_VERSION:
        raise ScriptError(f'{path}: not a version {SCRIPT_VERSION} script (no "version": {SCRIPT_VERSION})')
    steps = script.get("steps")
    if not isinstance(steps, list):
        raise ScriptError(f'{path}: no "steps" list')

    stories: list[Story] = []
    seen: set[str] = set()
    for index, step in enumerate(steps, start=1):
        if not isinstance(step, dict) or "story" not in step:
            continue
        where = f"{path}: step {index} (story)"
        text = step["story"]
        if not isinstance(text, str) or not text.strip():
            raise ScriptError(f"{where}: wants non-empty text")
        story_id = step.get("id", f"story-{len(stories) + 1}")
        if not isinstance(story_id, str) or not ID_PATTERN.match(story_id):
            raise ScriptError(f"{where}: id wants letters, digits, - or _")
        try:
            for match in _MARKER.finditer(text):
                _pause_ms(match.group(1))
        except ScriptError as e:
            raise ScriptError(f"{where}: {e}") from None
        if not shown(text):
            raise ScriptError(f"{where}: only pauses, nothing to say")
        if story_id in seen:
            raise ScriptError(f'{where}: id "{story_id}" is used twice')
        seen.add(story_id)
        stories.append(Story(story_id, text))
    return stories


def normalize(text: str) -> str:
    """Whitespace collapsed inside each paragraph; paragraphs (lines) kept,
    empty ones dropped. What gets spoken, hashed and shown."""
    lines = (" ".join(line.split()) for line in text.splitlines())
    return "\n".join(line for line in lines if line)


# A sentence ends at . ! ? or … followed by whitespace (closing quotes and
# brackets stay with it). Simple on purpose: "e.g. this" splits after "e.g."
# -- write such texts without the abbreviation, or accept a short cue.
_SENTENCE_END = re.compile(r"(?<=[.!?…])[\"'”’)\]]*\s+")


def split_sentences(text: str) -> list[str]:
    """The normalized text as sentences, paragraph by paragraph."""
    sentences: list[str] = []
    for paragraph in normalize(text).split("\n"):
        start = 0
        for match in _SENTENCE_END.finditer(paragraph):
            end = match.start() + len(match.group(0).rstrip())
            sentences.append(paragraph[start:end].strip())
            start = match.end()
        rest = paragraph[start:].strip()
        if rest:
            sentences.append(rest)
    return [s for s in sentences if s]
