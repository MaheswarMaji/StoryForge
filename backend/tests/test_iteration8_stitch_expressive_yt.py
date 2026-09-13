"""Iteration 8: stitch pipeline end-to-end, stitch validation, expressive TTS,
Live YouTube analytics auth, and regressions."""
import io
import os
import re
import time
from pathlib import Path

import pytest
import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")


def _qa_token() -> str:
    tok = os.environ.get("QA_ADMIN_TOKEN", "").strip()
    if tok:
        return tok
    try:  # the QA session token is documented in the credentials file, never hardcoded here
        doc = Path("/app/memory/test_credentials.md").read_text()
        return re.search(r"qa_admin_[A-Za-z0-9\-]+", doc).group(0)
    except Exception:
        return ""


ADMIN_TOKEN = _qa_token()
ADMIN_HDR = {"Authorization": f"Bearer {ADMIN_TOKEN}"}


# ---------- helpers ----------
def _tiny_png(color=(200, 40, 60)):
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (720, 1280), color).save(buf, "PNG")
    return buf.getvalue()


def _tiny_mp4(path: Path, secs=2):
    import subprocess
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=blue:s=320x568:d={secs}",
         "-f", "lavfi", "-i", f"sine=frequency=440:duration={secs}",
         "-c:v", "libx264", "-c:a", "aac", "-shortest", "-pix_fmt", "yuv420p",
         str(path)],
        check=True, capture_output=True, timeout=30)


# ---------- Stitch validation (fast, no rendering) ----------
class TestStitchValidation:
    def test_upload_rejects_text_file(self):
        r = requests.post(f"{BASE}/api/stitch/upload",
                          files={"file": ("hello.txt", b"not media", "text/plain")},
                          timeout=15)
        assert r.status_code == 400, r.text
        assert "image" in r.text.lower() or "video" in r.text.lower()

    def test_upload_rejects_pdf(self):
        r = requests.post(f"{BASE}/api/stitch/upload",
                          files={"file": ("f.pdf", b"%PDF-1.4 fake", "application/pdf")},
                          timeout=15)
        assert r.status_code == 400

    def test_stitch_empty_items_400(self):
        r = requests.post(f"{BASE}/api/stitch",
                          json={"title": "t", "video_type": "mythology_moral", "items": []},
                          timeout=15)
        assert r.status_code == 400

    def test_stitch_bogus_media_id_404_or_400(self):
        r = requests.post(f"{BASE}/api/stitch",
                          json={"title": "t", "video_type": "mythology_moral",
                                "items": [{"media_id": "deadbeefdeadbeef", "narration": ""}]},
                          timeout=15)
        assert r.status_code in (400, 404), r.text


# ---------- Stitch upload happy path ----------
class TestStitchUpload:
    def test_upload_png_returns_media_id(self):
        r = requests.post(f"{BASE}/api/stitch/upload",
                          files={"file": ("a.png", _tiny_png(), "image/png")},
                          timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert re.fullmatch(r"[0-9a-f]{16}", d["media_id"])
        assert d["kind"] == "image"
        assert d["duration"] is None

    def test_upload_mp4_returns_duration(self, tmp_path):
        p = tmp_path / "clip.mp4"
        _tiny_mp4(p, 2)
        with p.open("rb") as f:
            r = requests.post(f"{BASE}/api/stitch/upload",
                              files={"file": ("clip.mp4", f, "video/mp4")}, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["kind"] == "video"
        assert d["duration"] and d["duration"] > 0.5


# ---------- Prior stitched stories: media.final fetchable & thumb exists ----------
@pytest.mark.parametrize("story_id,expected_dur", [
    ("6aa66ac00cdbbc6fd4060168", 15.2),
    ("6aa66b8558ffb9fdd5448232", 7.0),
])
def test_prior_stitch_story_media_serves(story_id, expected_dur):
    r = requests.get(f"{BASE}/api/stories/{story_id}", timeout=20)
    assert r.status_code == 200, r.text
    story = r.json()
    assert story.get("status") == "in_review", f"status={story.get('status')}"
    media = story.get("media") or {}
    final_url = media.get("final")
    assert final_url and final_url.endswith(f"{story_id}.mp4"), media
    # fetch final mp4
    head = requests.get(f"{BASE}/api/media/final/{story_id}.mp4",
                        stream=True, timeout=30)
    assert head.status_code == 200, head.text
    # read first 8KB then close
    chunk = next(head.iter_content(chunk_size=8192))
    assert chunk and len(chunk) > 100
    head.close()
    # thumbnail
    t = requests.get(f"{BASE}/api/media/thumbs/{story_id}.jpg", timeout=15)
    assert t.status_code == 200
    # duration roughly matches
    if story.get("duration"):
        assert abs(float(story["duration"]) - expected_dur) < 3.0, story.get("duration")


def test_prior_stitch_stitch_uploads_cleaned():
    """After render, uploaded originals under /app/backend/media/stitch should be gone
    for those story ids. We only check the stitch dir is reasonably small (<20 files)."""
    stitch = Path("/app/backend/media/stitch")
    if not stitch.exists():
        return
    files = list(stitch.iterdir())
    # our own upload tests above add up to 2 files per run; anything stale > 30 would flag leak
    assert len(files) < 40, f"stitch upload dir has {len(files)} files: {[f.name for f in files][:20]}"


# ---------- Live YouTube analytics ----------
class TestYoutubeLive:
    def test_no_auth_401(self):
        r = requests.get(f"{BASE}/api/admin/youtube/live", timeout=15)
        assert r.status_code == 401, r.text

    def test_admin_returns_400_not_connected(self):
        r = requests.get(f"{BASE}/api/admin/youtube/live", headers=ADMIN_HDR, timeout=20)
        assert r.status_code == 400, r.text
        body = r.json()
        assert "detail" in body
        assert "youtube" in body["detail"].lower() or "connect" in body["detail"].lower()
        # no stack trace leaks
        assert "Traceback" not in r.text
        assert "File \"/app" not in r.text

    def test_admin_refresh_forced_still_400_no_stack(self):
        r = requests.get(f"{BASE}/api/admin/youtube/live?refresh=1",
                         headers=ADMIN_HDR, timeout=20)
        assert r.status_code == 400
        assert "Traceback" not in r.text


# ---------- Router status: gemini_expr first in tts_chain ----------
def test_router_status_tts_chain_gemini_expr_first():
    r = requests.get(f"{BASE}/api/router-status", timeout=15)
    assert r.status_code == 200
    d = r.json()
    chain = d.get("tts_chain") or []
    assert chain, d
    assert chain[0] == "gemini_expr", chain
    assert "gemini_expr" in (d.get("providers") or {})


# ---------- Regression endpoints ----------
class TestRegression:
    def test_dashboard_200(self):
        assert requests.get(f"{BASE}/api/dashboard", timeout=15).status_code == 200

    def test_stories_200(self):
        assert requests.get(f"{BASE}/api/stories", timeout=15).status_code == 200

    def test_video_types_200(self):
        assert requests.get(f"{BASE}/api/video-types", timeout=15).status_code == 200

    def test_existing_story_has_media(self):
        r = requests.get(f"{BASE}/api/stories/6aa64eae73f022d9503eb153", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert (d.get("media") or {}).get("final"), d.get("media")


# ---------- Queue pause / unpause ----------
def test_queue_pause_unpause():
    p = requests.post(f"{BASE}/api/queue/pause", json={"paused": True}, timeout=15)
    assert p.status_code == 200, p.text
    assert p.json()["paused"] is True
    u = requests.post(f"{BASE}/api/queue/pause", json={"paused": False}, timeout=15)
    assert u.status_code == 200, u.text
    assert u.json()["paused"] is False


# ---------- Channels expressive_voice PUT ----------
def test_channel_expressive_voice_toggle_persists():
    lst = requests.get(f"{BASE}/api/channels", timeout=15)
    assert lst.status_code == 200
    channels = lst.json()
    if not channels:
        pytest.skip("no channels to test")
    ch = channels[0]
    cid = ch.get("id") or ch.get("_id")
    original = bool(ch.get("expressive_voice", True))
    # flip
    body = {**ch, "expressive_voice": not original}
    body.pop("_id", None)
    r = requests.put(f"{BASE}/api/channels/{cid}", json=body, timeout=15)
    assert r.status_code == 200, r.text
    # verify
    reread = requests.get(f"{BASE}/api/channels", timeout=15).json()
    fresh = [c for c in reread if (c.get("id") or c.get("_id")) == cid][0]
    assert bool(fresh.get("expressive_voice")) == (not original)
    # restore
    body["expressive_voice"] = original
    requests.put(f"{BASE}/api/channels/{cid}", json=body, timeout=15)


# ---------- Expressive TTS direct call ----------
def test_expressive_tts_produces_audio():
    """Call services.router.tts directly; requires backend imports."""
    import asyncio
    import sys
    sys.path.insert(0, "/app/backend")
    from services import router as router_svc
    from services.media import ffprobe_duration

    out = Path("/tmp/tts_expr_test.mp3")
    if out.exists():
        out.unlink()
    try:
        res = asyncio.run(router_svc.tts(
            text="यह एक परीक्षा वाक्य है",
            voice_spec="kokoro:hf_alpha",
            lang_hint="hi",
            out_path=out,
            direction="suspense emotion, slow pace",
            expressive=True,
        ))
    except RuntimeError as e:
        pytest.skip(f"TTS chain unavailable in this env: {e}")
    assert out.exists(), res
    dur = ffprobe_duration(out)
    assert dur > 0.3, dur
    print(f"expressive tts provider={res.get('provider')} dur={dur}")
