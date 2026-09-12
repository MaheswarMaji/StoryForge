import { BookOpen, Clock, DollarSign, Film, Layers, Zap } from "lucide-react";
import { Link } from "react-router-dom";
import { usePoll, useChannels, MEDIA } from "@/lib/api";
import { STATUS, statusMeta, jobDuration } from "@/lib/ui";
import { Badge } from "@/components/ui/badge";
import {
  Bar as RBar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from "recharts";

const COLORS = ["#F59E0B", "#3B82F6", "#EF4444"];
const STATUS_ORDER = ["draft", "scripting", "script_ready", "rendering", "in_review", "approved", "edits_requested", "rejected", "failed"];

const StatCard = ({ icon: Icon, label, value, sub, testid, accent = "text-amber-400" }) => (
  <div data-testid={testid} className="card-glow rounded-2xl border border-amber-500/10 bg-[#12141F] p-5 rise">
    <div className="mb-3 flex items-center gap-2 text-xs font-medium uppercase tracking-wider text-slate-400">
      <Icon className={`h-4 w-4 ${accent}`} /> {label}
    </div>
    <div className="font-display text-3xl font-bold text-slate-100">{value}</div>
    {sub && <div className="mt-1 text-xs text-slate-500">{sub}</div>}
  </div>
);

export default function DashboardPage() {
  const [dash] = usePoll("/dashboard", 4000);
  const { channels } = useChannels();
  if (!dash) return <div className="p-10 text-slate-500">Loading factory floor…</div>;

  const funnel = STATUS_ORDER.filter((s) => dash.status_counts?.[s]).map((s) => ({
    status: STATUS[s]?.label || s, count: dash.status_counts[s], key: s,
  }));
  const costPie = [
    { name: "LLM", value: dash.cost?.llm || 0 },
    { name: "TTS Voice", value: dash.cost?.tts || 0 },
    { name: "Image Gen", value: dash.cost?.image || 0 },
  ].filter((d) => d.value > 0);
  const beatData = Object.entries(dash.beat_coverage || {}).map(([k, v]) => ({ beat: k, stories: v }));
  const chName = (id) => channels?.find((c) => c.id === id)?.name || "—";

  return (
    <div className="mx-auto max-w-7xl space-y-8">
      <div>
        <h1 className="font-display text-3xl font-extrabold tracking-tight text-slate-100 lg:text-4xl">Production Dashboard</h1>
        <p className="mt-1 text-sm text-slate-400">Mythology & folk story video factory — live pipeline status, spend and queue health</p>
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard testid="stat-stories" icon={BookOpen} label="Stories in system" value={dash.cost?.n ?? 0} sub="extracted from PDFs" />
        <StatCard testid="stat-videos" icon={Film} label="Videos produced" value={dash.cost?.videos_produced ?? 0} sub="awaiting review or approved" accent="text-emerald-400" />
        <StatCard testid="stat-avg-cost" icon={DollarSign} label="Avg cost / video" value={`$${(dash.cost?.avg_per_video || 0).toFixed(3)}`} sub="LLM + voice + image gen" accent="text-blue-400" />
        <StatCard testid="stat-queue" icon={Zap} label="Queue health" value={`${dash.queue?.active || 0} / ${dash.queue?.depth || 0}`} sub={`${dash.queue?.workers || 2} workers · ${dash.queue?.job_counts?.failed || 0} failed`} accent="text-rose-400" />
      </div>

      <div className="grid gap-6 lg:grid-cols-5">
        <div className="card-glow rounded-2xl border border-amber-500/10 bg-[#12141F] p-6 lg:col-span-3">
          <h3 className="mb-1 font-display text-lg font-semibold text-amber-300">Production Status Funnel</h3>
          <p className="mb-4 text-xs text-slate-500">Stories by pipeline stage</p>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={funnel} margin={{ top: 4, right: 8, left: -18, bottom: 0 }}>
              <CartesianGrid stroke="rgba(148,163,184,0.08)" vertical={false} />
              <XAxis dataKey="status" tick={{ fill: "#94A3B8", fontSize: 10 }} interval={0} angle={-18} dy={8} />
              <YAxis tick={{ fill: "#94A3B8", fontSize: 11 }} allowDecimals={false} />
              <Tooltip cursor={{ fill: "rgba(245,158,11,0.06)" }} contentStyle={{ background: "#1A1D2E", border: "1px solid rgba(245,158,11,0.25)", borderRadius: 12, color: "#F8FAFC" }} />
              <RBar dataKey="count" radius={[6, 6, 0, 0]}>
                {funnel.map((f) => (
                  <Cell key={f.key} fill={f.key === "approved" ? "#10B981" : f.key === "failed" ? "#EF4444" : f.key === "in_review" ? "#A855F7" : "#F59E0B"} />
                ))}
              </RBar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="card-glow rounded-2xl border border-amber-500/10 bg-[#12141F] p-6 lg:col-span-2">
          <h3 className="mb-1 font-display text-lg font-semibold text-amber-300">API Cost Breakdown</h3>
          <p className="mb-4 text-xs text-slate-500">Total spend ${(dash.cost?.total || 0).toFixed(3)}</p>
          {costPie.length ? (
            <ResponsiveContainer width="100%" height={260}>
              <PieChart>
                <Pie data={costPie} dataKey="value" nameKey="name" innerRadius={55} outerRadius={90} paddingAngle={4} stroke="none">
                  {costPie.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Pie>
                <Tooltip contentStyle={{ background: "#1A1D2E", border: "1px solid rgba(245,158,11,0.25)", borderRadius: 12, color: "#F8FAFC" }} formatter={(v) => `$${Number(v).toFixed(3)}`} />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex h-56 items-center justify-center text-sm text-slate-500">No spend yet — produce a video</div>
          )}
          <div className="mt-2 flex justify-center gap-4 text-xs text-slate-400">
            {costPie.map((c, i) => (
              <span key={c.name} className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full" style={{ background: COLORS[i % COLORS.length] }} />{c.name}
              </span>
            ))}
          </div>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-5">
        <div className="card-glow rounded-2xl border border-amber-500/10 bg-[#12141F] p-6 lg:col-span-2">
          <h3 className="mb-1 flex items-center gap-2 font-display text-lg font-semibold text-amber-300"><Layers className="h-4 w-4" /> Beat Coverage</h3>
          <p className="mb-4 text-xs text-slate-500">Stories whose scripts contain each narrative beat</p>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={beatData} layout="vertical" margin={{ top: 0, right: 16, left: 30, bottom: 0 }}>
              <XAxis type="number" hide allowDecimals={false} />
              <YAxis type="category" dataKey="beat" tick={{ fill: "#94A3B8", fontSize: 11, textTransform: "capitalize" }} width={64} />
              <Tooltip cursor={{ fill: "rgba(245,158,11,0.06)" }} contentStyle={{ background: "#1A1D2E", border: "1px solid rgba(245,158,11,0.25)", borderRadius: 12, color: "#F8FAFC" }} />
              <RBar dataKey="stories" fill="#F59E0B" radius={[0, 6, 6, 0]} barSize={16} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="card-glow overflow-hidden rounded-2xl border border-amber-500/10 bg-[#12141F] lg:col-span-3">
          <div className="flex items-center justify-between p-6 pb-3">
            <div>
              <h3 className="font-display text-lg font-semibold text-amber-300">Job Queue</h3>
              <p className="text-xs text-slate-500">Most recent async jobs — OCR, story mining, scripts, rendering</p>
            </div>
            <Clock className="h-4 w-4 text-slate-500" />
          </div>
          <div className="max-h-72 overflow-y-auto px-6 pb-6">
            <table className="w-full text-left text-xs">
              <thead className="text-slate-500">
                <tr className="border-b border-white/5">
                  <th className="py-2 font-medium">Job</th><th className="py-2 font-medium">Status</th><th className="py-2 font-medium">Stage</th><th className="py-2 font-medium">Time</th>
                </tr>
              </thead>
              <tbody data-testid="jobs-table">
                {(dash.jobs || []).map((j) => (
                  <tr key={j.id} data-testid="job-row" className="border-b border-white/5 text-slate-300">
                    <td className="max-w-56 truncate py-2 pr-3 font-mono2 text-[11px] text-amber-200/80">{j.type} · {j.label || j.ref_id?.slice(-6)}</td>
                    <td className="py-2 pr-3">
                      <Badge className={`${j.status === "done" ? "bg-emerald-950 text-emerald-300 border-emerald-700" : j.status === "failed" ? "bg-red-950 text-red-300 border-red-700" : "bg-amber-950 text-amber-300 border-amber-700"} border text-[10px]`}>{j.status}</Badge>
                    </td>
                    <td className="max-w-40 truncate py-2 pr-3 text-slate-400">{j.error ? j.error.slice(0, 60) : j.stage || "—"}</td>
                    <td className="py-2 font-mono2 text-slate-500">{jobDuration(j) !== null ? `${jobDuration(j)}s` : "—"}</td>
                  </tr>
                ))}
                {!(dash.jobs || []).length && <tr><td colSpan={4} className="py-6 text-center text-slate-500">No jobs yet</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div>
        <h3 className="mb-4 font-display text-lg font-semibold text-amber-300">Recent Story Projects</h3>
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {(dash.recent_stories || []).map((s) => (
            <Link to={`/stories/${s.id}`} key={s.id} data-testid="recent-story-card" className="card-glow group overflow-hidden rounded-2xl border border-amber-500/10 bg-[#12141F]">
              <div className="relative h-40 overflow-hidden bg-gradient-to-br from-[#1E1B4B] to-[#451A03]">
                {s.media?.frames?.[0] ? (
                  <img src={`${MEDIA}${s.media.frames[0]}`} alt="" className="h-full w-full object-cover opacity-90 transition-transform duration-500 group-hover:scale-105" />
                ) : (
                  <div className="flex h-full items-center justify-center font-display text-4xl text-amber-500/30">✦</div>
                )}
                <div className="absolute right-2 top-2"><Badge className={`${statusMeta(s.status).cls} border text-[10px]`}>{statusMeta(s.status).label}</Badge></div>
                {s.qa?.score != null && (
                  <div className="absolute bottom-2 left-2 rounded-full bg-black/60 px-2 py-0.5 text-[10px] font-semibold text-emerald-300">QA {Number(s.qa.score).toFixed(1)}/10</div>
                )}
              </div>
              <div className="p-4">
                <div className="truncate font-deva text-sm font-semibold text-slate-100">{s.title_hindi || s.title_english}</div>
                <div className="mt-0.5 truncate text-[11px] text-slate-500">{chName(s.channel_id)} · {s.category}</div>
              </div>
            </Link>
          ))}
          {!(dash.recent_stories || []).length && (
            <div className="col-span-4 rounded-2xl border border-dashed border-white/10 p-10 text-center text-sm text-slate-500">No stories yet — upload a scanned PDF to start the factory</div>
          )}
        </div>
      </div>
    </div>
  );
}
