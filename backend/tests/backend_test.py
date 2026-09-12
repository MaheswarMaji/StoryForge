"""StoryForge backend test suite — auth-gated app.

Covers:
- Auth gating (401 for /api/* without session, exemptions for /api/, /api/media-health, /api/media/*)
- Auth flows (/api/auth/session invalid, /api/auth/me with bearer)
- Instagram Integrations (GET/PUT with fake creds -> 400, DELETE)
- Engagement DRAFT-ONLY sync (no creds -> fetched=0, no crash)
- Improvement Coach wiring (409 no chunks, enqueue on valid story, non-existent 404)
- Publish IG without creds -> job fails gracefully
- Regression: dashboard, router-status, stories, story detail, channels, social creds, media
"""
import os
import time
import requests
import pytest
from pymongo import MongoClient
from datetime import datetime, timedelta, timezone

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"

# Real demo story with script chunks + approved status (this replaced the outdated id from iter_1)
STORY_ID = "6aa57c1eaad23f394fffaa41"
STORY_NO_CHUNKS = "6aa551bf261dd09045c67a16"  # scripting/no chunks yet
BOOK_ID = "6aa57126cf9d4dc77f7ff483"


# ------------- shared fixtures -------------
@pytest.fixture(scope="module")
def mongo():
    c = MongoClient("mongodb://localhost:27017")
    yield c["test_database"]
    c.close()


@pytest.fixture(scope="module")
def session_token(mongo):
    tok = f"test_session_{int(time.time()*1000)}"
    uid = f"test-user-{int(time.time()*1000)}"
    mongo.users.insert_one({"user_id": uid, "email": f"{uid}@example.com",
                            "name": "PyTest QA", "picture": "",
                            "role": "user",
                            "created_at": datetime.now(timezone.utc)})
    mongo.user_sessions.insert_one({"user_id": uid, "session_token": tok,
                                    "expires_at": datetime.now(timezone.utc) + timedelta(days=1),
                                    "created_at": datetime.now(timezone.utc)})
    yield tok
    mongo.user_sessions.delete_many({"session_token": tok})
    mongo.users.delete_many({"user_id": uid})


@pytest.fixture(scope="module")
def admin_session_token(mongo):
    """Mint a session for the pre-existing admin user nyai.deepak@gmail.com."""
    tok = f"test_admin_session_{int(time.time()*1000)}"
    admin = mongo.users.find_one({"user_id": "user_fba19a29ab52"})
    assert admin is not None, "admin seed user missing"
    mongo.user_sessions.insert_one({"user_id": admin["user_id"], "session_token": tok,
                                    "expires_at": datetime.now(timezone.utc) + timedelta(days=1),
                                    "created_at": datetime.now(timezone.utc)})
    yield tok
    mongo.user_sessions.delete_many({"session_token": tok})


@pytest.fixture(scope="module")
def admin_client(admin_session_token):
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json",
                      "Authorization": f"Bearer {admin_session_token}"})
    return s


@pytest.fixture(scope="module", autouse=True)
def ensure_story_approved(mongo):
    """Guarantee the demo story is in `approved` state before tests run."""
    mongo.stories.update_one({"_id": STORY_ID},
                             {"$set": {"status": "approved", "stage": "Ready", "error": ""}})
    yield
    mongo.stories.update_one({"_id": STORY_ID},
                             {"$set": {"status": "approved", "stage": "Ready", "error": ""}})


@pytest.fixture(scope="module")
def anon():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def client(session_token):
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json",
                      "Authorization": f"Bearer {session_token}"})
    return s


# ------------- auth gating -------------
class TestAuthGating:
    def test_root_open(self, anon):
        r = anon.get(f"{BASE_URL}/api/", timeout=30)
        assert r.status_code == 200
        assert "message" in r.json()

    def test_media_health_open(self, anon):
        r = anon.get(f"{BASE_URL}/api/media-health", timeout=30)
        assert r.status_code == 200

    def test_static_media_open(self, anon):
        r = anon.get(f"{BASE_URL}/api/media/final/{STORY_ID}.mp4", timeout=30, stream=True)
        assert r.status_code == 200

    def test_stories_requires_auth(self, anon):
        r = anon.get(f"{BASE_URL}/api/stories", timeout=30)
        assert r.status_code == 401

    def test_dashboard_requires_auth(self, anon):
        r = anon.get(f"{BASE_URL}/api/dashboard", timeout=30)
        assert r.status_code == 401

    def test_ig_settings_requires_auth(self, anon):
        r = anon.get(f"{BASE_URL}/api/settings/instagram", timeout=30)
        assert r.status_code == 401

    def test_invalid_session_id_returns_401(self, anon):
        r = anon.post(f"{BASE_URL}/api/auth/session",
                      json={"session_id": "BAD_INVALID_SESSION_ID"}, timeout=30)
        assert r.status_code == 401

    def test_auth_me_with_bearer(self, client):
        r = client.get(f"{BASE_URL}/api/auth/me", timeout=30)
        assert r.status_code == 200
        d = r.json()
        for k in ("user_id", "email", "name"):
            assert k in d
        assert "is_admin" in d, "is_admin field missing on /auth/me"
        assert d["is_admin"] is False, "non-admin QA user should have is_admin=False"

    def test_auth_me_admin_flag(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/auth/me", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d.get("is_admin") is True
        assert d.get("email", "").lower() == "nyai.deepak@gmail.com"


# ------------- Admin Console -------------
class TestAdminConsole:
    def test_admin_overview_forbidden_for_non_admin(self, client):
        r = client.get(f"{BASE_URL}/api/admin/overview", timeout=30)
        assert r.status_code == 403

    def test_admin_overview_unauthenticated(self, anon):
        r = anon.get(f"{BASE_URL}/api/admin/overview", timeout=30)
        assert r.status_code == 401

    def test_admin_overview_ok(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/admin/overview", timeout=60)
        assert r.status_code == 200
        d = r.json()
        for k in ("totals", "accounts", "channels", "videos"):
            assert k in d, f"missing key {k} in admin overview"


# ------------- Router chain / TTS local fallback -------------
class TestRouterChains:
    def test_router_status_chains(self, client):
        r = client.get(f"{BASE_URL}/api/router-status", timeout=30)
        assert r.status_code == 200
        d = r.json()
        # Accept multiple shapes; look for tts+image chain data
        blob = str(d).lower()
        assert "xtts" in blob, "xtts provider not present in router-status"
        assert "kokoro" in blob, "kokoro provider not present in router-status"
        assert "qwen_local" in blob, "qwen_local provider not present in router-status"
        assert "procedural" in blob, "procedural fallback not present in router-status"


# ------------- Instagram Integrations -------------
class TestInstagramIntegration:
    def test_get_ig_initial(self, client):
        r = client.get(f"{BASE_URL}/api/settings/instagram", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert "connected" in d

    def test_put_ig_fake_creds_returns_400(self, client):
        r = client.put(f"{BASE_URL}/api/settings/instagram",
                       json={"access_token": "FAKE_TOKEN_ABC123", "user_id": "1234567890"},
                       timeout=45)
        assert r.status_code == 400
        assert "Instagram rejected" in r.json().get("detail", "")

    def test_ig_still_not_connected_after_fake(self, client):
        r = client.get(f"{BASE_URL}/api/settings/instagram", timeout=30)
        assert r.status_code == 200
        assert r.json().get("connected") is False

    def test_delete_ig(self, client):
        r = client.delete(f"{BASE_URL}/api/settings/instagram", timeout=30)
        assert r.status_code == 200
        assert r.json().get("connected") is False

    def test_ig_publish_without_creds_fails_gracefully(self, client, mongo):
        # ensure story is approved (may have been left rendering by improve test on another worker)
        mongo.stories.update_one({"_id": STORY_ID},
                                 {"$set": {"status": "approved", "stage": "Ready", "error": ""}})
        r = client.post(f"{BASE_URL}/api/stories/{STORY_ID}/publish",
                        json={"platform": "instagram"}, timeout=30)
        assert r.status_code == 200
        job_id = r.json()["job_id"]
        # Poll job (may sit behind the improve job which takes ~90s under LLM retries)
        for _ in range(60):
            time.sleep(3)
            job = mongo.jobs.find_one({"_id": job_id})
            if job and job.get("status") in ("failed", "done"):
                break
        assert job is not None
        assert job.get("status") == "failed"
        assert "Instagram not connected" in (job.get("error") or "")


# ------------- Engagement (DRAFT-ONLY) -------------
class TestEngagement:
    def test_engagement_sync_no_crash(self, client, mongo):
        r = client.post(f"{BASE_URL}/api/social/engagement/sync", timeout=30)
        assert r.status_code == 200
        job_id = r.json()["job_id"]
        # Poll — under parallel workers backlog may push into 3-4min territory.
        job = None
        for _ in range(80):
            time.sleep(3)
            job = mongo.jobs.find_one({"_id": job_id})
            if job and job.get("status") in ("done", "failed"):
                break
        # Job must have been persisted and either done (no creds -> fetched=0) or failed with clear msg.
        assert job is not None, f"engagement job {job_id} not found in mongo"
        assert job.get("status") in ("done", "failed"), f"stuck: {job.get('status')}"
        if job.get("status") == "failed":
            # Only acceptable failure is missing YT/IG creds
            assert "creds" in (job.get("error") or "").lower() or "connect" in (job.get("error") or "").lower(), job.get("error")

    def test_no_auto_posted_replies(self, client):
        r = client.get(f"{BASE_URL}/api/social/comments", timeout=30)
        assert r.status_code == 200
        for c in r.json():
            # Every persisted comment must have posted=false unless manually approved
            assert c.get("posted") in (False, True)  # sanity — schema present
            if c.get("triage", {}).get("needs_reply") and not c.get("handled"):
                assert c.get("posted") is False, "draft-only violated: auto-posted a reply"


# ------------- Improvement Coach wiring -------------
class TestImprovementCoach:
    def test_improve_404(self, client):
        r = client.post(f"{BASE_URL}/api/stories/DOES_NOT_EXIST/improve", timeout=30)
        assert r.status_code == 404

    def test_improve_no_chunks_409(self, client):
        r = client.post(f"{BASE_URL}/api/stories/{STORY_NO_CHUNKS}/improve", timeout=30)
        assert r.status_code == 409
        assert "script" in r.json().get("detail", "").lower()

    def test_improve_enqueues_job(self, client, mongo):
        # Make sure story is not busy first
        mongo.stories.update_one({"_id": STORY_ID},
                                 {"$set": {"status": "approved", "stage": "Ready", "error": ""}})
        r = client.post(f"{BASE_URL}/api/stories/{STORY_ID}/improve", timeout=30)
        assert r.status_code == 200
        job_id = r.json()["job_id"]
        job = mongo.jobs.find_one({"_id": job_id})
        assert job is not None
        assert job["type"] == "improve"
        assert job["ref_id"] == STORY_ID
        # Wait for terminal state
        for _ in range(30):
            time.sleep(3)
            job = mongo.jobs.find_one({"_id": job_id})
            if job.get("status") in ("done", "failed"):
                break
        # Either it worked OR it failed due to LLM quota — both acceptable per review request.
        # But story integrity must be preserved:
        s = mongo.stories.find_one({"_id": STORY_ID})
        assert s is not None
        assert len((s.get("script") or {}).get("chunks") or []) >= 6, "script chunks lost after improve"
        # Reset if the improve left story stuck in rendering (bug workaround)
        if s.get("status") == "rendering" and job.get("status") == "failed":
            mongo.stories.update_one({"_id": STORY_ID},
                                     {"$set": {"status": "approved", "stage": "Ready", "error": ""}})


# ------------- Regression -------------
class TestRegression:
    def test_dashboard(self, client):
        r = client.get(f"{BASE_URL}/api/dashboard", timeout=30)
        assert r.status_code == 200
        d = r.json()
        for k in ("status_counts", "cost", "queue", "jobs", "recent_stories"):
            assert k in d

    def test_router_status(self, client):
        r = client.get(f"{BASE_URL}/api/router-status", timeout=30)
        assert r.status_code == 200
        assert isinstance(r.json(), dict) and len(r.json()) > 0

    def test_stories_list(self, client):
        r = client.get(f"{BASE_URL}/api/stories", timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list) and len(data) > 0

    def test_story_detail(self, client):
        r = client.get(f"{BASE_URL}/api/stories/{STORY_ID}", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d.get("id") == STORY_ID
        assert len((d.get("script") or {}).get("chunks") or []) > 0

    def test_channels(self, client):
        r = client.get(f"{BASE_URL}/api/channels", timeout=30)
        assert r.status_code == 200
        assert len(r.json()) >= 3

    def test_social_creds(self, client):
        r = client.get(f"{BASE_URL}/api/social/credentials", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert "youtube" in d and "instagram" in d

    def test_media_final(self, client):
        # static /api/media is exempt — verify open (no auth needed) 200
        r = requests.get(f"{BASE_URL}/api/media/final/{STORY_ID}.mp4", timeout=30, stream=True)
        assert r.status_code == 200
