"""Story/segment media-engine overrides inherit defaults without rewriting supplied scripts.

Creates an isolated tscheck- test story via the structured-script importer (so the exact
narration/visual text is known and verbatim), then exercises:
  - GET story engines defaults to the global default (inherit) before any override
  - PUT a story-level image engine override
  - PUT a segment-level video engine override, "effective" merges story override + segment override
  - Engine changes never touch script.chunks (voiceover/visual stay byte-identical)
Never touches the seeded Dhruv story (6ab4cc6f012840d396d83a85).
"""
import httpx

BASE = "http://localhost:8001"

SCRIPT = """पात्र एवं दृश्य संगति गाइड (Consistency Bible)
tscheck-engine-नायक: सफेद वस्त्र, शांत मुख भाव।

सीन-दर-सीन स्क्रिप्ट

सीन 1: हुक
विज़ुअल: tscheck-engine नायक जंगल में खड़ा है, वाइड शॉट।
नैरेशन: "tscheck-engine एक जंगल में एक नायक रहता था।"

सीन 2: मोड़
विज़ुअल: tscheck-engine नायक तूफान का सामना करता है, क्लोज़ अप।
नैरेशन: "tscheck-engine अचानक एक तूफान आया।"

सीन 3: सीख
विज़ुअल: tscheck-engine नायक मुस्कुराता है, स्थिर शॉट।
नैरेशन: "tscheck-engine साहस ही सच्ची शक्ति है।"
"""


def _create_story():
    resp = httpx.post(f"{BASE}/api/stories/create", json={
        "title": "tscheck-engine-override-story",
        "source_text": SCRIPT,
        "video_type": "mythology_moral",
        "length_seconds": 90,
        "mode": "slide",
    }, timeout=30)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["imported"] is True and body["imported_segments"] == 3
    return body["story_id"]


def test_story_and_segment_engine_overrides_inherit_and_preserve_script():
    story_id = _create_story()

    defaults = httpx.get(f"{BASE}/api/settings/media-engines", timeout=30).json()
    original_chunks = httpx.get(f"{BASE}/api/stories/{story_id}", timeout=30).json()["script"]["chunks"]

    # Before any override: story-level image/video are unset, effective falls back to global defaults.
    before = httpx.get(f"{BASE}/api/stories/{story_id}/media-engines", timeout=30)
    assert before.status_code == 200, before.text
    before_body = before.json()
    assert before_body["image"] is None
    assert before_body["video"] is None
    assert before_body["effective"]["image"] == defaults["image"]
    assert before_body["effective"]["video"] == defaults["video"]

    # Story-level override: force image engine to 'auto' regardless of global default.
    put1 = httpx.put(f"{BASE}/api/stories/{story_id}/media-engines", json={
        **before_body, "image": "auto",
    }, timeout=30)
    assert put1.status_code == 200, put1.text
    put1_body = put1.json()
    assert put1_body["image"] == "auto"
    assert put1_body["effective"]["image"] == "auto"
    # video still inherits the global default since no override was set for it.
    assert put1_body["effective"]["video"] == defaults["video"]

    # Segment-level override: segment 1 gets its own video engine, distinct from story-level.
    put2 = httpx.put(f"{BASE}/api/stories/{story_id}/media-engines", json={
        **put1_body, "segments": {**put1_body["segments"], "1": {"image": None, "video": "kenburns"}},
    }, timeout=30)
    assert put2.status_code == 200, put2.text
    put2_body = put2.json()
    assert put2_body["segments"]["1"]["video"] == "kenburns"
    # Story-level override from the previous step is retained (not clobbered by the segment PUT).
    assert put2_body["image"] == "auto"

    # Invalid segment index must be rejected (bounds-checked against the actual script length).
    bad = httpx.put(f"{BASE}/api/stories/{story_id}/media-engines", json={
        **put2_body, "segments": {**put2_body["segments"], "99": {"image": None, "video": "kenburns"}},
    }, timeout=30)
    assert bad.status_code == 422, bad.text

    # The exact supplied script is untouched by any engine change.
    after_chunks = httpx.get(f"{BASE}/api/stories/{story_id}", timeout=30).json()["script"]["chunks"]
    assert after_chunks == original_chunks
    assert "tscheck-engine एक जंगल में एक नायक रहता था" in after_chunks[0]["voiceover"]


def test_seeded_dhruv_story_untouched_reference_state():
    # Read-only sanity check on the seeded story per briefing: image=gemini, segment0 inherits,
    # never mutated by this or any other tscheck test.
    resp = httpx.get(f"{BASE}/api/stories/6ab4cc6f012840d396d83a85/media-engines", timeout=30)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["image"] == "gemini"
    assert body["segments"].get("0", {}).get("image") is None
    assert body["segments"].get("0", {}).get("video") is None
