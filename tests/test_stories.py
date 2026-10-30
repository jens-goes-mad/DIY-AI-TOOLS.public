import json

import pytest

from ai_tools.stories import Pause, ScriptError, Speech, Story, normalize, parts, read_lexicon, read_stories, shown, split_sentences, spoken


def script(tmp_path, steps, version=1):
    path = tmp_path / "tutorial.json"
    path.write_text(json.dumps({"version": version, "steps": steps}), encoding="utf-8")
    return path


def test_only_stories_in_script_order_with_the_apps_id_rule(tmp_path):
    path = script(tmp_path, [
        {"story": "a"}, {"click": "#x"}, {"caption": "not a story", "id": "c"},
        {"story": "b", "id": "intro"}, {"story": "c"},
    ])
    # story-<n> counts stories (not steps, not captions) from 1 -- like the app
    assert read_stories(path) == [Story("story-1", "a"), Story("intro", "b"), Story("story-3", "c")]


def test_bad_scripts(tmp_path):
    with pytest.raises(ScriptError, match="version 1"):
        read_stories(script(tmp_path, [], version=2))
    with pytest.raises(ScriptError, match="used twice"):
        read_stories(script(tmp_path, [{"story": "a", "id": "x"}, {"story": "b", "id": "x"}]))
    with pytest.raises(ScriptError, match="non-empty"):
        read_stories(script(tmp_path, [{"story": "  "}]))
    with pytest.raises(ScriptError, match="letters, digits"):
        read_stories(script(tmp_path, [{"story": "a", "id": "has space"}]))


def test_normalize_keeps_paragraphs_collapses_spaces():
    assert normalize("  Welcome   to\tthe tutorial. \n\n Next  line \n") == "Welcome to the tutorial.\nNext line"


def test_sentences_per_paragraph():
    text = "Welcome to the DIYKKE Tutorial, which shows panes.\nThe app shows two panes! Really? Yes.\nFirst, let's open a dataset."
    assert split_sentences(text) == [
        "Welcome to the DIYKKE Tutorial, which shows panes.",
        "The app shows two panes!", "Really?", "Yes.",
        "First, let's open a dataset.",
    ]


def test_sentences_keep_closing_quotes_and_unfinished_ends():
    assert split_sentences('He said "stop." Then (finally.) it ended') == ['He said "stop."', "Then (finally.)", "it ended"]


def test_pause_markers_split_speech_and_set_silence():
    assert parts("It shows two panes [pause] and [pause 1.5s] three [PAUSE 500ms] functions.") == [
        Speech("It shows two panes"), Pause(700), Speech("and"), Pause(1500),
        Speech("three"), Pause(500), Speech("functions."),
    ]
    assert shown("It shows two panes [pause] and three.") == "It shows two panes and three."


def test_pause_markers_between_sentences_stay_out_of_the_text():
    sentences = split_sentences("Welcome. [pause 2s] Next sentence.\nLast [pause].")
    assert sentences == ["Welcome.", "[pause 2s] Next sentence.", "Last [pause]."]
    assert [shown(s) for s in sentences] == ["Welcome.", "Next sentence.", "Last."]
    # punctuation after a marker joins the speech before it -- not spoken alone
    assert parts("Last [pause].") == [Speech("Last."), Pause(700)]


def test_bad_markers_are_errors(tmp_path):
    with pytest.raises(ScriptError, match=r'step 1 \(story\): unknown marker "\[pauze\]"'):
        read_stories(script(tmp_path, [{"story": "a [pauze] b"}]))
    with pytest.raises(ScriptError, match="at most 10 s"):
        read_stories(script(tmp_path, [{"story": "a [pause 11s] b"}]))
    with pytest.raises(ScriptError, match="nothing to say"):
        read_stories(script(tmp_path, [{"story": "[pause 2s]"}]))


def test_lexicon_replaces_whole_words_longest_first():
    lexicon = {"Kronos": "[[kɹˈəʊnɒs]]", "Combi": "Kombie", "Combis": "Kombies", "Korg Kronos": "Korg [[kɹˈəʊnɒs]]"}
    assert spoken("Korg Kronos keeps Combis and one Combi; Kronoses stay.", lexicon) == \
        "Korg [[kɹˈəʊnɒs]] keeps Kombies and one Kombie; Kronoses stay."
    assert spoken("combis stays (case-sensitive), Combi-Set too", lexicon) == "combis stays (case-sensitive), Combi-Set too"
    assert spoken("no lexicon", {}) == "no lexicon"


def test_read_lexicon(tmp_path):
    path = tmp_path / "lexicon.json"
    path.write_text(json.dumps({"Kronos": "Crow-noss"}), encoding="utf-8")
    assert read_lexicon(path) == {"Kronos": "Crow-noss"}
    path.write_text(json.dumps({"Kronos": ""}), encoding="utf-8")
    with pytest.raises(ScriptError, match="how to say it"):
        read_lexicon(path)
