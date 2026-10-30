# STATE

Read this first. Plans and decisions for DIY-AI-TOOLS; the README says what
the project is.

## Status (2026-10-30)

**Phases 2 (`tts`) and 3 (`render`) built and verified** -- the first
finished video: `DIY-KRONOS-EDITOR.tutorials/tutorial/out/tutorial.en.mp4`.
Public repo: https://github.com/jens-goes-mad/DIY-AI-TOOLS.public (D14).

`render` verified on the same tutorial (15 s for a 37.6 s video):
- 1470x1080, 30 fps, H.264 + AAC; video and audio both 37.57 s.
- Voices start where planned: 0.917 s (planned 0.900 + Piper's ~15 ms
  lead-in) and 29.838 s (planned 29.830).
- Frames checked: box 90% wide, centred, orange at 80% (the app shows
  through), sized for its story's longest sentence; the recording's mark
  visible in the held frame; plain playback between stories.
- The recording is variable frame rate (68 frames in 10 s, none inside a
  gap), so `render` first makes a constant 30 fps copy -- every cut and
  held frame is then a whole frame.
- ffmpeg 5.1 pitfall: `apad` + `-shortest` with a filtergraph never stops
  (it wrote silence until killed); fixed with `apad=whole_dur` + `-t`.
- 16 unit tests pass in the image.

Verified on the Kronos `tutorial.json` (→ `DIY-KRONOS-EDITOR.tutorials/tutorial/`):
- 2 stories voiced in ~25 s including the first voice download; `welcome`
  24.08 s (3 sentence cues), `loaded` 3.83 s.
- Second run: both skipped by hash, 0.4 s, the model not loaded.
- MP3 timing: decoded sample counts equal the manifest's `ms` exactly
  (24083 / 3831 ms) -- the LAME header trims encoder delay and padding, so
  the narration starts where the subtitles say (speech begins ~15 ms in).
  ffprobe's container duration reads ~55 ms longer; that's only its
  frame-rounded estimate.
- 10 unit tests (stories, hash, manifest, VTT, joining) pass in the image.

## Decisions

```
D1  2026-10-30  Own generic project, not part of any app or app library: AI,
                audio and video tools in one Docker container with CLI
                commands (owner). It knows nothing about the apps.
D2  2026-10-30  Shared with the apps: the script (stays in the app's repo)
                and one tutorial directory -- recording.mov + recording.csv
                from the app, stories/<lang>/ (per-story MP3 + VTT +
                manifest) from here (docs/interface.md). MOV + CSV +
                stories/ are enough to render and re-render (owner).
D3  2026-10-30  No story box in the CHOC app any more; ffmpeg draws it
                (owner).
D4  2026-10-30  (replaced by D11) Voice first: TTS before recording, the
                MP3's length as the story's pause.
D5  2026-10-30  The recording reports only where each story is:
                recording.csv (id, start_ms, end_ms) (owner).
D6  2026-10-30  TTS skips a story whose hash (text + voice/engine settings)
                is unchanged (owner).
D7  2026-10-30  Piper is the default engine (owner). Default voice
                en_US-ljspeech-high: female, US English, reading style, its
                dataset (LJ Speech) public domain per its MODEL_CARD.
                Rejected: hfc_female (CC BY-NC-SA, non-commercial), amy (no
                licence on its card).
D8  2026-10-30  Kokoro-82M to try as a second engine, for its word-level
                timestamps (finer subtitle chunks, word highlighting) (owner).
D9  2026-10-30  Story text and narration are burned into one MP4 per
                language; it goes to YouTube, the Hugo docs sites link it
                (owner).
D10 2026-10-30  Scripts stay in the app's repo (committed); every tutorial's
                directory lives outside it -- for the Kronos editor in
                DIY-KRONOS-EDITOR.tutorials/<name>/ (owner).
D11 2026-10-30  A story is a 1-second gap in the recording; the render
                holds a frame from that gap as long as the narration needs.
                One recording serves every language and voice (owner).
D12 2026-10-30  The box: ffmpeg, orange rgb(255,140,0) at 80% opacity (the
                former in-app box's colour), 90% of the width, centred
                vertically, the subtitles on top of it (owner).
D13 2026-10-30  Captions and marks stay drawn in the app (owner) -- marks
                are language-free, captions stay in the recording's
                language.
D14 2026-10-30  DIY-AI-TOOLS becomes a public git repo later (owner).
D15 2026-10-30  Piper's licence verified: piper-tts 1.8.0 is GPL-3.0-or-later
                (its package METADATA). ai-tools imports it as a library
                (piper_engine.py -- only the API gives per-sentence audio),
                so the published repo is GPL-3.0-or-later (owner confirmed
                2026-10-30; LICENSE added). Sentences are split
                here and synthesized one by one, so every audio piece has
                its exact text for the subtitles.
D16 2026-10-30  Speech tempo 0.9 by default (owner: "a little slower"):
                Piper's length_scale = the voice's own (1) / 0.9; part of
                the hash. Measured on one sentence: 12.0 s -> 13.1 s (+9%).
                Piper varies sound lengths randomly per run (VITS noise), so
                one story's length differs by a few % on every re-voicing --
                harmless here, since the recording no longer depends on it.
D17 2026-10-30  New defaults after listening tests (owner): voice
                en_GB-cori-high (UK English, female, high quality; dataset
                LibriVox, public domain per its MODEL_CARD) at tempo 0.85,
                sentence pause 500 ms. Replaces D7's voice and D16's 0.9.
                Pronunciation lexicon (lexicon.json next to the script) for
                the app's words; the Kronos one: Kronos "KRON-oss", Combis
                "KOM-beeze", DIYKKE "D I Y, Korg Kronos Editor".
D18 2026-10-30  Box fade in/out, default 1 s (`render --fade MS`, owner). The
                text fades with the box (in with the first sentence, out with
                the last); the voice starts once the box is fully in and ends
                before it fades out -- lead/tail = max(0.4/0.7 s, fade).
                Checked: half-faded box and text at 1.0 s, voice from 1.55 s.
D19 2026-10-30  Tempo 0.88 by default (owner: 0.85 "a bit slow", 0.9 earlier a
                bit fast for cori).
D20 2026-10-30  Steadier rhythm by default: `--variation 0.33` (Piper's noise_w;
                cori's own 0.8). Measured on one sentence at tempo 0.88: 5 runs
                5.24-5.47 s (mean 5.32) vs 5.62-6.25 s (mean 5.89) -- less
                random spread and ~10% faster; the 0.85 -> 0.88 tempo step
                alone was only ~2%, hidden by cori's own variation (owner
                chose the steadier version after a comparison render).
```

## Next

1. Owner's review of the first video (voice, pauses, box look, font).
2. `check`; a git repo for this project; Kokoro as a second engine.

## Open

- Translated captions; whether `DIY-KRONOS-EDITOR.tutorials` gets a repo.

## Depends on (outside this repo)

- The apps' demo mode: story = 1 s gap without a box, the stories CSV
  next to the video (RFC-001, "Changes needed in the apps"). **Built
  2026-10-30** (not committed yet); the Kronos `tutorial.json` recorded with
  it: `recording.csv` = `welcome,505,1507` / `loaded,5276,6277`, nothing drawn
  in the gaps.
