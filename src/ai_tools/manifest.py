"""stories/<lang>/manifest.json (docs/interface.md): per story its text, hash
and narration length; plus which script, language and voice made it."""

import hashlib
import json
import os
from pathlib import Path

from .stories import normalize

MANIFEST_VERSION = 2  # 2: kind + pages per story (2026-10-30)


def story_hash(kind: str, pages: list[str], voice: dict) -> str:
    """SHA-256 over the kind, the normalized pages and everything about the
    voice (engine, its version, voice name, settings) -- a change to any of
    them means new audio."""
    payload = json.dumps({"kind": kind, "pages": [normalize(p) for p in pages], "voice": voice},
                         sort_keys=True, ensure_ascii=False)
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load(path: Path, rewriting: bool = False) -> dict:
    """The manifest at `path`, or an empty one if there is none (a first
    run). A manifest of another version is an error -- except for `tts`
    (`rewriting`), which simply voices everything again over an older one."""
    empty = {"version": MANIFEST_VERSION, "stories": {}}
    try:
        manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return empty
    if manifest.get("version") != MANIFEST_VERSION:
        if rewriting and isinstance(manifest.get("version"), int) and manifest["version"] < MANIFEST_VERSION:
            return empty
        raise ValueError(f"{path}: manifest version {manifest.get('version')!r}, this tool knows {MANIFEST_VERSION}"
                         + (" -- run `ai-tools tts` again" if manifest.get("version", 0) < MANIFEST_VERSION else ""))
    return manifest


def save(path: Path, manifest: dict) -> None:
    """Written through a temp file renamed at the end -- a crash never leaves
    a half-written manifest."""
    path = Path(path)
    partial = path.with_name(path.name + ".partial")
    partial.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(partial, path)
