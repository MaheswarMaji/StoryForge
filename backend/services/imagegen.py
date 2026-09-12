"""Provider chains: Gemini (user key) -> OpenAI -> Emergent -> procedural fallback."""
import asyncio
import base64
import os
from pathlib import Path

from services import gemini
from services.ocr import MEDIA_ROOT

IMAGE_PRICE = 0.03


def _ref_bytes(ref_image):
    if ref_image and Path(ref_image).exists():
        return Path(ref_image).read_bytes()
    return None


async def generate_image(prompt: str, out_path: Path, ref_image: Path = None, session: str = "img"):
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    ref = _ref_bytes(ref_image)

    ek = gemini.emergent_key()
    if ek:
        try:
            await asyncio.wait_for(
                _gen_gemini_proxy(ek, prompt, out_path, ref_image, session), timeout=240)
            return True
        except Exception as e:
            print(f"[media] emergent nano-banana failed: {str(e)[:120]}", flush=True)

    if gemini.gemini_key() and not gemini.circuit_open():
        try:
            data = await asyncio.wait_for(gemini.gen_image(prompt, ref), timeout=240)
            out_path.write_bytes(data)
            return True
        except Exception as e:
            print(f"[media] gemini image failed: {str(e)[:120]}", flush=True)

    ok = gemini.openai_key()
    if ok:
        try:
            await _gen_openai_image(ok, prompt, out_path)
            return True
        except Exception as e:
            print(f"[media] openai image failed: {str(e)[:120]}", flush=True)

    await asyncio.to_thread(procedural_frame, prompt, out_path)
    return False


async def _gen_gemini_proxy(key, prompt, out_path, ref_image, session):
    import uuid
    from emergentintegrations.llm.chat import ImageContent, LlmChat, UserMessage

    for attempt in range(2):
        try:
            chat = LlmChat(
                api_key=key, session_id=f"{session}-{uuid.uuid4().hex[:8]}",
                system_message="You are a world-class cinematic artist creating viral mythological video visuals.",
            ).with_model("gemini", "gemini-3.1-flash-image-preview").with_params(modalities=["image", "text"])
            if ref_image and Path(ref_image).exists():
                b64 = base64.b64encode(Path(ref_image).read_bytes()).decode()
                msg = UserMessage(text=prompt[:2200], file_contents=[ImageContent(b64)])
            else:
                msg = UserMessage(text=prompt[:2200])
            _, images = await chat.send_message_multimodal_response(msg)
            if not images:
                raise RuntimeError("no images")
            out_path.write_bytes(base64.b64decode(images[0]["data"]))
            return
        except Exception as e:
            if attempt == 1:
                raise
            print(f"[media] nano-banana attempt {attempt + 1} failed: {str(e)[:100]}", flush=True)
            await asyncio.sleep(8)


async def _gen_openai_image(key, prompt, out_path):
    from emergentintegrations.llm.openai.image_generation import OpenAIImageGeneration
    gen = OpenAIImageGeneration(api_key=key)
    images = await gen.generate_images(prompt=prompt, model="gpt-image-1", quality="medium")
    if not images:
        raise RuntimeError("no images returned")
    out_path.write_bytes(images[0])


# ---------- procedural fallback frames (free, no API) ----------
MOOD_PALETTES = {
    "devotional": [(38, 20, 4), (120, 63, 8), (245, 158, 11)],
    "suspense": [(6, 8, 24), (30, 27, 75), (99, 102, 241)],
    "horror": [(4, 6, 10), (40, 12, 24), (127, 29, 29)],
    "moral": [(10, 30, 28), (19, 78, 74), (45, 212, 191)],
    "action": [(30, 8, 4), (127, 29, 29), (239, 68, 68)],
    "sad": [(12, 16, 32), (30, 41, 59), (148, 163, 184)],
    "happy": [(30, 24, 4), (133, 77, 14), (251, 191, 36)],
}


def procedural_frame(prompt: str, out_path: Path):
    from PIL import Image, ImageDraw, ImageFilter, ImageFont

    text = str(prompt).lower()
    mood = next((m for m in MOOD_PALETTES if m in text), "devotional")
    c1, c2, c3 = MOOD_PALETTES[mood]
    W, H = 1080, 1920
    img = Image.new("RGB", (W, H), c1)
    d = ImageDraw.Draw(img)
    for y in range(H):
        k = y / H
        r = int(c1[0] + (c2[0] - c1[0]) * k)
        g = int(c1[1] + (c2[1] - c1[1]) * k)
        b = int(c1[2] + (c2[2] - c1[2]) * k)
        d.line([(0, y), (W, y)], fill=(r, g, b))
    # radiant mandala motif
    cx, cy = W // 2, int(H * 0.42)
    glow = Image.new("RGB", (W, H), (0, 0, 0))
    dg = ImageDraw.Draw(glow)
    import math
    for ring in range(9, 0, -1):
        rad = 90 + ring * 68
        col = tuple(int(c * (1 - ring / 14)) for c in c3)
        dg.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], outline=col, width=10)
        for i in range(24):
            a = math.pi * 2 * i / 24 + ring * 0.13
            dg.line([(cx + rad * math.cos(a), cy + rad * math.sin(a)),
                     (cx + (rad + 46) * math.cos(a), cy + (rad + 46) * math.sin(a))], fill=col, width=6)
    glow = glow.filter(ImageFilter.GaussianBlur(6))
    img = Image.blend(img, Image.composite(glow, img, glow.convert("L").point(lambda v: min(255, v * 2))), 0.55)
    d = ImageDraw.Draw(img, "RGBA")
    d.rectangle([0, 0, W, H], fill=(0, 0, 0, 60))
    d.ellipse([cx - 190, cy - 190, cx + 190, cy + 190], fill=c3 + (230,))
    d.ellipse([cx - 150, cy - 150, cx + 150, cy + 150], fill=c1 + (255,))
    f = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 40)
    words = str(prompt).split()[:6]
    d.text((cx, cy), " ".join(words[:3]), font=f, fill=(20, 12, 2), anchor="mm")
    d.text((cx, cy + 54), " ".join(words[3:6]), font=f, fill=(20, 12, 2), anchor="mm")
    # film grain + vignette
    import numpy as np
    arr = np.array(img).astype(np.float64)
    rng = np.random.default_rng(3)
    arr += rng.integers(-9, 9, arr.shape)
    yy, xx = np.mgrid[0:H, 0:W]
    vig = np.clip(1 - ((xx - W / 2) ** 2 + (yy - H / 2) ** 2) / ((W / 2) ** 2) / 2.4, 0.25, 1)
    arr = arr * vig[:, :, None]
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    img.save(out_path)
    return out_path
