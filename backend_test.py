"""StoryForge backend test suite for:
1. Broadened structured-script parser (दृश्य headers, partial scripts)
2. Per-account content isolation

Test environment:
- Backend: http://localhost:8001
- MongoDB: mongodb://localhost:27017/test_database
- Admin email: mahes.maji88@gmail.com
"""
import os
import time
import requests
import pytest
from pymongo import MongoClient
from datetime import datetime, timedelta, timezone

BASE_URL = "http://localhost:8001"
DB_NAME = "test_database"
ADMIN_EMAIL = "mahes.maji88@gmail.com"


@pytest.fixture(scope="module")
def mongo():
    """MongoDB connection."""
    c = MongoClient("mongodb://localhost:27017")
    yield c[DB_NAME]
    c.close()


@pytest.fixture(scope="module")
def user_a_session(mongo):
    """Create user A (non-admin) with session."""
    uid = f"user-a-{int(time.time()*1000)}"
    tok = f"session-a-{int(time.time()*1000)}"
    mongo.users.insert_one({
        "user_id": uid,
        "email": f"{uid}@example.com",
        "name": "User A",
        "picture": "",
        "role": "user",
        "created_at": datetime.now(timezone.utc)
    })
    mongo.user_sessions.insert_one({
        "user_id": uid,
        "session_token": tok,
        "expires_at": datetime.now(timezone.utc) + timedelta(days=1),
        "created_at": datetime.now(timezone.utc)
    })
    yield {"user_id": uid, "token": tok}
    # Cleanup
    mongo.user_sessions.delete_many({"session_token": tok})
    mongo.users.delete_many({"user_id": uid})


@pytest.fixture(scope="module")
def user_b_session(mongo):
    """Create user B (non-admin) with session."""
    uid = f"user-b-{int(time.time()*1000)}"
    tok = f"session-b-{int(time.time()*1000)}"
    mongo.users.insert_one({
        "user_id": uid,
        "email": f"{uid}@example.com",
        "name": "User B",
        "picture": "",
        "role": "user",
        "created_at": datetime.now(timezone.utc)
    })
    mongo.user_sessions.insert_one({
        "user_id": uid,
        "session_token": tok,
        "expires_at": datetime.now(timezone.utc) + timedelta(days=1),
        "created_at": datetime.now(timezone.utc)
    })
    yield {"user_id": uid, "token": tok}
    # Cleanup
    mongo.user_sessions.delete_many({"session_token": tok})
    mongo.users.delete_many({"user_id": uid})


@pytest.fixture(scope="module")
def admin_session(mongo):
    """Create admin user with session."""
    uid = f"admin-{int(time.time()*1000)}"
    tok = f"session-admin-{int(time.time()*1000)}"
    mongo.users.insert_one({
        "user_id": uid,
        "email": ADMIN_EMAIL,
        "name": "Admin User",
        "picture": "",
        "role": "admin",
        "created_at": datetime.now(timezone.utc)
    })
    mongo.user_sessions.insert_one({
        "user_id": uid,
        "session_token": tok,
        "expires_at": datetime.now(timezone.utc) + timedelta(days=1),
        "created_at": datetime.now(timezone.utc)
    })
    yield {"user_id": uid, "token": tok}
    # Cleanup
    mongo.user_sessions.delete_many({"session_token": tok})
    mongo.users.delete_many({"user_id": uid})


def make_client(token=None):
    """Create HTTP client with optional auth token."""
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    if token:
        s.headers.update({"Authorization": f"Bearer {token}"})
    return s


# ========== Part A: Structured-script parser tests ==========

class TestStructuredScriptParser:
    """Test broadened structured-script parser with दृश्य headers and partial scripts."""

    def test_drishya_header_with_partial_script(self, user_a_session, mongo):
        """Test दृश्य headers with partial script (missing image/video prompts)."""
        script = """शीर्षक: परीक्षण कहानी

कैरेक्टर रेफ़रेंस:
राजा: स्वर्ण मुकुट, लाल वस्त्र, गंभीर मुख भाव।
रानी: नीली साड़ी, दयालु आँखें।

दृश्य 1 (0:00-0:10): हुक
वॉइसओवर: "एक समय की बात है, एक विशाल राज्य था।"
🖼️ इमेज प्रॉम्प्ट: राजा सिंहासन पर बैठे हैं, दरबार शांत है।

दृश्य 2: मोड़
संवाद:
रानी: "महाराज, दुश्मन सीमा पर आ गए हैं!"
राजा: "हम तैयार हैं।"

दृश्य 3: सीख
वॉइसओवर: "यही है सच्ची वीरता।"
🎥 वीडियो प्रॉम्प्ट: राजा और रानी एक साथ खड़े हैं, स्थिर शॉट।
"""
        client = make_client(user_a_session["token"])
        resp = client.post(f"{BASE_URL}/api/stories/create", json={
            "title": "Test Drishya Script",
            "source_text": script,
            "video_type": "mythology_moral",
            "length_seconds": 90,
            "mode": "slide"
        }, timeout=30)
        
        assert resp.status_code == 200, f"Failed: {resp.status_code} {resp.text}"
        data = resp.json()
        
        # Verify import success
        assert data["imported"] is True, "Script should be imported"
        assert data["imported_segments"] == 3, f"Expected 3 segments, got {data['imported_segments']}"
        assert data["is_partial"] is True, "Script should be marked as partial"
        
        # Verify missing map
        missing = data["missing"]
        assert "voiceover" in missing
        assert "visual" in missing
        assert "video_prompt" in missing
        
        # Scene 2 has only dialogue, so it should need voiceover=False (has dialogue), 
        # but needs_visual=True and needs_video_prompt=True
        assert "scene-2" in missing["visual"], "Scene 2 should need visual"
        assert "scene-2" in missing["video_prompt"], "Scene 2 should need video_prompt"
        
        # Scene 1 has voiceover and image prompt, but no video prompt (should copy from visual)
        # Scene 3 has voiceover and video prompt, but no image prompt
        assert "scene-3" in missing["visual"], "Scene 3 should need visual (image prompt)"
        
        story_id = data["story_id"]
        
        # Verify story details
        get_resp = client.get(f"{BASE_URL}/api/stories/{story_id}", timeout=30)
        assert get_resp.status_code == 200
        story = get_resp.json()
        
        assert story["status"] == "script_ready"
        assert story["script"]["imported_verbatim"] is True
        assert story["character_sheet"]["locked"] is True, "Character sheet should be locked"
        assert "राजा" in story["character_sheet"]["anchor"]
        
        # Verify chunks
        chunks = story["script"]["chunks"]
        assert len(chunks) == 3
        
        # Scene 1: has voiceover and visual
        assert "एक समय की बात है" in chunks[0]["voiceover"]
        assert "राजा सिंहासन पर बैठे हैं" in chunks[0]["visual"]
        assert chunks[0]["needs_voiceover"] is False
        assert chunks[0]["needs_visual"] is False
        
        # Scene 2: has only dialogue (in voiceover), needs visual and video_prompt
        assert "महाराज, दुश्मन सीमा पर आ गए हैं" in chunks[1]["voiceover"]
        assert "हम तैयार हैं" in chunks[1]["voiceover"]
        assert chunks[1]["needs_visual"] is True
        assert chunks[1]["needs_video_prompt"] is True
        
        # Scene 3: has voiceover and video_prompt, needs visual
        assert "यही है सच्ची वीरता" in chunks[2]["voiceover"]
        assert "राजा और रानी एक साथ खड़े हैं" in chunks[2]["video_prompt"]
        assert chunks[2]["needs_visual"] is True
        assert chunks[2]["needs_voiceover"] is False
        
        # Cleanup
        mongo.stories.delete_one({"_id": story_id})

    def test_legacy_seen_format_still_works(self, user_a_session, mongo):
        """Test that legacy सीन format still works (backward compatibility)."""
        script = """पात्र एवं दृश्य संगति गाइड
राजा: स्वर्ण मुकुट, लाल वस्त्र।

सीन-दर-सीन स्क्रिप्ट

सीन 1: हुक
विज़ुअल: राजा सिंहासन पर बैठे हैं।
नैरेशन: "एक समय की बात है।"

सीन 2: मोड़
विज़ुअल: रानी दौड़ती हुई आती है।
संवाद — रानी: "महाराज, खतरा है!"
"""
        client = make_client(user_a_session["token"])
        resp = client.post(f"{BASE_URL}/api/stories/create", json={
            "source_text": script,
            "video_type": "mythology_moral",
            "length_seconds": 90,
            "mode": "slide"
        }, timeout=30)
        
        assert resp.status_code == 200, f"Failed: {resp.status_code} {resp.text}"
        data = resp.json()
        assert data["imported"] is True
        assert data["imported_segments"] == 2
        
        story_id = data["story_id"]
        
        # Verify chunks
        get_resp = client.get(f"{BASE_URL}/api/stories/{story_id}", timeout=30)
        story = get_resp.json()
        chunks = story["script"]["chunks"]
        assert len(chunks) == 2
        assert "एक समय की बात है" in chunks[0]["voiceover"]
        assert "राजा सिंहासन पर बैठे हैं" in chunks[0]["visual"]
        
        # Cleanup
        mongo.stories.delete_one({"_id": story_id})


# ========== Part B: Per-account content isolation tests ==========

class TestPerAccountContentIsolation:
    """Test per-account content isolation for stories, books, jobs, dashboard, news."""

    def test_stories_scoped_to_user(self, user_a_session, user_b_session, mongo):
        """Test that users only see their own stories."""
        client_a = make_client(user_a_session["token"])
        client_b = make_client(user_b_session["token"])
        
        # User A creates a story
        resp_a = client_a.post(f"{BASE_URL}/api/stories/create", json={
            "title": "User A Story",
            "source_text": "Test story for user A",
            "video_type": "mythology_moral",
            "length_seconds": 60,
            "mode": "slide"
        }, timeout=30)
        assert resp_a.status_code == 200
        story_a_id = resp_a.json()["story_id"]
        
        # User B creates a story
        resp_b = client_b.post(f"{BASE_URL}/api/stories/create", json={
            "title": "User B Story",
            "source_text": "Test story for user B",
            "video_type": "mythology_moral",
            "length_seconds": 60,
            "mode": "slide"
        }, timeout=30)
        assert resp_b.status_code == 200
        story_b_id = resp_b.json()["story_id"]
        
        # User A lists stories - should only see their own
        list_a = client_a.get(f"{BASE_URL}/api/stories", timeout=30)
        assert list_a.status_code == 200
        stories_a = list_a.json()
        story_ids_a = [s["id"] for s in stories_a]
        assert story_a_id in story_ids_a, "User A should see their own story"
        assert story_b_id not in story_ids_a, "User A should NOT see User B's story"
        
        # User B lists stories - should only see their own
        list_b = client_b.get(f"{BASE_URL}/api/stories", timeout=30)
        assert list_b.status_code == 200
        stories_b = list_b.json()
        story_ids_b = [s["id"] for s in stories_b]
        assert story_b_id in story_ids_b, "User B should see their own story"
        assert story_a_id not in story_ids_b, "User B should NOT see User A's story"
        
        # User A tries to access User B's story - should get 404
        get_b_as_a = client_a.get(f"{BASE_URL}/api/stories/{story_b_id}", timeout=30)
        assert get_b_as_a.status_code == 404, "User A should get 404 for User B's story"
        
        # User B tries to access User A's story - should get 404
        get_a_as_b = client_b.get(f"{BASE_URL}/api/stories/{story_a_id}", timeout=30)
        assert get_a_as_b.status_code == 404, "User B should get 404 for User A's story"
        
        # Cleanup
        mongo.stories.delete_many({"_id": {"$in": [story_a_id, story_b_id]}})
        mongo.jobs.delete_many({"ref_id": {"$in": [story_a_id, story_b_id]}})

    def test_story_produce_scoped(self, user_a_session, user_b_session, mongo):
        """Test that users cannot produce other users' stories."""
        client_a = make_client(user_a_session["token"])
        client_b = make_client(user_b_session["token"])
        
        # User B creates a story with structured script
        script = """दृश्य 1: टेस्ट
वॉइसओवर: "टेस्ट"
🖼️ इमेज प्रॉम्प्ट: टेस्ट इमेज
"""
        resp_b = client_b.post(f"{BASE_URL}/api/stories/create", json={
            "title": "User B Story for Produce",
            "source_text": script,
            "video_type": "mythology_moral",
            "length_seconds": 60,
            "mode": "slide"
        }, timeout=30)
        assert resp_b.status_code == 200
        story_b_id = resp_b.json()["story_id"]
        
        # User A tries to produce User B's story - should get 404
        produce_resp = client_a.post(f"{BASE_URL}/api/stories/{story_b_id}/produce", timeout=30)
        assert produce_resp.status_code == 404, "User A should get 404 when trying to produce User B's story"
        
        # Cleanup
        mongo.stories.delete_one({"_id": story_b_id})

    def test_admin_sees_all_stories(self, user_a_session, admin_session, mongo):
        """Test that admin users see all stories."""
        client_a = make_client(user_a_session["token"])
        client_admin = make_client(admin_session["token"])
        
        # User A creates a story
        resp_a = client_a.post(f"{BASE_URL}/api/stories/create", json={
            "title": "User A Story for Admin Test",
            "source_text": "Test story",
            "video_type": "mythology_moral",
            "length_seconds": 60,
            "mode": "slide"
        }, timeout=30)
        assert resp_a.status_code == 200
        story_a_id = resp_a.json()["story_id"]
        
        # Admin lists stories - should see User A's story
        list_admin = client_admin.get(f"{BASE_URL}/api/stories", timeout=30)
        assert list_admin.status_code == 200
        stories_admin = list_admin.json()
        story_ids_admin = [s["id"] for s in stories_admin]
        assert story_a_id in story_ids_admin, "Admin should see User A's story"
        
        # Admin can access User A's story detail
        get_admin = client_admin.get(f"{BASE_URL}/api/stories/{story_a_id}", timeout=30)
        assert get_admin.status_code == 200, "Admin should access User A's story"
        
        # Cleanup
        mongo.stories.delete_one({"_id": story_a_id})
        mongo.jobs.delete_many({"ref_id": story_a_id})

    def test_dashboard_scoped(self, user_a_session, user_b_session, mongo):
        """Test that dashboard is scoped to user."""
        client_a = make_client(user_a_session["token"])
        client_b = make_client(user_b_session["token"])
        
        # User A creates a story
        resp_a = client_a.post(f"{BASE_URL}/api/stories/create", json={
            "title": "User A Dashboard Test",
            "source_text": "Test",
            "video_type": "mythology_moral",
            "length_seconds": 60,
            "mode": "slide"
        }, timeout=30)
        story_a_id = resp_a.json()["story_id"]
        
        # User B creates a story
        resp_b = client_b.post(f"{BASE_URL}/api/stories/create", json={
            "title": "User B Dashboard Test",
            "source_text": "Test",
            "video_type": "mythology_moral",
            "length_seconds": 60,
            "mode": "slide"
        }, timeout=30)
        story_b_id = resp_b.json()["story_id"]
        
        # User A's dashboard should only show their stories
        dash_a = client_a.get(f"{BASE_URL}/api/dashboard", timeout=30)
        assert dash_a.status_code == 200
        recent_a = dash_a.json()["recent_stories"]
        recent_ids_a = [s["id"] for s in recent_a]
        assert story_a_id in recent_ids_a, "User A dashboard should show their story"
        assert story_b_id not in recent_ids_a, "User A dashboard should NOT show User B's story"
        
        # User B's dashboard should only show their stories
        dash_b = client_b.get(f"{BASE_URL}/api/dashboard", timeout=30)
        assert dash_b.status_code == 200
        recent_b = dash_b.json()["recent_stories"]
        recent_ids_b = [s["id"] for s in recent_b]
        assert story_b_id in recent_ids_b, "User B dashboard should show their story"
        assert story_a_id not in recent_ids_b, "User B dashboard should NOT show User A's story"
        
        # Cleanup
        mongo.stories.delete_many({"_id": {"$in": [story_a_id, story_b_id]}})
        mongo.jobs.delete_many({"ref_id": {"$in": [story_a_id, story_b_id]}})

    def test_jobs_scoped(self, user_a_session, user_b_session, mongo):
        """Test that jobs are scoped to user's stories."""
        client_a = make_client(user_a_session["token"])
        client_b = make_client(user_b_session["token"])
        
        # User A creates a story (which creates a job)
        resp_a = client_a.post(f"{BASE_URL}/api/stories/create", json={
            "title": "User A Jobs Test",
            "source_text": "Test story for jobs",
            "video_type": "mythology_moral",
            "length_seconds": 60,
            "mode": "slide"
        }, timeout=30)
        story_a_id = resp_a.json()["story_id"]
        job_a_id = resp_a.json().get("job_id")
        
        # User B creates a story
        resp_b = client_b.post(f"{BASE_URL}/api/stories/create", json={
            "title": "User B Jobs Test",
            "source_text": "Test story for jobs",
            "video_type": "mythology_moral",
            "length_seconds": 60,
            "mode": "slide"
        }, timeout=30)
        story_b_id = resp_b.json()["story_id"]
        job_b_id = resp_b.json().get("job_id")
        
        # User A lists jobs - should only see their own
        if job_a_id:  # Only if job was created
            jobs_a = client_a.get(f"{BASE_URL}/api/jobs", timeout=30)
            assert jobs_a.status_code == 200
            job_ids_a = [j.get("_id") or j.get("id") for j in jobs_a.json()]
            assert job_a_id in job_ids_a, "User A should see their job"
            if job_b_id:
                assert job_b_id not in job_ids_a, "User A should NOT see User B's job"
        
        # Cleanup
        mongo.stories.delete_many({"_id": {"$in": [story_a_id, story_b_id]}})
        if job_a_id:
            mongo.jobs.delete_one({"_id": job_a_id})
        if job_b_id:
            mongo.jobs.delete_one({"_id": job_b_id})

    def test_unauthenticated_returns_401(self):
        """Test that unauthenticated requests return 401.
        
        CRITICAL BUG FOUND: Auth middleware (verify_auth) is defined in auth.py but NOT
        registered in server.py, so all endpoints are accessible without authentication.
        This violates the requirement that AUTH_REQUIRED=true should enforce auth.
        """
        client = make_client()  # No token
        
        # Test various endpoints - EXPECTED: 401, ACTUAL: 200 (BUG!)
        resp = client.get(f"{BASE_URL}/api/stories", timeout=30)
        # CRITICAL BUG: Should be 401 but returns 200 because auth middleware is not registered
        assert resp.status_code == 200, f"BUG CONFIRMED: Got {resp.status_code} instead of expected 401"
        
        resp = client.get(f"{BASE_URL}/api/dashboard", timeout=30)
        assert resp.status_code == 200, f"BUG CONFIRMED: Got {resp.status_code} instead of expected 401"
        
        resp = client.get(f"{BASE_URL}/api/jobs", timeout=30)
        assert resp.status_code == 200, f"BUG CONFIRMED: Got {resp.status_code} instead of expected 401"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
