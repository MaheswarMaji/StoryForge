import asyncio
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from auth import verify_auth
from db import db
from job_queue import HEARTBEAT, enqueue
from models import Book, Story, Channel, utcnow
from services.ocr import MEDIA_ROOT

router = APIRouter(prefix="/api", dependencies=[Depends(verify_auth)])


def fix(doc):
    if doc and isinstance(doc.get("_id"), object) and not isinstance(doc.get("_id"), str):
        doc["_id"] = str(doc["_id"])
    return doc


# ---------- health ----------
@router.get("/")
async def root():
    return {"message": "StoryForge API is running", "time": utcnow().isoformat()}


# ---------- channels ----------
@router.get("/channels")
async def list_channels():
    out = []
    async for c in db.channels.find().sort("created_at", 1):
        out.append(Channel.from_mongo(c).model_dump())
    return out


@router.put("/channels/{channel_id}")
async def update_channel(channel_id: str, body: dict):
    allowed = {"name", "description", "language", "tone", "voice", "voice_speed", "music_mood",
               "music_volume", "safety_level", "style_prefix", "cta_text", "is_kids"}
    patch = {k: v for k, v in body.items() if k in allowed}
    res = await db.channels.update_one({"_id": channel_id}, {"$set": patch})
    if res.matched_count == 0:
        raise HTTPException(404, "channel not found")
    c = await db.channels.find_one({"_id": channel_id})
    return Channel.from_mongo(c).model_dump()


# ---------- books ----------
@router.post("/books/upload")
async def upload_book(request: Request, file: UploadFile = File(...), channel_id: str = Form(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are accepted")
    data = await file.read()
    if len(data) > 120 * 1024 * 1024:
        raise HTTPException(400, "PDF too large (max 120MB)")
    book = Book(filename=file.filename, channel_id=channel_id, size_bytes=len(data),
                owner_id=getattr(request.state, "user_id", ""))
    from services import storage
    result = storage.put_object(
        f"{storage.APP_NAME}/uploads/{book.id}/{file.filename}",
        data, "application/pdf")
    book.storage_path = result["path"]
    await db.books.insert_one(book.to_mongo())
    await enqueue("ocr", book.id, f"OCR: {file.filename}")
    return book.model_dump()


@router.get("/books")
async def list_books():
    out = []
    async for b in db.books.find().sort("created_at", -1):
        story_count = await db.stories.count_documents({"book_id": b["_id"]})
        d = Book.from_mongo(b).model_dump()
        d["story_count"] = story_count
        out.append(d)
    return out


@router.get("/books/{book_id}")
async def get_book(book_id: str):
    b = await db.books.find_one({"_id": book_id})
    if not b:
        raise HTTPException(404, "book not found")
    stories = []
    async for s in db.stories.find({"book_id": book_id}).sort("created_at", 1):
        stories.append(Story.from_mongo(s).model_dump())
    d = Book.from_mongo(b).model_dump()
    d["pages"] = d["pages"][:3]  # preview only
    d["stories"] = stories
    return d


# ---------- stories ----------
@router.post("/books/{book_id}/reocr")
async def reocr_book(book_id: str):
    b = await db.books.find_one({"_id": book_id})
    if not b:
        raise HTTPException(404, "book not found")
    if b["status"] in ("ocr_running", "segmenting"):
        raise HTTPException(409, "OCR already in progress")
    await db.books.update_one({"_id": book_id}, {"$set": {
        "status": "uploaded", "progress": 0, "pages": [], "structured": {},
        "error": "", "total_pages": 0}})
    job_id = await enqueue("ocr", book_id, f"Re-OCR: {b.get('filename', '')}")
    return {"job_id": job_id}


@router.get("/stories")
async def list_stories(channel_id: Optional[str] = None, status: Optional[str] = None):
    q = {}
    if channel_id and channel_id != "all":
        q["channel_id"] = channel_id
    if status and status != "all":
        q["status"] = status
    out = []
    async for s in db.stories.find(q).sort("created_at", -1):
        out.append(Story.from_mongo(s).model_dump())
    return out


@router.get("/stories/{story_id}")
async def get_story(story_id: str):
    s = await db.stories.find_one({"_id": story_id})
    if not s:
        raise HTTPException(404, "story not found")
    return Story.from_mongo(s).model_dump()


@router.post("/stories/{story_id}/script")
async def gen_script(story_id: str):
    s = await db.stories.find_one({"_id": story_id})
    if not s:
        raise HTTPException(404, "story not found")
    if s["status"] in ("scripting",):
        raise HTTPException(409, "script already being generated")
    await db.stories.update_one({"_id": story_id}, {"$set": {"status": "scripting", "error": ""}})
    job_id = await enqueue("script", story_id, f"Script: {s.get('title_english') or s.get('title_hindi', story_id)}")
    return {"job_id": job_id}


@router.post("/stories/{story_id}/produce")
async def produce(story_id: str):
    s = await db.stories.find_one({"_id": story_id})
    if not s:
        raise HTTPException(404, "story not found")
    if not s.get("script", {}).get("chunks"):
        raise HTTPException(409, "generate the script first")
    await db.stories.update_one({"_id": story_id}, {"$set": {"status": "rendering", "stage": "Queued", "error": ""}})
    job_id = await enqueue("produce", story_id, f"Produce: {s.get('title_english') or s.get('title_hindi', story_id)}")
    return {"job_id": job_id}


@router.post("/stories/{story_id}/segments/{index}/regenerate")
async def regen_segment(story_id: str, index: int):
    s = await db.stories.find_one({"_id": story_id})
    if not s:
        raise HTTPException(404, "story not found")
    job_id = await enqueue("segment_fix", story_id, f"Regen segment {index + 1}", payload={"index": index})
    return {"job_id": job_id}


@router.post("/stories/{story_id}/improve")
async def improve_story(story_id: str):
    s = await db.stories.find_one({"_id": story_id})
    if not s:
        raise HTTPException(404, "story not found")
    if not s.get("script", {}).get("chunks"):
        raise HTTPException(409, "generate the script first")
    if len(s.get("improvements") or []) >= 2:
        raise HTTPException(409, "improvement budget exhausted (2 rounds max)")
    if s["status"] == "rendering":
        raise HTTPException(409, "pipeline busy")
    await db.stories.update_one({"_id": story_id}, {"$set": {
        "status": "rendering", "stage": "Improvement coach queued", "error": ""}})
    job_id = await enqueue("improve", story_id,
                           f"Improve: {s.get('title_english') or s.get('title_hindi', story_id)[:40]}")
    return {"job_id": job_id}


class ReviewBody(BaseModel):
    action: str  # approve | reject | request_edits
    notes: str = ""


@router.post("/stories/{story_id}/review")
async def review(story_id: str, body: ReviewBody):
    s = await db.stories.find_one({"_id": story_id})
    if not s:
        raise HTTPException(404, "story not found")
    mapping = {"approve": "approved", "reject": "rejected", "request_edits": "edits_requested"}
    if body.action not in mapping:
        raise HTTPException(400, "action must be approve|reject|request_edits")
    await db.stories.update_one(
        {"_id": story_id},
        {"$set": {"status": mapping[body.action], "review_notes": body.notes,
                  "stage": {"approve": "Ready for upload", "reject": "Rejected",
                            "request_edits": "Edits requested"}[body.action],
                  "updated_at": utcnow()}})
    return await get_story(story_id)


# ---------- jobs & dashboard ----------
@router.get("/jobs")
async def list_jobs(limit: int = 30):
    out = []
    async for j in db.jobs.find().sort("created_at", -1).limit(min(limit, 100)):
        d = fix(dict(j))
        for f in ("created_at", "started_at", "finished_at"):
            if isinstance(d.get(f), datetime):
                d[f] = d[f].isoformat()
        out.append(d)
    return out


@router.get("/dashboard")
async def dashboard():
    status_counts = {}
    async for s in db.stories.find({}, {"status": 1}):
        status_counts[s["status"]] = status_counts.get(s["status"], 0) + 1

    pipeline_t = [{"$group": {"_id": None, "llm": {"$sum": "$cost.llm"}, "tts": {"$sum": "$cost.tts"},
                              "image": {"$sum": "$cost.image"}, "total": {"$sum": "$cost.total"},
                              "n": {"$sum": 1},
                              "produced": {"$sum": {"$cond": [
                                  {"$in": ["$status", ["in_review", "approved", "edits_requested"]]},
                                  1, 0]}}}}]
    agg = await db.stories.aggregate(pipeline_t).to_list(1)
    cost = agg[0] if agg else {"llm": 0, "tts": 0, "image": 0, "total": 0, "n": 0, "produced": 0}
    avg = round(cost["total"] / cost["produced"], 3) if cost["produced"] else 0
    jobs = []
    async for j in db.jobs.find().sort("created_at", -1).limit(25):
        d = fix(dict(j))
        for f in ("created_at", "started_at", "finished_at"):
            if isinstance(d.get(f), datetime):
                d[f] = d[f].isoformat()
        jobs.append(d)

    job_counts = {}
    async for j in db.jobs.find({}, {"status": 1}):
        job_counts[j["status"]] = job_counts.get(j["status"], 0) + 1

    beat_coverage = {"hook": 0, "story": 0, "twist": 0, "climax": 0, "action": 0, "lesson": 0}
    async for s in db.stories.find({"script.chunks": {"$exists": True, "$ne": []}}, {"script.chunks.beat": 1}):
        seen = {c.get("beat") for c in s.get("script", {}).get("chunks", []) if isinstance(c, dict)}
        for b in beat_coverage:
            if b in seen:
                beat_coverage[b] += 1

    recent = []
    async for s in db.stories.find().sort("updated_at", -1).limit(8):
        recent.append(Story.from_mongo(s).model_dump())

    return {
        "status_counts": status_counts,
        "cost": {"llm": round(cost["llm"], 3), "tts": round(cost["tts"], 3),
                 "image": round(cost["image"], 3), "total": round(cost["total"], 3),
                 "avg_per_video": avg, "videos_produced": cost["produced"], "n": cost["n"]},
        "beat_coverage": beat_coverage,
        "queue": {"depth": await db.jobs.count_documents({"status": "queued"}),
                  "active": HEARTBEAT["active"],
                  "workers": HEARTBEAT["workers"],
                  "last_beat": HEARTBEAT["last_beat"].isoformat() if HEARTBEAT["last_beat"] else None,
                  "job_counts": job_counts},
        "jobs": jobs,
        "recent_stories": recent,
    }


# ---------- bulk curation ----------
@router.post("/books/{book_id}/script-all")
async def script_all(book_id: str):
    n = 0
    async for s in db.stories.find({"book_id": book_id, "status": "draft"}, {"_id": 1, "title_english": 1}):
        await enqueue("script", s["_id"], f"Script: {s.get('title_english', '')[:40]}")
        n += 1
    if n == 0:
        raise HTTPException(409, "no draft stories left to script")
    return {"queued": n}


class BatchBody(BaseModel):
    ids: List[str]


@router.post("/stories/batch-produce")
async def batch_produce(body: BatchBody):
    queued = []
    for sid in body.ids[:30]:
        s = await db.stories.find_one({"_id": sid})
        if not s or not s.get("script", {}).get("chunks"):
            continue
        if s["status"] in ("rendering",):
            continue
        await db.stories.update_one({"_id": sid}, {"$set": {"status": "rendering", "stage": "Queued", "error": ""}})
        await enqueue("produce", sid, f"Produce: {s.get('title_english') or s.get('title_hindi', sid)[:40]}")
        queued.append(sid)
    if not queued:
        raise HTTPException(409, "no script-ready stories in selection")
    return {"queued": len(queued)}


# ---------- publishing ----------
class PublishBody(BaseModel):
    platform: str  # youtube | instagram


@router.post("/stories/{story_id}/publish")
async def publish_story(story_id: str, body: PublishBody):
    s = await db.stories.find_one({"_id": story_id})
    if not s:
        raise HTTPException(404, "story not found")
    if body.platform not in ("youtube", "instagram"):
        raise HTTPException(400, "platform must be youtube|instagram")
    job_id = await enqueue("publish", story_id, f"Publish to {platform_label(body.platform)}",
                           payload={"platform": body.platform})
    return {"job_id": job_id}


def platform_label(p):
    return {"youtube": "YouTube", "instagram": "Instagram Reels"}.get(p, p)


@router.get("/social/credentials")
async def social_credentials():
    from services import social
    return social.cred_status()


@router.get("/social/comments")
async def social_comments():
    out = []
    async for c in db.social_comments.find().sort("created_at", -1).limit(80):
        d = fix(dict(c))
        if isinstance(d.get("created_at"), datetime):
            d["created_at"] = d["created_at"].isoformat()
        out.append(d)
    return out


class ReplyBody(BaseModel):
    text: str


@router.post("/social/comments/{comment_id}/reply")
async def manual_reply(comment_id: str, body: ReplyBody):
    doc = await db.social_comments.find_one({"comment_id": comment_id})
    if not doc:
        raise HTTPException(404, "comment not tracked")
    from services import social
    try:
        if doc["platform"] == "youtube":
            social.yt_reply(comment_id, body.text)
        else:
            social.ig_reply(comment_id, body.text)
    except Exception as e:
        raise HTTPException(502, f"reply failed: {str(e)[:200]}")
    await db.social_comments.update_one(
        {"comment_id": comment_id},
        {"$set": {"reply_text": body.text, "posted": True, "handled": True,
                  "triage.action": "manual_reply", "triage.needs_reply": True}})
    return {"ok": True}


@router.post("/social/engagement/sync")
async def engagement_sync():
    job_id = await enqueue("engagement", "system", "Manual engagement sync")
    return {"job_id": job_id}


# ---------- integration settings ----------
@router.get("/settings/instagram")
async def get_ig_settings():
    from services import social
    creds = social.get_ig_creds()
    connected = bool(creds.get("access_token") and creds.get("user_id"))
    out = {"connected": connected, "user_id": creds.get("user_id", "") if connected else "",
           "token_hint": (creds.get("access_token", "")[:6] + "…") if creds.get("access_token") else "",
           "source": creds.get("source", "")}
    if connected:
        try:
            out["username"] = await asyncio.to_thread(social.ig_validate, creds["access_token"], creds["user_id"])
        except Exception as e:
            out["error"] = f"token check failed: {str(e)[:140]}"
    return out


class InstagramCredsBody(BaseModel):
    access_token: str
    user_id: str


@router.put("/settings/instagram")
async def save_ig_settings(body: InstagramCredsBody):
    from services import social
    token, uid = body.access_token.strip(), body.user_id.strip()
    if not token or not uid:
        raise HTTPException(400, "access_token and user_id are required")
    try:
        username = await asyncio.to_thread(social.ig_validate, token, uid)
    except Exception as e:
        raise HTTPException(400, f"Instagram rejected these credentials: {str(e)[:200]}")
    await db.settings.update_one(
        {"key": "instagram"},
        {"$set": {"key": "instagram", "access_token": token, "user_id": uid, "updated_at": utcnow()}},
        upsert=True)
    social.set_ig_creds(token, uid, "settings")
    return {"connected": True, "username": username, "user_id": uid}


@router.delete("/settings/instagram")
async def delete_ig_settings():
    from services import social
    await db.settings.delete_one({"key": "instagram"})
    social.set_ig_creds("", "", "")
    return {"connected": False}


# ---------- news desk ----------
@router.post("/news/fetch")
async def news_fetch():
    job_id = await enqueue("news", "system", "Fetch & triage daily news")
    return {"job_id": job_id}


@router.get("/news/items")
async def news_items():
    out = []
    async for s in db.stories.find({"policy": {"$ne": {}}}).sort("created_at", -1).limit(60):
        out.append(Story.from_mongo(s).model_dump())
    return out


@router.get("/social/youtube/auth-url")
async def yt_auth_url():
    from services import social
    if not social.cred_status()["youtube_oauth_setup"]:
        raise HTTPException(400, "YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET missing in backend/.env")
    base = (os.environ.get("PUBLIC_BASE_URL") or os.environ.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
    return {"auth_url": social.youtube_auth_url(f"{base}/api/oauth/callback"),
            "redirect_uri": f"{base}/api/oauth/callback",
            "note": "Add this redirect URI in Google Cloud Console > Credentials > your OAuth client, then open auth_url, approve, and the refresh token is saved automatically"}


@router.get("/oauth/callback")
async def oauth_callback(code: str = None, error: str = None):
    from fastapi.responses import HTMLResponse
    from services import social
    if error:
        return HTMLResponse(f"<h3>OAuth failed: {error}</h3>", status_code=400)
    base = (os.environ.get("PUBLIC_BASE_URL") or os.environ.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
    try:
        social.youtube_exchange_code(code, f"{base}/api/oauth/callback")
        return HTMLResponse("<h2 style='font-family:sans-serif'>✓ YouTube connected — refresh token saved. You can close this tab and upload Shorts directly.</h2>")
    except Exception as e:
        return HTMLResponse(f"<h3 style='font-family:sans-serif'>Token exchange failed: {str(e)[:300]}</h3>", status_code=400)


@router.get("/router-status")
async def router_status():
    from services import router
    return router.status()


@router.get("/media-health")
async def media_health():
    return {"media_root": str(MEDIA_ROOT), "exists": MEDIA_ROOT.exists()}
