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


MEASURE = lambda size: (lambda s: len(s) * size / 2)  # a fake font: half the size a character


def test_story_box_sized_for_the_longest_sentence_text_on_top_fades():
    layout = ass.Layout(1470, 1080)
    story = ass.StoryOverlay(500, 25633, [[(1500, 9724, "Short."), (9724, 24000, "x " * 60)]])
    doc = ass.build(layout, [story], MEASURE)
    inner = layout.box_w - 2 * layout.pad_x
    lines = len(ass.wrap("x " * 60, inner, MEASURE(layout.font_size)))
    box_h = round(lines * layout.line_height + 2 * layout.pad_y)
    assert f"\\pos({layout.box_x},{round((1080 - box_h) / 2)})" in doc
    assert ass.box_path(layout.box_w, box_h, 0) in doc                       # square by default
    assert "Dialogue: 0,0:00:00.50,0:00:25.63,Box" in doc and "\\fad(1000,1000)" in doc
    assert "Dialogue: 1,0:00:00.50,0:00:09.72,Text" in doc                  # first sentence from the box's start
    assert "\\fad(1000,0)}Short." in doc and "\\fad(0,1000)}x x" in doc     # text fades with the box
    assert "&H33008CFF" in doc                                              # orange at 80%


def test_rounded_corners():
    assert ass.box_path(100, 50, 0) == "m 0 0 l 100 0 100 50 0 50"
    path = ass.box_path(100, 50, 10)
    assert path.startswith("m 10 0 l 90 0 b ") and path.count(" b ") == 4
    doc = ass.build(ass.Layout(1470, 1080), [ass.StoryOverlay(0, 5000, [[(0, 5000, "Hi.")]])], MEASURE, rounded=True)
    assert " b " in doc


def test_chapter_box_leaves_10_percent_and_uses_title_text():
    layout = ass.Layout(1470, 1080)
    doc = ass.build(layout, [ass.StoryOverlay(0, 5000, [[(1000, 4000, "Part 1")]], kind="chapter")], MEASURE)
    x, y, w, h = layout.chapter_box()
    assert (x, y, w, h) == (147, 108, 1176, 864)
    assert f"\\pos({x},{y})" in doc and ass.box_path(w, h, 0) in doc
    assert f"Title,,0,0,0,,{{\\an5\\pos({x + w // 2},{y + h // 2})" in doc
    assert f"Style: Title,DejaVu Sans,{layout.title_size}," in doc and layout.title_size > layout.font_size


def test_pages_fly_in_from_the_right_and_out_to_the_left():
    layout = ass.Layout(1470, 1080)
    # page 1 spoken 1000-4000, page 2 from 5500: the 1.5 s pause holds an 800 ms change at 4350-5150
    story = ass.StoryOverlay(0, 8000, [[(1000, 4000, "One.")], [(5500, 7000, "Two.")]])
    doc = ass.build(layout, [story], MEASURE, fps=30)
    boxes = [line for line in doc.splitlines() if ",Box," in line]
    assert boxes[0].startswith("Dialogue: 0,0:00:00.00,0:00:04.35,Box") and "\\fad(1000,0)" in boxes[0]
    assert boxes[1].startswith("Dialogue: 0,0:00:05.15,0:00:08.00,Box") and "\\fad(0,1000)" in boxes[1]
    frames = boxes[2:]
    assert len(frames) == 2 * 24                                  # 800 ms at 30 fps, two boxes a frame
    xs_out = [int(f.split("\\pos(")[1].split(",")[0]) for f in frames[0::2]]
    xs_in = [int(f.split("\\pos(")[1].split(",")[0]) for f in frames[1::2]]
    alphas_in = [int(f.split("\\1a&H")[1][:2], 16) for f in frames[1::2]]
    steps_out = [a - b for a, b in zip(xs_out, xs_out[1:])]
    steps_in = [a - b for a, b in zip(xs_in, xs_in[1:])]
    assert xs_out[0] > layout.box_x - 5 and xs_out[-1] < -layout.box_w + 100   # leaves to the left
    moving_out, moving_in = [d for d in steps_out if d > 0], [d for d in steps_in if d > 0]
    assert moving_out[-1] > moving_out[0] > 0                                   # speeding up
    assert xs_in[0] > layout.width - 100 and abs(xs_in[-1] - layout.box_x) < 5  # arrives from the right
    assert moving_in[0] > moving_in[-1]                                         # slowing down
    assert len(moving_out) < len(steps_out) and len(moving_in) < len(steps_in) # staggered
    assert alphas_in[0] > 0xF0 and alphas_in[-1] <= 0x36                        # invisible -> 80%
    assert all(i >= o + layout.box_w for o, i in zip(xs_out, xs_in))           # never overlapping


def test_vtt_round_trip_and_srt():
    cues = [(0, 1474, "Welcome <here> & now."), (1824, 3264, "Next.")]
    assert vtt.parse(vtt.build("welcome", cues)) == cues
    assert vtt.srt([(900, 2374, "A."), (61000, 62500, "B.")]) == (
        "1\n00:00:00,900 --> 00:00:02,374\nA.\n\n2\n00:01:01,000 --> 00:01:02,500\nB.\n"
    )


def test_fade_length_is_a_parameter_and_one_sentence_fades_both_ways():
    layout = ass.Layout(1470, 1080)
    doc = ass.build(layout, [ass.StoryOverlay(0, 5000, [[(0, 5000, "Only.")]])], MEASURE, fade_ms=300)
    assert "\\fad(300,300)" in doc and "\\fad(300,300)}Only." in doc
