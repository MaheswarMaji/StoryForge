"""Emergent-managed Google OAuth — login with Google only."""
import uuid
from datetime import datetime, timedelta, timezone
import os

import httpx
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from db import db

SESSION_COOKIE = "session_token"
SESSION_DAYS = 7

auth_router = APIRouter(prefix="/api/auth")

EXEMPT_PREFIXES = ("/api/auth", "/api/oauth/callback", "/api/media-health")


def admin_emails():
    return {e.strip().lower() for e in os.environ.get("ADMIN_EMAILS", "").split(",") if e.strip()}


def _utc(v):
    if isinstance(v, str):
        v = datetime.fromisoformat(v)
    if isinstance(v, datetime) and v.tzinfo is None:
        v = v.replace(tzinfo=timezone.utc)
    return v


def _token_from(request: Request) -> str:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        header = request.headers.get("authorization", "")
        token = header[7:].strip() if header.lower().startswith("bearer ") else ""
    return token


async def verify_auth(request: Request):
    path = request.url.path
    if path in ("/api", "/api/") or any(path.startswith(p) for p in EXEMPT_PREFIXES):
        return
    token = _token_from(request)
    if not token:
        raise HTTPException(401, "login required")
    doc = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
    if not doc or _utc(doc.get("expires_at")) < datetime.now(timezone.utc):
        raise HTTPException(401, "session expired — sign in again")
    request.state.user_id = doc.get("user_id")


class SessionBody(BaseModel):
    session_id: str


@auth_router.post("/session")
async def create_session(body: SessionBody, response: Response):
    # REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
            headers={"X-Session-ID": body.session_id},
        )
    if r.status_code != 200:
        raise HTTPException(401, "Google sign-in could not be verified")
    data = r.json()
    email = data.get("email", "")
    user = await db.users.find_one({"email": email}, {"_id": 0})
    if not user:
        first = await db.users.count_documents({}) == 0
        user = {"user_id": f"user_{uuid.uuid4().hex[:12]}", "email": email,
                "name": data.get("name", ""), "picture": data.get("picture", ""),
                "role": "admin" if first or email in admin_emails() else "user",
                "created_at": datetime.now(timezone.utc)}
        await db.users.insert_one(dict(user))
    else:
        await db.users.update_one(
            {"user_id": user["user_id"]},
            {"$set": {"name": data.get("name", user.get("name", "")),
                      "picture": data.get("picture", user.get("picture", ""))}})
    await db.user_sessions.insert_one({
        "user_id": user["user_id"], "session_token": data["session_token"],
        "expires_at": datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS),
        "created_at": datetime.now(timezone.utc)})
    response.set_cookie(SESSION_COOKIE, data["session_token"], max_age=SESSION_DAYS * 86400,
                        path="/", secure=True, samesite="none", httponly=True)
    return {"user": {k: user[k] for k in ("user_id", "email", "name", "picture")}}


@auth_router.get("/me")
async def me(request: Request):
    token = _token_from(request)
    if not token:
        raise HTTPException(401, "not signed in")
    sess = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
    if not sess or _utc(sess.get("expires_at")) < datetime.now(timezone.utc):
        raise HTTPException(401, "session expired — sign in again")
    user = await db.users.find_one({"user_id": sess["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(401, "user not found")
    out = {k: user.get(k) for k in ("user_id", "email", "name", "picture")}
    out["is_admin"] = user.get("role") == "admin" or user.get("email", "").lower() in admin_emails()
    return out


@auth_router.post("/logout")
async def logout(request: Request, response: Response):
    token = _token_from(request)
    if token:
        await db.user_sessions.delete_one({"session_token": token})
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}
