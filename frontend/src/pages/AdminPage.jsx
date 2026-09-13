import { useState } from "react";
import { api, usePoll } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  BarChart3, DollarSign, ExternalLink, Eye, MessageSquare, Radio, RefreshCw,
  ThumbsUp, Timer, TrendingUp, Users, Youtube,
} from "lucide-react";
import { toast } from "sonner";

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
const dur = (s) => (s ? `${Math.floor(s / 60)}m ${Math.round(s % 60)}s` : "—");

export default function AdminPage() {
  const [data, refresh] = usePoll("/admin/overview", 15000);
  const [live, liveErr] = usePoll("/admin/youtube/live", 60000);
  const [forcing, setForcing] = useState(false);
  const t = data?.totals || {};

  const forceLive = async () => {
    setForcing(true);
    try {
      await api.get("/admin/youtube/live?refresh=1");
      await refresh();
      toast.success("Live analytics refreshed from YouTube");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Refresh failed");
    } finally {
      setForcing(false);
    }
  };

  const reconnectYouTube = async () => {
    try {
      const r = await api.get("/social/youtube/auth-url");
      window.open(r.data.auth_url, "_blank");
      toast.info("Complete the Google consent — it now grants watch-time analytics too");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "OAuth setup missing");
    }
  };

  const a = live?.analytics || {};
  const trend = (a.trend || []).slice(-14);
  const trendMax = Math.max(1, ...trend.map((d) => d.views || 0));

  return (
    <div className="mx-auto max-w-7xl space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl font-extrabold tracking-tight text-slate-100 lg:text-4xl">Admin Console</h1>
          <p className="mt-1 text-sm text-slate-400">Every account, channel, published video and its live performance — views, engagement, estimated revenue and API spend.</p>
        </div>
        <button data-testid="admin-refresh-button" onClick={refresh} className="rounded-full border border-white/10 bg-[#12141F] px-4 py-2 text-xs text-slate-300 hover:bg-white/5">Refresh</button>
      </div>

      {/* ---------- Live YouTube Analytics ---------- */}
      <div data-testid="yt-live-card" className="card-glow space-y-5 rounded-2xl border border-red-500/15 bg-[#12141F] p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <Youtube className="h-6 w-6 text-red-500" />
            <div>
              <h2 className="font-display text-lg font-semibold text-slate-100">Live YouTube Analytics</h2>
              <p className="text-xs text-slate-500">
                {live?.channel?.title
                  ? `${live.channel.title} · ${num(live.channel.subscribers)} subscribers · ${num(live.channel.total_views)} lifetime views`
                  : "Connect your channel to stream real performance data"}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {live?.fetched_at && (
              <span data-testid="yt-live-updated" className="text-[11px] text-slate-500">
                {live.cached ? "cached" : "live"} · {new Date(live.fetched_at).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })}
              </span>
            )}
            <Button data-testid="yt-live-refresh-button" size="sm" variant="outline" disabled={forcing}
              onClick={forceLive} className="border-white/10 bg-black/30 text-xs text-slate-300 hover:bg-white/5">
              <RefreshCw className={`mr-1.5 h-3.5 w-3.5 ${forcing ? "animate-spin" : ""}`} /> Fetch now
            </Button>
          </div>
        </div>

        {liveErr && (
          <div data-testid="yt-live-connect-note" className="rounded-xl border border-amber-500/25 bg-amber-950/20 px-4 py-3 text-xs text-amber-200/90">
            {liveErr?.response?.status === 400
              ? "YouTube isn't connected yet — connect the channel in Settings → Integrations, then live views, watch time and subscriber data appear here."
              : "Live analytics temporarily unavailable (quota or connection) — retry with Fetch now."}
          </div>
        )}

        {live && !liveErr && (
          <>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
              <Stat testid="yt-live-views-28d" icon={Eye} label="Views (28 days)" value={num(a.views_28d)} />
              <Stat testid="yt-live-watch-28d" icon={Timer} label="Watch time (28d)" value={dur((a.watch_minutes_28d || 0) * 60)} />
              <Stat testid="yt-live-avg-duration" icon={Radio} label="Avg view duration" value={dur(a.avg_view_duration_sec)} />
              <Stat testid="yt-live-subs-gained" icon={Users} label={`Subs gained (${a.days || 28}d)`} value={`+${num(a.subs_gained_28d)} / −${num(a.subs_lost_28d)}`} />
              <Stat testid="yt-live-est-revenue" icon={DollarSign} label="Est. revenue (28d)" value={`$${(((a.views_28d || 0) / 1000) * (live.rpm_used || 0.05)).toFixed(2)}`} />
            </div>

            {a.scope_ok === false && (
              <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-blue-500/20 bg-blue-950/10 px-4 py-3 text-xs text-slate-400">
                <span data-testid="yt-live-scope-note">
                  {a.note
                    ? "Watch-time analytics need the extra Analytics permission — reconnect the channel (one Google consent, everything else stays connected)."
                    : "Basic live stats are on. Reconnect once to unlock watch time & retention metrics."}
                </span>
                <Button size="sm" variant="outline" onClick={reconnectYouTube} className="border-amber-500/40 bg-amber-500/10 text-xs text-amber-300 hover:bg-amber-500/20">
                  Reconnect YouTube
                </Button>
              </div>
            )}

            {trend.length > 1 && (
              <div data-testid="yt-live-trend" className="flex h-24 items-end gap-1.5 rounded-xl border border-white/5 bg-black/20 px-4 py-3">
                {trend.map((d) => (
                  <div key={d.date} className="group relative flex-1" title={`${d.date}: ${num(d.views)} views`}>
                    <div className="w-full rounded-t bg-gradient-to-t from-red-900/70 to-red-500 transition-all group-hover:from-red-700 group-hover:to-red-400"
                      style={{ height: `${Math.max(4, ((d.views || 0) / trendMax) * 72)}px` }} />
                  </div>
                ))}
              </div>
            )}

            <div className="overflow-hidden rounded-xl border border-white/5">
              <table className="w-full text-left text-sm">
                <thead className="bg-black/30 text-xs uppercase tracking-wider text-slate-500">
                  <tr>
                    <th className="px-4 py-2.5 font-medium">Recent upload</th>
                    <th className="px-3 py-2.5 font-medium">Published</th>
                    <th className="px-3 py-2.5 font-medium">Views</th>
                    <th className="px-3 py-2.5 font-medium">Likes</th>
                    <th className="px-3 py-2.5 font-medium">Comments</th>
                  </tr>
                </thead>
                <tbody>
                  {(live.videos || []).slice(0, 10).map((v) => (
                    <tr key={v.video_id} data-testid="yt-live-video-row" className="border-t border-white/5">
                      <td className="max-w-md px-4 py-2.5">
                        <a href={`https://www.youtube.com/shorts/${v.video_id}`} target="_blank" rel="noreferrer" className="flex items-center gap-1.5 text-slate-200 hover:text-amber-300">
                          {v.title || v.video_id} <ExternalLink className="h-3 w-3 shrink-0" />
                        </a>
                      </td>
                      <td className="px-3 py-2.5 text-[11px] text-slate-500">{v.published_at}</td>
                      <td className="px-3 py-2.5 font-mono2 text-slate-300">{num(v.views)}</td>
                      <td className="px-3 py-2.5 font-mono2 text-slate-300">{num(v.likes)}</td>
                      <td className="px-3 py-2.5 font-mono2 text-slate-300">{num(v.comments)}</td>
                    </tr>
                  ))}
                  {!(live.videos || []).length && (
                    <tr><td colSpan={5} className="px-4 py-6 text-center text-sm text-slate-500">No uploads found on the channel yet.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat testid="admin-stat-accounts" icon={Users} label="Accounts" value={num(t.accounts)} />
        <Stat testid="admin-stat-videos" icon={Youtube} label="Videos Published" value={num(t.videos_published)} />
        <Stat testid="admin-stat-views" icon={Eye} label="Total Views" value={num(t.views)} />
        <Stat testid="admin-stat-subs" icon={Radio} label="Subscribers" value={num(t.subscribers)} />
        <Stat testid="admin-stat-revenue" icon={DollarSign} label="Est. Revenue" value={`$${(t.est_revenue || 0).toFixed(2)}`} />
        <Stat testid="admin-stat-cost" icon={BarChart3} label="API Spend" value={`$${(t.api_cost || 0).toFixed(2)}`} />
        <Stat testid="admin-stat-likes" icon={ThumbsUp} label="Likes" value={num(t.likes)} />
        <Stat testid="admin-stat-trend" icon={TrendingUp} label="Views (28d, live)" value={num(a.views_28d)} />
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
