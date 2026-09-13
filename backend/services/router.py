"""Quota-aware model router.

Preference: best available API with free/paid quota first (fal.ai FLUX/Wan, Replicate, Gemini,
OpenAI) — once a provider is exhausted (circuit breaker) the router automatically falls through
to free open-source models (Kokoro TTS, gTTS) and finally the always-free local pipeline
(procedural frames, Ken Burns motion).
"""
import asyncio
import os
import time
from pathlib import Path

HEALTH = {}
COOLDOWN = 900  # seconds a provider is benched after repeated failures


def _fail(provider: str):
    h = HEALTH.setdefault(provider, {"fails": 0, "until": 0})
    h["fails"] += 1
    if h["fails"] >= 3:
        h["until"] = time.time() + COOLDOWN
        print(f"[router] {provider} benched for {COOLDOWN}s after {h['fails']} failures", flush=True)


def _ok(provider: str):
    HEALTH[provider] = {"fails": 0, "until": 0}


def available(provider: str) -> bool:
    h = HEALTH.get(provider)
    return not h or time.time() >= h.get("until", 0)


def _key(name: str) -> str:
    return (os.environ.get(name) or "").strip()


def chain(kind: str) -> list:
    order = {
        "tts": os.environ.get("TTS_PROVIDER_ORDER", "kokoro,xtts,gtts,gemini,openai"),
        "image": os.environ.get("IMAGE_PROVIDER_ORDER",
                                "openai,stability,hf_flux,fal_flux,replicate_flux,emergent,gemini,qwen_local,pexels,procedural"),
        "video": os.environ.get("VIDEO_PROVIDER_ORDER", "gemini_veo,replicate_wan,fal_wan,pexels_video,kenburns"),
    }
    return [p.strip() for p in order[kind].split(",") if p.strip()]


def status() -> dict:
    return {
        "tts_chain": chain("tts"),
        "image_chain": chain("image"),
        "video_chain": chain("video"),
        "providers": {
            "fal_flux": {"key": bool(_key("FAL_KEY")), "healthy": available("fal_flux")},
            "fal_wan": {"key": bool(_key("FAL_KEY")), "healthy": available("fal_wan")},
            "replicate": {"key": bool(_key("REPLICATE_API_TOKEN")), "healthy": available("replicate")},
            "gemini_veo": {"key": bool(_key("GEMINI_API_KEY")), "healthy": available("gemini_veo")},
            "hf_flux": {"key": bool(_key("HF_TOKEN")), "healthy": available("hf_flux")},
            "stability": {"key": bool(_key("STABILITY_API_KEY")), "healthy": available("stability")},
            "gemini": {"key": bool(_key("GEMINI_API_KEY")), "healthy": available("gemini")},
            "openai": {"key": bool(_key("OPENAI_API_KEY")), "healthy": available("openai")},
            "kokoro": {"key": True, "healthy": available("kokoro")},
            "xtts": {"key": True, "healthy": available("xtts")},
            "gtts": {"key": True, "healthy": available("gtts")},
            "procedural": {"key": True, "healthy": True},
            "kenburns": {"key": True, "healthy": True},
            "qwen_local": {"key": True, "healthy": available("qwen_local"), "capable": _qwen_capable()},
            "pexels": {"key": bool(_key("PEXELS_API_KEY")), "healthy": True},
            "pexels_video": {"key": bool(_key("PEXELS_API_KEY")), "healthy": True},
        },
        "notes": "Slide mode image priority: OpenAI → Hugging Face FLUX.1-schnell → fal.ai. Clip mode video priority: Gemini Veo → Replicate (Wan 2.1) → fal.ai. Free local fallbacks (Kokoro/XTTS/gTTS voice, procedural frames + Ken Burns) always available. Add HF_TOKEN / FAL_KEY / REPLICATE_API_TOKEN in Settings → API Keys.",
    }


# ---------------- TTS ----------------
KOKORO_LANGS = {"hi", "en"}
KOKORO_VOICES = {"hi": "hf_alpha", "en": "af_heart"}
KOKORO_ALL = {"hf_alpha", "hf_beta", "af_heart", "af_bella", "af_nicole", "af_sky",
              "am_adam", "am_michael", "am_echo", "hm_omega", "hm_psi"}
XTTS_LANGS = {"hi", "en"}
_xtts_model = None
_pipes = {}


async def tts(text: str, voice_spec: str, lang_hint: str, out_path: Path) -> dict:
    from services import gemini
    from services.media import ffprobe_duration

    out_path.parent.mkdir(parents=True, exist_ok=True)
    lang = (lang_hint or "hi").split("-")[0]

    for provider in chain("tts"):
        if not available(provider):
            continue
        try:
            if provider == "gemini":
                if not (voice_spec or "").startswith("gemini:") or not gemini.gemini_key():
                    raise RuntimeError("gemini tts not applicable")
                dur = await gemini.tts(text, voice_spec.split(":", 1)[1] or "Kore", out_path)
                _ok(provider)
                return {"provider": provider, "duration": dur}

            if provider == "kokoro":
                if lang not in KOKORO_LANGS:
                    raise RuntimeError(f"kokoro lacks lang {lang}")
                spec_voice = (voice_spec or "").split(":", 1)[1] if (voice_spec or "").startswith("kokoro:") else ""
                voice = spec_voice if spec_voice in KOKORO_ALL else KOKORO_VOICES.get(lang, "af_heart")
                dur = await _kokoro(text, voice, out_path)
                _ok(provider)
                return {"provider": provider, "duration": dur}

            if provider == "xtts":
                if lang not in XTTS_LANGS:
                    raise RuntimeError(f"xtts lacks lang {lang}")
                dur = await _xtts(text, lang, out_path)
                _ok(provider)
                return {"provider": provider, "duration": dur}

            if provider == "gtts":
                from services.media import gtts_tts
                dur = await gtts_tts(text, lang, out_path)
                _ok(provider)
                return {"provider": provider, "duration": dur}

            if provider == "openai":
                from services.media import openai_tts
                dur = await openai_tts(text, voice_spec, out_path)
                _ok(provider)
                return {"provider": provider, "duration": dur}
        except Exception as e:
            _fail(provider)
            print(f"[router] tts:{provider} failed -> next: {str(e)[:110]}", flush=True)

    raise RuntimeError("all TTS providers failed")


async def _kokoro(text: str, voice: str, out_path: Path) -> float:
    import numpy as np
    import soundfile as sf

    def run():
        from kokoro import KPipeline
        lang = "hi" if voice.startswith(("h", "hm_", "hf_")) else "en"
        if lang not in _pipes:
            _pipes[lang] = KPipeline(lang_code=lang)
        audio = [out for _, _, out in _pipes[lang](text[:900], voice=voice)]
        sf.write(str(out_path), np.concatenate(audio), 24000)

    await asyncio.to_thread(run)
    from services.media import ffprobe_duration
    return ffprobe_duration(out_path)


async def _xtts(text: str, lang: str, out_path: Path) -> float:
    """XTTS v2 (Coqui, local CPU) — deep open-source fallback with expressive Hindi/English voices."""
    global _xtts_model
    os.environ.setdefault("COQUI_TOS_AGREED", "1")

    def run():
        global _xtts_model
        if _xtts_model is None:
            import torch
            from TTS.api import TTS as CoquiTTS
            device = "cuda" if torch.cuda.is_available() else "cpu"
            print(f"[router] loading XTTS v2 on {device} (first call downloads ~1.8GB)…", flush=True)
            _xtts_model = CoquiTTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)
        speaker = "Damien Black" if lang == "hi" else "Ana Florence"
        _xtts_model.tts_to_file(text=" ".join(str(text).split())[:800], language=lang,
                                speaker=speaker, file_path=str(out_path))

    await asyncio.to_thread(run)
    from services.media import ffprobe_duration
    return ffprobe_duration(out_path)


# ---------------- IMAGE ----------------
def _qwen_capable() -> bool:
    """Qwen-Image-2512 is a 20B MMDiT model — needs a CUDA GPU or ~40GB+ free RAM (bf16)."""
    if (os.environ.get("ENABLE_QWEN_LOCAL", "1") != "1"):
        return False
    try:
        import psutil
        import torch
        if torch.cuda.is_available():
            return True
        return psutil.virtual_memory().available > 40 * 1024 ** 3
    except Exception:
        return False


async def _qwen_image(prompt: str, ref_image: Path = None) -> bytes:
    global _qwen_pipe
    if not _qwen_capable():
        raise RuntimeError("qwen_local: host not capable (needs CUDA GPU or ~40GB free RAM for the "
                           "20B model) — falling through; set ENABLE_QWEN_LOCAL=0 to silence")

    def run():
        global _qwen_pipe
        import io

        import torch
        from diffusers import DiffusionPipeline
        if _qwen_pipe is None:
            model = os.environ.get("QWEN_IMAGE_MODEL", "Qwen/Qwen-Image-2512")
            print(f"[router] loading {model} locally (one-time heavy download)…", flush=True)
            _qwen_pipe = DiffusionPipeline.from_pretrained(model, torch_dtype=torch.bfloat16)
            _qwen_pipe.enable_model_cpu_offload()
        img = _qwen_pipe(prompt[:1800], height=1344, width=768,
                         num_inference_steps=40, guidance_scale=4.0).images[0]
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    return await asyncio.to_thread(run)


async def _hf_image(prompt: str) -> bytes:
    """Hugging Face free inference — FLUX.1-schnell (free tier, needs HF_TOKEN)."""
    token = _key("HF_TOKEN")
    if not token:
        raise RuntimeError("HF_TOKEN not set (add it in Settings → API Keys)")
    import httpx

    model = os.environ.get("HF_IMAGE_MODEL", "black-forest-labs/FLUX.1-schnell")
    urls = [f"https://router.huggingface.co/hf-inference/models/{model}",
            f"https://api-inference.huggingface.co/models/{model}"]
    last = None
    async with httpx.AsyncClient(timeout=120) as client:
        for url in urls:
            r = await client.post(url, headers={"Authorization": f"Bearer {token}"},
                                  json={"inputs": prompt[:800]})
            if r.status_code == 200 and r.content[:3] in (b"\x89PN", b"\xff\xd8\xff"):
                return r.content
            last = f"{r.status_code} {r.text[:100]}"
    raise RuntimeError(f"hf flux failed: {last}")


async def _pexels_video(prompt: str) -> bytes:
    import tempfile
    from pathlib import Path as _P

    from services import pexels
    tmp = _P(tempfile.gettempdir()) / f"pxv-{abs(hash(prompt)) % 99999}.mp4"
    ok = await pexels.fetch_video(prompt, tmp)
    if not ok:
        raise RuntimeError("pexels video: no match")
    return tmp.read_bytes()


async def _veo_video(prompt: str, duration: float) -> bytes:
    """Gemini API Veo (paid tier) — LRO submit + poll + download; falls through on quota errors."""
    import httpx

    key = _key("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY not set")
    base = "https://generativelanguage.googleapis.com/v1beta"
    headers = {"x-goog-api-key": key}
    models = ["veo-3.1-fast-generate-preview", "veo-3.0-generate-001", "veo-3.0-fast-generate-001"]
    last = None
    async with httpx.AsyncClient(timeout=120) as client:
        for model in models:
            try:
                r = await client.post(
                    f"{base}/models/{model}:predictLongRunning", headers=headers,
                    json={"instances": [{"prompt": prompt[:1500]}],
                          "parameters": {"sampleCount": 1, "aspectRatio": "9:16"}})
                r.raise_for_status()
                op = r.json().get("name")
                if not op:
                    raise RuntimeError("no operation name")
                for _ in range(80):
                    s = await client.get(f"{base}/{op}", headers=headers)
                    d = s.json()
                    if d.get("error"):
                        raise RuntimeError(str(d["error"])[:140])
                    if d.get("done"):
                        uri = (d.get("response", {}).get("generateVideoResponse", {})
                               .get("generatedSamples") or [{}])[0].get("video", {}).get("uri")
                        if not uri:
                            raise RuntimeError("veo: no video uri")
                        dl = await client.get(uri, headers=headers, timeout=300, follow_redirects=True)
                        dl.raise_for_status()
                        return dl.content
                    await asyncio.sleep(8)
                raise RuntimeError("veo timeout")
            except httpx.HTTPStatusError as e:
                last = f"{model}: {e.response.status_code}"
                continue
            except Exception as e:
                last = f"{model}: {str(e)[:100]}"
                continue
    raise RuntimeError(f"veo exhausted: {last}")


async def image(prompt: str, out_path: Path, ref_image: Path = None, session: str = "img") -> dict:
    from services import imagegen

    for provider in chain("image"):
        if not available(provider):
            continue
        try:
            if provider == "fal_flux":
                data = await _fal_image(prompt)
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_bytes(data)
                _ok(provider)
                return {"provider": provider}
            if provider == "replicate_flux":
                data = await _replicate_image(prompt)
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_bytes(data)
                _ok(provider)
                return {"provider": provider}
            if provider == "hf_flux":
                data = await _hf_image(prompt)
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_bytes(data)
                _ok(provider)
                return {"provider": provider}
            if provider == "qwen_local":
                data = await _qwen_image(prompt, ref_image)
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_bytes(data)
                _ok(provider)
                return {"provider": provider}
            if provider == "stability":
                from services.llm import _stability_image
                if not await _stability_image(prompt, out_path):
                    raise RuntimeError("stability: no image")
                _ok(provider)
                return {"provider": provider}
            if provider == "pexels":
                from services import pexels
                if not await pexels.fetch_photo(prompt, out_path):
                    raise RuntimeError("pexels: no match")
                _ok(provider)
                return {"provider": provider}
            if provider in ("gemini", "emergent", "openai", "procedural"):
                res = await imagegen.generate_image(prompt, out_path, ref_image=ref_image, session=session)
                return {"provider": f"{provider}", "ai": res}
        except Exception as e:
            _fail(provider)
            print(f"[router] image:{provider} failed -> next: {str(e)[:110]}", flush=True)
    raise RuntimeError("all image providers failed")


async def _fal_image(prompt: str) -> bytes:
    key = _key("FAL_KEY")
    if not key:
        raise RuntimeError("FAL_KEY not set")
    import httpx

    # FLUX first, then open-source SD endpoints (SD 3.5, SDXL, Juggernaut XL)
    endpoints = [e.strip() for e in os.environ.get(
        "FAL_IMAGE_ENDPOINTS",
        "fal-ai/flux/schnell,fal-ai/stable-diffusion-3.5-large,fal-ai/fast-sdxl,fal-ai/juggernaut-xl-v9"
    ).split(",") if e.strip()]
    last = None
    async with httpx.AsyncClient(timeout=240) as client:
        for endpoint in endpoints:
            try:
                r = await client.post(
                    f"https://queue.fal.run/{endpoint}",
                    headers={"Authorization": f"Key {key}", "Content-Type": "application/json"},
                    json={"prompt": prompt[:1800], "num_images": 1,
                          "image_size": {"width": 768, "height": 1344}},
                )
                r.raise_for_status()
                sub = r.json()
                for _ in range(90):
                    s = await client.get(sub["status_url"], headers={"Authorization": f"Key {key}"})
                    st = s.json().get("status", "").upper()
                    if st in ("COMPLETED", "OK"):
                        res = await client.get(sub["response_url"], headers={"Authorization": f"Key {key}"})
                        res.raise_for_status()
                        out = res.json()
                        url = (out.get("images") or [{}])[0].get("url")
                        if not url:
                            raise RuntimeError("no image url in fal response")
                        img = await client.get(url)
                        return img.content
                    if st in ("FAILED", "ERROR", "CANCELLED"):
                        raise RuntimeError(f"fal {endpoint} failed: {st}")
                    await asyncio.sleep(3)
                raise RuntimeError("fal timeout")
            except httpx.HTTPStatusError as e:
                last = f"{endpoint}: {e.response.status_code}"
                continue  # try next open-source endpoint
            except Exception as e:
                last = f"{endpoint}: {str(e)[:90]}"
                continue
    raise RuntimeError(f"fal image endpoints exhausted: {last}")


async def _replicate_image(prompt: str) -> bytes:
    token = _key("REPLICATE_API_TOKEN")
    if not token:
        raise RuntimeError("REPLICATE_API_TOKEN not set")
    import httpx

    model = os.environ.get("REPLICATE_IMAGE_MODEL", "black-forest-labs/flux-schnell")
    async with httpx.AsyncClient(timeout=300) as client:
        r = await client.post(
            f"https://api.replicate.com/v1/models/{model}/predictions",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"input": {"prompt": prompt[:1800], "aspect_ratio": "9:16", "output_format": "png"}},
        )
        r.raise_for_status()
        job = r.json()
        for _ in range(100):
            u = job["urls"]["get"]
            s = await client.get(u, headers={"Authorization": f"Bearer {token}"})
            job = s.json()
            if job.get("status") == "succeeded":
                out = job.get("output") or []
                if not out:
                    raise RuntimeError("replicate: no output")
                img = await client.get(out[0])
                return img.content
            if job.get("status") in ("failed", "canceled"):
                raise RuntimeError(f"replicate failed: {str(job.get('error'))[:120]}")
            await asyncio.sleep(3)
    raise RuntimeError("replicate timeout")


# ---------------- VIDEO ----------------
async def video(prompt: str, ref_image: Path, out_path: Path, duration: float = 10.0) -> dict:
    for provider in chain("video"):
        if not available(provider):
            continue
        try:
            if provider == "gemini_veo":
                data = await _veo_video(prompt, duration)
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_bytes(data)
                _ok(provider)
                return {"provider": provider}
            if provider == "fal_wan":
                data = await _fal_video(prompt, duration)
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_bytes(data)
                _ok(provider)
                return {"provider": provider}
            if provider == "replicate_wan":
                data = await _replicate_video(prompt, duration)
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_bytes(data)
                _ok(provider)
                return {"provider": provider}
            if provider == "pexels_video":
                data = await _pexels_video(prompt)
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_bytes(data)
                _ok(provider)
                return {"provider": provider}
            if provider == "kenburns":
                return {"provider": "kenburns"}  # local motion renderer in media.py
        except Exception as e:
            _fail(provider)
            print(f"[router] video:{provider} failed -> next: {str(e)[:110]}", flush=True)
    return {"provider": "kenburns"}


async def _fal_video(prompt: str, duration: float) -> bytes:
    key = _key("FAL_KEY")
    if not key:
        raise RuntimeError("FAL_KEY not set")
    import httpx

    endpoints = [e.strip() for e in os.environ.get(
        "FAL_VIDEO_ENDPOINTS", "fal-ai/wan-t2v,fal-ai/cogvideox-5b").split(",") if e.strip()]
    last = None
    async with httpx.AsyncClient(timeout=120) as client:
        for endpoint in endpoints:
            try:
                r = await client.post(
                    f"https://queue.fal.run/{endpoint}",
                    headers={"Authorization": f"Key {key}", "Content-Type": "application/json"},
                    json={"prompt": prompt[:1800]},
                )
                r.raise_for_status()
                sub = r.json()
                for _ in range(240):
                    s = await client.get(sub["status_url"], headers={"Authorization": f"Key {key}"})
                    st = s.json().get("status", "").upper()
                    if st in ("COMPLETED", "OK"):
                        res = await client.get(sub["response_url"], headers={"Authorization": f"Key {key}"})
                        res.raise_for_status()
                        out = res.json()
                        url = (out.get("video") or {}).get("url")
                        if not url:
                            raise RuntimeError("fal video: no video url")
                        vid = await client.get(url, timeout=300)
                        return vid.content
                    if st in ("FAILED", "ERROR", "CANCELLED"):
                        raise RuntimeError(f"fal {endpoint} failed: {st}")
                    await asyncio.sleep(4)
                raise RuntimeError("fal video timeout")
            except httpx.HTTPStatusError as e:
                last = f"{endpoint}: {e.response.status_code}"
                continue
            except Exception as e:
                last = f"{endpoint}: {str(e)[:90]}"
                continue
    raise RuntimeError(f"fal video endpoints exhausted: {last}")


async def _replicate_video(prompt: str, duration: float) -> bytes:
    token = _key("REPLICATE_API_TOKEN")
    if not token:
        raise RuntimeError("REPLICATE_API_TOKEN not set")
    import httpx

    model = os.environ.get("REPLICATE_VIDEO_MODEL", "wan-video/wan-2.1-1.3b")
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            f"https://api.replicate.com/v1/models/{model}/predictions",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"input": {"prompt": prompt[:1800]}},
        )
        r.raise_for_status()
        job = r.json()
        for _ in range(240):
            s = await client.get(job["urls"]["get"], headers={"Authorization": f"Bearer {token}"})
            job = s.json()
            if job.get("status") == "succeeded":
                out = job.get("output") or []
                if not out:
                    raise RuntimeError("replicate: no output")
                vid = await client.get(out[0], timeout=300)
                return vid.content
            if job.get("status") in ("failed", "canceled"):
                raise RuntimeError(f"replicate failed: {str(job.get('error'))[:120]}")
            await asyncio.sleep(4)
    raise RuntimeError("replicate timeout")
