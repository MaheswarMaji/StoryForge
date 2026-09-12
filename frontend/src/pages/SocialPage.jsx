import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Radio, RefreshCw, Send, ShieldAlert, ShieldCheck, MessageSquare, Bot, CheckCircle2 } from "lucide-react";
import { api, usePoll } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";

function YouTubeConnect() {
  const [info, setInfo] = useState(null);
  useEffect(() => {
    api.get("/social/youtube/auth-url").then((r) => setInfo(r.data)).catch(() => {});
  }, []);
  if (!info) return null;
  return (
    <div data-testid="youtube-connect-card" className="rounded-2xl border border-cyan-500/25 bg-cyan-950/15 p-5">
      <div className="font-display text-lg font-semibold text-cyan-200">Connect YouTube (one-time OAuth)</div>
      <p className="mt-1 text-xs text-slate-400">
        1. Add this redirect URI in Google Cloud Console → Credentials → your OAuth client:
        <code className="ml-1 rounded bg-black/40 px-2 py-0.5 font-mono2 text-[11px] text-amber-300">{info.redirect_uri}</code>
      </p>
      <a data-testid="youtube-oauth-link" href={info.auth_url} className="mt-3 inline-block rounded-xl bg-cyan-500 px-4 py-2 text-sm font-semibold text-[#090A0F] hover:bg-cyan-400">
        Authorize YouTube Access →
      </a>
      <p className="mt-2 text-[11px] text-slate-500">The refresh token is saved to backend/.env automatically after consent — then direct Shorts upload works from any approved story.</p>
    </div>
  );
}

export default function SocialPage() {
  const [creds] = usePoll("/social/credentials", 30000);
  const [comments, refresh] = usePoll("/social/comments", 6000);
  const [syncing, setSyncing] = useState(false);
  const [replyFor, setReplyFor] = useState(null);
  const [replyText, setReplyText] = useState("");
  const syncOnce = useRef(false);

  const sync = async () => {
    setSyncing(true);
    try {
      await api.post("/social/engagement/sync");
      toast.success("Sync queued — the agent will triage comments and prepare drafts for your approval");
      setTimeout(refresh, 4000);
    } catch { toast.error("Sync failed"); } finally { setSyncing(false); }
  };

  const postDraft = async (commentId, text) => {
    try {
      await api.post(`/social/comments/${commentId}/reply`, { text });
      toast.success("Reply posted");
      refresh();
    } catch (e) { toast.error(e?.response?.data?.detail || "Reply failed"); }
  };

  const sendReply = async (commentId) => {
    try {
      await api.post(`/social/comments/${commentId}/reply`, { text: replyText });
      toast.success("Reply posted");
      setReplyFor(null); setReplyText("");
      refresh();
    } catch (e) { toast.error(e?.response?.data?.detail || "Reply failed"); }
  };

const CredCard = ({ name, label, ok, hint }) => (
  <div data-testid={`social-cred-${name}`} className={`rounded-2xl border p-5 ${ok ? "border-emerald-500/30 bg-emerald-950/20" : "border-amber-500/25 bg-amber-950/10"}`}>
    <div className="flex items-center gap-2 font-display text-lg font-semibold text-slate-100">
      {ok ? <ShieldCheck className="h-5 w-5 text-emerald-400" /> : <ShieldAlert className="h-5 w-5 text-amber-400" />}
      {label}
    </div>
    <p className="mt-1 text-xs text-slate-400">{ok ? "Connected — publishing and comment monitoring active" : hint}</p>
  </div>
);

  return (
    <div className="mx-auto max-w-6xl space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl font-extrabold tracking-tight text-slate-100 lg:text-4xl">Engagement Agent</h1>
          <p className="mt-1 text-sm text-slate-400">Monitors comments on published videos and drafts short replies only where genuinely needed (questions, corrections, issues). <span className="text-amber-300">Draft-only:</span> nothing is posted until you approve it below.</p>
        </div>
        <Button data-testid="sync-comments-button" onClick={sync} disabled={syncing} className="bg-amber-500 font-semibold text-[#090A0F] hover:bg-amber-400">
          <RefreshCw className={`mr-2 h-4 w-4 ${syncing ? "animate-spin" : ""}`} /> Sync Comments Now
        </Button>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <CredCard name="youtube" label="YouTube" ok={!!creds?.youtube} hint="Add YOUTUBE_CLIENT_ID/SECRET to backend/.env, then connect below (needs the redirect URI whitelisted in Google Cloud Console)" />
        <CredCard name="instagram" label="Instagram" ok={!!creds?.instagram} hint="Not connected — open Integrations (Settings) and paste a long-lived access token + Instagram user ID" />
      </div>

      {creds?.youtube_oauth_setup && !creds?.youtube && <YouTubeConnect />}

      <div className="card-glow overflow-hidden rounded-2xl border border-amber-500/10 bg-[#12141F]">
        <div className="flex items-center gap-2 border-b border-white/5 px-6 py-4">
          <MessageSquare className="h-4 w-4 text-amber-400" />
          <h3 className="font-display text-lg font-semibold text-amber-300">Comment Triage Log</h3>
          <span className="ml-auto text-xs text-slate-500">{(comments || []).length} tracked</span>
        </div>
        <div data-testid="comments-table" className="max-h-[560px] overflow-y-auto">
          <table className="w-full text-left text-sm">
            <thead className="sticky top-0 bg-[#12141F] text-xs uppercase tracking-wider text-slate-500">
              <tr>
                <th className="px-6 py-3 font-medium">Comment</th>
                <th className="px-4 py-3 font-medium">Platform</th>
                <th className="px-4 py-3 font-medium">Agent decision</th>
                <th className="px-4 py-3 font-medium">Reply</th>
              </tr>
            </thead>
            <tbody>
              {(comments || []).map((c) => (
                <tr key={c.id} data-testid="comment-row" className="border-b border-white/5 align-top">
                  <td className="max-w-md px-6 py-3">
                    <div className="text-xs font-semibold text-amber-200">{c.author}</div>
                    <div className="mt-0.5 text-xs text-slate-300">{c.text}</div>
                  </td>
                  <td className="px-4 py-3 text-xs capitalize text-slate-400">{c.platform}</td>
                  <td className="px-4 py-3">
                    <Badge className={`border text-[10px] ${c.triage?.needs_reply ? "bg-emerald-950 text-emerald-300 border-emerald-700" : c.triage?.action === "ignore" ? "bg-rose-950 text-rose-300 border-rose-700" : "bg-slate-800 text-slate-300 border-slate-600"}`}>
                      {c.triage?.action === "manual_reply" ? "manual reply" : c.triage?.action || "acknowledge"}
                    </Badge>
                  </td>
                  <td className="max-w-xs px-4 py-3">
                    {c.posted ? (
                      <div className="text-xs text-emerald-300">Posted: “{c.reply_text}”</div>
                    ) : c.triage?.needs_reply || replyFor === c.id ? (
                      replyFor === c.id ? (
                        <div className="flex gap-2">
                          <Input data-testid="reply-input" value={replyText} onChange={(e) => setReplyText(e.target.value)} className="border-white/10 bg-black/30 text-xs text-slate-200" placeholder="type reply…" />
                          <Button data-testid="send-reply-button" size="sm" className="bg-amber-500 text-[#090A0F]" onClick={() => sendReply(c.comment_id)}><Send className="h-3.5 w-3.5" /></Button>
                        </div>
                      ) : (
                        <div className="flex flex-wrap items-center gap-2 text-xs text-slate-400">
                          <span>Draft: “{c.reply_text}”</span>
                          <Button data-testid="approve-post-reply-button" size="sm" className="h-7 bg-emerald-500 px-2.5 text-[11px] font-semibold text-[#090A0F] hover:bg-emerald-400" onClick={() => postDraft(c.comment_id, c.reply_text)}>
                            <CheckCircle2 className="mr-1 h-3 w-3" /> Approve &amp; Post
                          </Button>
                          <button data-testid="show-reply-input-button" onClick={() => { setReplyFor(c.id); setReplyText(c.reply_text || ""); }} className="text-amber-300 underline">edit</button>
                        </div>
                      )
                    ) : (
                      <span className="text-xs text-slate-500">No action needed</span>
                    )}
                  </td>
                </tr>
              ))}
              {!(comments || []).length && (
                <tr><td colSpan={4} className="px-6 py-12 text-center text-sm text-slate-500">
                  <Bot className="mx-auto mb-3 h-8 w-8 text-slate-600" />
                  No comments yet — the agent polls automatically every 15 min once a video is published, or sync now
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
