import asyncio
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

load_dotenv(Path(__file__).parent / ".env")

from db import db
from routes import router
from auth import auth_router
from admin import admin_router
from services.ocr import MEDIA_ROOT
import job_queue
import tasks as tasks_mod

app = FastAPI(title="StoryForge API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(auth_router)
app.include_router(admin_router)
MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
app.mount("/api/media", StaticFiles(directory=str(MEDIA_ROOT)), name="media")

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("storyforge")

CHANNEL_SEEDS = [
    {
        "key": "mythology", "name": "Mythic Shorts — Dramatic",
        "description": "Puranas, Bhagwat, Ramayana & Mahabharata retellings. Warm authoritative male narration, devotional-to-epic music.",
        "language": "hi", "tone": "Warm, authoritative, dramatic storytelling with dramatic pauses",
        "voice": "gemini:Charon", "voice_speed": 0.95, "music_mood": "devotional", "music_volume": 0.16,
        "safety_level": "general", "is_kids": False,
        "style_prefix": "Indian miniature painting style with gold leaf details, deep indigo and saffron palette, cinematic 4K, dramatic temple lighting",
        "cta_text": "Follow for more legendary tales from the Puranas",
    },
    {
        "key": "folk_ghost", "name": "Folk Tales — Whimsical",
        "description": "Thakurmar Jhuli & Bengali/Indian folk and ghost lore for kids. Playful narrator, gentle spooks, kind morals.",
        "language": "bn", "tone": "Friendly, playful, animated grandmother-style narration for kids",
        "voice": "gemini:Kore", "voice_speed": 1.0, "music_mood": "moral", "music_volume": 0.14,
        "safety_level": "strict_kids", "is_kids": True,
        "style_prefix": "Whimsical storybook illustration, soft pastel palette with glowing lanterns, rounded friendly shapes, gentle magical night atmosphere",
        "cta_text": "Subscribe for more bedtime folk tales",
    },
    {
        "key": "public_interest", "name": "Public Interest — News Explained",
        "description": "Daily factual Shorts on climate, disasters, science & tech, institutional reports, economy and public health. Every video passes an independent policy agent + human review before publishing.",
        "language": "en", "tone": "Crisp, factual, engaging news-explainer — neutral and authoritative",
        "voice": "gemini:Charon", "voice_speed": 1.05, "music_mood": "suspense", "music_volume": 0.10,
        "safety_level": "news", "is_kids": False,
        "style_prefix": "Clean broadcast news style, modern flat infographic aesthetic, deep navy and white with a single accent color, professional studio lighting",
        "cta_text": "Follow for daily public-interest briefings",
    },
]


async def seed_channels():
    from bson import ObjectId
    for seed in CHANNEL_SEEDS:
        existing = await db.channels.find_one({"key": seed["key"]})
        if not existing:
            await db.channels.insert_one({"_id": str(ObjectId()), **seed})
        else:
            if isinstance(existing["_id"], ObjectId):
                doc = dict(existing)
                doc["_id"] = str(existing["_id"])
                await db.channels.delete_one({"key": seed["key"]})
                await db.channels.insert_one(doc)
            # migrate legacy openai voice names to gemini voices
            if existing.get("voice") in ("onyx", "fable"):
                await db.channels.update_one({"key": seed["key"]}, {"$set": {"voice": seed["voice"]}})


@app.on_event("startup")
async def startup():
    await seed_channels()
    await _load_social_settings()
    await _load_key_vault()
    await _seed_video_type_channels()
    tasks_mod.register_all()
    asyncio.create_task(_delayed_workers())


async def _load_key_vault():
    doc = await db.settings.find_one({"key": "api_keys"})
    n = 0
    for k, v in (doc or {}).get("values", {}).items():
        if not (os.environ.get(k) or "").strip() and str(v).strip():
            os.environ[k] = str(v).strip()
            n += 1
    if n:
        print(f"[startup] loaded {n} API keys from settings vault", flush=True)


async def _seed_video_type_channels():
    from services.video_types import VIDEO_TYPES
    for vtype, cfg in VIDEO_TYPES.items():
        key = f"vt-{vtype}"
        if not await db.channels.find_one({"key": key}):
            from models import Channel
            doc = Channel(key=key, name=cfg["name"],
                          description=f"{cfg['name']} ({cfg['audience']}) — voice & music auto-selected",
                          language=cfg["language"], tone=cfg["tone"], voice=cfg["voice"],
                          music_mood=cfg["music_mood"], music_volume=cfg["music_volume"],
                          safety_level=cfg["safety_level"], is_kids=cfg["is_kids"],
                          style_prefix=cfg["style_prefix"], cta_text=cfg["cta_text"],
                          mode="slide", video_type=vtype)
            await db.channels.insert_one(doc.to_mongo())
            print(f"[startup] seeded channel {key}", flush=True)


async def _load_social_settings():
    from services import social
    doc = await db.settings.find_one({"key": "instagram"})
    if doc and doc.get("access_token") and doc.get("user_id"):
        social.set_ig_creds(doc["access_token"], doc["user_id"], "settings")
        print("[social] Instagram credentials loaded from settings", flush=True)


async def _delayed_workers():
    await job_queue.start_workers(2)
    log.info("job queue workers started")
    asyncio.create_task(_periodic("engagement", 900, _engagement_ready))
    asyncio.create_task(_periodic("news", 6 * 3600, lambda: True))


async def _engagement_ready():
    from services import social
    return any(social.cred_status().values())


async def _periodic(job_type: str, interval: int, ready):
    from job_queue import enqueue
    await asyncio.sleep(30)
    while True:
        try:
            if await ready() if asyncio.iscoroutinefunction(ready) else ready():
                await enqueue(job_type, "system", f"Scheduled {job_type}")
        except Exception as e:
            log.warning("periodic %s failed: %s", job_type, e)
        await asyncio.sleep(interval)


@app.on_event("shutdown")
async def shutdown():
    db.client.close()
