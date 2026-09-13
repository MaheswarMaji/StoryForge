"""One-shot storyboard mode: a SINGLE image-generation call renders every slide as a numbered
grid poster; the poster is sliced into slides locally — 1 API call per video instead of N."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

PALETTE = ["#14532D", "#166534", "#1D4ED8", "#7C2D12", "#4C1D95", "#134E4A"]


def _grid_for(n):
    if n <= 4:
        return 2, 2
    if n <= 6:
        return 3, 2
    if n <= 9:
        return 3, 3
    return 4, 3


def _font(size):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def _wrap(draw, text, font, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=font) <= max_w:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines[:6]


def _pil_poster(titles, out_path: Path, rows, cols):
    """Fully local fallback poster — zero API calls, always works."""
    n = min(len(titles), rows * cols)
    tw, th, pad = 640, 780, 10
    W = cols * tw + (cols + 1) * pad
    H = rows * th + (rows + 1) * pad + 100
    img = Image.new("RGB", (W, H), "#0B0D16")
    d = ImageDraw.Draw(img)
    f_head, f_body, f_badge = _font(34), _font(24), _font(24)
    for i in range(n):
        r, c = divmod(i, cols)
        x0 = pad + c * (tw + pad)
        y0 = pad + r * (th + pad)
        bg = PALETTE[i % len(PALETTE)]
        d.rounded_rectangle([x0, y0, x0 + tw, y0 + th], radius=16, fill=bg)
        d.rounded_rectangle([x0 + 16, y0 + 16, x0 + 96, y0 + 60], radius=10, fill="#090A0F")
        d.text((x0 + 38, y0 + 24), str(i + 1), font=f_badge, fill="#FCD34D")
        y = y0 + 78
        raw = (titles[i] or f"Slide {i + 1}").strip()
        parts = raw.split(". ")
        for line in _wrap(d, parts[0][:90], f_head, tw - 48):
            d.text((x0 + 24, y), line, font=f_head, fill="#FFFFFF")
            y += 44
        rest = ". ".join(parts[1:]).strip() or raw
        for line in _wrap(d, rest[:240], f_body, tw - 48):
            d.text((x0 + 24, y), "• " + line, font=f_body, fill="#E2E8F0")
            y += 34
    d.text((pad + 12, H - 66), "StoryForge instant storyboard", font=_font(34), fill="#FCD34D")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)


def _slice(poster: Path, rows, cols, n, out_dir: Path):
    img = Image.open(poster).convert("RGB")
    W, H = img.size
    tw, th = W // cols, H // rows
    tiles = []
    for i in range(n):
        r, c = divmod(i, cols)
        tile = img.crop((c * tw, r * th, min((c + 1) * tw, W), min((r + 1) * th, H)))
        p = out_dir / f"{i:02d}.png"
        tile.save(p)
        tiles.append(p)
    return tiles


async def generate_storyboard(segments, out_dir: Path, style: str, channel: dict):
    """One AI call for the whole poster (or a local PIL poster when every image API is dead),
    then local slicing into per-segment slides named 00.png, 01.png, …"""
    from services import media

    n = len(segments)
    rows, cols = _grid_for(n)
    out_dir.mkdir(parents=True, exist_ok=True)
    poster = out_dir / "storyboard.png"

    # cache: if the poster and all tiles already exist, skip the AI call entirely (instant re-renders)
    tiles = [out_dir / f"{i:02d}.png" for i in range(n)]
    if poster.exists() and all(t.exists() for t in tiles):
        print("[storyboard] poster + tiles cached — skipped generation", flush=True)
        return tiles

    titles = []
    for s in segments:
        t = (s.get("visual") or s.get("video_prompt") or s.get("voiceover", "")).strip()
        titles.append(t[:260] or "slide")

    prompt = (
        f"One cohesive vertical infographic poster divided into a {rows}-row x {cols}-column grid of equal "
        f"panels separated by thin white gutters. Art style: {style}. Poster title band at the bottom: "
        f"'{(channel or {}).get('name', 'StoryForge')} — illustrated guide'. "
        + " ".join(
            f"Panel {i + 1} (numbered badge top-left, row-major order): photorealistic illustration for "
            f"headline '{t.split('. ')[0][:80]}' with supporting text '{('. '.join(t.split('. ')[1:]) or t)[:150]}'."
            for i, t in enumerate(titles[: rows * cols]))
        + " Bold readable English text inside every panel, high contrast, no watermark."
    )

    tmp = out_dir / "poster_ai.png"
    ok = False
    try:
        ok = await media.generate_image(prompt[:3500], tmp, session="storyboard")
    except Exception as e:
        print(f"[storyboard] AI poster failed: {str(e)[:140]}", flush=True)
    if ok and tmp.exists():
        tmp.replace(poster)
        print("[storyboard] AI poster generated (1 API call)", flush=True)
    else:
        print("[storyboard] falling back to local PIL poster", flush=True)
        _pil_poster(titles, poster, rows, cols)

    return _slice(poster, rows, cols, n, out_dir)
