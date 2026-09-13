"""Pexels free stock imagery — real photos & video clips when AI generation is unavailable."""
import asyncio
import re

import httpx

KEY = None  # set from env at call time


def _key():
    global KEY
    if KEY is None:
        import os
        KEY = (os.environ.get("PEXELS_API_KEY") or "").strip()
    return KEY

STOP = set("a an the of in on at to with for and or is are be been into from his her its their this that "
           "scene shot style cinematic close closeup up down left right slow fast motion camera zoom pan "
           "dolly static lighting light dark dawn dusk night day shot vertical portrait landscape".split())


def _keywords(text: str, limit: int = 8) -> str:
    words = re.findall(r"[A-Za-z]{3,}", (text or "").lower())
    seen, out = set(), []
    for w in words:
        if w not in STOP and w not in seen:
            seen.add(w)
            out.append(w)
        if len(out) >= limit:
            break
    return " ".join(out) or "indian village story"


async def fetch_photo(query: str, out_path) -> bool:
    """Download a free Pexels photo (portrait crop) matching the query."""
    import os
    key = (os.environ.get("PEXELS_API_KEY") or "").strip()
    if not key:
        return False
    try:
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as c:
            r = await c.get("https://api.pexels.com/v1/search",
                            params={"query": _keywords(query), "per_page": 3, "orientation": "portrait"},
                            headers={"Authorization": key})
            r.raise_for_status()
            photos = r.json().get("photos", [])
            if not photos:
                return False
            src = photos[0]["src"].get("portrait") or photos[0]["src"].get("large")
            img = await c.get(src)
            img.raise_for_status()
            Path_ = __import__("pathlib").Path
            Path_(out_path).parent.mkdir(parents=True, exist_ok=True)
            Path_(out_path).write_bytes(img.content)
            return True
    except Exception as e:
        print(f"[pexels] photo failed: {str(e)[:110]}", flush=True)
        return False


async def fetch_video(query: str, out_path, min_h: int = 1080) -> bool:
    """Download a free Pexels HD portrait video clip matching the query."""
    import os
    key = (os.environ.get("PEXELS_API_KEY") or "").strip()
    if not key:
        return False
    try:
        async with httpx.AsyncClient(timeout=90, follow_redirects=True) as c:
            r = await c.get("https://api.pexels.com/videos/search",
                            params={"query": _keywords(query), "per_page": 5, "orientation": "portrait"},
                            headers={"Authorization": key})
            r.raise_for_status()
            videos = r.json().get("videos", [])
            files = []
            for v in videos:
                files += [f for f in v.get("video_files", []) if f.get("height", 0) >= min_h and f.get("width", 0) < f.get("height", 1)]
            if not files:
                return False
            files.sort(key=lambda f: f.get("height", 0))
            link = files[0]["link"]
            vid = await c.get(link)
            vid.raise_for_status()
            Path_ = __import__("pathlib").Path
            Path_(out_path).parent.mkdir(parents=True, exist_ok=True)
            Path_(out_path).write_bytes(vid.content)
            return True
    except Exception as e:
        print(f"[pexels] video failed: {str(e)[:110]}", flush=True)
        return False


async def fetch_photos_for_panels(queries, out_dir) -> list:
    """Photos for each storyboard panel (parallel, fail-soft). Returns paths (or None)."""
    out_dir = __import__("pathlib").Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    sem = asyncio.Semaphore(4)

    async def one(i, q):
        async with sem:
            p = out_dir / f"px-{i:02d}.jpg"
            ok = await fetch_photo(q, p)
            return p if ok else None

    return await asyncio.gather(*[one(i, q) for i, q in enumerate(queries)])
