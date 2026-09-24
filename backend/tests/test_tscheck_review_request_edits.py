"""
Criterion: Request Edits is operational and requires notes.
POST /api/stories/{id}/review with action=request_edits:
  - blank notes -> HTTP 400
  - non-blank notes -> 200, story status becomes edits_requested, review_notes
    updated, and an edit_request job is queued (edit_job_id present).

Uses the seeded story `feature-segment-controls`. The story is already in an
edits_requested-family status from prior seeding; we only assert the API
contract, and we restore nothing since request_edits is idempotent by design
(review notes are meant to be overwritten by the reviewer).
"""
import time
import httpx

BASE = "http://localhost:8001"
STORY_ID = "feature-segment-controls"


def test_request_edits_blank_notes_rejected():
    resp = httpx.post(
        f"{BASE}/api/stories/{STORY_ID}/review",
        json={"action": "request_edits", "notes": "   "},
        timeout=30,
    )
    assert resp.status_code == 400, f"expected 400, got {resp.status_code} {resp.text[:300]}"
    assert "note" in resp.json().get("detail", "").lower()


def _cancel_active_edit_request_jobs():
    """The queue dedupes edit_request jobs per-story, so a leftover queued job
    from seeding/an earlier run would make enqueue return None. Clear it first
    so this check exercises a fresh enqueue."""
    jobs = httpx.get(f"{BASE}/api/jobs", params={"limit": 50}, timeout=30).json()
    for j in jobs:
        if (j.get("ref_id") == STORY_ID and j.get("type") == "edit_request"
                and j.get("status") in ("queued", "running")):
            httpx.post(f"{BASE}/api/jobs/{j['_id']}/cancel", timeout=30)


def test_request_edits_with_notes_queues_job_and_updates_story():
    _cancel_active_edit_request_jobs()
    marker_notes = f"tscheck-request-edits-{int(time.time())}: make segment 1 punchier"
    resp = httpx.post(
        f"{BASE}/api/stories/{STORY_ID}/review",
        json={"action": "request_edits", "notes": marker_notes},
        timeout=30,
    )
    assert resp.status_code == 200, f"{resp.status_code} {resp.text[:300]}"
    body = resp.json()
    assert body.get("status") == "edits_requested"
    assert body.get("review_notes") == marker_notes
    assert body.get("edit_job_id"), f"expected edit_job_id in response: {body}"

    # confirm persisted via GET
    got = httpx.get(f"{BASE}/api/stories/{STORY_ID}", timeout=30).json()
    assert got["review_notes"] == marker_notes
    assert got["status"] == "edits_requested"
