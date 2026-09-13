import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Clapperboard, Film, Images, Loader2, Wand2 } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";

export default function CreatePage() {
  const [types, setTypes] = useState([]);
  const [title, setTitle] = useState("");
  const [source, setSource] = useState("");
  const [vtype, setVtype] = useState("mythology_moral");
  const [mode, setMode] = useState("slide");
  const [length, setLength] = useState(90);
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    api.get("/video-types").then((r) => setTypes(r.data)).catch(() => {});
  }, []);

  const submit = async () => {
    if (!source.trim()) {
      toast.error("Paste a script or prompt first");
      return;
    }
    setBusy(true);
    try {
      const { data } = await api.post("/stories/create", {
        title, source_text: source, video_type: vtype, length_seconds: length, mode,
      });
      toast.success("Script is being written — review it in the Story Studio before rendering");
      navigate(`/stories/${data.story_id}`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Create failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-5xl space-y-8 pb-16">
      <div>
        <h1 className="flex items-center gap-3 font-display text-3xl font-extrabold tracking-tight text-slate-100 lg:text-4xl">
          <Clapperboard className="h-8 w-8 text-amber-400" /> Create from Script or Prompt
        </h1>
        <p className="mt-1 text-sm text-slate-400">
          Paste a full script or just a story idea. Voice and background music are chosen automatically from the video type; length is yours to set.
        </p>
      </div>

      <div className="card-glow space-y-5 rounded-2xl border border-amber-500/10 bg-[#12141F] p-6">
        <div>
          <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-400">Video title (optional)</label>
          <Input data-testid="create-title-input" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. The Boy Who Shared His Last Roti" className="border-white/10 bg-black/30 text-slate-200" />
        </div>
        <div>
          <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-400">Script or prompt *</label>
          <Textarea data-testid="create-script-textarea" value={source} onChange={(e) => setSource(e.target.value)} rows={8}
            placeholder={"Paste your full script here…\n\n—or—\n\nJust describe the video: \"A 90-second Hindi short about a poor farmer in Vidarbha whose honesty is rewarded during a drought, ending with a life lesson about integrity.\""}
            className="border-white/10 bg-black/30 text-sm leading-relaxed text-slate-200" />
        </div>

        <div>
          <label className="mb-2 block text-xs font-semibold uppercase tracking-wider text-slate-400">Video type — sets voice, music &amp; visuals automatically</label>
          <div className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-4">
            {(types || []).map((t) => (
              <button
                key={t.key}
                data-testid={`video-type-${t.key}`}
                onClick={() => setVtype(t.key)}
                className={`rounded-xl border p-3.5 text-left transition-colors ${vtype === t.key ? "border-amber-500/60 bg-amber-500/10" : "border-white/10 bg-black/30 hover:border-amber-500/30"}`}
              >
                <div className={`text-xs font-bold ${vtype === t.key ? "text-amber-300" : "text-slate-200"}`}>{t.name}</div>
                <div className="mt-1 text-[10px] leading-relaxed text-slate-500">{t.audience} · {t.language.toUpperCase()} · {t.music_mood} music</div>
              </button>
            ))}
          </div>
        </div>

        <div className="grid gap-5 sm:grid-cols-2">
          <div>
            <label className="mb-2 block text-xs font-semibold uppercase tracking-wider text-slate-400">Production style</label>
            <div className="grid grid-cols-2 gap-2.5">
              <button data-testid="mode-slide-radio" onClick={() => setMode("slide")}
                className={`flex flex-col items-center gap-1.5 rounded-xl border p-4 transition-colors ${mode === "slide" ? "border-cyan-500/60 bg-cyan-500/10 text-cyan-200" : "border-white/10 bg-black/30 text-slate-400"}`}>
                <Images className="h-5 w-5" />
                <span className="text-xs font-semibold">Slide-based</span>
                <span className="text-[10px] leading-snug text-slate-500">AI image slides &amp; infographics + narration</span>
              </button>
              <button data-testid="mode-clip-radio" onClick={() => setMode("clip")}
                className={`flex flex-col items-center gap-1.5 rounded-xl border p-4 transition-colors ${mode === "clip" ? "border-fuchsia-500/60 bg-fuchsia-500/10 text-fuchsia-200" : "border-white/10 bg-black/30 text-slate-400"}`}>
                <Film className="h-5 w-5" />
                <span className="text-xs font-semibold">AI video clips</span>
                <span className="text-[10px] leading-snug text-slate-500">Short AI video clips per scene, stitched</span>
              </button>
            </div>
          </div>
          <div>
            <label className="mb-2 block text-xs font-semibold uppercase tracking-wider text-slate-400">Target length: <span className="text-amber-300">{length}s</span></label>
            <input data-testid="length-slider" type="range" min="30" max="240" step="15" value={length}
              onChange={(e) => setLength(Number(e.target.value))}
              className="mt-3 w-full accent-amber-500" />
            <div className="mt-1 flex justify-between text-[10px] text-slate-500"><span>30s</span><span>2 min</span><span>4 min</span></div>
          </div>
        </div>

        <Button data-testid="create-video-button" onClick={submit} disabled={busy} className="w-full bg-amber-500 py-3 font-semibold text-[#090A0F] hover:bg-amber-400">
          {busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Wand2 className="mr-2 h-4 w-4" />}
          Write Script &amp; Open Story Studio
        </Button>
        <p className="text-[11px] leading-relaxed text-slate-500">
          Next: review &amp; edit the script in the Story Studio → produce (slides or AI clips, free TTS narration, music, captions) → approve → upload to YouTube.
        </p>
      </div>
    </div>
  );
}
