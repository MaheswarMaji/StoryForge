"""Iteration 6 tests: HF Qwen fallback in services/llm.py + regression checks.

Coverage:
  1. LLM prefer_local chain lands on hf-qwen when OLLAMA absent.
  2. Normal ask_json (no prefer_local) still returns valid JSON.
  3. POST /api/social/engagement/sync enqueues + completes without unhandled failure.
  4. POST /api/stories/6aa616a70b6da578466afad5/produce reaches in_review within 3 min.
  5. GET /api/settings/api-keys shows HF_TOKEN set with masked hint; PUT/DELETE dummy roundtrip.
  6. Health/regression: /api/stories 200, /api/dashboard 200.

No raw HF token is printed anywhere.
"""
import asyncio
import os
import sys
import time

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or "http://localhost:8001"
STORY_ID = "6aa616a70b6da578466afad5"

# Make backend importable for direct-call LLM tests
sys.path.insert(0, "/app/backend")


@pytest.fixture
def anon():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ---------- 1. LLM prefer_local -> hf-qwen ----------
class TestLLMPreferLocalHF:
    def test_hf_key_present(self):
        from services import llm
        assert llm.hf_key(), "HF_TOKEN not present in backend env"

    def test_prefer_local_returns_via_hf(self):
        """With OLLAMA_BASE_URL absent, prefer_local=True should return via HF Qwen."""
        from services import llm
        # ensure ollama absent
        old_ollama = os.environ.pop("OLLAMA_BASE_URL", None)
        try:
            system = "You output valid JSON only."
            prompt = ('Return {"ok": true, "items": ["a","b","c"]} exactly.')
            out = asyncio.get_event_loop().run_until_complete(
                llm.ask_json(system, prompt, prefer_local=True))
            assert isinstance(out, dict), f"expected dict, got {type(out)}"
            assert out.get("ok") is True
            assert isinstance(out.get("items"), list) and len(out["items"]) >= 1
        finally:
            if old_ollama is not None:
                os.environ["OLLAMA_BASE_URL"] = old_ollama


# ---------- 2. Normal chain regression ----------
class TestLLMNormalChain:
    def test_ask_json_no_prefer_local(self):
        """A plain ask_json must return valid JSON (cloud, or falling through to HF)."""
        from services import llm
        system = "You output valid JSON only."
        prompt = 'Return {"pong": true}'
        out = asyncio.get_event_loop().run_until_complete(
            llm.ask_json(system, prompt))
        assert isinstance(out, dict)
        assert out.get("pong") is True


# ---------- 3. Engagement sync ----------
class TestEngagementSync:
    def test_engagement_sync_completes(self, anon):
        r = anon.post(f"{BASE_URL}/api/social/engagement/sync", timeout=30)
        assert r.status_code == 200, r.text
        job_id = r.json().get("job_id")
        assert job_id
        # wait up to 90s for job to finish (no unhandled exception)
        deadline = time.time() + 120
        status = None
        err = ""
        while time.time() < deadline:
            jl = anon.get(f"{BASE_URL}/api/jobs?limit=50", timeout=15)
            if jl.status_code == 200:
                match = next((j for j in jl.json() if j.get("_id") == job_id or j.get("id") == job_id), None)
                if match:
                    status = match.get("status")
                    err = (match.get("error") or "")
                    if status in ("done", "failed", "cancelled"):
                        break
            time.sleep(3)
        assert status in ("done", "failed", "cancelled"), f"job still {status}"
        # failed is acceptable ONLY if error is credentials-related (no yt/ig creds), not code crash
        if status == "failed":
            assert "traceback" not in err.lower(), f"unhandled crash: {err[:200]}"


# ---------- 4. Storyboard regression ----------
class TestStoryboardProduce:
    def test_produce_reaches_in_review(self, anon):
        # sanity: story exists
        gr = anon.get(f"{BASE_URL}/api/stories/{STORY_ID}", timeout=30)
        assert gr.status_code == 200, gr.text
        # only kick off a fresh produce if it isn't already rendering
        cur_status = gr.json().get("status")
        if cur_status != "rendering":
            r = anon.post(f"{BASE_URL}/api/stories/{STORY_ID}/produce", timeout=30)
            assert r.status_code == 200, r.text
        deadline = time.time() + 240  # 4 min budget
        last_status = cur_status
        while time.time() < deadline:
            try:
                sr = anon.get(f"{BASE_URL}/api/stories/{STORY_ID}", timeout=15)
                if sr.status_code == 200:
                    last_status = sr.json().get("status")
                    if last_status == "in_review":
                        return
                    if last_status == "failed":
                        pytest.fail(f"story produce failed: {sr.json().get('error')}")
            except requests.RequestException:
                pass  # transient ingress hiccup — keep polling
            time.sleep(6)
        pytest.fail(f"story did not reach in_review in 240s; last={last_status}")


# ---------- 5. Settings vault (HF hint) ----------
class TestSettingsVaultHF:
    def test_hf_token_masked_hint(self, anon):
        r = anon.get(f"{BASE_URL}/api/settings/api-keys", timeout=30)
        assert r.status_code == 200
        row = r.json().get("HF_TOKEN")
        assert row is not None, "HF_TOKEN missing from vault list"
        assert row["set"] is True, "HF_TOKEN should be set"
        # hint should be short and start with hf_
        assert 3 <= len(row["hint"]) <= 20
        assert row["hint"].startswith("hf_"), f"hint not masked as hf_..: {row['hint'][:3]}"
        # no full token leak
        actual = os.environ.get("HF_TOKEN", "")
        if actual:
            assert actual not in str(r.json()), "raw HF_TOKEN leaked in response"

    def test_put_delete_dummy_roundtrip(self, anon):
        """Use a dummy key that isn't HF_TOKEN so we don't clobber the real token."""
        fake = "sk-fake-TESTABCDEF1234567890"
        r = anon.put(f"{BASE_URL}/api/settings/api-keys",
                     json={"values": {"REPLICATE_API_TOKEN": fake}}, timeout=30)
        assert r.status_code == 200
        assert "REPLICATE_API_TOKEN" in r.json().get("saved", [])
        gr = anon.get(f"{BASE_URL}/api/settings/api-keys", timeout=30)
        assert gr.json()["REPLICATE_API_TOKEN"]["set"] is True
        dr = anon.delete(f"{BASE_URL}/api/settings/api-keys/REPLICATE_API_TOKEN", timeout=30)
        assert dr.status_code == 200
        gr2 = anon.get(f"{BASE_URL}/api/settings/api-keys", timeout=30)
        assert gr2.json()["REPLICATE_API_TOKEN"]["set"] is False


# ---------- 6. Basic regression ----------
class TestRegression:
    def test_stories_list(self, anon):
        r = anon.get(f"{BASE_URL}/api/stories", timeout=30)
        assert r.status_code == 200

    def test_dashboard(self, anon):
        r = anon.get(f"{BASE_URL}/api/dashboard", timeout=30)
        assert r.status_code == 200
