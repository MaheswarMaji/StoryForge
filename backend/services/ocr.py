import asyncio
import os
import re
import subprocess
from pathlib import Path

from db import db

MEDIA_ROOT = Path(__file__).resolve().parent.parent / "media"
PAGE_DPI = 170


def disk_guard(min_free_mb: int = 600):
    """Disk is tight in this container — sweep re-renderable artifacts when free space runs low."""
    import shutil
    free_mb = shutil.disk_usage(MEDIA_ROOT).free // (1024 * 1024)
    if free_mb < min_free_mb:
        tmp = MEDIA_ROOT / "tmp"
        if tmp.exists():
            shutil.rmtree(tmp, ignore_errors=True)
            tmp.mkdir(parents=True, exist_ok=True)
        for stale in (MEDIA_ROOT / "books").glob("*/page-*.png"):
            stale.unlink(missing_ok=True)
        free_mb = shutil.disk_usage(MEDIA_ROOT).free // (1024 * 1024)
        if free_mb < min_free_mb:
            raise RuntimeError(f"low disk: only {free_mb}MB free after cleaning — free /app space and retry")
    return free_mb

DEV = re.compile(r"[\u0900-\u097F]")
BEN = re.compile(r"[\u0980-\u09FF]")
CHAPTER_RE = re.compile(r"^\s*(अध्याय|चैप्टर|Chapter|CHAPTER|অধ্যায়|চ্যাপ্টার)\s*[:\-\.\d]")

CLEAN_LINES = [
    re.compile(r"^\s*(page|p\.?|पृष्ठ|পৃষ্ঠা)\s*\d+\s*$", re.I),
    re.compile(r"^\s*\d{1,4}\s*$"),
    re.compile(r"^\s*[-–—_*·]{3,}\s*$"),
]


def detect_language(text: str) -> str:
    counts = {"hi": len(DEV.findall(text)), "bn": len(BEN.findall(text)), "en": 0}
    counts["en"] = sum(1 for c in text if c.isascii() and c.isalpha())
    best = max(counts, key=counts.get)
    return best if counts[best] > 0 else "en"


def clean_page_text(raw: str) -> str:
    lines = []
    for ln in raw.splitlines():
        if any(p.match(ln) for p in CLEAN_LINES):
            continue
        ln = re.sub(r"[ \t]+", " ", ln).strip()
        if ln:
            lines.append(ln)
    return "\n".join(lines)


def build_chapters(pages):
    chapters = []
    current = {"chapter_number": 1, "title": "Full Text", "pages": [], "raw_text": ""}
    for p in pages:
        heading = None
        for ln in p["text"].split("\n"):
            if CHAPTER_RE.match(ln):
                heading = ln.strip()[:120]
                break
        if heading and current["pages"]:
            chapters.append(current)
            current = {"chapter_number": len(chapters) + 1, "title": heading, "pages": [], "raw_text": ""}
        current["pages"].append(p["page"])
        current["raw_text"] += p["text"] + "\n\n"
    if current["pages"]:
        chapters.append(current)
    for ch in chapters:
        ch["raw_text"] = ch["raw_text"][:12000]
    return chapters


async def run_ocr(book_id: str, setp):
    book = await db.books.find_one({"_id": book_id})
    pdf_path = Path(book["path"]) if book.get("path") else None
    if not pdf_path or not pdf_path.is_file():
        from services import storage
        if not book.get("storage_path"):
            raise RuntimeError("book file missing")
        pdf_path = MEDIA_ROOT / "books" / book_id / "source.pdf"
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        data, _ = storage.get_object(book["storage_path"])
        pdf_path.write_bytes(data)
    outdir = pdf_path.parent
    for stale in outdir.glob("page-*.png"):  # leftovers from a crashed previous run
        stale.unlink(missing_ok=True)
    disk_guard()

    max_pages = int(os.environ.get("OCR_MAX_PAGES", "150"))
    chunk_size = 40  # render+OCR in bounded chunks (memory/disk safe for huge books)
    info = subprocess.run(["pdfinfo", str(pdf_path)], capture_output=True, text=True)
    total = 0
    for ln in info.stdout.splitlines():
        if ln.startswith("Pages:"):
            total = int(ln.split(":")[1].strip())
    total = min(total, max_pages)
    if total == 0:
        raise RuntimeError("PDF rendered to 0 pages — is it a valid PDF?")

    results = []
    for start in range(1, total + 1, chunk_size):
        end = min(start + chunk_size - 1, total)
        await setp(3 + int(start / total * 15), f"Rendering pages {start}–{end}")
        await asyncio.to_thread(
            subprocess.run,
            ["pdftoppm", "-png", "-r", str(PAGE_DPI), "-f", str(start), "-l", str(end),
             str(pdf_path), str(outdir / "page")],
            check=True, capture_output=True,
        )
        chunk_images = sorted(outdir.glob("page-*.png"))
        for j, img in enumerate(chunk_images):
            proc = await asyncio.create_subprocess_exec(
                "tesseract", str(img), "stdout", "-l", "hin+ben+eng",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            out, err = await proc.communicate()
            text = clean_page_text(out.decode("utf-8", "ignore"))
            results.append({"page": start + j, "language": detect_language(text), "text": text})
            Path(img).unlink(missing_ok=True)
            await setp(15 + int(len(results) / total * 70),
                       f"OCR page {len(results)}/{total}")

    langs = sorted({r["language"] for r in results if r["text"].strip()})
    chapters = build_chapters(results)
    await db.books.update_one(
        {"_id": book_id},
        {"$set": {
            "status": "ocr_done", "progress": 100, "pages": results,
            "total_pages": total, "languages": langs,
            "structured": {"source_file": book["filename"], "language": ",".join(langs),
                           "total_pages": total, "chapters": chapters},
        }},
    )
    for leftover in outdir.glob("page-*.png"):
        leftover.unlink(missing_ok=True)
    return total, langs
