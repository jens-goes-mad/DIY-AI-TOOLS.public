"""stories/<lang>/manifest.json (docs/interface.md): per story its text, hash
and narration length; plus which script, language and voice made it."""

import hashlib
import json
import os
from pathlib import Path

from .stories import normalize

MANIFEST_VERSION = 1


def story_hash(text: str, voice: dict) -> str:
    """SHA-256 over the normalized text and everything about the voice
    (engine, its version, voice name, settings) -- a change to any of them
    means new audio."""
    payload = json.dumps({"text": normalize(text), "voice": voice}, sort_keys=True, ensure_ascii=False)
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load(path: Path) -> dict:
    """The manifest at `path`, or an empty one if there is none (a first
    run). A manifest of an unknown version is an error, not overwritten."""
    try:
        manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"version": MANIFEST_VERSION, "stories": {}}
    if manifest.get("version") != MANIFEST_VERSION:
        raise ValueError(f"{path}: manifest version {manifest.get('version')!r}, this tool knows {MANIFEST_VERSION}")
    return manifest


def save(path: Path, manifest: dict) -> None:
    """Written through a temp file renamed at the end -- a crash never leaves
    a half-written manifest."""
    path = Path(path)
    partial = path.with_name(path.name + ".partial")
    partial.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(partial, path)
