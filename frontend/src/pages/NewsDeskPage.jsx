import { RefreshCw, Newspaper, CheckCircle2, XCircle, ExternalLink } from "lucide-react";
import { Link } from "react-router-dom";
import { api, usePoll } from "@/lib/api";
import { statusMeta } from "@/lib/ui";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

export default function NewsDeskPage() {
  const [items, refresh] = usePoll("/news/items", 6000);

  const fetchNews = async () => {
    try {
      await api.post("/news/fetch");
      toast.success("News fetch queued — RSS scan + policy triage running");
      setTimeout(refresh, 8000);
    } catch { toast.error("Fetch failed"); }
  };

  const approved = (items || []).filter((i) => i.policy?.approved);
  const rejected = (items || []).filter((i) => i.policy && !i.policy.approved);

  return (
    <div className="mx-auto max-w-6xl space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl font-extrabold tracking-tight text-slate-100 lg:text-4xl">Public Interest News Desk</h1>
          <p className="mt-1 max-w-2xl text-sm text-slate-400">Daily Google News scan for climate, disasters, science & tech, institutional reports and economy. The compliance agent independently rejects anything political, sensitive or controversial — every approved item still needs human review before publishing.</p>
        </div>
        <Button data-testid="fetch-news-button" onClick={fetchNews} className="bg-amber-500 font-semibold text-[#090A0F] hover:bg-amber-400">
          <RefreshCw className="mr-2 h-4 w-4" /> Fetch Today's News
        </Button>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 space-y-4">
          <h3 className="font-display text-xl font-semibold text-emerald-300">Approved for scripting ({approved.length})</h3>
          {approved.map((s) => (
            <div key={s.id} data-testid="news-item-approved" className="card-glow rounded-2xl border border-emerald-500/15 bg-[#12141F] p-5">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="font-medium leading-snug text-slate-100">{s.title_hindi || s.title_english}</div>
                  <div className="mt-1 text-[11px] text-slate-500">{s.source}</div>
                  <p className="mt-2 text-xs leading-relaxed text-slate-400">{s.policy?.summary}</p>
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <Badge className={`${statusMeta(s.status).cls} border text-[10px]`}>{statusMeta(s.status).label}</Badge>
                    <Badge variant="outline" className="border-emerald-500/30 text-emerald-300">{s.category}</Badge>
                    {s.source_url && <a href={s.source_url} target="_blank" rel="noreferrer" className="flex items-center gap-1 text-[11px] text-slate-500 underline hover:text-amber-300"><ExternalLink className="h-3 w-3" /> source</a>}
                  </div>
                </div>
                <Link to={`/stories/${s.id}`} className="rounded-xl border border-amber-500/40 px-4 py-2 text-xs font-medium text-amber-300 hover:bg-amber-500/10">Open Studio</Link>
              </div>
            </div>
          ))}
          {!approved.length && <div className="rounded-2xl border border-dashed border-white/10 p-8 text-center text-sm text-slate-500">No approved items yet — fetch today's news</div>}
        </div>

        <div className="space-y-3">
          <h3 className="font-display text-xl font-semibold text-rose-300">Blocked by policy ({rejected.length})</h3>
          {rejected.map((s) => (
            <div key={s.id} data-testid="news-item-rejected" className="rounded-xl border border-rose-500/15 bg-rose-950/10 p-4">
              <div className="flex gap-2 text-xs text-slate-300"><XCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-rose-400" />
                <div>
                  <div className="line-clamp-2">{s.title_english}</div>
                  <div className="mt-1 text-[10px] text-rose-300/80">{s.policy?.reason || "policy"}</div>
                </div>
              </div>
            </div>
          ))}
          {!rejected.length && <div className="text-xs text-slate-500">Nothing blocked yet</div>}
        </div>
      </div>
    </div>
  );
}
