"""`ai-tools` -- see README.md and docs/interface.md."""

import argparse
import os
import sys
import tempfile
from pathlib import Path

from . import audio, manifest, vtt
from .stories import Speech, ScriptError, normalize, parts, read_lexicon, read_stories, shown, split_sentences, spoken

DEFAULT_VOICES = {"en": "en_GB-cori-high"}  # STATE.md D17
DEFAULT_SENTENCE_PAUSE_MS = 500  # owner, 2026-10-30
DEFAULT_TEMPO = 0.85  # slower than the voice speaks by itself: tutorial reading (STATE.md D17)


def voices_dir() -> Path:
    return Path(os.environ.get("AI_TOOLS_VOICES", Path.home() / ".cache" / "ai-tools" / "voices"))


def cmd_tts(args) -> int:
    from . import piper_engine

    voice_name = args.voice or DEFAULT_VOICES.get(args.lang)
    if not voice_name:
        print(f"no default voice for --lang {args.lang}: give --voice", file=sys.stderr)
        return 2
    try:
        stories = read_stories(args.script)
        # --lexicon, else lexicon.json next to the script if there is one.
        lexicon_path = args.lexicon or Path(args.script).with_name("lexicon.json")
        lexicon = read_lexicon(lexicon_path) if args.lexicon or lexicon_path.exists() else {}
        if lexicon:
            print(f"lexicon: {lexicon_path} ({len(lexicon)} words)")
    except ScriptError as e:
        print(e, file=sys.stderr)
        return 2
    out = Path(args.dir) / "stories" / args.lang
    out.mkdir(parents=True, exist_ok=True)
    manifest_path = out / "manifest.json"
    old = manifest.load(manifest_path)

    if not 0.5 <= args.tempo <= 2.0:
        print("--tempo wants 0.5 .. 2.0", file=sys.stderr)
        return 2
    voice = {**piper_engine.describe(voice_name), "tempo": args.tempo, "sentencePauseMs": args.sentence_pause}
    engine = None  # loaded only when a story actually needs new audio
    entries, made, kept = {}, [], []
    for story in stories:
        # Over what is spoken: a lexicon change re-voices only the stories it touches.
        digest = manifest.story_hash(spoken(story.text, lexicon), voice)
        mp3, cues = out / f"{story.id}.mp3", out / f"{story.id}.vtt"
        previous = old["stories"].get(story.id)
        if previous and previous.get("hash") == digest and mp3.exists() and cues.exists():
            entries[story.id] = previous
            kept.append(story.id)
            continue
        if engine is None:
            engine = piper_engine.PiperEngine(voice_name, voices_dir(), args.tempo)
        # Per sentence: speech synthesized, [pause] markers as silence.
        sentences = split_sentences(story.text)
        pcm, spans = audio.assemble(
            [[engine.synthesize(spoken(p.text, lexicon)) if isinstance(p, Speech) else p.ms for p in parts(s)] for s in sentences],
            engine.sample_rate, args.sentence_pause)
        with tempfile.TemporaryDirectory() as tmp:
            wav = Path(tmp) / "story.wav"
            audio.write_wav(wav, pcm, engine.sample_rate)
            partial = out / f"{story.id}.partial.mp3"
            audio.wav_to_mp3(wav, partial)
            os.replace(partial, mp3)
        subtitles = [(*span, shown(s)) for span, s in zip(spans, sentences) if span is not None]
        cues.write_text(vtt.build(story.id, subtitles), encoding="utf-8")
        entries[story.id] = {"text": normalize(story.text), "hash": digest,
                             "ms": round(audio.to_ms(len(pcm), engine.sample_rate))}
        made.append(story.id)

    # Files of stories the script no longer has (only ids this tool wrote).
    for gone in set(old["stories"]) - set(entries):
        for ext in (".mp3", ".vtt"):
            (out / f"{gone}{ext}").unlink(missing_ok=True)

    manifest.save(manifest_path, {
        "version": manifest.MANIFEST_VERSION,
        "script": str(Path(args.script).resolve()),
        "lang": args.lang,
        "voice": voice,
        "stories": entries,
    })
    for story_id in entries:
        state = "new" if story_id in made else "unchanged"
        print(f"{story_id}: {entries[story_id]['ms'] / 1000:.2f} s ({state})")
    print(f"{len(made)} voiced, {len(kept)} unchanged -> {manifest_path}")
    return 0


def cmd_render(args) -> int:
    from .render import render

    render(Path(args.dir), args.lang, args.height)
    return 0


def cmd_voices(args) -> int:
    from . import piper_engine

    for name in args.download:
        piper_engine.ensure_voice(name, voices_dir())
    for model in sorted(voices_dir().glob("*.onnx")):
        print(model.stem)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="ai-tools", description="AI, audio and video tools (see README.md).")
    sub = parser.add_subparsers(dest="command", required=True)

    tts = sub.add_parser("tts", help="narrate a script's stories: one MP3 + VTT per story, plus manifest.json")
    tts.add_argument("script", help="the tutorial script (JSON); only its story steps are read")
    tts.add_argument("dir", help="the tutorial directory; writes stories/<lang>/")
    tts.add_argument("--lang", default="en", help="language of the script's texts (default: en)")
    tts.add_argument("--voice", help=f"Piper voice (default for en: {DEFAULT_VOICES['en']})")
    tts.add_argument("--sentence-pause", type=int, default=DEFAULT_SENTENCE_PAUSE_MS, metavar="MS",
                     help=f"silence between sentences (default: {DEFAULT_SENTENCE_PAUSE_MS})")
    tts.add_argument("--lexicon", type=Path, metavar="FILE",
                     help='pronunciations, {"word": "how to say it"} (default: lexicon.json next to the script, if any)')
    tts.add_argument("--tempo", type=float, default=DEFAULT_TEMPO,
                     help=f"speaking rate relative to the voice's own, 0.5-2.0 (default: {DEFAULT_TEMPO})")
    tts.set_defaults(run=cmd_tts)

    render = sub.add_parser("render", help="recording + narration -> out/<name>.<lang>.mp4 (+ .srt), for YouTube")
    render.add_argument("dir", help="the tutorial directory (recording.mov, recording.csv, stories/<lang>/)")
    render.add_argument("--lang", default="en", help="which narration (default: en)")
    render.add_argument("--height", type=int, default=1080, help="output height in pixels (default: 1080)")
    render.set_defaults(run=cmd_render)

    voices = sub.add_parser("voices", help="list downloaded voices; --download NAME fetches one")
    voices.add_argument("--download", action="append", default=[], metavar="NAME")
    voices.set_defaults(run=cmd_voices)

    args = parser.parse_args(argv)
    return args.run(args)


if __name__ == "__main__":
    sys.exit(main())
