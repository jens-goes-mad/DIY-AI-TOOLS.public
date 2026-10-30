# DIY-AI-TOOLS

A Docker container with command-line tools for AI, audio and video work:
text-to-speech, subtitles, and ffmpeg rendering. Scripted from the shell or
Python, batch-friendly, no GUI. It knows nothing about any particular app.

**Status:** `tts` (Piper) and `render` work; `check` is planned. Read
`STATE.md` first, then the RFC in `docs/`.

## Use

Needs Docker. `bin/ai-tools` builds the image on first use and runs the
command in the container, on the current directory:

```sh
cd ~/projects        # holds DIY-AI-TOOLS, the app's repo and its tutorials folder
DIY-AI-TOOLS/bin/ai-tools tts \
    DIY-KRONOS-EDITOR/docs/howto/tutorial.json \
    DIY-KRONOS-EDITOR.tutorials/tutorial
# welcome: 24.08 s (new)
# loaded: 3.83 s (new)
DIY-AI-TOOLS/bin/ai-tools render DIY-KRONOS-EDITOR.tutorials/tutorial
# 37.6 s, 1470x1080 -> DIY-KRONOS-EDITOR.tutorials/tutorial/out/tutorial.en.mp4
```

- The first run downloads the voice (about 110 MB) into the Docker volume
  `ai-tools-voices`; later runs reuse it.
- A story whose text and voice are unchanged is skipped (its hash) -- a run
  with nothing to do doesn't even load the TTS model.
- Rhythm: `--variation` (Piper's noise_w), default 0.33 -- steadier than
  cori's own 0.8, less random drag, about 10% faster; `--variation 0.8` for
  cori's own livelier rhythm. Intonation: `--expression` (Piper's
  noise_scale), default 0.4 -- calmer, less theatrical than cori's own 0.667.
- Pauses: `--sentence-pause 600` (ms after every sentence, default 500);
  in a story's text `[pause]` (0.7 s), `[pause 2s]`, `[pause 500ms]`.
- Pronunciation: `lexicon.json` next to the script (or `--lexicon FILE`),
  `{"Combis": "Kombies", "Kronos": "[[kɹˈəʊnɒs]]"}` -- a respelling or raw
  phonemes (Piper's espeak IPA in `[[…]]`), whole words, case-sensitive.
  Spoken only; the subtitles keep the real spelling. `"DIY": ""` drops a
  word from the speech. A change re-voices only
  the stories containing the word.
- Stories and chapters: a step's text may be a list of pages -- they fly in
  from the right and out to the left; `chapter` steps are title cards
  (10% margin, larger text). `"render": {"rounded": true}` in the script (or
  `render --rounded`) rounds the box corners. See `docs/interface.md`.
- After changing the code or the Dockerfile: `AI_TOOLS_REBUILD=1 bin/ai-tools …`.
- Tests: `docker run --rm --entrypoint pytest ai-tools /opt/ai-tools/tests`
  (the pure parts, no TTS needed).

## First use: narrated tutorial videos

The DIY desktop apps (Kronos editor, Maschine editor, Metronome editor) can
record themselves playing a tutorial script (`--demo`). This project turns
such a recording into a finished video, in as many languages as wanted:

```
tutorial.json (in the app's repo)
      │  the app records once: every story is just a 1-second gap
      ▼
<tutorials>/<name>/recording.mov + recording.csv (where each gap is)

per language:
tutorial.json ──tts──▶ stories/<lang>/<id>.mp3 + <id>.vtt + manifest.json
                       (Piper, en_GB-cori-high at 88%; unchanged stories skipped)
      │ render: at each gap the frame is held as long as the narration,
      ▼         an orange box with the subtitles on top, the voice mixed in
<tutorials>/<name>/out/<name>.<lang>.mp4   ready for YouTube
```

The apps and this project share a script and a tutorial directory -- see
`docs/interface.md`. The recording is language-free: a new language or voice
is TTS + render, no new recording.

## Commands

| Command | | Does |
|---|---|---|
| `ai-tools tts <script.json> <dir> [--lang en] [--voice <name>] [--tempo 0.88] [--variation 0.33] [--expression 0.4] [--page-pause 1500] [--sentence-pause ms] [--lexicon file]` | **built** | one MP3 + VTT (a cue per sentence) per story, `stories/<lang>/manifest.json`; skips stories whose hash is unchanged |
| `ai-tools voices [--download <name>]` | **built** | list downloaded voices, fetch one |
| `ai-tools render <dir> [--lang en] [--height 1080] [--fade 1000] [--rounded]` | **built** | holds the frame at each story's gap for its narration, draws box + subtitles, mixes the voice → `out/<name>.<lang>.mp4` (+ `.srt`) |
| `ai-tools check <dir> <script.json>` | planned | does the recording still match the script (story ids, order)? |

## Code

| | |
|---|---|
| `src/ai_tools/stories.py` | the script's stories (the app's id rule), normalizing, sentence splitting |
| `src/ai_tools/manifest.py` | the manifest, the story hash |
| `src/ai_tools/vtt.py` | per-story WebVTT |
| `src/ai_tools/audio.py` | joining sentences with pauses, WAV, MP3 (ffmpeg) |
| `src/ai_tools/piper_engine.py` | Piper -- the only module importing it |
| `src/ai_tools/timeline.py` | where clips and held frames go, in whole frames |
| `src/ai_tools/ass.py` | the box and the subtitles as ASS, lines wrapped with the font's real widths |
| `src/ai_tools/render.py` | ffmpeg: constant-rate copy, clips + held frames, overlay, narration |
| `src/ai_tools/cli.py` | the commands |
| `Dockerfile`, `bin/ai-tools` | the image (Debian, ffmpeg 5.1, Python, Piper 1.8.0 and Pillow pinned, DejaVu fonts) and the host wrapper |

## Documents

| File | What |
|---|---|
| `STATE.md` | decisions, what's open, next steps |
| `docs/interface.md` | the contract with the apps: script and tutorial directory |
| `docs/rfc-001-narrated-tutorials.md` | the plan for narrated tutorial videos |

## Licence

GPL-3.0-or-later (`LICENSE`). `ai-tools` imports Piper (piper-tts,
GPL-3.0-or-later) as a library. Voices have licences of their own -- see
each voice's MODEL_CARD; the default `en_GB-cori-high` is public domain.
