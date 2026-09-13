"""Iteration 4 — Storyboard mode, stop/cancel, queue pause, key vault, engagement fallback."""
import os
import time
import requests
import pytest
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL

STORY_STORYBOARD_DONE = "6aa616a70b6da578466afad5"     # finished storyboard demo
STORY_SLIDE_INTACT = "6aa57c1eaad23f394fffaa41"         # slide mode, must not re-render
MEDIA_ROOT = "/app/backend/media"


@pytest.fixture(scope="module")
def mongo():
    c = MongoClient("mongodb://localhost:27017")
    yield c["test_database"]
    c.close()


@pytest.fixture(scope="module")
def anon():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ---------- 1. Mode validation: storyboard accepted ----------
class TestModeValidation:
    def test_create_storyboard_mode(self, anon, mongo):
        r = anon.post(f"{BASE_URL}/api/stories/create",
                      json={"title": "TEST_storyboard_validate",
                            "source_text": "AI is eating software. Just a test.",
                            "video_type": "tech", "length_seconds": 45,
                            "mode": "storyboard"}, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        sid, jid = d["story_id"], d["job_id"]
        gr = anon.get(f"{BASE_URL}/api/stories/{sid}", timeout=30)
        assert gr.json().get("mode") == "storyboard"
        # cleanup — don't let this script job actually run to completion
        mongo.jobs.update_one({"_id": jid}, {"$set": {"status": "cancelled"}})
        mongo.stories.delete_one({"_id": sid})
        mongo.jobs.delete_one({"_id": jid})

    def test_config_switch_to_storyboard(self, anon, mongo):
        r = anon.put(f"{BASE_URL}/api/stories/{STORY_SLIDE_INTACT}/config",
                     json={"mode": "storyboard"}, timeout=30)
        assert r.status_code == 200
        assert r.json().get("mode") == "storyboard"
        # restore slide mode so slide-story stays intact
        r2 = anon.put(f"{BASE_URL}/api/stories/{STORY_SLIDE_INTACT}/config",
                      json={"mode": "slide"}, timeout=30)
        assert r2.json().get("mode") == "slide"


# ---------- 2. Queue pause / resume ----------
class TestQueuePause:
    def test_pause_and_resume(self, anon):
        # pause
        r = anon.post(f"{BASE_URL}/api/queue/pause", json={"paused": True}, timeout=15)
        assert r.status_code == 200 and r.json().get("paused") is True
        dr = anon.get(f"{BASE_URL}/api/dashboard", timeout=15)
        assert dr.json()["queue"].get("paused") is True
        # resume
        r2 = anon.post(f"{BASE_URL}/api/queue/pause", json={"paused": False}, timeout=15)
        assert r2.status_code == 200 and r2.json().get("paused") is False
        dr2 = anon.get(f"{BASE_URL}/api/dashboard", timeout=15)
        assert dr2.json()["queue"].get("paused") is False

    def test_paused_queue_does_not_claim_jobs(self, anon, mongo):
        # Pause queue then enqueue a script job — it should remain queued for ≥3s.
        anon.post(f"{BASE_URL}/api/queue/pause", json={"paused": True}, timeout=15)
        try:
            r = anon.post(f"{BASE_URL}/api/stories/create",
                          json={"title": "TEST_paused_enq",
                                "source_text": "quick test text",
                                "video_type": "educational",
                                "length_seconds": 30, "mode": "slide"}, timeout=30)
            assert r.status_code == 200
            sid, jid = r.json()["story_id"], r.json()["job_id"]
            time.sleep(4)
            j = mongo.jobs.find_one({"_id": jid})
            assert j is not None
            # while paused, worker must not have moved it to running/done
            assert j["status"] == "queued", f"job status={j['status']} while paused"
        finally:
            # cleanup and unpause
            anon.post(f"{BASE_URL}/api/queue/pause", json={"paused": False}, timeout=15)
            mongo.jobs.update_one({"_id": jid}, {"$set": {"status": "cancelled"}})
            mongo.stories.delete_one({"_id": sid})
            mongo.jobs.delete_one({"_id": jid})


# ---------- 3. Cancel job endpoint ----------
class TestCancelJob:
    def test_cancel_queued_job(self, anon, mongo):
        # pause queue so job stays queued
        anon.post(f"{BASE_URL}/api/queue/pause", json={"paused": True}, timeout=15)
        try:
            r = anon.post(f"{BASE_URL}/api/stories/create",
                          json={"title": "TEST_cancelme",
                                "source_text": "cancel me source text",
                                "video_type": "tech", "length_seconds": 30,
                                "mode": "slide"}, timeout=30)
            sid, jid = r.json()["story_id"], r.json()["job_id"]
            cr = anon.post(f"{BASE_URL}/api/jobs/{jid}/cancel", timeout=15)
            assert cr.status_code == 200 and cr.json().get("ok") is True
            j = mongo.jobs.find_one({"_id": jid})
            assert j["status"] == "cancelled"
        finally:
            anon.post(f"{BASE_URL}/api/queue/pause", json={"paused": False}, timeout=15)
            mongo.stories.delete_one({"_id": sid})
            mongo.jobs.delete_one({"_id": jid})

    def test_cancel_unknown_job_404(self, anon):
        r = anon.post(f"{BASE_URL}/api/jobs/does_not_exist_xyz/cancel", timeout=15)
        assert r.status_code == 404


# ---------- 4. Stop story endpoint ----------
class TestStopStory:
    def test_stop_no_active_409(self, anon):
        # Finished story has no active job → 409
        r = anon.post(f"{BASE_URL}/api/stories/{STORY_STORYBOARD_DONE}/stop", timeout=15)
        assert r.status_code == 409

    def test_stop_queued_produce(self, anon, mongo):
        anon.post(f"{BASE_URL}/api/queue/pause", json={"paused": True}, timeout=15)
        sid, jid = None, None
        try:
            r = anon.post(f"{BASE_URL}/api/stories/create",
                          json={"title": "TEST_stopme",
                                "source_text": "stop me source",
                                "video_type": "tech", "length_seconds": 30,
                                "mode": "storyboard"}, timeout=30)
            sid = r.json()["story_id"]
            # skip the script job and enqueue a produce job directly
            mongo.jobs.update_one({"_id": r.json()["job_id"]},
                                  {"$set": {"status": "cancelled"}})
            # simulate a produce job in queue
            from datetime import datetime, timezone
            pjid = f"testprod_{int(time.time()*1000)}"
            mongo.jobs.insert_one({"_id": pjid, "type": "produce", "ref_id": sid,
                                   "status": "queued", "priority": 0,
                                   "created_at": datetime.now(timezone.utc),
                                   "payload": {}, "label": "TEST produce"})
            mongo.stories.update_one({"_id": sid}, {"$set": {"status": "rendering"}})
            jid = pjid
            sr = anon.post(f"{BASE_URL}/api/stories/{sid}/stop", timeout=15)
            assert sr.status_code == 200 and sr.json().get("ok") is True
            j = mongo.jobs.find_one({"_id": jid})
            assert j["status"] == "cancelled"
            st = mongo.stories.find_one({"_id": sid})
            assert st["status"] == "script_ready"
            assert st.get("stage") == "Stopped by user"
        finally:
            anon.post(f"{BASE_URL}/api/queue/pause", json={"paused": False}, timeout=15)
            if sid:
                mongo.stories.delete_one({"_id": sid})
            if jid:
                mongo.jobs.delete_one({"_id": jid})


# ---------- 5. Storyboard artifacts on finished story ----------
class TestStoryboardArtifacts:
    def test_poster_and_tiles_exist(self):
        fdir = os.path.join(MEDIA_ROOT, "frames", STORY_STORYBOARD_DONE)
        assert os.path.isfile(os.path.join(fdir, "storyboard.png"))
        sizes = []
        for i in range(6):
            p = os.path.join(fdir, f"{i:02d}.png")
            assert os.path.isfile(p), f"missing tile {p}"
            sz = os.path.getsize(p)
            assert sz > 500, f"tile {p} suspiciously small ({sz}B)"
            sizes.append(sz)
        # tiles should differ from each other (at least some variation)
        assert len(set(sizes)) > 1, f"all tiles same size {sizes[0]} — likely identical"

    def test_final_video_exists(self):
        assert os.path.isfile(os.path.join(MEDIA_ROOT, "final",
                                           f"{STORY_STORYBOARD_DONE}.mp4"))

    def test_slide_story_video_intact(self):
        # regression: slide-mode demo must not be re-rendered
        assert os.path.isfile(os.path.join(MEDIA_ROOT, "final",
                                           f"{STORY_SLIDE_INTACT}.mp4"))


# ---------- 6. API keys — new Gemini + OpenAI set ----------
class TestApiKeysSet:
    def test_gemini_and_openai_set(self, anon):
        r = anon.get(f"{BASE_URL}/api/settings/api-keys", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["GEMINI_API_KEY"]["set"] is True
        assert d["OPENAI_API_KEY"]["set"] is True


# ---------- 7. Engagement fallback (Ollama absent) ----------
class TestEngagementFallback:
    def test_engagement_sync_returns(self, anon):
        r = anon.post(f"{BASE_URL}/api/social/engagement/sync", timeout=30)
        # accept 200/202/204 — must NOT 500
        assert r.status_code in (200, 202, 204), f"engagement crashed: {r.status_code} {r.text[:200]}"


# ---------- 8. Storyboard PIL poster module — direct call ----------
class TestStoryboardPILModule:
    def test_pil_poster_generates(self, tmp_path):
        from PIL import Image
        import sys
        sys.path.insert(0, "/app/backend")
        from services.storyboard import _pil_poster, _grid_for, _slice

        titles = [f"Segment {i+1}. body text here" for i in range(6)]
        rows, cols = _grid_for(6)
        poster = tmp_path / "storyboard.png"
        _pil_poster(titles, poster, rows, cols)
        assert poster.exists()
        img = Image.open(poster)
        assert img.size[0] > 500 and img.size[1] > 500
        tiles = _slice(poster, rows, cols, 6, tmp_path)
        assert len(tiles) == 6
        for t in tiles:
            assert t.exists()
