import { useState } from "react";
import { useParams } from "react-router-dom";
import { Play, RefreshCw, Download, CheckCircle2, XCircle, AlertTriangle, Loader2, Wand2, Sparkles, TrendingUp } from "lucide-react";
import { api, usePoll, useChannels, MEDIA } from "@/lib/api";
import { BEATS, beatMeta, PIPELINE_STEPS, statusMeta } from "@/lib/ui";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { toast } from "sonner";

const CAMERAS = { zoom_in: "Zoom In", zoom_out: "Zoom Out", pan_left: "Pan Left", pan_right: "Pan Right", static: "Static" };

export default function StoryDetailPage() {
  const { id } = useParams();
  const [story, refresh, err] = usePoll(`/stories/${id}`, 4000);
  const { channels } = useChannels();
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);

  if (err) return <div className="p-10 text-red-400">Story not found</div>;
  if (!story) return <div className="p-10 text-slate-500">Opening studio…</div>;

  const channel = channels?.find((c) => c.id === story.channel_id);
  const chunks = story.script?.chunks || [];
  const media = story.media || {};
  const hasVideo = !!media.final;

  const act = async (fn) => { setBusy(true); try { await fn(); refresh(); } catch (e) { toast.error(e?.response?.data?.detail || "Action failed"); } finally { setBusy(false); } };
  const genScript = () => act(() => api.post(`/stories/${id}/script`).then(() => toast.success("Script generation queued")));
  const produce = () => act(() => api.post(`/stories/${id}/produce`).then(() => toast.success("Production pipeline started — voices, frames, clips, stitch, QA")));
  const regen = (i) => act(() => api.post(`/stories/${id}/segments/${i}/regenerate`).then(() => toast.success(`Regenerating segment ${i + 1}`)));
  const review = (action, note = "") => act(() => api.post(`/stories/${id}/review`, { action, notes: note }).then(() => toast.success(`Review recorded: ${action.replace("_", " ")}`)));
  const improve = () => act(() => api.post(`/stories/${id}/improve`).then(() => toast.success("Improvement Coach queued — targeted edits, kept only if the score improves")));

  const stageIdx = (() => {
    if (["approved", "edits_requested", "rejected"].includes(story.status)) return PIPELINE_STEPS.length - 1;
    const m = { "": 0, Scripting: 0, "Script ready": 0, "Character sheet": 1, "Queued": 1 };
    const s = story.stage || "";
    if (/Segment|Voices/i.test(s)) return 1;
    if (/Stitch/i.test(s)) return 4;
    if (/QA/i.test(s)) return 5;
    if (/Metadata/i.test(s)) return 5;
    if (/review/i.test(s)) return 6;
    return m[s] ?? (hasVideo ? 6 : chunks.length ? 1 : 0);
  })();

  return (
    <div className="mx-auto max-w-7xl space-y-8 pb-16">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge data-testid="story-detail-status" className={`${statusMeta(story.status).cls} border text-[11px]`}>{statusMeta(story.status).label}</Badge>
            {channel && <Badge variant="outline" className="border-amber-500/30 text-amber-300">{channel.name}</Badge>}
            {story.category && <Badge variant="outline" className="border-white/15 text-slate-400">{story.category} · {story.target_audience}</Badge>}
            {story.script?.viral_score?.total != null && (
              <Badge data-testid="viral-score-badge" variant="outline" className={`border text-[11px] font-semibold ${(story.script.viral_score.total >= 80 && "border-emerald-500/50 text-emerald-300") || (story.script.viral_score.total >= 60 && "border-amber-500/50 text-amber-300") || "border-rose-500/50 text-rose-300"}`}>
                Viral {story.script.viral_score.total}/100
              </Badge>
            )}
            {story.script?.editor?.factual_ok === false && (
              <Badge className="border border-orange-500/50 bg-orange-950/40 text-[11px] text-orange-300">Fact-check: corrections applied</Badge>
            )}
            <Badge variant="outline" className="border-white/15 font-mono2 text-slate-400">${(story.cost?.total || 0).toFixed(3)}</Badge>
          </div>
          <h1 data-testid="story-detail-title" className="mt-3 font-display text-3xl font-extrabold tracking-tight text-slate-100 lg:text-4xl">{story.title_hindi || story.title_english}</h1>
          <p className="mt-1 text-sm text-slate-400">{story.title_english} · {story.source} {story.page_start ? `· pp.${story.page_start}–${story.page_end}` : ""}</p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          {story.status === "draft" && (
            <Button data-testid="generate-script-cta" onClick={genScript} disabled={busy} className="bg-amber-500 font-semibold text-[#090A0F] hover:bg-amber-400">
              <Wand2 className="mr-2 h-4 w-4" /> Generate 6-Beat Script
            </Button>
          )}
          {(story.status === "script_ready" || story.status === "edits_requested" || story.status === "rejected") && (
            <Button data-testid="produce-video-cta" onClick={produce} disabled={busy} className="bg-emerald-500 font-semibold text-[#090A0F] hover:bg-emerald-400">
              <Sparkles className="mr-2 h-4 w-4" /> Produce Video
            </Button>
          )}
          {story.status === "failed" && (
            <Button data-testid="retry-cta" onClick={chunks.length ? produce : genScript} disabled={busy} className="bg-amber-500 font-semibold text-[#090A0F] hover:bg-amber-400">
              <RefreshCw className="mr-2 h-4 w-4" /> Retry {chunks.length ? "Production" : "Script"}
            </Button>
          )}
        </div>
      </div>

      {story.error && <div className="rounded-xl border border-red-500/30 bg-red-950/30 px-4 py-3 text-sm text-red-300">{story.error}</div>}

      <div data-testid="pipeline-tracker" className="card-glow flex flex-wrap items-center gap-2 rounded-2xl border border-amber-500/10 bg-[#12141F] px-6 py-4">
        {PIPELINE_STEPS.map((s, i) => (
          <div key={s.key} className="flex items-center gap-2">
            <div className={`flex items-center gap-2 rounded-full px-3.5 py-1.5 text-xs font-medium ${i < stageIdx ? "bg-emerald-500/10 text-emerald-300" : i === stageIdx ? "bg-amber-500/15 text-amber-300 ring-1 ring-amber-500/40" : "text-slate-500"}`}>
              {i < stageIdx ? <CheckCircle2 className="h-3.5 w-3.5" /> : i === stageIdx && story.status === "rendering" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <span className="h-1.5 w-1.5 rounded-full bg-current" />}
              {s.label}
            </div>
            {i < PIPELINE_STEPS.length - 1 && <div className="h-px w-5 bg-white/10" />}
          </div>
        ))}
        {story.stage && <span className="ml-auto font-mono2 text-[11px] text-slate-500">{story.stage}</span>}
      </div>

      {(story.script?.editor?.notes?.length || story.script?.editor?.factual_ok != null) && (
        <div data-testid="editor-log-card" className="card-glow rounded-2xl border border-blue-500/20 bg-blue-950/10 p-6">
          <h3 className="mb-2 flex items-center gap-2 font-display text-lg font-semibold text-blue-300">
            Editor & Fact-Check Log
            <Badge className={`border text-[10px] ${story.script.editor.factual_ok ? "border-emerald-600/50 text-emerald-300" : "border-orange-500/50 text-orange-300"}`}>
              {story.script.editor.factual_ok ? "factual ✓" : "corrections applied"}
            </Badge>
            {story.script?.editor?.corrections_applied > 0 && (
              <span className="text-xs text-slate-500">{story.script.editor.corrections_applied} edits applied</span>
            )}
          </h3>
          <ul className="space-y-1.5">
            {(story.script.editor.notes || []).map((n, i) => (
              <li key={i} className="flex gap-2 text-xs text-slate-300"><span className="text-blue-400">•</span>{n}</li>
            ))}
          </ul>
          {story.script?.viral_score?.total != null && (
            <div className="mt-4 flex flex-wrap gap-2">
              {Object.entries(story.script.viral_score).filter(([k]) => !["total", "verdict", "notes"].includes(k)).map(([k, v]) => (
                <div key={k} className="rounded-lg bg-black/30 px-3 py-1.5 text-center">
                  <div className="font-mono2 text-sm font-semibold text-amber-300">{v}</div>
                  <div className="text-[9px] uppercase tracking-wide text-slate-500">{k}</div>
                </div>
              ))}
              <div className="rounded-lg bg-amber-500/15 px-3 py-1.5 text-center ring-1 ring-amber-500/40">
                <div className="font-mono2 text-sm font-bold text-amber-300">{story.script.viral_score.total}</div>
                <div className="text-[9px] uppercase tracking-wide text-amber-500">total</div>
              </div>
            </div>
          )}
        </div>
      )}

      {chunks.length > 0 && (
        <div data-testid="improvement-coach-card" className="card-glow rounded-2xl border border-emerald-500/20 bg-emerald-950/10 p-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h3 className="flex flex-wrap items-center gap-2 font-display text-lg font-semibold text-emerald-300">
                <TrendingUp className="h-5 w-5" /> Improvement Coach
                <Badge variant="outline" className="border-white/15 text-[10px] text-slate-400">{(story.improvements || []).length}/2 rounds used</Badge>
              </h3>
              <p className="mt-1 max-w-2xl text-xs leading-relaxed text-slate-400">
                After assessment, the coach pinpoints the single weakest scope and applies minimal targeted edits — kept only if the overall viral score improves, otherwise auto-reverted. Max 2 rounds.
              </p>
            </div>
            <Button data-testid="improve-video-button" disabled={busy || (story.improvements || []).length >= 2 || story.status === "rendering"} onClick={improve} className="bg-emerald-500 font-semibold text-[#090A0F] hover:bg-emerald-400">
              <Sparkles className="mr-2 h-4 w-4" /> {(story.improvements || []).length >= 2 ? "Budget used (2/2)" : "Run Improvement Coach"}
            </Button>
          </div>
          {!!(story.improvements || []).length && (
            <div className="mt-4 space-y-2">
              {story.improvements.map((it, i) => (
                <div key={i} data-testid={`improvement-round-${i}`} className="flex flex-wrap items-center gap-3 rounded-xl bg-black/30 px-4 py-2.5 text-xs">
                  <Badge className={`border text-[10px] ${it.accepted ? "border-emerald-600/50 bg-emerald-950 text-emerald-300" : "border-orange-600/50 bg-orange-950 text-orange-300"}`}>
                    {it.accepted ? "score improved" : "reverted — no gain"}
                  </Badge>
                  <span className="text-slate-300">Round {it.round}: {it.scope}</span>
                  <span className="ml-auto font-mono2 text-slate-400">{it.base_score} → {it.new_score ?? it.base_score}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {chunks.length > 0 && (
        <>
          <div className="grid gap-6 lg:grid-cols-3">
            <div className="card-glow rounded-2xl border border-amber-500/10 bg-[#12141F] p-6 lg:col-span-2">
              <h3 className="mb-2 font-display text-lg font-semibold text-amber-300">Character Consistency Sheet</h3>
              <p data-testid="character-sheet-anchor" className="text-sm leading-relaxed text-slate-300">{story.character_sheet?.anchor || "—"}</p>
              <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-slate-400">
                {(story.characters || []).map((c, i) => (
                  <span key={i} className="rounded-full bg-black/30 px-3 py-1">{c.name}: {c.description}</span>
                ))}
              </div>
            </div>
            {media.char_sheet && (
              <div className="card-glow overflow-hidden rounded-2xl border border-amber-500/10 bg-[#12141F]">
                <img data-testid="character-sheet-image" src={`${MEDIA}${media.char_sheet}`} alt="character sheet" className="h-64 w-full object-cover" />
              </div>
            )}
          </div>

          <div className="space-y-4">
            <h3 className="font-display text-xl font-semibold text-amber-300">Script Segments</h3>
            {chunks.map((c, i) => {
              const bm = beatMeta(c.beat);
              return (
                <div key={i} data-testid={`story-beat-${c.beat}`} className={`rise rounded-2xl border p-5 ${bm.cls}`}>
                  <div className="mb-3 flex flex-wrap items-center gap-2">
                    <Badge className={`${bm.text} border ${bm.border} bg-black/30 text-[11px] font-semibold uppercase tracking-wider`}>{bm.label}</Badge>
                    <span className="font-mono2 text-[11px] text-slate-400">segment {i + 1} · ~10s · {bm.hint}</span>
                    <span className="ml-auto flex items-center gap-2">
                      <span className="rounded-full bg-black/30 px-3 py-1 text-[11px] text-slate-300">{CAMERAS[c.camera] || c.camera}</span>
                      <span className="rounded-full bg-black/30 px-3 py-1 text-[11px] text-slate-300">{c.emotion}</span>
                    </span>
                  </div>
                  <div className="grid gap-5 lg:grid-cols-5">
                    <div className="lg:col-span-3">
                      <p data-testid="segment-voiceover" className="font-deva text-lg font-medium leading-relaxed text-slate-100">“{c.voiceover}”</p>
                      <p className="mt-3 font-mono2 text-[11px] leading-relaxed text-slate-400">VISUAL: {c.video_prompt || c.visual}</p>
                      <div className="mt-4 flex items-center gap-3">
                        {media.audio?.[i] && (
                          <div className="flex items-center gap-2 rounded-full bg-black/40 px-3 py-1.5">
                            <button data-testid="play-segment-audio-button" onClick={() => document.getElementById(`seg-audio-${i}`)?.play()} className="text-amber-300 hover:text-amber-200">
                              <Play className="h-4 w-4" />
                            </button>
                            <audio id={`seg-audio-${i}`} src={`${MEDIA}${media.audio[i]}`} preload="none" controls className="h-8 max-w-52" />
                          </div>
                        )}
                        <Button data-testid="regenerate-segment-video-button" size="sm" variant="outline" className="border-white/20 text-slate-300 hover:bg-white/5" disabled={busy} onClick={() => regen(i)}>
                          <RefreshCw className="mr-1.5 h-3.5 w-3.5" /> Regenerate
                        </Button>
                      </div>
                    </div>
                    {media.frames?.[i] && (
                      <div className="overflow-hidden rounded-xl lg:col-span-2">
                        <img data-testid="segment-frame-image" src={`${MEDIA}${media.frames[i]}`} alt={`frame ${i + 1}`} className="h-56 w-full object-cover ring-1 ring-white/10" />
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}

      {hasVideo && story.status === "approved" && (
        <div data-testid="publish-panel" className="card-glow flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-cyan-500/25 bg-cyan-950/15 p-6">
          <div>
            <h3 className="font-display text-lg font-semibold text-cyan-200">Approved — Ready to Publish</h3>
            <p className="text-xs text-slate-400">Upload the final 9:16 video straight to your connected channels</p>
            {story.publish?.youtube?.url && (
              <a data-testid="published-youtube-link" href={story.publish.youtube.url} target="_blank" rel="noreferrer" className="mt-2 block text-xs text-emerald-300 underline">Published on YouTube: {story.publish.youtube.url}</a>
            )}
            {story.publish?.instagram?.url && (
              <a data-testid="published-instagram-link" href={story.publish.instagram.url} target="_blank" rel="noreferrer" className="mt-1 block text-xs text-emerald-300 underline">Published on Instagram: {story.publish.instagram.url}</a>
            )}
          </div>
          <div className="flex flex-wrap gap-3">
            <Button data-testid="publish-youtube-button" disabled={busy} className="bg-red-600 font-semibold text-white hover:bg-red-500" onClick={() => act(() => api.post(`/stories/${id}/publish`, { platform: "youtube" }).then(() => toast.success("YouTube upload queued")))}>
              Upload to YouTube Shorts
            </Button>
            <Button data-testid="publish-instagram-button" disabled={busy} className="bg-fuchsia-600 font-semibold text-white hover:bg-fuchsia-500" onClick={() => act(() => api.post(`/stories/${id}/publish`, { platform: "instagram" }).then(() => toast.success("Instagram Reels upload queued")))}>
              Upload to Instagram Reels
            </Button>
          </div>
        </div>
      )}

      {hasVideo && (
        <div className="grid gap-6 lg:grid-cols-3">
          <div className="card-glow rounded-2xl border border-amber-500/10 bg-[#12141F] p-6">
            <h3 className="mb-4 font-display text-lg font-semibold text-amber-300">Final 9:16 Master</h3>
            <div className="phone-frame mx-auto w-72">
              <video data-testid="final-video-player" src={`${MEDIA}${media.final}`} controls className="h-[512px] w-full bg-black object-contain" />
            </div>
            <div className="mt-3 text-center text-xs text-slate-500">{media.duration_sec ? `${media.duration_sec}s · 1080×1920 · 30fps` : ""}</div>
            <a data-testid="export-shorts-mp4-button" href={`${MEDIA}${media.final}`} download={`${(story.title_english || "story").replace(/\s+/g, "-")}.mp4`}
              className="mt-3 flex items-center justify-center gap-2 rounded-xl bg-amber-500 px-4 py-2.5 text-sm font-semibold text-[#090A0F] hover:bg-amber-400">
              <Download className="h-4 w-4" /> Download MP4 (Shorts / Reels)
            </a>
          </div>

          <div className="card-glow rounded-2xl border border-amber-500/10 bg-[#12141F] p-6">
            <h3 data-testid="qa-report-accordion" className="mb-4 font-display text-lg font-semibold text-amber-300">Automated QA Report</h3>
            {story.qa?.score != null && (
              <div className="mb-4 flex items-center gap-3">
                <div className={`font-display text-4xl font-bold ${story.qa.passed ? "text-emerald-400" : "text-orange-400"}`}>{Number(story.qa.score).toFixed(1)}</div>
                <div className="text-xs text-slate-400">/ 10 overall<br />{story.qa.passed ? "All critical checks passed" : "Flagged — see issues"}</div>
              </div>
            )}
            <Accordion type="multiple" className="w-full">
              {(story.qa?.checks || []).map((c, i) => (
                <AccordionItem key={i} value={`c${i}`} className="border-white/5">
                  <AccordionTrigger className="py-2.5 text-left text-sm text-slate-200 hover:no-underline">
                    <span className="flex items-center gap-2">
                      {c.passed ? <CheckCircle2 className="h-4 w-4 text-emerald-400" /> : <XCircle className="h-4 w-4 text-red-400" />}
                      <span className="capitalize">{c.name?.replace(/_/g, " ")}</span>
                    </span>
                  </AccordionTrigger>
                  <AccordionContent className="text-xs leading-relaxed text-slate-400">{c.detail}</AccordionContent>
                </AccordionItem>
              ))}
            </Accordion>
            {!!(story.qa?.issues || []).length && (
              <div className="mt-4 space-y-1.5">
                {(story.qa.issues || []).map((x, i) => (
                  <div key={i} className="flex gap-2 text-xs text-orange-300"><AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />{x}</div>
                ))}
              </div>
            )}
            {!story.qa?.checks?.length && <div className="text-sm text-slate-500">QA runs automatically at the end of production</div>}
          </div>

          <div className="card-glow rounded-2xl border border-amber-500/10 bg-[#12141F] p-6">
            <h3 className="mb-4 font-display text-lg font-semibold text-amber-300">Publishing Metadata</h3>
            {media.thumbnail && <img data-testid="thumbnail-image" src={`${MEDIA}${media.thumbnail}`} alt="thumbnail" className="mb-4 w-full rounded-xl ring-1 ring-white/10" />}
            <div data-testid="meta-title" className="font-medium leading-snug text-slate-100">{story.metadata?.title}</div>
            <p data-testid="meta-description" className="mt-2 text-xs leading-relaxed text-slate-400">{story.metadata?.description}</p>
            <div className="mt-3 flex flex-wrap gap-1.5">
              {(story.metadata?.hashtags || []).map((h, i) => (
                <span key={i} className="rounded-full bg-blue-950/60 px-2.5 py-0.5 text-[10px] text-blue-300">#{h}</span>
              ))}
            </div>
          </div>
        </div>
      )}

      {hasVideo && (
        <div data-testid="review-bar" className="card-glow flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-purple-500/25 bg-purple-950/20 p-6">
          <div>
            <h3 className="font-display text-lg font-semibold text-purple-200">Human Review</h3>
            <p className="text-xs text-slate-400">Approve to mark ready for upload, or send back with notes</p>
            {story.review_notes && <p className="mt-2 max-w-xl text-xs italic text-yellow-300">“{story.review_notes}”</p>}
          </div>
          <div className="flex flex-wrap gap-3">
            <Button data-testid="review-approve-button" disabled={busy} className="bg-emerald-500 font-semibold text-[#090A0F] hover:bg-emerald-400" onClick={() => review("approve")}>
              <CheckCircle2 className="mr-2 h-4 w-4" /> Approve for Upload
            </Button>
            <Dialog>
              <DialogTrigger asChild>
                <Button data-testid="review-request-edits-button" disabled={busy} variant="outline" className="border-amber-500/40 text-amber-300 hover:bg-amber-500/10">
                  <Wand2 className="mr-2 h-4 w-4" /> Request Edits
                </Button>
              </DialogTrigger>
              <DialogContent className="border-amber-500/20 bg-[#12141F]">
                <DialogHeader><DialogTitle className="font-display text-amber-300">Request Edits</DialogTitle></DialogHeader>
                <Textarea data-testid="edit-notes-input" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="e.g. segment 3 visual shows the wrong character; slow down the climax narration…" className="border-white/10 bg-black/30 text-slate-200" rows={4} />
                <Button data-testid="submit-edit-request-button" onClick={() => review("request_edits", notes)} className="bg-amber-500 font-semibold text-[#090A0F] hover:bg-amber-400">Submit</Button>
              </DialogContent>
            </Dialog>
            <Button data-testid="review-reject-button" disabled={busy} variant="outline" className="border-rose-500/40 text-rose-300 hover:bg-rose-500/10" onClick={() => review("reject", "Rejected by reviewer")}>
              <XCircle className="mr-2 h-4 w-4" /> Reject
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
