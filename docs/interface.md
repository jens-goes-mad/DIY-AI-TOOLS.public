# Interface with the apps

DIY-AI-TOOLS and the apps (through their `--demo` recording mode) share a **script**
and a **tutorial directory**. No code, no library: either side can change
freely as long as these files stay as described.

```
<app repo>/…/tutorial.json        the script -- stays in the app's repo,      in
<app repo>/…/tutorial.de.json     a translation (same ids; only stories read) in
<app repo>/…/lexicon.json         pronunciations of the app's words (optional) in

<tutorials folder>/<name>/        one directory per tutorial (not in a repo)
  recording.mov                   the recorded window: a 1 s gap per story,  app
                                  no story boxes
  recording.csv                   where each gap is                          app
  stories/<lang>/
    manifest.json                 ids, texts, hashes, durations              ai-tools
    <id>.mp3                      the narration of one story                 ai-tools
    <id>.vtt                      its subtitle cues, times from 0            ai-tools
  out/<name>.<lang>.mp4           the finished video (+ .srt)                ai-tools
```

For example, the Kronos editor keeps its scripts in its repo's
`docs/howto/` and the tutorial directories next to the repo, in
`DIY-KRONOS-EDITOR.tutorials/<name>/` (e.g. `tutorial/` for
`tutorial.json`).

**The recording is language-free.** `recording.mov` + `recording.csv` +
`stories/<lang>/` are everything a render needs; it never reads the script.
A new language or voice is TTS + render -- no new recording.

## The script

The app's demo script (its format is documented with the app's demo mode).
This project reads its **`story`** and **`chapter`** steps and its
**`render`** block:

```json
{
  "version": 1,
  "render": { "rounded": true },
  "steps": [
    { "chapter": ["Getting started", "Panes and datasets"], "id": "intro" },
    { "story": "Welcome to the tutorial. …", "id": "welcome" },
    { "story": ["First page …", "Second page …"], "id": "panes" }
  ]
}
```

- A step's text is one page (a string) or several (a list). Each page is
  spoken sentence by sentence; the box shows the sentence being spoken. With
  several pages the next page's box flies in from the right while the old
  one flies out to the left; the last page fades out.
- `story`: a box 90% wide, centred vertically, as high as its text needs.
  `chapter`: a title card -- the box leaves 10% of the frame free on every
  side, larger title text.
- `id`: unique in the script; names the files and the CSV row, and pairs a
  step with its translation. Without one: `story-<n>` / `chapter-<n>`, n
  counting that kind from 1 -- give explicit ids, since inserting a step
  would renumber the rest.
- In the recording a story or chapter is **one second of waiting**; the text
  is spoken and shown only in the render.
- **Pauses**: `[pause]` (0.7 s), `[pause 2s]`, `[pause 500ms]` (at most
  10 s) anywhere in the text -- silence in the narration there, neither
  spoken nor shown; a sentence with a pause inside stays one subtitle. Any
  other `[...]` is an error. Between sentences there is always
  `--sentence-pause` (500 ms), between pages `--page-pause` (1.5 s).
- `render` (optional): settings for the render -- `rounded` (box corners,
  default false). Unknown keys are an error. The app only checks that the
  block is an object.
- Every other step (click, type, open, caption, mark, …) is the app's
  business and is in the recording as it is.

## `recording.csv` -- written by the app

```
id,start_ms,end_ms
welcome,520,1520
loaded,6410,7410
```

Milliseconds from the first frame of `recording.mov`, one row per story in
script order. `end_ms - start_ms` is the gap (1000 ms, give or take a frame).
The render holds a frame from the middle of each gap for as long as the
narration needs.

Why the CSV is needed at all: everything **between** stories -- a file load,
a redraw -- takes a different time on every run, so only the recording knows
where each gap landed.

## `stories/<lang>/manifest.json` -- written by `ai-tools tts`

```json
{
  "version": 2,
  "script": "…/docs/howto/tutorial.json",
  "lang": "en",
  "voice": { "engine": "piper", "engineVersion": "1.8.0", "voice": "en_GB-cori-high", "…": "…" },
  "stories": {
    "welcome": {
      "kind": "story",
      "pages": [ { "text": "Welcome to …", "startMs": 0, "endMs": 9764 },
                 { "text": "The application …", "startMs": 11264, "endMs": 23501 } ],
      "hash": "sha256:9f2c…",
      "ms": 23501
    }
  }
}
```

- `pages`: each page's text and where its speech starts and ends in
  `<id>.mp3` -- the render groups the sentences into pages with it.
- `ms`: length of `<id>.mp3` -- how long the render holds that story's frame
  (plus a short lead and tail).
- `hash`: over the normalized text **and** engine, engine version, voice and
  its settings. `tts` skips a story whose hash and files are unchanged.

## `stories/<lang>/<id>.mp3` and `<id>.vtt`

One narration per story; its subtitle cues (one per sentence, or a few words
with word timestamps), timed from the start of that story's audio, cue ids
`<id>-1`, `<id>-2`, ….

## When to record again

- A non-story step changed, or stories were added, removed or reordered →
  **record again** (`ai-tools check` compares the CSV's ids with the script).
- Story text, voice, language, box look, subtitle style, mixing → **TTS
  and/or render only**.

## Versioning

`manifest.json` and the script carry a `"version"`. A change that breaks a
file raises its version, and both sides refuse versions they don't know.
