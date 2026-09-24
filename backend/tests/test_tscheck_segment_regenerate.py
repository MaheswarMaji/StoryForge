"""
Criterion: Segment regeneration API validates requests and queues the selected
operation. Valid kinds (script, voice, visual) return a job id when no
duplicate job is active; an invalid kind returns HTTP 400 with a useful detail.

Exercised against the seeded story `feature-segment-controls` (2 script
chunks), read-only for the story itself -- we only touch the jobs collection
via enqueue, which is namespaced by story/kind and safe to repeat.
"""
import httpx

STORY_ID = "feature-segment-controls"


def _cancel_active_segment_fix_jobs(base_url):
    """The queue dedupes segment_fix jobs per-story (not per-kind/index), so a
    leftover queued job from an earlier run/kind would make enqueue return
    None. Clear any active segment_fix job for this story first so each kind
    is exercised from a clean slate."""
    jobs = httpx.get(f"{base_url}/api/jobs", params={"limit": 50}, timeout=30).json()
    for j in jobs:
        if (j.get("ref_id") == STORY_ID and j.get("type") == "segment_fix"
                and j.get("status") in ("queued", "running")):
            httpx.post(f"{base_url}/api/jobs/{j['_id']}/cancel", timeout=30)


def test_regenerate_valid_kinds_return_job_id(base_url):
    for kind in ("script", "voice", "visual"):
        _cancel_active_segment_fix_jobs(base_url)
        resp = httpx.post(
            f"{base_url}/api/stories/{STORY_ID}/segments/0/regenerate",
            json={"kind": kind},
            timeout=30,
        )
        assert resp.status_code == 200, f"kind={kind} -> {resp.status_code} {resp.text[:300]}"
        body = resp.json()
        assert "job_id" in body and body["job_id"], f"kind={kind} missing job_id: {body}"
    _cancel_active_segment_fix_jobs(base_url)


def test_regenerate_invalid_kind_returns_400_with_detail():
    resp = httpx.post(
        f"http://localhost:8001/api/stories/{STORY_ID}/segments/0/regenerate",
        json={"kind": "not-a-real-kind"},
        timeout=30,
    )
    assert resp.status_code == 400, f"expected 400, got {resp.status_code} {resp.text[:300]}"
    detail = resp.json().get("detail", "")
    assert detail, "expected a useful detail message on 400"
    assert "kind" in detail.lower()


def test_regenerate_invalid_segment_index_returns_400():
    resp = httpx.post(
        f"http://localhost:8001/api/stories/{STORY_ID}/segments/99/regenerate",
        json={"kind": "script"},
        timeout=30,
    )
    assert resp.status_code == 400, f"expected 400, got {resp.status_code} {resp.text[:300]}"
