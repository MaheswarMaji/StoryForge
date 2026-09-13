import asyncio
import logging
import os
from datetime import datetime, timezone

from db import db

log = logging.getLogger("queue")

HEARTBEAT = {"last_beat": None, "active": 0, "workers": 0}
HANDLERS = {}
PRIORITY = {"produce": 0, "publish": 0, "improve": 0, "script": 1, "segment_fix": 1,
            "ocr": 2, "segment": 2, "news": 3, "engagement": 3}
FAILURE_COLLECTION = {"ocr": "books", "segment": "books", "script": "stories",
                      "produce": "stories", "segment_fix": "stories"}
CANCELLED = set()          # job ids cancelled while running (same-process workers)
QUEUE_PAUSED = {"paused": False}


class JobCancelled(Exception):
    pass


def cancel_job(job_id):
    CANCELLED.add(str(job_id))


def is_cancelled(job_id):
    return str(job_id) in CANCELLED


def now():
    return datetime.now(timezone.utc)


def register(job_type: str, handler):
    HANDLERS[job_type] = handler


async def enqueue(job_type: str, ref_id: str, label: str = "", payload=None):
    from models import Job

    # never stack duplicate system jobs
    if job_type in ("news", "engagement"):
        active = await db.jobs.count_documents(
            {"type": job_type, "ref_id": "system", "status": {"$in": ["queued", "running"]}})
        if active:
            return None
    # one active job per (type, ref) — re-enqueue is a no-op while one is queued/running
    active = await db.jobs.count_documents(
        {"type": job_type, "ref_id": ref_id, "status": {"$in": ["queued", "running"]}})
    if active:
        return None
    job = Job(type=job_type, ref_id=ref_id, label=label, payload=payload or {},
              priority=PRIORITY.get(job_type, 2))
    await db.jobs.insert_one(job.to_mongo())
    return job.id


async def _update(job_id, **kw):
    await db.jobs.update_one({"_id": job_id}, {"$set": kw})


async def _claim_next(idx: int):
    return await db.jobs.find_one_and_update(
        {"status": "queued"},
        {"$set": {"status": "running", "started_at": now(), "worker": f"worker-{idx}"}},
        sort=[("priority", 1), ("created_at", 1)],
    )


async def _execute_job(job, idx):
    """Run one claimed job to completion and record its terminal status."""
    job_id = job["_id"]
    try:
        HEARTBEAT["active"] += 1
        HEARTBEAT["last_beat"] = now()
        handler = HANDLERS.get(job["type"])
        if not handler:
            raise RuntimeError(f"no handler for job type {job['type']}")

        async def setp(progress, stage, jid=job_id):
            await _update(jid, progress=int(progress), stage=stage)

        await handler(job, setp)
        await _update(job_id, status="done", progress=100, stage="complete", finished_at=now())
    except JobCancelled:
        print(f"[queue] job {job_id} cancelled by user", flush=True)
        await _update(job_id, status="cancelled", stage="stopped by user", finished_at=now())
        if job.get("ref_id") and job["ref_id"] != "system":
            await db.stories.update_one(
                {"_id": job["ref_id"], "status": "rendering"},
                {"$set": {"status": "script_ready", "stage": "Stopped by user", "error": ""}})
    except Exception as e:
        log.exception("job %s failed", job_id)
        await _update(job_id, status="failed", error=str(e)[:900], finished_at=now())
        coll = FAILURE_COLLECTION.get(job["type"])
        if coll and job.get("ref_id") and job["ref_id"] != "system":
            await db[coll].update_one(
                {"_id": job["ref_id"]},
                {"$set": {"status": "failed", "error": str(e)[:500]}},
            )
    finally:
        HEARTBEAT["active"] = max(0, HEARTBEAT["active"] - 1)
        HEARTBEAT["last_beat"] = now()


async def _worker(idx: int):
    while True:
        if QUEUE_PAUSED["paused"]:
            HEARTBEAT["active"] = 0
            await asyncio.sleep(2)
            continue
        job = await _claim_next(idx)
        if not job:
            HEARTBEAT["active"] = 0
            await asyncio.sleep(1.5)
            continue
        await _execute_job(job, idx)


async def recover():
    async for j in db.jobs.find({"status": "running"}):
        await _update(j["_id"], status="queued", stage="recovered")


async def start_workers(n=2):
    await recover()
    for i in range(n):
        asyncio.create_task(_worker(i))
    HEARTBEAT["workers"] = n
    HEARTBEAT["last_beat"] = now()
