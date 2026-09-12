import { useState } from "react";
import { Link } from "react-router-dom";
import { Layers, Sparkles, Wand2 } from "lucide-react";
import { api, usePoll, useChannels } from "@/lib/api";
import { STATUS, statusMeta } from "@/lib/ui";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";

export default function LibraryPage() {
  const { channels, selected } = useChannels();
  const [status, setStatus] = useState("all");
  const [checked, setChecked] = useState({});
  const [busy, setBusy] = useState(false);
  const [data, refresh] = usePoll(`/stories${selected !== "all" ? `?channel_id=${selected}` : ""}`, 4000);
  const stories = (data || []).filter((s) => status === "all" || s.status === status);
  const chName = (id) => channels?.find((c) => c.id === id)?.name || "—";

  const selectedIds = Object.entries(checked).filter(([, v]) => v).map(([k]) => k);
  const scriptReadySelected = selectedIds.filter((id) => {
    const s = (data || []).find((x) => x.id === id);
    return s && s.status === "script_ready";
  });

  const produceSelected = async () => {
    if (!scriptReadySelected.length) return toast.error("Select script-ready stories to produce");
    setBusy(true);
    try {
      const r = await api.post("/stories/batch-produce", { ids: scriptReadySelected });
      toast.success(`${r.data.queued} videos queued for production`);
      setChecked({});
      refresh();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); } finally { setBusy(false); }
  };

  const scriptAll = async () => {
    const bookIds = [...new Set((data || []).filter((s) => s.status === "draft").map((s) => s.book_id))];
    if (!bookIds.length) return toast.error("No draft stories need scripts");
    setBusy(true);
    try {
      let n = 0;
      for (const bid of bookIds) {
        const r = await api.post(`/books/${bid}/script-all`);
        n += r.data.queued;
      }
      toast.success(`${n} scripts queued — they will process at the API's pace`);
      refresh();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); } finally { setBusy(false); }
  };

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl font-extrabold tracking-tight text-slate-100 lg:text-4xl">Books & Story Library</h1>
          <p className="mt-1 text-sm text-slate-400">All stories extracted from your PDFs — scripts generate automatically; you choose which stories go to video production</p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Select value={status} onValueChange={setStatus}>
            <SelectTrigger data-testid="library-status-filter" className="w-48 border-amber-500/25 bg-[#12141F] text-slate-200"><SelectValue /></SelectTrigger>
            <SelectContent className="border-amber-500/20 bg-[#12141F]">
              <SelectItem value="all">All statuses</SelectItem>
              {Object.entries(STATUS).map(([k, v]) => <SelectItem key={k} value={k}>{v.label}</SelectItem>)}
            </SelectContent>
          </Select>
          <Button data-testid="generate-all-scripts-button" variant="outline" disabled={busy} onClick={scriptAll} className="border-amber-500/40 text-amber-300 hover:bg-amber-500/10">
            <Wand2 className="mr-2 h-4 w-4" /> Generate Scripts (All Drafts)
          </Button>
          <Button data-testid="produce-selected-button" onClick={produceSelected} disabled={busy || !scriptReadySelected.length} className="bg-emerald-500 font-semibold text-[#090A0F] hover:bg-emerald-400">
            <Sparkles className="mr-2 h-4 w-4" /> Produce Selected ({scriptReadySelected.length})
          </Button>
        </div>
      </div>

      <div className="card-glow overflow-hidden rounded-2xl border border-amber-500/10 bg-[#12141F]">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-white/5 text-xs uppercase tracking-wider text-slate-500">
            <tr>
              <th className="px-4 py-4 w-10"><Layers className="h-4 w-4 text-slate-500" /></th>
              <th className="px-4 py-4 font-medium">Story</th>
              <th className="px-4 py-4 font-medium">Channel</th>
              <th className="px-4 py-4 font-medium">Category</th>
              <th className="px-4 py-4 font-medium">Status</th>
              <th className="px-4 py-4 font-medium">QA</th>
              <th className="px-4 py-4 font-medium">Cost</th>
              <th className="px-4 py-4 font-medium">Pages</th>
            </tr>
          </thead>
          <tbody>
            {stories.map((s) => (
              <tr key={s.id} data-testid="story-row" className="border-b border-white/5 transition-colors hover:bg-amber-500/5">
                <td className="px-4 py-4">
                  <Checkbox
                    data-testid={`story-select-${s.id}`}
                    checked={!!checked[s.id]}
                    disabled={!["script_ready", "edits_requested", "rejected"].includes(s.status)}
                    onCheckedChange={(v) => setChecked({ ...checked, [s.id]: !!v })}
                  />
                </td>
                <td className="max-w-72 px-4 py-4">
                  <Link to={`/stories/${s.id}`} className="block truncate font-deva font-semibold text-amber-200 hover:underline">{s.title_hindi || s.title_english}</Link>
                  <div className="truncate text-[11px] text-slate-500">{s.title_english}</div>
                </td>
                <td className="px-4 py-4 text-xs text-slate-400">{chName(s.channel_id)}</td>
                <td className="px-4 py-4 text-xs text-slate-400">{s.category}</td>
                <td className="px-4 py-4"><Badge data-testid="story-status-badge" className={`${statusMeta(s.status).cls} border text-[10px]`}>{statusMeta(s.status).label}</Badge></td>
                <td className="px-4 py-4 font-mono2 text-xs text-slate-400">{s.qa?.score != null ? `${Number(s.qa.score).toFixed(1)}/10` : "—"}</td>
                <td className="px-4 py-4 font-mono2 text-xs text-slate-400">${(s.cost?.total || 0).toFixed(3)}</td>
                <td className="px-4 py-4 font-mono2 text-xs text-slate-500">{s.page_start ? `${s.page_start}–${s.page_end}` : "—"}</td>
              </tr>
            ))}
            {!stories.length && (
              <tr><td colSpan={8} className="px-6 py-12 text-center text-sm text-slate-500">No stories match this filter yet</td></tr>
            )}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-slate-500">Only script-ready stories can be selected for production — drafts and scripting stories process automatically.</p>
    </div>
  );
}
