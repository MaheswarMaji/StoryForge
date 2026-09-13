"""Iteration 7 tests — Stability AI integration (image provider).

Covers:
- Router status includes 'stability' with key & healthy true, chain order
- Direct services.llm._stability_image call produces a real PNG > 500KB
- Vault (GET /api/settings/api-keys) exposes STABILITY_API_KEY
- Frontend SettingsPage labels include a Stability row
- Regression: /api/stories, /api/dashboard 200; /api/admin/overview 401 anon
- Storyboard story 6aa616a70b6da578466afad5 in_review
"""
import os
import re
import sys
import time
from pathlib import Path

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # fallback for local runs; kept simple, no default url logic
    BASE_URL = "http://localhost:8001"

sys.path.insert(0, "/app/backend")


# ---------- fixtures ----------
@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ---------- 1. router-status ----------
class TestRouterStatus:
    def test_router_status_ok(self, api):
        r = api.get(f"{BASE_URL}/api/router-status", timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert "image_chain" in data
        assert "providers" in data
        self.data = data

    def test_stability_provider_present(self, api):
        r = api.get(f"{BASE_URL}/api/router-status", timeout=30)
        data = r.json()
        providers = data["providers"]
        assert "stability" in providers, "stability provider missing from /api/router-status"
        assert providers["stability"]["key"] is True, "STABILITY_API_KEY not detected in env"
        assert providers["stability"]["healthy"] is True

    def test_image_chain_order(self, api):
        r = api.get(f"{BASE_URL}/api/router-status", timeout=30)
        chain = r.json()["image_chain"]
        assert "stability" in chain, f"stability not in image chain: {chain}"
        # openai first, stability second per problem statement
        assert chain[0] == "openai", f"expected openai first, got {chain[0]}"
        assert chain[1] == "stability", f"expected stability second, got {chain[1]}"


# ---------- 2. Direct stability image ----------
class TestStabilityDirect:
    def test_stability_image_live_call(self):
        """Live call to Stability AI Stable Image Core — costs ~$0.03."""
        import asyncio

        from services.llm import _stability_image

        out = Path("/tmp/stab-verif.png")
        if out.exists():
            out.unlink()
        prompt = ("a 40-year-old Indian farmer, light-blue cotton kurta, "
                  "golden wheat field, dawn, cinematic photorealistic")
        try:
            ok = asyncio.run(_stability_image(prompt, out))
        except Exception as e:
            pytest.fail(f"_stability_image raised: {e}")
        assert ok is True
        assert out.exists()
        size = out.stat().st_size
        assert size > 500_000, f"expected >500KB real PNG, got {size} bytes"
        header = out.read_bytes()[:3]
        assert header in (b"\x89PN", b"\xff\xd8\xff"), f"bad magic bytes: {header!r}"


# ---------- 3. Vault ----------
class TestVault:
    def test_api_keys_lists_stability(self, api):
        r = api.get(f"{BASE_URL}/api/settings/api-keys", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert "STABILITY_API_KEY" in data, (
            f"STABILITY_API_KEY missing from vault. Keys: {sorted(data.keys())}"
        )
        entry = data["STABILITY_API_KEY"]
        assert entry.get("set") is True, "STABILITY_API_KEY not marked set"
        assert entry.get("hint"), "no masked hint for STABILITY_API_KEY"
        # Never leak full key
        assert len(entry["hint"]) < 20


# ---------- 4. Regression ----------
class TestRegression:
    def test_stories_public(self, api):
        r = api.get(f"{BASE_URL}/api/stories", timeout=20)
        assert r.status_code == 200

    def test_dashboard_public(self, api):
        r = api.get(f"{BASE_URL}/api/dashboard", timeout=20)
        assert r.status_code == 200

    def test_admin_overview_anon_401(self, api):
        # fresh session with no auth
        s = requests.Session()
        r = s.get(f"{BASE_URL}/api/admin/overview", timeout=15)
        assert r.status_code in (401, 403), f"expected 401/403, got {r.status_code}"


# ---------- 5. Storyboard regression ----------
class TestStoryboardRegression:
    STORY_ID = "6aa616a70b6da578466afad5"

    def test_story_exists_and_reviewable(self, api):
        r = api.get(f"{BASE_URL}/api/stories/{self.STORY_ID}", timeout=20)
        if r.status_code == 404:
            pytest.skip("storyboard regression story missing in this env")
        assert r.status_code == 200
        data = r.json()
        assert data.get("status") in ("in_review", "approved", "posted", "scheduled"), (
            f"unexpected status: {data.get('status')}"
        )


# ---------- 6. Frontend settings labels ----------
class TestFrontendSettingsLabel:
    def test_stability_label_present(self):
        p = Path("/app/frontend/src/pages/SettingsPage.jsx")
        assert p.exists()
        src = p.read_text()
        assert re.search(r"STABILITY_API_KEY", src), (
            "SettingsPage.jsx has no STABILITY_API_KEY label — "
            "vault row will render with no description"
        )
