"""
Criterion: A user can edit each segment's narration script, visual summary,
and image/video prompt. PATCH /api/stories/{id}/script persists the changed
segment and flips the story to edits_requested (ready to re-render).

Uses seeded story `feature-segment-controls`. We patch segment index 1
(second chunk) with a `tscheck-` tagged marker value and assert it round
-trips via GET, then restore the original values so we don't corrupt the
shared seed fixture for other checks/tests.
"""
import time
import httpx

BASE = "http://localhost:8001"
STORY_ID = "feature-segment-controls"


def test_patch_script_persists_edit_and_flips_status():
    original = httpx.get(f"{BASE}/api/stories/{STORY_ID}", timeout=30).json()
    chunk = original["script"]["chunks"][1]
    orig_voiceover = chunk["voiceover"]
    orig_visual = chunk["visual"]
    orig_prompt = chunk["video_prompt"]

    marker = f"tscheck-script-patch-{int(time.time())}"
    try:
        resp = httpx.patch(
            f"{BASE}/api/stories/{STORY_ID}/script",
            json={"chunks": [{
                "index": 1,
                "voiceover": f"{marker} voiceover",
                "visual": f"{marker} visual",
                "video_prompt": f"{marker} prompt",
            }]},
            timeout=30,
        )
        assert resp.status_code == 200, f"{resp.status_code} {resp.text[:300]}"
        body = resp.json()
        assert body.get("edited") == [1]

        got = httpx.get(f"{BASE}/api/stories/{STORY_ID}", timeout=30).json()
        seg = got["script"]["chunks"][1]
        assert seg["voiceover"] == f"{marker} voiceover"
        assert seg["visual"] == f"{marker} visual"
        assert seg["video_prompt"] == f"{marker} prompt"
        assert got["status"] == "edits_requested"
    finally:
        # restore original content so the shared fixture stays stable
        httpx.patch(
            f"{BASE}/api/stories/{STORY_ID}/script",
            json={"chunks": [{
                "index": 1,
                "voiceover": orig_voiceover,
                "visual": orig_visual,
                "video_prompt": orig_prompt,
            }]},
            timeout=30,
        )
