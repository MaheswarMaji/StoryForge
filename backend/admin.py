"""Admin console: monitor all accounts, channels, video performance, revenue estimate, queue health."""
import os
from asyncio import to_thread as _to_thread
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request

from auth import _token_from, _utc, admin_emails
from db import db

admin_router = APIRouter(prefix="/api/admin")


def _fix(doc):
    if doc.get("_id") is not None and not isinstance(doc["_id"], str):
        doc["_id"] = str(doc["_id"])
    doc["id"] = doc.pop("_id")
    return doc


async def verify_admin(request: Request):
    token = _token_from(request)
    if not token:
        raise HTTPException(401, "login required")
    sess = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
    if not sess or _utc(sess.get("expires_at")) < datetime.now(timezone.utc):
        raise HTTPException(401, "session expired")
    user = await db.users.find_one({"user_id": sess["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(401, "user not found")
    if not (user.get("role") == "admin" or user.get("email", "").lower() in admin_emails()):
        raise HTTPException(403, "admin access required")
    request.state.user_id = user["user_id"]
    return user


async def _yt_stats(video_ids):
    from services import social
    try:
        return await _to_thread(social.yt_video_stats, video_ids)
    except Exception as e:
        print(f"[admin] yt stats failed: {str(e)[:120]}", flush=True)
        return {}


async def _yt_channel():
    from services import social
    try:
        return await _to_thread(social.yt_channel_info)
    except Exception as e:
        print(f"[admin] yt channel info failed: {str(e)[:120]}", flush=True)
        return {}


@admin_router.get("/overview")
async def overview(request: Request):
    await verify_admin(request)

    accounts = []
    async for u in db.users.find({}, {"_id": 0}).sort("created_at", 1):
        d = {"user_id": u.get("user_id"), "email": u.get("email"), "name": u.get("name"),
             "role": u.get("role", "user"), "created_at": u.get("created_at")}
        if isinstance(d["created_at"], datetime):
            d["created_at"] = d["created_at"].isoformat()
        d["stories"] = await db.stories.count_documents({"owner_id": u["user_id"]})
        accounts.append(d)

    channels = []
    async for c in db.channels.find().sort("created_at", 1):
        d = _fix(dict(c))
        if isinstance(d.get("created_at"), datetime):
            d["created_at"] = d["created_at"].isoformat()
        d["stories"] = await db.stories.count_documents({"channel_id": d["id"]})
        d["published"] = await db.stories.count_documents({"channel_id": d["id"], "status": "published"})
        channels.append(d)

    published, total_views, total_likes, total_comments = [], 0, 0, 0
    async for s in db.stories.find({"status": "published"}).sort("updated_at", -1).limit(100):
        pub = s.get("publish") or {}
        yt = pub.get("youtube") or {}
        row = {"id": s["id"], "title": s.get("title_english") or s.get("title_hindi", "Untitled"),
               "channel": s.get("channel_id"), "cost": (s.get("cost") or {}).get("total", 0)}
        if yt.get("video_id"):
            row["url"] = yt.get("url", f"https://www.youtube.com/shorts/{yt['video_id']}")
            row["platform"] = "youtube"
            stats = await _yt_stats([yt["video_id"]])
            st = stats.get(yt["video_id"], {})
            row.update(views=st.get("views", 0), likes=st.get("likes", 0), comments=st.get("comments", 0))
        elif pub.get("instagram", {}).get("post_id"):
            row.update(url=pub["instagram"].get("url", ""), platform="instagram",
                       views=0, likes=0, comments=0)
        else:
            row.update(url="", platform="", views=0, likes=0, comments=0)
        total_views += row.get("views", 0) or 0
        total_likes += row.get("likes", 0) or 0
        total_comments += row.get("comments", 0) or 0
        published.append(row)

    cost_agg = await db.stories.aggregate(
        [{"$group": {"_id": None, "total": {"$sum": "$cost.total"}}}]).to_list(1)
    rpm = float(os.environ.get("YT_RPM_USD", "0.05"))
    ch = await _yt_channel()

    return {
        "totals": {
            "accounts": len(accounts), "channels": len(channels),
            "videos_published": len(published),
            "views": total_views, "likes": total_likes, "comments": total_comments,
            "subscribers": (ch or {}).get("subscribers", 0),
            "est_revenue": round(total_views / 1000 * rpm, 2),
            "api_cost": round((cost_agg[0]["total"] if cost_agg else 0.0), 2),
            "rpm_used": rpm,
        },
        "accounts": accounts,
        "channels": channels,
        "videos": published,
        "youtube_channel": ch or {},
        "notes": "Revenue is an ESTIMATE (views x RPM, set YT_RPM_USD in backend/.env). Exact payouts require YouTube Analytics/AdSense access. Per-video views/likes/comments come live from the YouTube Data API.",
    }
