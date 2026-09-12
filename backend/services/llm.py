import json
import os
import re
import uuid

from emergentintegrations.llm.chat import LlmChat, UserMessage

from services.keys import candidate_keys

MODEL = ("openai", "gpt-5.4")
LLM_IN_PRICE = 2.5e-6   # $ per input token (estimate)
LLM_OUT_PRICE = 1.0e-5  # $ per output token (estimate)


def _chat_for(key):
    chat = LlmChat(
        api_key=key,
        session_id=f"s-{uuid.uuid4().hex[:10]}",
        system_message="",
    ).with_model(*MODEL)
    return chat


def _extract_text(resp):
    if resp is None:
        return ""
    if isinstance(resp, str):
        return resp
    content = getattr(resp, "content", None)
    if isinstance(content, str):
        return content
    return str(resp)


def estimate_llm_cost(prompt: str, response: str) -> float:
    return len(prompt) / 4 * LLM_IN_PRICE + len(response) / 4 * LLM_OUT_PRICE


def parse_json(text: str):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"```\s*$", "", text).strip()
    m = re.search(r"[\[{]", text)
    if not m:
        raise ValueError("no JSON found in LLM response")
    obj, _ = json.JSONDecoder().raw_decode(text[m.start():])
    return obj


async def ask_json(system: str, prompt: str, session: str = "job", retries: int = 2):
    from services import gemini  # lazy: avoids circular import
    last_err = None

    # 1) user's Gemini key first (cheapest)
    if gemini.gemini_key():
        for attempt in range(retries + 1):
            try:
                return await gemini.chat_json(system, prompt, session, retries=0)
            except Exception as e:
                last_err = e
        print(f"[llm] gemini chain failed: {str(last_err)[:120]}", flush=True)

    # 2) OpenAI-compatible keys via LlmChat (emergent first: funded universal key)
    keys = [k for k in (gemini.emergent_key(), gemini.openai_key()) if k]
    for attempt in range(retries + 1):
        for key in keys:
            try:
                chat = LlmChat(
                    api_key=key,
                    session_id=f"{session}-{uuid.uuid4().hex[:8]}",
                    system_message=system,
                ).with_model(*MODEL)
                msg_text = prompt if attempt == 0 else (
                    prompt + "\n\nCRITICAL: respond with ONLY a single valid JSON object/array. No markdown, no commentary."
                )
                resp = await chat.send_message(UserMessage(text=msg_text))
                txt = _extract_text(resp)
                return parse_json(txt)
            except Exception as e:
                last_err = e
                msg = str(e).lower()
                if not any(w in msg for w in ("budget", "credit", "quota", "rate", "429", "401", "exceeded")):
                    break
    raise ValueError(f"LLM call failed: {last_err}")
