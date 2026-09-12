import asyncio
import json
from pathlib import Path

from db import db
from models import utcnow
from services import agents, media
from services.ocr import MEDIA_ROOT


def _add_cost(cost: dict, kind: str, amount: float):
    cost[kind] = round(cost.get(kind, 0.0) + amount, 5)
    cost["total"] = round(cost.get("llm", 0.0) + cost.get("tts", 0.0) + cost.get("image", 0.0), 5)


async def _save_cost(story_id: str, kind: str, amount: float):
    await db.stories.update_one(
        {"_id": story_id},
        {"$inc": {f"cost.{kind}": round(amount, 5), "cost.total": round(amount, 5)},
         "$set": {"updated_at": utcnow()}},
    )

async def produce_video(story_id: str, setp):
    from services.ocr import disk_guard
    disk_guard()
    story = await db.stories.find_one({"_id": story_id})
    if not story:
        raise RuntimeError("story not found")
    channel = await db.channels.find_one({"_id": story["channel_id"]})
    if not channel:
        from bson import ObjectId
        try:
            channel = await db.channels.find_one({"_id": ObjectId(story["channel_id"])})
        except Exception:
            channel = None
    if not channel:
        raise RuntimeError(f"channel {story['channel_id']} not found")
    chunks = (story.get("script") or {}).get("chunks") or []
    if not chunks:
        raise RuntimeError("story has no script — generate the script first")
    chunks = chunks[:8]
    aid = story_id

    async def set_story(**kw):
        kw["updated_at"] = utcnow()
        await db.stories.update_one({"_id": story_id}, {"$set": kw})

    await set_story(status="rendering", stage="Fact check & edit")
    await setp(2, "Fact check & editor pass")

    # ---- Editor & fact-check agent: verify script against source, apply corrections ----
    book = await db.books.find_one({"_id": story["book_id"]}) if story.get("book_id") else None
    if story.get("policy", {}).get("summary"):
        source_text = story["policy"]["summary"]
    elif book and book.get("pages"):
        source_text = "\n".join(p["text"] for p in book["pages"] if p.get("text"))
    else:
        source_text = story.get("conflict", "") + " " + story.get("climax", "") + " " + story.get("moral", "")

    editor = {}
    try:
        editor, edit_cost = await agents.editor_pass(story, channel, source_text)
        await _save_cost(story_id, "llm", edit_cost)
        chunks = story["script"]["chunks"]
        applied = 0
        for c in (editor.get("corrections") or []):
            idx = int(c.get("index", -1))
            if 0 <= idx < len(chunks) and isinstance(c, dict):
                if c.get("voiceover"):
                    chunks[idx]["voiceover"] = c["voiceover"]
                if c.get("visual"):
                    chunks[idx]["visual"] = c["visual"]
                if c.get("video_prompt"):
                    chunks[idx]["video_prompt"] = c["video_prompt"]
                applied += 1
        hook_line = editor.get("hook_line") or ""
        if hook_line and chunks:
            chunks[0]["voiceover"] = hook_line
        if applied or hook_line:
            for sub in ("audio", "clips", "frames"):
                d = MEDIA_ROOT / sub / aid
                if d.exists():
                    import shutil
                    shutil.rmtree(d, ignore_errors=True)
            story["script"]["chunks"] = chunks
        story["script"]["editor"] = {
            "factual_ok": editor.get("factual_ok"),
            "silence_before_index": editor.get("silence_before_index", -1),
            "corrections_applied": applied + (1 if hook_line else 0),
            "notes": editor.get("editor_notes", []),
        }
        story["script"]["viral_score"] = editor.get("viral_score", {})
        await set_story(script=story["script"])
        chunks = story["script"]["chunks"]
    except Exception as e:
        print(f"[pipeline] editor pass unavailable: {str(e)[:120]}", flush=True)

    await set_story(status="rendering", stage="Character sheet", error="")
    await setp(5, "Character sheet")

    cs = story.get("character_sheet") or {}
    anchor = cs.get("anchor") or "; ".join(
        f"{c.get('name')}: {c.get('description')}" for c in story.get("characters", []))
    style = channel.get("style_prefix") or story.get("visual_style") or "Indian miniature painting style"
    char_path = MEDIA_ROOT / "char" / f"{aid}.png"
    if not char_path.exists():
        ai_ok = await media.generate_image(
            f"Character reference sheet, single illustration on plain dark backdrop, vertical 9:16. "
            f"Art style: {style}. Characters: {anchor}. Clean detailed lineup, no text, no watermark.",
            char_path, session=f"char-{aid}")
        if ai_ok:
            await _save_cost(story_id, "image", media.IMAGE_PRICE)

    audio_urls, frame_urls = [], []
    sem = asyncio.Semaphore(2)
    from services import router

    async def one_segment(i, chunk):
        nonlocal audio_urls, frame_urls
        async with sem:
            audio_dir = MEDIA_ROOT / "audio" / aid
            aud = audio_dir / f"{i:02d}.mp3"
            if aud.exists():
                adur = media.ffprobe_duration(aud)
            else:
                adur = await media.synthesize_voice(
                    chunk.get("voiceover", ""), channel.get("voice", ""),
                    channel.get("voice_speed", 1.0), aud, lang_hint=channel.get("language", "hi"))
                await _save_cost(story_id, "tts", media.tts_cost(chunk.get("voiceover", "")))
            dur = max(6.0, min(16.0, adur + 0.6))

            frame = MEDIA_ROOT / "frames" / aid / f"{i:02d}.png"
            if not frame.exists():
                res = await router.image(
                    f"{style}. {chunk.get('video_prompt', chunk.get('visual', ''))} "
                    f"Vertical 9:16 composition, cinematic, highly detailed, no text, no watermark. "
                    f"Recurring character appearance MUST match this reference sheet exactly: {anchor[:600]}",
                    frame, ref_image=char_path, session=f"frame-{aid}-{i}")
                if res.get("provider") not in ("procedural",):
                    await _save_cost(story_id, "image", media.IMAGE_PRICE)

            cap = MEDIA_ROOT / "tmp" / f"{aid}-{i:02d}.png"
            await asyncio.to_thread(media.render_caption, chunk.get("voiceover", ""), cap)
            clip = MEDIA_ROOT / "clips" / aid / f"{i:02d}.mp4"
            if clip.exists():
                audio_urls.append((i, f"/api/media/audio/{aid}/{i:02d}.mp3"))
                frame_urls.append((i, f"/api/media/frames/{aid}/{i:02d}.png"))
                await setp(8 + int((i + 1) / len(chunks) * 50), f"Segments {i + 1}/{len(chunks)} (cached)")
                return
            silence_pad = 0.0
            if editor.get("silence_before_index") == i:
                silence_pad = 0.6
            rate_mult = {"climax": 1.7, "action": 1.4, "twist": 1.2, "hook": 1.15}.get(chunk.get("beat"), 1.0)
            vid_res = await router.video(
                f"{style}. {chunk.get('video_prompt', chunk.get('visual', ''))} "
                f"Characters must match: {anchor[:400]}",
                char_path, MEDIA_ROOT / "tmp" / f"{aid}-raw-{i:02d}.mp4", dur + silence_pad)
            hook_card = None
            if i == 0:
                hook_card = await asyncio.to_thread(
                    media.render_hook_card, chunks[0].get("voiceover", ""),
                    MEDIA_ROOT / "tmp" / f"{aid}-hook.png")
            if vid_res.get("provider") == "kenburns":
                await media.make_segment_clip(frame, aud, cap, clip, chunk.get("camera", "zoom_in"),
                                              dur + silence_pad, rate_mult=rate_mult,
                                              hook_card=hook_card, silence_pad=silence_pad)
            else:
                await media.compose_ai_clip(MEDIA_ROOT / "tmp" / f"{aid}-raw-{i:02d}.mp4",
                                            aud, cap, clip, dur + silence_pad,
                                            hook_card=hook_card)
                await _save_cost(story_id, "video", round(0.05 * dur, 3))
            audio_urls.append((i, f"/api/media/audio/{aid}/{i:02d}.mp3"))
            frame_urls.append((i, f"/api/media/frames/{aid}/{i:02d}.png"))
            await setp(8 + int((i + 1) / len(chunks) * 50), f"Segments {i + 1}/{len(chunks)}")

    await asyncio.gather(*[one_segment(i, c) for i, c in enumerate(chunks)])

    setp(62, "Stitching")
    await set_story(stage="Stitching")
    clips = sorted((MEDIA_ROOT / "clips" / aid).glob("*.mp4"))
    main = MEDIA_ROOT / "final" / f"{aid}_main.mp4"
    await media.concat_clips(clips, main)
    total = media.ffprobe_duration(main)

    mood = (story["script"].get("chunks", [{}])[0].get("music_mood")
            or channel.get("music_mood") or "devotional")
    music = MEDIA_ROOT / "music" / f"{mood}.wav"
    if not music.exists():
        await asyncio.to_thread(media.synth_music, mood, music)
    ambience = MEDIA_ROOT / "music" / f"{mood}_amb.wav"
    if not ambience.exists():
        await asyncio.to_thread(media.synth_ambience, mood, ambience)
    mixed = MEDIA_ROOT / "final" / f"{aid}_mix.mp4"
    await media.mix_music(main, music, mixed, total, channel.get("music_volume", 0.16),
                          ambience=ambience)

    end_png = MEDIA_ROOT / "tmp" / f"{aid}-end.png"
    await asyncio.to_thread(media.render_endcard, channel.get("name", "StoryForge"),
                            channel.get("cta_text", "Subscribe for more stories"), end_png)
    end_clip = MEDIA_ROOT / "tmp" / f"{aid}-end.mp4"
    await media.make_endcard_clip(end_png, end_clip)
    final = MEDIA_ROOT / "final" / f"{aid}.mp4"
    await media.concat_clips([mixed, end_clip], final)

    setp(72, "QA review")
    await set_story(stage="QA")
    try:
        qa, qa_cost = await agents.run_qa(story, channel)
        await _save_cost(story_id, "llm", qa_cost)
    except Exception as e:
        print(f"[pipeline] QA unavailable: {str(e)[:120]}", flush=True)
        qa = {"passed": None, "score": None, "checks": [], "issues": [],
              "note": "QA agent temporarily unavailable (API quota) — rerun after quota resets"}

    setp(86, "Metadata & thumbnail")
    await set_story(stage="Metadata")
    try:
        meta, meta_cost = await agents.make_metadata(story, channel)
        await _save_cost(story_id, "llm", meta_cost)
    except Exception as e:
        print(f"[pipeline] metadata unavailable: {str(e)[:120]}", flush=True)
        meta = {"title": story.get("title_english") or story.get("title_hindi", ""),
                "description": story.get("moral", ""),
                "hashtags": ["stories", "india", "mythology", "shorts"],
                "thumbnail_text": story.get("title_english", "")[:40],
                "note": "auto-metadata unavailable (API quota) — rerun later"}

    thumb_art = MEDIA_ROOT / "tmp" / f"{aid}-thumb-raw.png"
    main_char = (story.get("characters") or [{}])[0]
    ai_ok = await media.generate_image(
        f"Dramatic viral YouTube Shorts thumbnail artwork, vertical 9:16, extreme emotional close-up, "
        f"high contrast rim lighting, {style}. Main character: {main_char.get('description', anchor[:300])}. "
        f"Scene: {story.get('climax', '')}. No text, no watermark.",
        thumb_art, ref_image=char_path, session=f"thumb-{aid}")
    if ai_ok:
        await _save_cost(story_id, "image", media.IMAGE_PRICE)
    thumb_path = MEDIA_ROOT / "thumbs" / f"{aid}.jpg"
    await asyncio.to_thread(
        media.overlay_title_on_image, thumb_art,
        meta.get("thumbnail_text") or story.get("title_english") or story.get("title_hindi", ""),
        channel.get("name", ""), thumb_path)

    audio_urls.sort(key=lambda t: t[0])
    frame_urls.sort(key=lambda t: t[0])
    await set_story(
        status="in_review", stage="Awaiting review",
        qa=qa if isinstance(qa, dict) else {},
        metadata=meta if isinstance(meta, dict) else {},
        media={
            "final": f"/api/media/final/{aid}.mp4",
            "duration_sec": round(media.ffprobe_duration(final), 1),
            "char_sheet": f"/api/media/char/{aid}.png",
            "audio": [u for _, u in audio_urls],
            "frames": [u for _, u in frame_urls],
            "thumbnail": f"/api/media/thumbs/{aid}.jpg",
        },
    )


async def regenerate_segment(story_id: str, index: int, setp):
    story = await db.stories.find_one({"_id": story_id})
    if not story:
        raise RuntimeError("story not found")
    channel = await db.channels.find_one({"_id": story["channel_id"]})
    chunks = (story.get("script") or {}).get("chunks") or []
    if index < 0 or index >= len(chunks):
        raise RuntimeError("invalid segment index")
    chunk = chunks[index]
    aid = story_id

    await set_story_async(story_id, stage=f"Regenerating segment {index + 1}", status="rendering")
    await setp(10, f"Segment {index + 1}")

    audio_dir = MEDIA_ROOT / "audio" / aid
    aud = audio_dir / f"{index:02d}.mp3"
    adur = await media.synthesize_voice(chunk.get("voiceover", ""), channel.get("voice", ""),
                                        channel.get("voice_speed", 1.0), aud,
                                        lang_hint=channel.get("language", "hi"))
    await _save_cost(story_id, "tts", media.tts_cost(chunk.get("voiceover", "")))
    dur = max(6.0, min(16.0, adur + 0.6))

    frame = MEDIA_ROOT / "frames" / aid / f"{index:02d}.png"
    ai_ok = await media.generate_image(
        f"{channel.get('style_prefix') or story.get('visual_style', '')}. "
        f"{chunk.get('video_prompt', chunk.get('visual', ''))} Vertical 9:16, cinematic, no text.",
        frame, ref_image=MEDIA_ROOT / "char" / f"{aid}.png", session=f"frame-{aid}-{index}-r")
    if ai_ok:
        await _save_cost(story_id, "image", media.IMAGE_PRICE)

    cap = MEDIA_ROOT / "tmp" / f"{aid}-{index:02d}.png"
    await asyncio.to_thread(media.render_caption, chunk.get("voiceover", ""), cap)
    clip = MEDIA_ROOT / "clips" / aid / f"{index:02d}.mp4"
    await media.make_segment_clip(frame, aud, cap, clip, chunk.get("camera", "zoom_in"), dur)

    setp(70, "Re-stitching")
    clips = sorted((MEDIA_ROOT / "clips" / aid).glob("*.mp4"))
    main = MEDIA_ROOT / "final" / f"{aid}_main.mp4"
    await media.concat_clips(clips, main)
    total = media.ffprobe_duration(main)
    mood = chunks[0].get("music_mood") or channel.get("music_mood") or "devotional"
    music = MEDIA_ROOT / "music" / f"{mood}.wav"
    if not music.exists():
        await asyncio.to_thread(media.synth_music, mood, music)
    mixed = MEDIA_ROOT / "final" / f"{aid}_mix.mp4"
    await media.mix_music(main, music, mixed, total, channel.get("music_volume", 0.16))
    end_clip = MEDIA_ROOT / "tmp" / f"{aid}-end.mp4"
    if not end_clip.exists():
        end_png = MEDIA_ROOT / "tmp" / f"{aid}-end.png"
        await asyncio.to_thread(media.render_endcard, channel.get("name", "StoryForge"),
                                channel.get("cta_text", "Subscribe"), end_png)
        await media.make_endcard_clip(end_png, end_clip)
    final = MEDIA_ROOT / "final" / f"{aid}.mp4"
    await media.concat_clips([mixed, end_clip], final)

    await set_story_async(
        story_id, status="in_review", stage="Awaiting review",
        media={**(story.get("media") or {}),
               "final": f"/api/media/final/{aid}.mp4",
               "duration_sec": round(media.ffprobe_duration(final), 1),
               "audio": [f"/api/media/audio/{aid}/{i:02d}.mp3" for i in range(len(chunks))],
               "frames": [f"/api/media/frames/{aid}/{i:02d}.png" for i in range(len(chunks))]})


async def improve_video(story_id: str, setp):
    """Improvement coach: after assessment, pinpoint the weakest scope, apply targeted edits
    (max 2 rounds) and keep them ONLY if the overall viral score improves — auto-revert otherwise."""
    import json as _json

    story = await db.stories.find_one({"_id": story_id})
    if not story:
        raise RuntimeError("story not found")
    attempts = story.get("improvements") or []
    if len(attempts) >= 2:
        raise RuntimeError("improvement budget exhausted (2 rounds max)")
    script = story.get("script") or {}
    chunks = script.get("chunks") or []
    if not chunks:
        raise RuntimeError("story has no script")
    base_score = (script.get("viral_score") or {}).get("total")
    if base_score is None:
        q = story.get("qa") or {}
        base_score = round(q["score"] * 10) if q.get("score") is not None else 0
    prev_script = _json.loads(_json.dumps(script))

    channel = await db.channels.find_one({"_id": story["channel_id"]})
    if not channel:
        from bson import ObjectId
        channel = await db.channels.find_one({"_id": ObjectId(story["channel_id"])})

    await set_story_async(story_id, status="rendering", stage="Improvement coach", error="")
    await setp(5, "Pinpointing weakest scope")
    sug, cost = await agents.improvement_pass(story, channel or {}, attempts)
    await _save_cost(story_id, "llm", cost)

    changed = set()
    for c in (sug.get("edits") or []):
        try:
            idx = int(c.get("index", -1))
        except (TypeError, ValueError):
            continue
        if 0 <= idx < len(chunks) and isinstance(c, dict):
            for k in ("voiceover", "visual", "video_prompt"):
                if c.get(k):
                    chunks[idx][k] = c[k]
                    changed.add(idx)
    hook_line = sug.get("hook_line") or ""
    if hook_line and chunks:
        chunks[0]["voiceover"] = hook_line
        changed.add(0)

    for i in changed:  # invalidate caches so only edited segments re-render
        for sub, ext in (("audio", "mp3"), ("frames", "png")):
            (MEDIA_ROOT / sub / story_id / f"{i:02d}.{ext}").unlink(missing_ok=True)
        (MEDIA_ROOT / "clips" / story_id / f"{i:02d}.mp4").unlink(missing_ok=True)

    story["script"]["chunks"] = chunks
    await db.stories.update_one({"_id": story_id}, {"$set": {
        "script": story["script"], "status": "rendering",
        "stage": f"Improvement round {len(attempts) + 1}: re-render"}})

    await setp(15, "Re-rendering with targeted edits")
    await produce_video(story_id, setp)

    fresh = await db.stories.find_one({"_id": story_id})
    new_score = ((fresh.get("script") or {}).get("viral_score") or {}).get("total")
    accepted = new_score is not None and new_score > base_score
    iteration = {
        "round": len(attempts) + 1, "scope": sug.get("scope", ""), "why": sug.get("why", ""),
        "base_score": base_score, "new_score": new_score, "segments_edited": sorted(changed),
        "accepted": accepted, "attempted": True, "at": utcnow().isoformat(),
    }
    if not accepted:
        await set_story_async(story_id, script=prev_script, stage="Reverting — no score gain")
        await setp(55, "Reverting to previous script")
        await produce_video(story_id, setp)

    await db.stories.update_one(
        {"_id": story_id},
        {"$push": {"improvements": iteration}, "$set": {"updated_at": utcnow()}})
    print(f"[improve] round {iteration['round']}: {base_score} -> {new_score} "
          f"({'kept' if accepted else 'reverted'}) scope={str(iteration['scope'])[:80]}", flush=True)


async def set_story_async(story_id, **kw):
    kw["updated_at"] = utcnow()
    await db.stories.update_one({"_id": story_id}, {"$set": kw})
