from app.canary import find_canaries
from app.config import DEFAULT_CANARIES


def test_offsets_point_at_the_match():
    body = '{"content": "Acquire Zentra Ltd for USD 212M under Project Falcon (BM-7731-KX)."}'
    hits = find_canaries(body, DEFAULT_CANARIES)
    assert [h["text"] for h in hits] == ["Zentra Ltd", "USD 212M", "Project Falcon", "BM-7731-KX"]
    assert all(body[h["start"]:h["end"]] == h["text"] for h in hits)


def test_every_occurrence_is_tagged():
    hits = find_canaries("Project Falcon. Again: Project Falcon.", ["Project Falcon"])
    assert [(h["start"], h["end"]) for h in hits] == [(0, 14), (23, 37)]


def test_case_insensitive_keeps_original_text():
    hits = find_canaries("about PROJECT FALCON", ["Project Falcon"])
    assert hits == [{"text": "PROJECT FALCON", "start": 6, "end": 20}]


def test_overlapping_canaries_prefer_longest():
    hits = find_canaries("Project Falcon", ["Falcon", "Project Falcon", "Project"])
    assert hits == [{"text": "Project Falcon", "start": 0, "end": 14}]


def test_regex_characters_are_literal():
    assert find_canaries("cost USD 2.5M", ["USD 2.5M"])[0]["text"] == "USD 2.5M"
    assert find_canaries("cost USD 2x5M", ["USD 2.5M"]) == []


def test_blank_and_missing_canaries():
    assert find_canaries("anything", []) == []
    assert find_canaries("anything", ["", "  "]) == []
    assert find_canaries("nothing sensitive here", DEFAULT_CANARIES) == []
