"""Google News RSS ingestion + strict public-interest policy triage for Channel C."""
import hashlib
import xml.etree.ElementTree as ET
from urllib.parse import quote

import httpx

from services import gemini

RSS = "https://news.google.com/rss/search?q={q}&hl=en-IN&gl=IN&ceid=IN:en"
QUERIES = [
    "climate change report",
    "natural disaster warning",
    "science technology invention",
    "institutional report economy",
    "public health study",
]
ALLOWED = ("climate change, disasters and disaster preparedness, environment, public health, "
           "science & technology, inventions, new reports by national/international institutions "
           "(WHO, UN, NASA, ISRO, RBI, World Bank etc), economy, business and success stories of "
           "people/institutions")
FORBIDDEN = ("politics, elections, politicians or political parties, religion or communal topics, "
             "national security, defence, foreign relations/diplomacy, crime, celebrity gossip, "
             "sports, anything politically debatable, over-sensitive, or opinion-driven controversy")


async def fetch_items(limit_per_query: int = 8):
    items, seen = [], set()
    async with httpx.AsyncClient(timeout=60, follow_redirects=True,
                                 headers={"User-Agent": "Mozilla/5.0 (compatible; StoryForge/1.0)"}) as client:
        for q in QUERIES:
            try:
                r = await client.get(RSS.format(q=quote(q)))
                root = ET.fromstring(r.text)
                count = 0
                for it in root.iter("item"):
                    title = (it.findtext("title") or "").strip()
                    link = (it.findtext("link") or "").strip()
                    if not title or not link:
                        continue
                    h = hashlib.md5(title.lower().encode()).hexdigest()
                    if h in seen:
                        continue
                    seen.add(h)
                    items.append({
                        "title": title, "link": link,
                        "source": (it.findtext("source") or "").strip() or "Google News",
                        "published": it.findtext("pubDate") or "",
                        "query": q,
                    })
                    count += 1
                    if count >= limit_per_query:
                        break
            except Exception as e:
                print(f"[news] fetch failed for '{q}': {str(e)[:120]}")
    return items


POLICY_SYSTEM = (
    "You are the editorial compliance agent for a strictly factual, public-interest news Shorts channel. "
    "You approve ONLY content that is factual, conceptual and of broad public interest. You reject anything "
    "political, religious, communal, controversial, opinion-driven, about national security, defence, foreign "
    "relations, crime, celebrities or sports. You always respond with valid JSON only."
)


async def triage_item(item: dict, channel: dict) -> dict:
    prompt = f"""Review this news item for the channel "{channel.get('name')}".

ALLOWED topics: {ALLOWED}.
STRICTLY FORBIDDEN: {FORBIDDEN}.

NEWS ITEM: "{item['title']}" (source: {item['source']}, found via query '{item['query']}')

Decide: is a 60-second factual public-information Short appropriate? If approved, propose a neutral, factual,
conceptual angle that explains the underlying issue/report/development (never the political framing).

Return JSON: {{"approved": bool, "reason": str (one line, required when rejected),
"summary": str (2-3 factual sentences for the story record, required when approved),
"story_title": str (a clean neutral title, required when approved),
"category": str from [Climate, Disaster, Science & Tech, Economy, Health, Environment, Business]}}"""
    return await gemini.chat_json(POLICY_SYSTEM, prompt, session="news-triage")
