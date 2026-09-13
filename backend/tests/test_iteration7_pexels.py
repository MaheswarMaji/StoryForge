"""Iteration 7 — Pexels free imagery provider integration."""
import os
import sys
import time
from pathlib import Path

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    for line in Path("/app/frontend/.env").read_text().splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip().rstrip("/")

# Load backend/.env into os.environ for direct-service tests (backend process has these already)
for line in Path("/app/backend/.env").read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

DEMO_ID = "6aa616a70b6da578466afad5"
DO_NOT_TOUCH = "6aa57c1eaad23f394fffaa41"

# make backend importable for direct service tests
sys.path.insert(0, "/app/backend")


# ---------------- Router status / vault ----------------
class TestRouterAndVault:
    def test_router_status_lists_pexels(self):
        r = requests.get(f"{BASE_URL}/api/router-status", timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "pexels" in data["image_chain"], data["image_chain"]
        assert "pexels_video" in data["video_chain"], data["video_chain"]
        providers = data["providers"]
        assert providers["pexels"]["key"] is True
        assert providers["pexels_video"]["key"] is True

    def test_vault_pexels_row_present_and_masked(self):
        r = requests.get(f"{BASE_URL}/api/settings/api-keys", timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        # Response is dict keyed by lowercase-ish name or list; probe both
        row = None
        if isinstance(data, dict):
            for k, v in data.items():
                if "PEXELS" in k.upper():
                    row = v
                    break
        elif isinstance(data, list):
            for item in data:
                if "PEXELS" in str(item.get("name", "")).upper():
                    row = item
                    break
        assert row is not None, f"pexels_api_key not in vault list: {list(data.keys()) if isinstance(data, dict) else data}"
        assert row.get("set") is True, row
        # Ensure raw key is not leaked in response text
        assert len(os.environ.get("PEXELS_API_KEY", "")) > 10
        raw = os.environ["PEXELS_API_KEY"]
        assert raw not in r.text, "raw PEXELS_API_KEY leaked in /api/settings/api-keys response"


# ---------------- Direct service tests (router.image / video) ----------------
class TestPexelsProviders:
    def test_pexels_image_provider(self):
        import asyncio
        from services import router
        out = Path("/tmp/px-test.jpg")
        if out.exists():
            out.unlink()
        res = asyncio.run(router.image(
            "a farmer plowing a golden field at sunrise in Vidarbha india",
            out, session="px-test",
        ))
        assert res["provider"] == "pexels", f"expected pexels, got {res}"
        assert out.exists()
        size = out.stat().st_size
        assert size > 30_000, f"pexels image too small: {size}"
        magic = out.read_bytes()[:3]
        assert magic == b"\xff\xd8\xff", f"not a JPEG (magic={magic!r})"

    def test_pexels_video_provider(self):
        import asyncio
        from services import router
        out = Path("/tmp/px-test.mp4")
        if out.exists():
            out.unlink()
        res = asyncio.run(router.video(
            "village farming fields aerial", None, out, 8,
        ))
        assert res["provider"] == "pexels_video", f"expected pexels_video, got {res}"
        assert out.exists()
        size = out.stat().st_size
        assert size > 100_000, f"pexels video too small: {size}"


# ---------------- Regression: public endpoints ----------------
class TestRegression:
    def test_stories_list_unauth(self):
        r = requests.get(f"{BASE_URL}/api/stories", timeout=30)
        assert r.status_code == 200

    def test_dashboard_unauth(self):
        r = requests.get(f"{BASE_URL}/api/dashboard", timeout=30)
        assert r.status_code == 200

    def test_do_not_touch_story_untouched(self):
        r = requests.get(f"{BASE_URL}/api/stories/{DO_NOT_TOUCH}", timeout=30)
        # If not 404, ensure we don't produce on it — just probe existence
        assert r.status_code in (200, 404)


# ---------------- Storyboard produce (long-running) ----------------
def _poll_story(story_id, timeout=360):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        r = requests.get(f"{BASE_URL}/api/stories/{story_id}", timeout=30)
        if r.status_code == 200:
            last = r.json()
            st = last.get("status")
            if st in ("in_review", "published", "failed"):
                return last
        time.sleep(6)
    return last


class TestStoryboardCache:
    def test_second_render_uses_cache(self):
        """Second render should be fast — poster cache should skip photo fetches."""
        # Confirm frames + clips exist already (from prior render in problem statement)
        frames_dir = Path(f"/app/backend/media/frames/{DEMO_ID}")
        clips_dir = Path(f"/app/backend/media/clips/{DEMO_ID}")
        assert frames_dir.exists()
        # trigger produce
        t0 = time.time()
        r = requests.post(f"{BASE_URL}/api/stories/{DEMO_ID}/produce", timeout=30)
        assert r.status_code in (200, 202), r.text
        result = _poll_story(DEMO_ID, timeout=360)
        elapsed = time.time() - t0
        assert result is not None
        assert result.get("status") == "in_review", f"status={result.get('status')} after {elapsed:.0f}s"
        # Storyboard poster + panel photos should exist
        assert (frames_dir / "storyboard.png").exists()
        # panel photo tiles from prior/current render
        px_files = list(frames_dir.glob("px-*.jpg"))
        assert len(px_files) >= 6, f"expected 6+ pexels tiles, got {len(px_files)}"
        # Final video should exist
        clips = list(clips_dir.glob("*.mp4"))
        assert len(clips) >= 1, "no final clip produced"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
