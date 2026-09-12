import { BarChart3, DollarSign, Eye, ExternalLink, MessageSquare, Radio, ThumbsUp, Users, Youtube } from "lucide-react";
import { usePoll } from "@/lib/api";
import { Badge } from "@/components/ui/badge";

function Stat({ icon: Icon, label, value, testid }) {
  return (
    <div data-testid={testid} className="card-glow rounded-2xl border border-amber-500/10 bg-[#12141F] p-5">
      <div className="flex items-center gap-2 text-xs uppercase tracking-wider text-slate-500">
        <Icon className="h-4 w-4 text-amber-400" /> {label}
      </div>
      <div className="mt-2 font-display text-2xl font-bold text-slate-100">{value}</div>
    </div>
  );
}

const num = (n) => (n || 0).toLocaleString("en-IN");

export default function AdminPage() {
  const [data, refresh] = usePoll("/admin/overview", 15000);
  const t = data?.totals || {};

  return (
    <div className="mx-auto max-w-7xl space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl font-extrabold tracking-tight text-slate-100 lg:text-4xl">Admin Console</h1>
          <p className="mt-1 text-sm text-slate-400">Every account, channel, published video and its live performance — views, engagement, estimated revenue and API spend.</p>
        </div>
        <button data-testid="admin-refresh-button" onClick={refresh} className="rounded-full border border-white/10 bg-[#12141F] px-4 py-2 text-xs text-slate-300 hover:bg-white/5">Refresh</button>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat testid="admin-stat-accounts" icon={Users} label="Accounts" value={num(t.accounts)} />
        <Stat testid="admin-stat-videos" icon={Youtube} label="Videos Published" value={num(t.videos_published)} />
        <Stat testid="admin-stat-views" icon={Eye} label="Total Views" value={num(t.views)} />
        <Stat testid="admin-stat-subs" icon={Radio} label="Subscribers" value={num(t.subscribers)} />
        <Stat testid="admin-stat-revenue" icon={DollarSign} label="Est. Revenue" value={`$${(t.est_revenue || 0).toFixed(2)}`} />
        <Stat testid="admin-stat-cost" icon={BarChart3} label="API Spend" value={`$${(t.api_cost || 0).toFixed(2)}`} />
        <Stat testid="admin-stat-likes" icon={ThumbsUp} label="Likes" value={num(t.likes)} />
        <Stat testid="admin-stat-comments" icon={MessageSquare} label="Comments" value={num(t.comments)} />
      </div>

      {data?.notes && <div className="rounded-xl border border-blue-500/20 bg-blue-950/10 px-4 py-3 text-xs text-slate-400">{data.notes}</div>}

      <div className="card-glow overflow-hidden rounded-2xl border border-amber-500/10 bg-[#12141F]">
        <div className="border-b border-white/5 px-6 py-4 font-display text-lg font-semibold text-amber-300">Video Performance</div>
        <div data-testid="admin-videos-table" className="max-h-[420px] overflow-y-auto">
          <table className="w-full text-left text-sm">
            <thead className="sticky top-0 bg-[#12141F] text-xs uppercase tracking-wider text-slate-500">
              <tr>
                <th className="px-6 py-3 font-medium">Video</th>
                <th className="px-4 py-3 font-medium">Platform</th>
                <th className="px-4 py-3 font-medium">Views</th>
                <th className="px-4 py-3 font-medium">Likes</th>
                <th className="px-4 py-3 font-medium">Comments</th>
                <th className="px-4 py-3 font-medium">API Cost</th>
              </tr>
            </thead>
            <tbody>
              {(data?.videos || []).map((v) => (
                <tr key={v.id} data-testid="admin-video-row" className="border-b border-white/5">
                  <td className="max-w-md px-6 py-3 text-slate-200">
                    {v.url ? <a href={v.url} target="_blank" rel="noreferrer" className="flex items-center gap-1.5 hover:text-amber-300">{v.title} <ExternalLink className="h-3 w-3" /></a> : v.title}
                  </td>
                  <td className="px-4 py-3"><Badge variant="outline" className="border-white/15 text-[10px] capitalize text-slate-400">{v.platform || "—"}</Badge></td>
                  <td className="px-4 py-3 font-mono2 text-slate-300">{num(v.views)}</td>
                  <td className="px-4 py-3 font-mono2 text-slate-300">{num(v.likes)}</td>
                  <td className="px-4 py-3 font-mono2 text-slate-300">{num(v.comments)}</td>
                  <td className="px-4 py-3 font-mono2 text-amber-300">${(v.cost || 0).toFixed(2)}</td>
                </tr>
              ))}
              {!(data?.videos || []).length && (
                <tr><td colSpan={6} className="px-6 py-10 text-center text-sm text-slate-500">No published videos yet — approve a story and hit Upload to YouTube/Instagram.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <div className="card-glow overflow-hidden rounded-2xl border border-amber-500/10 bg-[#12141F]">
          <div className="border-b border-white/5 px-6 py-4 font-display text-lg font-semibold text-amber-300">Accounts</div>
          <div data-testid="admin-accounts-table" className="max-h-[360px] overflow-y-auto">
            <table className="w-full text-left text-sm">
              <thead className="sticky top-0 bg-[#12141F] text-xs uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="px-6 py-3 font-medium">User</th>
                  <th className="px-4 py-3 font-medium">Role</th>
                  <th className="px-4 py-3 font-medium">Stories</th>
                  <th className="px-4 py-3 font-medium">Joined</th>
                </tr>
              </thead>
              <tbody>
                {(data?.accounts || []).map((u) => (
                  <tr key={u.user_id} data-testid="admin-account-row" className="border-b border-white/5">
                    <td className="max-w-xs px-6 py-3">
                      <div className="text-xs font-semibold text-slate-200">{u.name || "—"}</div>
                      <div className="text-[11px] text-slate-500">{u.email}</div>
                    </td>
                    <td className="px-4 py-3"><Badge className={`border text-[10px] ${u.role === "admin" ? "border-amber-600/50 bg-amber-950/50 text-amber-300" : "border-white/15 text-slate-400"}`}>{u.role}</Badge></td>
                    <td className="px-4 py-3 font-mono2 text-slate-300">{u.stories}</td>
                    <td className="px-4 py-3 text-[11px] text-slate-500">{u.created_at?.slice(0, 10)}</td>
                  </tr>
                ))}
                {!(data?.accounts || []).length && <tr><td colSpan={4} className="px-6 py-10 text-center text-sm text-slate-500">No accounts yet</td></tr>}
              </tbody>
            </table>
          </div>
        </div>

        <div className="card-glow overflow-hidden rounded-2xl border border-amber-500/10 bg-[#12141F]">
          <div className="border-b border-white/5 px-6 py-4 font-display text-lg font-semibold text-amber-300">Channels</div>
          <div data-testid="admin-channels-table" className="max-h-[360px] overflow-y-auto">
            <table className="w-full text-left text-sm">
              <thead className="sticky top-0 bg-[#12141F] text-xs uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="px-6 py-3 font-medium">Channel</th>
                  <th className="px-4 py-3 font-medium">Language</th>
                  <th className="px-4 py-3 font-medium">Stories</th>
                  <th className="px-4 py-3 font-medium">Published</th>
                </tr>
              </thead>
              <tbody>
                {(data?.channels || []).map((c) => (
                  <tr key={c.id} data-testid="admin-channel-row" className="border-b border-white/5">
                    <td className="px-6 py-3 text-xs font-semibold text-slate-200">{c.name}</td>
                    <td className="px-4 py-3 text-xs uppercase text-slate-400">{c.language}</td>
                    <td className="px-4 py-3 font-mono2 text-slate-300">{c.stories}</td>
                    <td className="px-4 py-3 font-mono2 text-emerald-300">{c.published}</td>
                  </tr>
                ))}
                {!(data?.channels || []).length && <tr><td colSpan={4} className="px-6 py-10 text-center text-sm text-slate-500">No channels</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
