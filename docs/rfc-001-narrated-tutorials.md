# RFC-001: narrated tutorial videos

Status: **proposed** (2026-10-30, third revision). Earlier drafts had the app
draw the story boxes, then had the narration set the pause lengths in the
recording -- both replaced by the freeze-frame model below.

## Goal

From a tutorial script (e.g. the Kronos editor's `docs/howto/tutorial.json`)
to a finished YouTube video: the recording, a spoken narration for every
story, the story text in an overlay -- and **the same recording reused for
every language and voice**.

## Decisions

1. **The app records, this project renders.** Recording needs the real screen
   and stays native in the app (`--demo`). Voice, overlays and mixing are file
   processing here, in a container.
2. **A story is a 1-second gap in the recording.** The app draws nothing for
   it and just waits one second. Every story is the same length on every run
   and in every language.
3. **The render freezes the frame for the narration.** At each story the
   render holds a frame from that gap for as long as that language's
   narration (plus a short lead and tail), lays the box and the subtitles
   over it and mixes the voice in. So the video's timeline depends on the
   language, the recording's doesn't.
4. **The recording reports where each gap is**: `recording.csv` (id, start,
   end). Everything between stories (file loads, redraws) varies per run.
5. **One recording, many renders.** A new language or voice = TTS + render;
   no new recording. Recording again is only needed when a non-story step,
   or the set or order of stories, changes.
6. **Only stories get audio.** TTS per story and language; a hash (text +
   voice/engine settings) skips unchanged stories.
7. **Box and text drawn by ffmpeg** -- no more story box in the CHOC app. An
   orange box (`rgb(255,140,0)`, 80% opacity, the in-app box's colour), 90% of
   the frame's width, centred vertically; the subtitles on top of it.
8. **Everything burned into one MP4 per language** for YouTube; the Hugo docs
   sites link it.
9. **Captions and marks stay in the app** (they're in the recording). Marks
   are language-free; captions are in the recording's language (see "Open").
10. **Scripts stay in the app's repo, generated material doesn't**: for the
    Kronos editor the scripts are in its repo's `docs/howto/`
    (committed), each tutorial's directory is
    `DIY-KRONOS-EDITOR.tutorials/<name>/`.
11. **Voice**: Piper by default, voice `en_GB-cori-high` at tempo 0.88 (STATE.md D17, D19; first choice was
    `en_US-ljspeech-high`); Kokoro to try.

## Pipeline

With `S=…/DIY-KRONOS-EDITOR/docs/howto` and
`T=…/DIY-KRONOS-EDITOR.tutorials/tutorial`:

```
once per recording:
  kronos_editor --demo $S/tutorial.json --demo-data … --demo-video $T/recording.mov
      → recording.mov (a 1 s gap per story, no boxes)
        recording.csv (where each gap is)

per language (English first):
  ai-tools tts    $S/tutorial.json $T --lang en      → $T/stories/en/<id>.mp3, <id>.vtt, manifest.json
  ai-tools render $T --lang en                        → $T/out/tutorial.en.mp4 (+ .srt)
```

`tts` and `render` don't depend on each other's run, only on their files:
re-render after changing the box look, re-voice after editing a story text --
the recording stays.

## The freeze

For story *i* with its gap at `[s, s + 1000 ms]` in `recording.mov` and
narration length `D`:

```
recording:  … ──────────── │ gap 1 s │ ─────────── …
output:     … ──────────── │ frame at s + 500 ms, held for lead + D + tail │ ─── …
                                       box + subtitles + voice
```

- The held frame is taken from the **middle of the gap**, so a pointer that
  just stopped or a redraw that just finished isn't caught half-way.
- The whole gap is replaced by the held frame; the video continues with the
  recording right after the gap.
- Lead and tail: about 300 ms each, so the box fades in before the voice
  starts and stays briefly after it ends.
- ffmpeg: the recording is cut at the gaps (`trim`), each held frame made
  with `tpad=stop_mode=clone` (or `loop` on one frame), everything joined with
  `concat`; the narration placed with `adelay` and mixed with `amix`. The
  per-story subtitle times are shifted to where that freeze lands in the
  **output**, which the render computes from the CSV and the durations.

## TTS per story

- Each story is split into sentences; every sentence is synthesized on its
  own and measured, then the sentences are joined with a short pause into
  `<id>.mp3`. That gives **exact** subtitle times per sentence in `<id>.vtt`.
- **Piper** by default: fast on the CPU (this Mac is an Intel i9 without an
  NVIDIA GPU, and Docker on macOS can't pass a GPU through anyway). Voice
  **`en_US-ljspeech-high`**: female, US English, high quality, trained on
  LJ Speech (non-fiction books read aloud, so a calm reading style), dataset
  **public domain** per its MODEL_CARD (checked 2026-10-30). Not chosen:
  `en_US-hfc_female-medium` (dataset CC BY-NC-SA 4.0, non-commercial -- risky
  on YouTube), `en_US-amy-medium` (its card names no licence).
- **Kokoro-82M** to try as a second engine: more natural English (Apache-2.0
  weights, female voices such as `af_heart`) and **word-level timestamps** --
  subtitles in chunks of a few words, or the spoken word highlighted. A second
  image target, since it pulls CPU PyTorch (about +2 GB). The timestamps to
  be confirmed when trying it.
- Voices are downloaded on first use into a Docker volume, never baked into
  the image.
- Hash = SHA-256 of the normalized text (whitespace collapsed) plus engine,
  engine version, voice and its settings.

## The box and the subtitles

- **Box**: ffmpeg `drawbox`, `x = 5% w`, width `90% w`, centred vertically,
  colour `0xFF8C00@0.8` (the in-app box's orange at 80% opacity), shown for
  the whole freeze, fading in and out (`--fade`, default 1 s); the text
  fades with it, and the voice waits until the box is fully there (lead and
  tail at least as long as the fade). Its height fits the
  story's longest subtitle cue, so it doesn't jump while the subtitles
  change inside it.
- **Subtitles on top**: ASS through libass, black text (as in the app box),
  centred in the box, margins inside the 90%; one cue per sentence (per few
  words with Kokoro). libass handles wrapping and umlauts.
- If the plain `drawbox` looks too square: the box as a PNG with rounded
  corners (Python, Pillow) laid on with `overlay` -- same position and colour.
- The video is Retina (2x): sizes are in video pixels, not window points.

## Output

- One H.264/AAC MP4 per language, `out/<name>.<lang>.mp4`, the recording's
  size scaled to fit 1080p if larger, story text and narration burned in --
  uploaded to YouTube as is. The Hugo docs sites link or embed it.
- Also `out/<name>.<lang>.srt` (output timeline), for YouTube's own captions
  if wanted later.

## Languages

A language = a translated script with the same ids (e.g.
`tutorial.de.json`, only its stories are read) → `tts --lang de` → `render
--lang de`. The recording is reused.

Exception: **captions** (decision 9) are in the recording and therefore in
its language. A translated video either keeps them as they are, or gets its
own recording with `--demo-captions de.vtt` (otherwise identical, unattended).

## The container

| | |
|---|---|
| Base | `debian:bookworm-slim`, amd64 (arm64 later for Apple Silicon) |
| Contents | ffmpeg (libx264, aac, libmp3lame, libass), Python 3, Piper |
| CLI | `ai-tools`, a Python package; every command usable on its own |
| Host wrapper | `bin/ai-tools`: `docker run --rm -v /Users:/Users -v ai-tools-voices:/voices ai-tools …` -- the project tree mounted at the **same path**, since a script (app repo) and its tutorial directory (`….tutorials/`) live in different places and the manifest records the script's path |
| Tests | the pure parts (script reading, hashing, CSV/VTT handling, the freeze timeline, filter-graph building) as plain `pytest` without Docker; render tests on tiny generated clips inside the container |

## Changes needed in the apps (their demo mode)

Small and generic -- they serve all three apps:

1. A `story` step: wait 1 second, draw nothing (the in-app story box goes
   away). Its reading-time duration and `for` no longer apply.
2. Write `recording.csv` next to the video (`--demo-video x.mov` → `x.csv`):
   `id,start_ms,end_ms` per story, times from the recording's first frame.
3. The `.vtt` keeps the captions; stories are no longer in it.

## Phases (each usable on its own)

1. **App side** (the apps' demo mode): story = 1 s gap, `recording.csv`. Record
   `tutorial.json` once.
2. **Container + `tts`** with Piper: per-story MP3 + VTT, manifest, hash skip.
3. **`render`**: freezes, box, subtitles, narration → MP4 for YouTube; `check`.
4. **Kokoro** as a second engine; a second language.
5. Optional: intro/outro cards, logo, background music with ducking, `make`
   (the whole chain).

## Settled (owner, 2026-10-30)

- Piper default; voice `en_GB-cori-high` at tempo 0.88 since D19 (was `en_US-ljspeech-high`); Kokoro to try.
- Text and audio burned in; YouTube, linked from Hugo.
- Box by ffmpeg, orange, 90% wide, centred vertically, 80% opacity,
  subtitles on top.
- Captions and marks stay in the app.
- One recording, frozen frames per story, per-language renders.
- Scripts in the app repo, tutorial directories in
  `DIY-KRONOS-EDITOR.tutorials/<name>/`.
- DIY-AI-TOOLS becomes a **public** git repo later.

## Open

1. **This repo's licence**: done -- GPL-3.0-or-later, like Piper, which
   `ai-tools` imports as a library (STATE.md D15).
2. **Before going public**: done -- the docs no longer use private paths.
3. **Translated captions**: keep the recording's captions in every language,
   or one recording per language when captions matter?
4. **`DIY-KRONOS-EDITOR.tutorials`**: no repo (videos are big), or one with
   Git LFS?
