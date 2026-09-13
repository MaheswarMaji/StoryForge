import { useEffect, useState } from "react";
import { LayoutDashboard, UploadCloud, BookOpen, Video, Sliders, Flame, Activity, DollarSign, Newspaper, Radio, Plug, LogOut, Users, Clapperboard } from "lucide-react";
import { NavLink, Outlet, useNavigate, Link } from "react-router-dom";
import { api, useChannels, usePoll } from "@/lib/api";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const NAV = [
  { to: "/dashboard", label: "Production Dashboard", icon: LayoutDashboard, id: "nav-dashboard-link" },
  { to: "/upload", label: "PDF Upload & OCR", icon: UploadCloud, id: "nav-upload-link" },
  { to: "/create", label: "Create from Script", icon: Clapperboard, id: "nav-create-link" },
  { to: "/stories", label: "Books & Story Library", icon: BookOpen, id: "nav-stories-link" },
  { to: "/news", label: "News Desk", icon: Newspaper, id: "nav-news-link" },
  { to: "/social", label: "Engagement Agent", icon: Radio, id: "nav-social-link" },
  { to: "/channels", label: "Channels", icon: Sliders, id: "nav-channels-link" },
  { to: "/settings", label: "Integrations", icon: Plug, id: "nav-integrations-link" },
];

export default function Layout() {  const { channels, selected, setSelected } = useChannels();
  const [dash] = usePoll("/dashboard", 6000);
  const [user, setUser] = useState(null);
  const navigate = useNavigate();
  const queue = dash?.queue || {};

  useEffect(() => {
    api.get("/auth/me").then((r) => setUser(r.data)).catch(() => {});
  }, []);

  const logout = async () => {
    try { await api.post("/auth/logout"); } catch {}
    window.location.href = "/login";
  };

  const nav = user?.is_admin
    ? [...NAV, { to: "/admin", label: "Admin Console", icon: Users, id: "nav-admin-link" }]
    : NAV;

  return (
    <div className="grain flex min-h-screen" style={{ background: "#090A0F" }}>
      <aside className="hidden lg:flex fixed inset-y-0 left-0 z-20 w-64 flex-col border-r border-amber-500/10 bg-[#0B0D16]/90 px-5 py-7 backdrop-blur-xl">
        <div className="mb-10 flex items-center gap-3 px-2">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-500/15 ring-1 ring-amber-500/40">
            <Flame className="h-5 w-5 text-amber-400" />
          </div>
          <div>
            <div className="font-display text-xl font-bold tracking-tight text-amber-100">StoryForge</div>
            <div className="text-[10px] uppercase tracking-[0.22em] text-slate-500">Myth Video Factory</div>
          </div>
        </div>

        <nav className="flex flex-1 flex-col gap-1.5">
          {nav.map(({ to, label, icon: Icon, id }) => (
            <NavLink
              key={to}
              to={to}
              data-testid={id}
              className={({ isActive }) =>
                `group flex items-center gap-3 rounded-xl px-3.5 py-2.5 text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-amber-500/10 text-amber-300 shadow-[inset_0_0_0_1px_rgba(245,158,11,0.25)]"
                    : "text-slate-400 hover:bg-white/5 hover:text-slate-200"
                }`
              }
            >
              <Icon className="h-4 w-4" />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="rounded-xl border border-white/5 bg-[#12141F] p-4 text-xs">
          <div className="mb-2 flex items-center gap-2 text-slate-400">
            <Activity className="h-3.5 w-3.5 text-emerald-400" />
            Job Queue Health
          </div>
          <div className="flex items-center justify-between text-slate-300">
            <span data-testid="queue-health-pill" className="font-mono2">
              {queue.active || 0} active · {queue.depth || 0} queued
            </span>
            <span className={`h-2 w-2 rounded-full ${(queue.active || 0) > 0 ? "bg-amber-400 pulse-amber" : "bg-emerald-400"}`} />
          </div>
          <div className="mt-2 text-[10px] text-slate-500">{queue.workers || 2} workers online</div>
        </div>
      </aside>

      <div className="flex min-h-screen min-w-0 flex-1 flex-col lg:ml-64">
        <nav className="glass sticky top-0 z-30 flex items-center justify-between gap-1 border-b border-amber-500/10 px-3 py-2 lg:hidden">
          {nav.map(({ to, icon: Icon, id }) => (
            <NavLink key={to} to={to} data-testid={id} className={({ isActive }) => `rounded-lg p-2 ${isActive ? "bg-amber-500/15 text-amber-300" : "text-slate-400"}`}>
              <Icon className="h-5 w-5" />
            </NavLink>
          ))}
        </nav>
        <header className="glass sticky top-[52px] lg:top-0 z-10 flex flex-wrap items-center justify-between gap-3 border-b border-amber-500/10 px-4 py-4 lg:px-8">
          <Select value={selected} onValueChange={setSelected}>
            <SelectTrigger data-testid="channel-select-dropdown" className="w-44 sm:w-72 border-amber-500/25 bg-[#12141F] text-slate-200">
              <Video className="mr-2 h-4 w-4 shrink-0 text-amber-400" />
              <SelectValue placeholder="All channels" />
            </SelectTrigger>
            <SelectContent className="border-amber-500/20 bg-[#12141F]">
              <SelectItem value="all">All Channels</SelectItem>
              {(channels || []).map((c) => (
                <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>

          <div className="flex items-center gap-3">
            <div data-testid="api-cost-pill" className="flex shrink-0 items-center gap-2 rounded-full border border-amber-500/25 bg-amber-500/10 px-3 py-1.5 text-sm text-amber-300 sm:px-4">
              <DollarSign className="h-4 w-4" />
              <span className="font-mono2">{(dash?.cost?.total || 0).toFixed(2)}</span>
              <span className="hidden text-amber-500/70 sm:inline">API spend</span>
            </div>
            {user ? (
              <div data-testid="user-chip" className="hidden items-center gap-2 rounded-full border border-white/10 bg-[#12141F] py-1 pl-1 pr-3 md:flex">
                {user.picture && <img src={user.picture} alt="" className="h-6 w-6 rounded-full" referrerPolicy="no-referrer" />}
                <span className="max-w-28 truncate text-xs text-slate-300">{user.name || user.email}</span>
              </div>
            ) : (
              <Link
                data-testid="signin-chip"
                to="/login"
                className="flex shrink-0 items-center gap-2 rounded-full border border-white/10 bg-[#12141F] px-4 py-1.5 text-xs font-semibold text-slate-200 transition-colors hover:border-amber-500/40 hover:text-amber-300"
              >
                Sign in
              </Link>
            )}
            <button
              data-testid="logout-button"
              onClick={logout}
              title="Sign out"
              className="rounded-full border border-white/10 bg-[#12141F] p-2 text-slate-400 transition-colors hover:text-rose-300"
            >
              <LogOut className="h-4 w-4" />
            </button>
            <button
              data-testid="header-upload-button"
              onClick={() => navigate("/upload")}
              className="rounded-full bg-amber-500 px-4 py-1.5 text-sm font-semibold text-[#090A0F] transition-colors hover:bg-amber-400"
            >
              Upload PDF
            </button>
          </div>
        </header>

        <main className="relative z-10 flex-1 overflow-x-hidden px-4 py-8 sm:px-6 lg:px-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
