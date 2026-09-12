import { useRef, useState } from "react";
import { UploadCloud, FileText, CheckCircle2, Loader2 } from "lucide-react";
import { Link } from "react-router-dom";
import { api, usePoll, useChannels } from "@/lib/api";
import { BOOK_STATUS, statusMeta, STATUS } from "@/lib/ui";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Checkbox } from "@/components/ui/checkbox";
import { toast } from "sonner";

export default function UploadPage() {
  const { channels } = useChannels();
  const [books, refresh] = usePoll("/books", 3000);
  const [drag, setDrag] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [langs, setLangs] = useState({ hi: true, bn: true, en: true });
  const inputRef = useRef(null);
  const channelId = channels?.[0]?.id;

  const upload = async (file) => {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".pdf")) return toast.error("Only scanned PDFs are accepted");
    if (!channelId) return toast.error("Channels still initializing");
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("channel_id", channelId);
      const hints = Object.entries(langs).filter(([, v]) => v).map(([k]) => k).join(",");
      await api.post(`/books/upload${hints ? `?ocr_langs=${hints}` : ""}`, fd);
      toast.success(`"${file.name}" queued for OCR`);
      refresh();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const genScript = async (id) => {
    try {
      await api.post(`/stories/${id}/script`);
      toast.success("Script generation queued");
      refresh();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed");
    }
  };

  const langLabel = { hi: "Hindi", bn: "Bengali", en: "English" };

  return (
    <div className="mx-auto max-w-6xl space-y-8">
      <div>
        <h1 className="font-display text-3xl font-extrabold tracking-tight text-slate-100 lg:text-4xl">PDF Upload & OCR Engine</h1>
        <p className="mt-1 text-sm text-slate-400">Scanned books in Bengali, Hindi/Devanagari and English — OCR runs automatically, then the story-mining agent segments self-contained tales</p>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div
          data-testid="upload-pdf-dropzone"
          onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => { e.preventDefault(); setDrag(false); upload(e.dataTransfer.files[0]); }}
          onClick={() => inputRef.current?.click()}
          className={`flex h-64 cursor-pointer flex-col items-center justify-center rounded-3xl border-2 border-dashed transition-colors lg:col-span-2 ${
            drag ? "border-amber-400 bg-amber-500/10" : "border-amber-500/25 bg-[#12141F] hover:border-amber-500/50"
          }`}
        >
          <input ref={inputRef} type="file" accept="application/pdf" hidden onChange={(e) => upload(e.target.files[0])} />
          {uploading ? (
            <Loader2 className="mb-3 h-10 w-10 animate-spin text-amber-400" />
          ) : (
            <UploadCloud className="mb-3 h-10 w-10 text-amber-400" />
          )}
          <div className="font-display text-lg font-semibold text-slate-100">Drop a scanned PDF book here</div>
          <div className="mt-1 text-xs text-slate-500">Puranas · Bhagwat · Thakurmar Jhuli · folk tale collections (max 60MB)</div>
          <Button data-testid="start-ocr-button" className="mt-5 bg-amber-500 text-[#090A0F] hover:bg-amber-400" onClick={(e) => { e.stopPropagation(); inputRef.current?.click(); }}>
            Browse & Start OCR
          </Button>
        </div>

        <div className="card-glow rounded-3xl border border-amber-500/10 bg-[#12141F] p-6">
          <h3 className="mb-3 font-display text-base font-semibold text-amber-300">OCR Language Packs</h3>
          {Object.entries(langs).map(([k, v]) => (
            <label key={k} className="mb-3 flex cursor-pointer items-center gap-3 text-sm text-slate-300">
              <Checkbox data-testid={`ocr-lang-${k}`} checked={v} onCheckedChange={(c) => setLangs({ ...langs, [k]: !!c })} />
              {langLabel[k]}
            </label>
          ))}
          <div className="mt-4 rounded-xl bg-black/30 p-3 text-[11px] leading-relaxed text-slate-500">
            Pipeline: page render → Tesseract OCR (hin+ben+eng) → language detection → text cleaning → LLM story segmentation. Channel for a book is set from the first channel; stories inherit it.
          </div>
        </div>
      </div>

      <div className="space-y-5">
        <h2 className="font-display text-xl font-semibold text-slate-100">Ingestion Queue</h2>
        {!(books || []).length && (
          <div className="rounded-2xl border border-dashed border-white/10 p-10 text-center text-sm text-slate-500">No books yet — the sample PDFs live in backend/samples if you want a quick start</div>
        )}
        {(books || []).map((b) => (
          <div key={b.id} data-testid="book-card" className="card-glow rounded-2xl border border-amber-500/10 bg-[#12141F] p-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <FileText className="h-8 w-8 text-amber-400/70" />
                <div>
                  <div className="font-medium text-slate-100">{b.filename}</div>
                  <div className="text-xs text-slate-500">
                    {b.total_pages || "?"} pages · {(b.languages || []).map((l) => langLabel[l]).join(" + ") || "detecting…"} · {(b.size_bytes / 1024 / 1024).toFixed(1)}MB
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <Badge data-testid="book-status-badge" className={`${statusMeta(b.status).cls} border text-[11px]`}>{statusMeta(b.status).label}</Badge>
                {b.story_count > 0 && <span className="text-xs text-slate-400">{b.story_count} stories found</span>}
              </div>
            </div>
            {(b.status === "ocr_running" || b.status === "uploaded") && <Progress value={b.progress || 4} className="mt-4" data-testid="ocr-progress-bar" />}
            {b.error && <div className="mt-3 rounded-lg bg-red-950/40 px-3 py-2 text-xs text-red-300">{b.error}</div>}

            {b.status === "segmented" && (
              <BookStories bookId={b.id} onGenScript={genScript} />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function BookStories({ bookId, onGenScript }) {
  const [book] = usePoll(`/books/${bookId}`, 5000);
  const stories = book?.stories || [];
  return (
    <div className="mt-5 space-y-3 border-t border-white/5 pt-5">
      {stories.map((s) => (
        <div key={s.id} data-testid="extracted-story-row" className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-black/25 px-4 py-3">
          <div className="min-w-0">
            <Link to={`/stories/${s.id}`} className="truncate font-deva text-sm font-semibold text-amber-200 hover:underline">{s.title_hindi || s.title_english}</Link>
            <div className="truncate text-[11px] text-slate-500">{s.title_english} · pp.{s.page_start}-{s.page_end} · {s.category} · {s.target_audience}</div>
          </div>
          <div className="flex items-center gap-2">
            <Badge className={`${statusMeta(s.status).cls} border text-[10px]`}>{statusMeta(s.status).label}</Badge>
            {s.status === "draft" && (
              <Button data-testid="generate-script-button" size="sm" variant="outline" className="border-amber-500/40 text-amber-300 hover:bg-amber-500/10" onClick={() => onGenScript(s.id)}>
                Generate Script
              </Button>
            )}
            {s.status !== "draft" && (
              <Button data-testid="open-story-button" size="sm" variant="outline" className="border-amber-500/40 text-amber-300 hover:bg-amber-500/10" onClick={() => window.open(`/stories/${s.id}`, "_self")}>
                Open Studio
              </Button>
            )}
          </div>
        </div>
      ))}
      {!stories.length && <div className="py-2 text-xs text-slate-500">No stories were identified in this book</div>}
    </div>
  );
}
