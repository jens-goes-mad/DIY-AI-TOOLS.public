"""`ai-tools render`: recording + stories → the finished video (RFC-001).

1. The recording (variable frame rate: the recorder only delivers frames when
   the window changes) becomes a constant-rate copy at the output height, so
   every cut and every held frame is a whole frame (timeline.py).
2. One ffmpeg run: the clips and the held frames concatenated, the overlay
   (ass.py) burned in, each story's narration placed at its voice start.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from . import ass, manifest, timeline, vtt

FPS = 30


def _run(cmd: list[str]) -> None:
    subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", *cmd], check=True)


def _probe_video(path: Path) -> tuple[int, int, int]:
    """(width, height, frame count) of a video's first stream."""
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
         "-show_entries", "stream=width,height,nb_read_frames", "-of", "json", str(path)],
        check=True, capture_output=True, text=True).stdout
    stream = json.loads(out)["streams"][0]
    return int(stream["width"]), int(stream["height"]), int(stream["nb_read_frames"])


def _seek(frame: int) -> str:
    """-ss for the input so its first decoded frame is exactly `frame`."""
    return f"{max(0.0, (frame - 0.5) / FPS):.4f}"


def render(directory: Path, lang: str, height: int, fade_ms: int = ass.DEFAULT_FADE_MS) -> Path:
    directory = Path(directory)
    stories_dir = directory / "stories" / lang
    data = manifest.load(stories_dir / "manifest.json")
    if not data["stories"]:
        raise SystemExit(f"{stories_dir}: no narration -- run `ai-tools tts` first")
    gaps = timeline.read_gaps(directory / "recording.csv")
    missing = [i for i in data["stories"] if i not in {g.id for g in gaps}]
    if missing:
        raise SystemExit(f"not in the recording: {', '.join(missing)} -- record the script again")

    out_dir = directory / "out"
    out_dir.mkdir(exist_ok=True)
    video = out_dir / f"{directory.name}.{lang}.mp4"

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        cfr = tmp / "cfr.mp4"
        print(f"constant {FPS} fps copy at {height} px ...", file=sys.stderr)
        _run(["-i", str(directory / "recording.mov"), "-an",
              "-vf", f"fps={FPS},scale=-2:{height}:flags=lanczos",
              "-c:v", "libx264", "-preset", "veryfast", "-crf", "12", "-g", str(FPS), str(cfr)])
        width, height, total = _probe_video(cfr)

        narration = {i: s["ms"] for i, s in data["stories"].items()}
        # The voice starts once the box has faded in and ends before it fades
        # out: lead and tail at least as long as the fade.
        pieces, placed, out_frames = timeline.plan(gaps, narration, total, FPS,
                                                   lead_ms=max(timeline.LEAD_MS, fade_ms),
                                                   tail_ms=max(timeline.TAIL_MS, fade_ms))

        # The overlay and the SRT, in output time.
        overlays, srt_cues = [], []
        for p in placed:
            cues = [(p.voice_ms + a, p.voice_ms + b, t)
                    for a, b, t in vtt.parse((stories_dir / f"{p.story_id}.vtt").read_text(encoding="utf-8"))]
            srt_cues += cues
            # On screen: each sentence until the next starts; the first from the
            # box's start, the last until the box goes.
            shown = [(p.start_ms if n == 0 else a,
                      cues[n + 1][0] if n + 1 < len(cues) else p.end_ms, t)
                     for n, (a, b, t) in enumerate(cues)]
            overlays.append(ass.StoryOverlay(p.start_ms, p.end_ms, shown))
        layout = ass.Layout(width, height)
        overlay = tmp / "overlay.ass"
        overlay.write_text(ass.build(layout, overlays, ass.pillow_measure(layout.font_size), fade_ms), encoding="utf-8")
        (out_dir / f"{directory.name}.{lang}.srt").write_text(vtt.srt(srt_cues), encoding="utf-8")

        # One input per piece (each seeked to its first frame), then the voices.
        inputs, chains, labels = [], [], []
        for k, piece in enumerate(pieces):
            if isinstance(piece, timeline.Clip):
                inputs += ["-ss", _seek(piece.first), "-i", str(cfr)]
                chains.append(f"[{k}:v]trim=end_frame={piece.count},setpts=PTS-STARTPTS[v{k}]")
            else:
                inputs += ["-ss", _seek(piece.frame), "-i", str(cfr)]
                chains.append(f"[{k}:v]trim=end_frame=1,setpts=PTS-STARTPTS,"
                              f"tpad=stop_mode=clone:stop={piece.count - 1}[v{k}]")
            labels.append(f"[v{k}]")
        chains.append(f"{''.join(labels)}concat=n={len(pieces)}:v=1:a=0,ass={overlay}[v]")

        first_audio = len(pieces)
        voices = []
        for n, p in enumerate(placed):
            inputs += ["-i", str(stories_dir / f"{p.story_id}.mp3")]
            chains.append(f"[{first_audio + n}:a]adelay=delays={round(p.voice_ms)}:all=1[a{n}]")
            voices.append(f"[a{n}]")
        # Mixed as they are (normalize=0: no level change), then silence up to
        # exactly the video's length. Not apad + -shortest: with a filtergraph
        # output this ffmpeg (5.1) never stops and writes silence forever.
        duration = out_frames / FPS
        mix = f"amix=inputs={len(voices)}:normalize=0:duration=longest" if len(voices) > 1 else "anull"
        chains.append(f"{''.join(voices)}{mix},apad=whole_dur={duration:.3f}[a]")

        partial = out_dir / f"{directory.name}.{lang}.partial.mp4"
        print(f"rendering {len(placed)} stories, {out_frames / FPS:.1f} s ...", file=sys.stderr)
        _run([*inputs, "-filter_complex", ";".join(chains), "-map", "[v]", "-map", "[a]",
              "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(FPS),
              "-c:a", "aac", "-b:a", "160k", "-t", f"{duration:.3f}", "-movflags", "+faststart", str(partial)])
        os.replace(partial, video)

    for p in placed:
        print(f"{p.story_id}: {p.start_ms / 1000:.2f}-{p.end_ms / 1000:.2f} s (voice from {p.voice_ms / 1000:.2f} s)")
    print(f"{out_frames / FPS:.1f} s, {width}x{height} -> {video}")
    return video
