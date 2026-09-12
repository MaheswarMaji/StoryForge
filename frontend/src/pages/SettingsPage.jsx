import { useState } from "react";
import { Link } from "react-router-dom";
import { CheckCircle2, ExternalLink, Instagram, Loader2, Plug, RefreshCw, ShieldCheck, ShieldAlert, XCircle, Youtube } from "lucide-react";
import { api, usePoll } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";

export default function SettingsPage() {
  const [ig, refreshIg] = usePoll("/settings/instagram", 20000);
  const [creds] = usePoll("/social/credentials", 30000);
  const [routerStatus] = usePoll("/router-status", 30000);
  const [token, setToken] = useState("");
  const [uid, setUid] = useState("");
  const [saving, setSaving] = useState(false);

  const save = async () => {
    if (!token.trim() || !uid.trim()) {
      toast.error("Paste both the access token and the Instagram user ID");
      return;
    }
    setSaving(true);
    try {
      await api.put("/settings/instagram", { access_token: token.trim(), user_id: uid.trim() });
      toast.success("Instagram connected & verified");
      setToken("");
      setUid("");
      refreshIg();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const disconnect = async () => {
    try {
      await api.delete("/settings/instagram");
      toast.success("Instagram disconnected");
      refreshIg();
    } catch {
      toast.error("Disconnect failed");
    }
  };

  return (
    <div className="mx-auto max-w-5xl space-y-8">
      <div>
        <h1 className="font-display text-3xl font-extrabold tracking-tight text-slate-100 lg:text-4xl">Integrations</h1>
        <p className="mt-1 text-sm text-slate-400">Connect publishing destinations and watch the model-router health. Credentials are validated before being saved.</p>
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <div data-testid="instagram-settings-card" className={`card-glow rounded-2xl border p-6 ${ig?.connected && !ig?.error ? "border-fuchsia-500/30 bg-fuchsia-950/10" : "border-amber-500/20 bg-[#12141F]"}`}>
          <div className="flex items-center gap-2">
            <Instagram className="h-5 w-5 text-fuchsia-400" />
            <h3 className="font-display text-lg font-semibold text-slate-100">Instagram Reels</h3>
            {ig?.connected ? (
              ig?.error ? (
                <Badge data-testid="instagram-status-badge" className="border border-orange-500/50 bg-orange-950/50 text-[10px] text-orange-300">token check failed</Badge>
              ) : (
                <Badge data-testid="instagram-status-badge" className="border border-emerald-600/50 bg-emerald-950/60 text-[10px] text-emerald-300">connected{ig?.username ? ` · @${ig.username}` : ""}</Badge>
              )
            ) : (
              <Badge data-testid="instagram-status-badge" variant="outline" className="border-white/15 text-[10px] text-slate-400">not connected</Badge>
            )}
          </div>

          {ig?.connected ? (
            <div className="mt-4 space-y-3 text-xs text-slate-400">
              <div>User ID: <span className="font-mono2 text-slate-200">{ig.user_id}</span> <span className="text-slate-600">({ig.source})</span></div>
              <div>Token: <span className="font-mono2 text-slate-200">{ig.token_hint}</span></div>
              {ig.error && <div className="text-orange-300">{ig.error}</div>}
              <p>Reels publish to this account as soon as a story is approved and you hit “Upload to Instagram Reels”.</p>
              <Button data-testid="instagram-disconnect-button" variant="outline" size="sm" className="border-rose-500/40 text-rose-300 hover:bg-rose-500/10" onClick={disconnect}>
                <XCircle className="mr-1.5 h-3.5 w-3.5" /> Disconnect
              </Button>
            </div>
          ) : (
            <div className="mt-4 space-y-3">
              <p className="text-xs leading-relaxed text-slate-400">
                From a Meta app with <span className="text-slate-200">instagram_business_basic</span> + <span className="text-slate-200">instagram_business_content_publish</span> permissions, generate a <span className="text-slate-200">long-lived access token</span> for your Instagram Professional account and paste it here with the account ID.
              </p>
              <Input data-testid="instagram-token-input" value={token} onChange={(e) => setToken(e.target.value)} placeholder="Long-lived access token" className="border-white/10 bg-black/30 font-mono2 text-xs text-slate-200" />
              <Input data-testid="instagram-userid-input" value={uid} onChange={(e) => setUid(e.target.value)} placeholder="Instagram Professional user ID (e.g. 1784xxxxxxxx)" className="border-white/10 bg-black/30 font-mono2 text-xs text-slate-200" />
              <Button data-testid="instagram-save-button" onClick={save} disabled={saving} className="bg-fuchsia-600 font-semibold text-white hover:bg-fuchsia-500">
                {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Plug className="mr-2 h-4 w-4" />}
                Validate &amp; Connect
              </Button>
            </div>
          )}
        </div>

        <div data-testid="youtube-settings-card" className="card-glow rounded-2xl border border-red-500/20 bg-[#12141F] p-6">
          <div className="flex items-center gap-2">
            <Youtube className="h-5 w-5 text-red-500" />
            <h3 className="font-display text-lg font-semibold text-slate-100">YouTube Shorts</h3>
            <Badge data-testid="youtube-status-badge" className={`border text-[10px] ${creds?.youtube ? "border-emerald-600/50 bg-emerald-950/60 text-emerald-300" : "border-amber-500/40 bg-amber-950/30 text-amber-300"}`}>
              {creds?.youtube ? "connected" : "setup on Engagement page"}
            </Badge>
          </div>
          <p className="mt-4 text-xs leading-relaxed text-slate-400">
            One-time OAuth: add the redirect URI in Google Cloud Console, authorize access, and the refresh token is stored automatically. Shorts upload then works from any approved story.
          </p>
          <Link to="/social">
            <Button data-testid="youtube-manage-link" variant="outline" size="sm" className="mt-4 border-red-500/40 text-red-300 hover:bg-red-500/10">
              <ExternalLink className="mr-1.5 h-3.5 w-3.5" /> Manage connection
            </Button>
          </Link>
        </div>
      </div>

      <div data-testid="router-health-card" className="card-glow rounded-2xl border border-amber-500/10 bg-[#12141F] p-6">
        <div className="mb-4 flex items-center gap-2">
          <ShieldCheck className="h-5 w-5 text-emerald-400" />
          <h3 className="font-display text-lg font-semibold text-amber-300">Model Router Health</h3>
          <Button data-testid="router-refresh-button" variant="outline" size="sm" className="ml-auto border-white/15 text-slate-300" onClick={refreshIg}>
            <RefreshCw className="mr-1.5 h-3.5 w-3.5" /> Refresh
          </Button>
        </div>
        <p className="mb-4 text-xs leading-relaxed text-slate-400">{routerStatus?.notes}</p>
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {Object.entries(routerStatus?.providers || {}).map(([name, p]) => (
            <div key={name} data-testid={`router-provider-${name}`} className="flex items-center justify-between rounded-xl bg-black/30 px-3 py-2 text-xs">
              <span className="font-mono2 text-slate-300">{name}</span>
              <span className="flex items-center gap-1.5 text-[10px] text-slate-500">
                {p.key ? "key ✓" : "no key"}
                <span className={`h-2 w-2 rounded-full ${p.healthy ? "bg-emerald-400" : "bg-rose-500"}`} />
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
