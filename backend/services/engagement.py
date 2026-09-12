"""Engagement agent: triages comments on published videos and DRAFTS replies only where
absolutely necessary (questions, issues, corrections). Nothing is auto-posted — a human
approves every reply from the dashboard (draft-only publishing)."""
from services import gemini, social

TRIAGE_SYSTEM = (
    "You are the community-engagement agent for factual myth/story/news Shorts channels. You decide which "
    "comments genuinely NEED a reply (factual questions, correction requests, reports of broken links/errors, "
    "safety concerns, repeated genuine confusion). General compliments, emojis, spam and ordinary chatter need "
    "NO reply. Replies must be short, warm, factual and never argue about politics or controversy. "
    "You always respond with valid JSON only."
)


async def triage_comments(comments, channel_name: str) -> dict:
    listing = "\n".join(
        f"{i}. [{c.get('author', 'user')}] {c.get('text', '')[:220]}" for i, c in enumerate(comments))
    prompt = f"""Channel: "{channel_name}". Review these comments:

{listing}

For EACH comment index, decide:
- needs_reply: true ONLY for factual questions, correction/error reports, broken-link reports, safety concerns or genuine repeated confusion. false for general praise/emojis/spam/chatter.
- reply: a short (max 2 sentences) warm factual reply — empty string when needs_reply is false.
- action: one of "reply" | "acknowledge" (like/heart, no reply) | "ignore" (spam/abuse).

Return JSON: {{"decisions": [{{"index": int, "needs_reply": bool, "action": str, "reply": str}}]}}"""
    return await gemini.chat_json(TRIAGE_SYSTEM, prompt, session="engagement")


async def sync_once(channel_name: str = "StoryForge") -> dict:
    from db import db
    from models import SocialComment, utcnow

    creds = social.cred_status()
    summary = {"fetched": 0, "drafts": 0, "skipped": 0}
    raw = []
    if creds["youtube"]:
        published = [s for s in await db.stories.find(
            {"publish.youtube.video_id": {"$exists": True}}).to_list(20)]
        for s in published:
            try:
                raw += [(c, s["id"], "youtube") for c in social.yt_list_comments(s["publish"]["youtube"]["video_id"])]
            except Exception as e:
                print(f"[engagement] yt comments failed: {str(e)[:120]}")
    if creds["instagram"]:
        try:
            raw += [(c, "", "instagram") for c in social.ig_list_comments()]
        except Exception as e:
            print(f"[engagement] ig comments failed: {str(e)[:120]}")

    if not raw:
        return summary

    existing_ids = {d["comment_id"] async for d in db.social_comments.find({}, {"comment_id": 1})}
    fresh = [(c, sid, plat) for c, sid, plat in raw if c["comment_id"] not in existing_ids]
    summary["fetched"] = len(fresh)
    if not fresh:
        return summary

    comments_only = [c for c, _, _ in fresh]
    decisions = {}
    try:
        data = await triage_comments(comments_only[:30], channel_name)
        decisions = {d.get("index"): d for d in data.get("decisions", []) if isinstance(d, dict)}
    except Exception as e:
        print(f"[engagement] triage failed: {str(e)[:150]}")

    for i, (c, story_id, platform) in enumerate(fresh):
        dec = decisions.get(i, {})
        needs_reply = bool(dec.get("needs_reply")) and bool(dec.get("reply"))
        doc = SocialComment(
            platform=platform, story_id=story_id, video_id=c.get("video_id", ""),
            comment_id=c["comment_id"], author=c.get("author", ""), text=c.get("text", ""),
            likes=c.get("likes", 0),
            triage={"action": dec.get("action", "acknowledge"),
                    "needs_reply": needs_reply, "reason": ""},
            reply_text=dec.get("reply", "") if needs_reply else "",
            posted=False, handled=False, created_at=utcnow())
        # DRAFT-ONLY: replies are stored unposted; the human approves each one in the dashboard
        if needs_reply:
            summary["drafts"] += 1
        else:
            summary["skipped"] += 1
            doc.handled = True
        await db.social_comments.update_one(
            {"comment_id": c["comment_id"]}, {"$set": doc.to_mongo()}, upsert=True)
    return summary
