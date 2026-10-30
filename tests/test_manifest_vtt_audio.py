import json

import pytest

from ai_tools import audio, manifest, vtt

VOICE = {"engine": "piper", "engineVersion": "1.8.0", "voice": "en_US-ljspeech-high", "sentencePauseMs": 350}


def test_hash_ignores_whitespace_but_not_words_pages_kind_or_voice():
    h = manifest.story_hash("story", ["Welcome  to the\ttutorial."], VOICE)
    assert h.startswith("sha256:")
    assert h == manifest.story_hash("story", [" Welcome to the tutorial. "], VOICE)
    assert h != manifest.story_hash("story", ["Welcome to the tutorial!"], VOICE)
    assert h != manifest.story_hash("chapter", ["Welcome to the tutorial."], VOICE)
    assert h != manifest.story_hash("story", ["Welcome to", "the tutorial."], VOICE)  # pages matter
    assert h != manifest.story_hash("story", ["Welcome to the tutorial."], {**VOICE, "voice": "en_US-amy-medium"})
    assert h != manifest.story_hash("story", ["Welcome to the tutorial."], {**VOICE, "sentencePauseMs": 300})


def test_manifest_round_trip_and_first_run(tmp_path):
    path = tmp_path / "manifest.json"
    assert manifest.load(path) == {"version": 2, "stories": {}}
    data = {"version": 2, "lang": "en", "voice": VOICE, "stories": {"welcome": {
        "kind": "story", "pages": [{"text": "Hi.", "startMs": 0, "endMs": 812}], "hash": "sha256:x", "ms": 812}}}
    manifest.save(path, data)
    assert manifest.load(path) == data
    assert not (tmp_path / "manifest.json.partial").exists()


def test_manifest_versions(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"version": 3, "stories": {}}))
    with pytest.raises(ValueError, match="version 3"):
        manifest.load(path)
    path.write_text(json.dumps({"version": 1, "stories": {"x": {}}}))
    with pytest.raises(ValueError, match="run `ai-tools tts` again"):
        manifest.load(path)                                   # render refuses an old one
    assert manifest.load(path, rewriting=True) == {"version": 2, "stories": {}}  # tts starts over


def test_vtt_cue_per_sentence():
    assert vtt.build("welcome", [(0, 1474.2, "Welcome <here> & now."), (1824, 3264, "Next.")]) == (
        "WEBVTT\n\n"
        "welcome-1\n00:00:00.000 --> 00:00:01.474\nWelcome &lt;here&gt; &amp; now.\n\n"
        "welcome-2\n00:00:01.824 --> 00:00:03.264\nNext.\n"
    )
    assert vtt.timestamp(3_723_004) == "01:02:03.004"


def test_assemble_speech_pauses_and_sentence_pauses():
    rate = 1000  # 1 sample = 1 ms, 2 bytes a sample
    speech = lambda ms, v=1: bytes([v, 0]) * ms
    pcm, spans = audio.assemble(
        [[speech(100), 50.0, speech(20)],  # a sentence with a [pause] inside
         [200.0],                          # only a pause: no subtitle
         [speech(50, 2)]],
        rate, sentence_pause_ms=30)
    assert len(pcm) == (100 + 50 + 20) * 2 + 30 * 2 + 200 * 2 + 30 * 2 + 50 * 2
    assert spans == [(0, 170), None, (430, 480)]  # the sentence's speech, its pause included
    assert pcm[200:300] == b"\x00" * 100        # the marker's pause is silence
    assert audio.assemble([], rate, 30) == (b"", [])
