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


def _pil_poster(titles, out_path: Path, rows, cols, photos=None):
    """Free poster: real Pexels photos composited per panel (when available) with dark overlay,
    headline text and numbered badges — zero AI cost, works always."""
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
        px = (photos or [None] * n)[i] if photos else None
        art = None
        if px and Path(px).exists():
            try:
                art = Image.open(px).convert("RGB")
                # cover-crop the photo into the panel
                scale = max(tw / art.width, th / art.height)
                art = art.resize((int(art.width * scale) + 1, int(art.height * scale) + 1))
                left = (art.width - tw) // 2
                top = (art.height - th) // 2
                img.paste(art.crop((left, top, left + tw, top + th)), (x0, y0))
            except Exception:
                art = None
        if art is None:
            d.rounded_rectangle([x0, y0, x0 + tw, y0 + th], radius=16, fill=PALETTE[i % len(PALETTE)])
        else:
            d.rounded_rectangle([x0, y0, x0 + tw, y0 + th], radius=16, outline="#0B0D16", width=4)
        # dark gradient overlay for text legibility
        ov = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
        od = ImageDraw.Draw(ov)
        for gy in range(th):
            od.line([(0, gy), (tw, gy)], fill=(0, 0, 0, int(150 * (gy / th) ** 1.3)))
        img.paste(Image.composite(ov, Image.new("RGBA", (tw, th)), Image.new("L", (tw, th), 255)).convert("RGB"), (x0, y0), ov)
        d = ImageDraw.Draw(img)
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


async def generate_storyboard(segments, out_dir: Path, style: str, anchor: str, ref_image: Path, channel: dict):
    """One AI call for the whole poster (or a local PIL poster when every image API is dead),
    then local slicing into per-segment slides named 00.png, 01.png, …"""
    from services import router

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
        f"STRICT CHARACTER, SETTING AND STYLE CONTINUITY BIBLE — obey in every panel: {anchor} "
        f"Create one cohesive vertical contact sheet divided into a {rows}-row x {cols}-column grid of equal narrative panels, "
        f"separated only by delicate ornamental gold borders. ART DIRECTION LOCK: {style}. "
        "Every reappearing character must have the exact same face, age, skin tone, hair, clothing colors, accessories, build and aura in every panel. "
        "Recurring locations must keep the same architecture and props. Use a unified deep-indigo and saffron palette, fine miniature-painting linework, "
        "rich natural pigments, subtle gold leaf, layered flat perspective, devotional atmosphere and cinematic lighting where requested. "
        + " ".join(
            f"Panel {i + 1}, row-major scene: {t[:360]}."
            for i, t in enumerate(titles[: rows * cols]))
        + " No captions, no title band, no letters, no numbered badges, no watermark, no photorealism, no 3D render, no style drift."
    )

    tmp = out_dir / "poster_ai.png"
    try:
        await router.image(prompt[:10000], tmp, ref_image=ref_image, session="storyboard",
                           require_reference=True, quality_required=True)
    except Exception as e:
        raise RuntimeError(f"continuity-locked storyboard generation failed; retry when a reference-aware provider is available: {str(e)[:180]}") from e
    if tmp.exists():
        tmp.replace(poster)
        print("[storyboard] AI poster generated (1 API call)", flush=True)
    else:
        raise RuntimeError("continuity-locked storyboard provider returned no image")

    return _slice(poster, rows, cols, n, out_dir)
