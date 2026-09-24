"""Exact generation failure diagnostics + Studio config honesty (backend/API surface).

- generation_events already contains the real Gemini HTTP 429 RESOURCE_EXHAUSTED / limit: 0
  diagnostic captured from a genuine attempt (never fabricated) — GET /api/generation-events
  exposes it with the exact provider error text and a billing/quota next-step action.
- STUDIO_API_TOKEN vault row is present and reports not-set (no token supplied) without ever
  leaking a value. POST /api/settings/studio/test explains "not configured" honestly since no
  Studio base URL/token exist, instead of pretending a live connection.
- API key vault persistence: writing a harmless tscheck test key round-trips through
  GET/PUT /api/settings/api-keys and is deletable again (proves new-key persistence without
  touching any real provider key).
"""
import httpx

BASE = "http://localhost:8001"


def test_generation_events_expose_real_gemini_429_diagnostic():
    resp = httpx.get(f"{BASE}/api/generation-events", timeout=30)
    assert resp.status_code == 200, resp.text
    events = resp.json()
    gemini_429 = [e for e in events if e.get("provider") == "gemini" and e.get("http_status") == 429]
    assert gemini_429, "expected at least one recorded Gemini 429 diagnostic event"
    event = gemini_429[0]
    assert event["code"] == "RESOURCE_EXHAUSTED"
    assert "limit: 0" in event["message"]
    assert event["status"] == "failed"
    assert event["action"], "expected a next-step action (billing/quota), not a bare failure"
    assert "billing" in event["action"].lower() or "quota" in event["action"].lower()
    # never a generic "all providers failed" placeholder — exact provider + reason are named
    assert "all providers failed" not in event["message"].lower()


def test_studio_not_configured_is_explained_honestly():
    keys = httpx.get(f"{BASE}/api/settings/api-keys", timeout=30)
    assert keys.status_code == 200, keys.text
    row = keys.json().get("STUDIO_API_TOKEN")
    assert row is not None, "STUDIO_API_TOKEN vault row missing"
    assert row["set"] is False
    assert row["hint"] in ("", None)

    settings = httpx.get(f"{BASE}/api/settings/media-engines", timeout=30).json()
    assert settings["studio_token_set"] is False

    test = httpx.post(f"{BASE}/api/settings/studio/test", timeout=30)
    assert test.status_code == 200, test.text
    body = test.json()
    assert body["status"] == "not_connected"
    assert body["message"], "expected an explanatory message, not a silent failure"


def test_api_key_vault_persists_new_key_and_cleans_up():
    # REPLICATE_API_TOKEN is an allowed vault key that is unset in this environment and not the
    # active default provider for any engine, so setting/clearing it is safe and reversible.
    marker_name = "REPLICATE_API_TOKEN"
    marker_value = "tscheck-value-12345"
    baseline = httpx.get(f"{BASE}/api/settings/api-keys", timeout=30).json().get(marker_name, {})
    assert baseline.get("set") is False, "test expects this vault slot to start unset"

    put = httpx.put(f"{BASE}/api/settings/api-keys", json={"values": {marker_name: marker_value}}, timeout=30)
    assert put.status_code == 200, put.text
    assert marker_name in put.json().get("saved", [])

    got = httpx.get(f"{BASE}/api/settings/api-keys", timeout=30)
    assert got.status_code == 200
    row = got.json().get(marker_name)
    assert row is not None and row["set"] is True
    # value itself is never echoed back in plaintext
    assert marker_value not in got.text

    delete = httpx.delete(f"{BASE}/api/settings/api-keys/{marker_name}", timeout=30)
    assert delete.status_code == 200, delete.text
    after = httpx.get(f"{BASE}/api/settings/api-keys", timeout=30).json().get(marker_name)
    assert after is None or after.get("set") is False
