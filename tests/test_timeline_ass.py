import pytest

from ai_tools import ass, timeline, vtt
from ai_tools.timeline import Clip, Gap, Placed, Still


def test_plan_freezes_the_middle_of_each_gap_for_the_narration():
    # 30 fps; gaps at 0.5-1.5 s and 5.3-6.3 s of a 10 s recording (300 frames)
    gaps = [Gap("welcome", 505, 1507), Gap("loaded", 5276, 6277)]
    pieces, placed, total = timeline.plan(gaps, {"welcome": 24083, "loaded": 3831}, 300, 30, lead_ms=400, tail_ms=700)
    hold_w = round((400 + 24083 + 700) * 30 / 1000)  # 755 frames
    hold_l = round((400 + 3831 + 700) * 30 / 1000)   # 148 frames
    assert pieces == [
        Clip(0, 15),                     # up to the first gap (frame 15 = 0.5 s)
        Still(30, hold_w, "welcome"),    # middle of frames 15..45
        Clip(45, 158 - 45),              # gap end to the next gap
        Still(173, hold_l, "loaded"),
        Clip(188, 300 - 188),            # to the end
    ]
    assert total == 15 + hold_w + 113 + hold_l + 112
    assert placed[0] == Placed("welcome", 500.0, (15 + hold_w) * 1000 / 30, 900.0)
    assert placed[1].start_ms == (15 + hold_w + 113) * 1000 / 30
    assert placed[1].voice_ms == placed[1].start_ms + 400


def test_plan_needs_narration_for_every_recorded_story():
    with pytest.raises(ValueError, match="has no narration"):
        timeline.plan([Gap("x", 100, 1100)], {}, 300, 30)


def test_read_gaps_checks_order(tmp_path):
    csv = tmp_path / "recording.csv"
    csv.write_text("id,start_ms,end_ms\na,505,1507\nb,1200,2200\n")
    with pytest.raises(ValueError, match="starts before"):
        timeline.read_gaps(csv)
    csv.write_text("id,start_ms,end_ms\na,505,1507\nb,5276,6277\n")
    assert timeline.read_gaps(csv) == [Gap("a", 505, 1507), Gap("b", 5276, 6277)]


def test_wrap_greedy_by_measured_width():
    measure = lambda s: len(s) * 10.0  # 10 px a character
    assert ass.wrap("one two three four five", 100, measure) == ["one two", "three four", "five"]  # exactly fits
    assert ass.wrap("one two three four five", 95, measure) == ["one two", "three", "four five"]
    assert ass.wrap("averyveryverylongword x", 50, measure) == ["averyveryverylongword", "x"]


def test_ass_box_sized_for_the_longest_sentence_and_text_on_top():
    layout = ass.Layout(1470, 1080)
    measure = lambda s: len(s) * 20.0
    story = ass.StoryOverlay(500, 25633, [(500, 9724, "Short."), (9724, 25633, "x " * 60)])
    doc = ass.build(layout, [story], measure)
    inner = layout.box_w - 2 * layout.pad_x
    lines = len(ass.wrap("x " * 60, inner, measure))
    box_h = round(lines * layout.line_height + 2 * layout.pad_y)
    assert f"\\pos({layout.box_x},{round((1080 - box_h) / 2)})" in doc
    assert f"m 0 0 l {layout.box_w} 0 {layout.box_w} {box_h} 0 {box_h}" in doc
    assert "Dialogue: 0,0:00:00.50,0:00:25.63,Box" in doc
    assert "Dialogue: 1,0:00:00.50,0:00:09.72,Text" in doc and doc.rstrip().endswith("x x")
    assert "&H33008CFF" in doc  # orange at 80% opacity
    assert layout.box_w == round(1470 * 0.9) and layout.box_x == round(1470 * 0.05)


def test_vtt_round_trip_and_srt():
    cues = [(0, 1474, "Welcome <here> & now."), (1824, 3264, "Next.")]
    assert vtt.parse(vtt.build("welcome", cues)) == cues
    assert vtt.srt([(900, 2374, "A."), (61000, 62500, "B.")]) == (
        "1\n00:00:00,900 --> 00:00:02,374\nA.\n\n2\n00:01:01,000 --> 00:01:02,500\nB.\n"
    )
