"""Structured Hindi scene-script import: detection, verbatim preservation, Bible anchor.

Covers acceptance-matrix criteria for POST /api/stories/create when given a structured
Hindi Consistency Bible + numbered scene script vs. blank/unstructured input.
"""
import httpx

BASE = "http://localhost:8001"

HINDI_SCRIPT = """पात्र एवं दृश्य संगति गाइड (Consistency Bible)
tscheck-राजा: स्वर्ण मुकुट, लाल वस्त्र, गंभीर मुख भाव।
tscheck-रानी: नीली साड़ी, दयालु आँखें।

सीन-दर-सीन स्क्रिप्ट

सीन 1: हुक
विज़ुअल: tscheck राजा सिंहासन पर बैठे हैं, दरबार शांत है, कैमरा ज़ूम इन।
नैरेशन: "tscheck एक समय की बात है, एक विशाल राज्य था।"
संवाद — राजा: "tscheck यह राज्य अब खतरे में है।"

सीन 2: मोड़
विज़ुअल: tscheck रानी दौड़ती हुई दरबार में आती है, पैन राइट।
संवाद — रानी: "tscheck महाराज, दुश्मन सीमा पर आ गए हैं!"

सीन 3: सीख
विज़ुअल: tscheck राजा और रानी एक साथ खड़े हैं, स्थिर शॉट।
नैरेशन (वॉयसओवर) + CTA: "tscheck यही है सच्ची वीरता। लाइक करें और सब्सक्राइब करें।"

प्रोडक्शन नोट्स
संगीत: tscheck नाटकीय पृष्ठभूमि संगीत, धीमी गति।
"""


def test_structured_script_is_detected_and_imported_verbatim():
    resp = httpx.post(f"{BASE}/api/stories/create", json={
        "title": "tscheck-structured-import",
        "source_text": HINDI_SCRIPT,
        "video_type": "mythology_moral",
        "length_seconds": 90,
        "mode": "slide",
    }, timeout=30)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["imported"] is True
    assert body["imported_segments"] == 3
    assert body["job_id"] is None
    story_id = body["story_id"]

    get_resp = httpx.get(f"{BASE}/api/stories/{story_id}", timeout=30)
    assert get_resp.status_code == 200
    story = get_resp.json()
    assert story["status"] == "script_ready"

    script = story["script"]
    assert script["imported_verbatim"] is True
    chunks = script["chunks"]
    assert len(chunks) == 3

    # Narration + dialogue preserved verbatim (quotes stripped, words unchanged) in voiceover.
    assert "tscheck एक समय की बात है, एक विशाल राज्य था।" in chunks[0]["voiceover"]
    assert "tscheck यह राज्य अब खतरे में है।" in chunks[0]["voiceover"]
    assert "tscheck महाराज, दुश्मन सीमा पर आ गए हैं!" in chunks[1]["voiceover"]
    # नैरेशन + CTA quoted text preserved in the closing scene.
    assert "tscheck यही है सच्ची वीरता। लाइक करें और सब्सक्राइब करें।" in chunks[2]["voiceover"]

    # Visuals preserved verbatim in both visual and video_prompt, not AI-rewritten.
    for chunk in chunks:
        assert chunk["visual"] == chunk["video_prompt"]
    assert "tscheck राजा सिंहासन पर बैठे हैं" in chunks[0]["visual"]
    assert "tscheck रानी दौड़ती हुई दरबार में आती है" in chunks[1]["visual"]
    assert "tscheck राजा और रानी एक साथ खड़े हैं" in chunks[2]["visual"]

    # Consistency Bible loaded as the canonical locked sheet.
    assert story["character_sheet"]["locked"] is True
    anchor = story["character_sheet"]["anchor"]
    assert "tscheck-राजा" in anchor
    assert "tscheck-रानी" in anchor
    assert script["character_sheet"]["anchor"] == anchor

    # Changing target length must not trigger script (re)generation for imported stories.
    cfg_resp = httpx.put(f"{BASE}/api/stories/{story_id}/config", json={"target_seconds": 60}, timeout=30)
    assert cfg_resp.status_code == 200, cfg_resp.text
    assert cfg_resp.json()["target_seconds"] == 60

    get_resp2 = httpx.get(f"{BASE}/api/stories/{story_id}", timeout=30)
    story2 = get_resp2.json()
    assert story2["target_seconds"] == 60
    # script untouched: same imported chunks, still imported_verbatim, no new job dispatched.
    assert story2["script"]["imported_verbatim"] is True
    assert len(story2["script"]["chunks"]) == 3
    assert story2["script"]["chunks"][0]["voiceover"] == chunks[0]["voiceover"]


def test_blank_source_text_returns_400():
    resp = httpx.post(f"{BASE}/api/stories/create", json={
        "title": "tscheck-blank",
        "source_text": "   ",
        "video_type": "mythology_moral",
        "length_seconds": 90,
        "mode": "slide",
    }, timeout=30)
    assert resp.status_code == 400, resp.text


def test_unstructured_input_falls_back_to_ai_script_generation():
    resp = httpx.post(f"{BASE}/api/stories/create", json={
        "title": "tscheck-unstructured-fallback",
        "source_text": "tscheck Write me a short mythology story about a brave prince.",
        "video_type": "mythology_moral",
        "length_seconds": 90,
        "mode": "slide",
    }, timeout=30)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # No usable scene blocks -> not falsely marked imported; falls back to AI generation job.
    assert body["imported"] is False
    assert body["imported_segments"] == 0
    assert body["job_id"] is not None
