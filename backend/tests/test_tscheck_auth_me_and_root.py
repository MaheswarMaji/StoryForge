"""
Criterion: Signed-out story-detail use is free of console/network errors.
Backend half: GET /api/auth/me without a session returns 204, and the API
root reports the running message (used by ingress smoke checks).
"""
import httpx

BASE = "http://localhost:8001"


def test_auth_me_signed_out_returns_204():
    resp = httpx.get(f"{BASE}/api/auth/me", timeout=30)
    assert resp.status_code == 204, f"expected 204, got {resp.status_code} {resp.text[:200]}"


def test_api_root_reports_running():
    resp = httpx.get(f"{BASE}/api/", timeout=30)
    assert resp.status_code == 200
    assert "running" in resp.json().get("message", "").lower()
