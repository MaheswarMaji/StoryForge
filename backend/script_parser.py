"""Deterministic parser for user-supplied scene scripts.

Structured scripts are source material, not prompts: their dialogue and visuals must be
preserved instead of rewritten by an LLM.
"""
import re


SCENE_RE = re.compile(
    r"(?im)^\s*(?:🎬\s*)?(?:सीन|scene)\s*(\d+)\s*(?:[|:.-]\s*)?([^\n]*)$"
)
SPEECH_RE = re.compile(
    r"(?im)(नैरेशन(?:\s*\(\s*वॉयसओवर\s*\))?(?:\s*\+\s*CTA)?|वॉयसओवर|"
    r"संवाद\s*[—–-]\s*[^:\n]+|narration(?:\s*\(\s*voiceover\s*\))?|"
    r"voiceover|dialogue\s*[—–-]\s*[^:\n]+)\s*:"
)
VISUAL_RE = re.compile(r"(?im)(?:विज़ुअल|विजुअल|visuals?|scene\s+visual)\s*:")
NOTES_RE = re.compile(r"(?im)^\s*(?:🎵\s*)?(?:प्रोडक्शन\s+नोट्स|production\s+notes)\s*$")
BIBLE_START_RE = re.compile(
    r"(?im)^.*(?:पात्र\s+एवं\s+दृश्य\s+संगति\s+गाइड|consistency\s+bible|character\s+(?:&|and)\s+style\s+guide).*$"
)
SCRIPT_START_RE = re.compile(r"(?im)^.*(?:सीन-दर-सीन\s+स्क्रिप्ट|scene-by-scene\s+script).*$")
QUOTE_RE = re.compile(r"[\"“](.*?)[\"”]", re.DOTALL)


def _clean(value: str) -> str:
    return re.sub(r"[ \t]+", " ", value).strip(" \t\r\n")


def _camera(text: str) -> str:
    value = text.lower()
    if re.search(r"zoom[\s-]*out|ज़ूम[\s-]*आउट|जूम[\s-]*आउट", value):
        return "zoom_out"
    if re.search(r"pan[\s-]*left|पैन[\s-]*लेफ्ट", value):
        return "pan_left"
    if re.search(r"pan[\s-]*right|पैन[\s-]*राइट", value):
        return "pan_right"
    if re.search(r"static|स्थिर", value):
        return "static"
    return "zoom_in"


def _beat(index: int, total: int, label: str) -> str:
    value = label.lower()
    if index == 0 or "hook" in value or "हुक" in value:
        return "hook"
    if index == total - 1 or "closing" in value or "क्लोज" in value or "lesson" in value or "सीख" in value:
        return "lesson"
    if "climax" in value or "प्रकटन" in value or "चरम" in value:
        return "climax"
    if "twist" in value or "मोड़" in value or "तपस्या" in value:
        return "twist"
    if "action" in value or "वरदान" in value:
        return "action"
    ratio = index / max(total - 1, 1)
    if ratio < 0.45:
        return "story"
    if ratio < 0.62:
        return "twist"
    if ratio < 0.78:
        return "climax"
    return "action"


def _emotion(label: str) -> str:
    parenthetical = re.findall(r"\(([^)]*)\)", label)
    return _clean(parenthetical[-1] if parenthetical else label) or "storytelling"


def _spoken_text(body: str, first_speech: re.Match | None) -> str:
    if not first_speech:
        return ""
    speech = body[first_speech.start():]
    parts = []
    matches = list(SPEECH_RE.finditer(speech))
    for i, marker in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(speech)
        content = speech[marker.end():end]
        quotes = [_clean(q) for q in QUOTE_RE.findall(content) if _clean(q)]
        if quotes:
            parts.extend(quotes)
        else:
            plain = NOTES_RE.split(content, maxsplit=1)[0]
            if _clean(plain):
                parts.append(_clean(plain))
    return "\n".join(parts)


def _visual_text(body: str, first_speech: re.Match | None) -> str:
    match = VISUAL_RE.search(body)
    if not match:
        return ""
    end = first_speech.start() if first_speech else len(body)
    return _clean(body[match.end():end])


def _consistency_bible(text: str, first_scene_start: int) -> str:
    head = text[:first_scene_start]
    start = BIBLE_START_RE.search(head)
    if not start:
        return ""
    script_marker = SCRIPT_START_RE.search(head, start.end())
    end = script_marker.start() if script_marker else len(head)
    bible = _clean(head[start.end():end])
    return bible[:12000]


def _title(text: str) -> str:
    for line in text.splitlines():
        clean = _clean(line).strip('"')
        if clean and not clean.startswith(("(", "फॉर्मेट", "Format")):
            return clean[:150]
    return "Imported scene script"


def parse_scene_script(text: str) -> dict | None:
    matches = list(SCENE_RE.finditer(text))
    if not matches:
        return None

    chunks = []
    for idx, match in enumerate(matches):
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        body = NOTES_RE.split(text[match.end():end], maxsplit=1)[0]
        first_speech = SPEECH_RE.search(body)
        visual = _visual_text(body, first_speech)
        voiceover = _spoken_text(body, first_speech)
        if not visual and not voiceover:
            continue
        label = _clean(match.group(2))
        chunks.append({
            "chunk_id": f"scene-{match.group(1)}",
            "source_scene": int(match.group(1)),
            "source_label": label,
            "beat": "story",  # assigned after skipped/usable scenes are known
            "voiceover": voiceover[:4000],
            "visual": visual[:4000],
            "video_prompt": visual[:4000],
            "camera": _camera(visual),
            "emotion": _emotion(label),
        })
    if not chunks:
        return None
    for idx, chunk in enumerate(chunks):
        chunk["beat"] = _beat(idx, len(chunks), chunk["source_label"])

    notes_match = NOTES_RE.search(text)
    notes = _clean(text[notes_match.end():]) if notes_match else ""
    return {
        "title": _title(text),
        "character_sheet": _consistency_bible(text, matches[0].start()),
        "chunks": chunks,
        "production_notes": notes[:8000],
    }