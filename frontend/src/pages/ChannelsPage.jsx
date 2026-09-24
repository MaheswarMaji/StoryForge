import { useEffect, useRef, useState } from "react";
import { Loader2, Play, Save, Shield, Square, Volume2, Music } from "lucide-react";
import { api, MEDIA, useChannels } from "@/lib/api";
import { TTS_VOICES, ttsVoiceLabel, MUSIC_MOODS, LANGS } from "@/lib/ui";
import { useQueryClient } from '@tanstack/react-query';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { toast } from "sonner";

export default function ChannelsPage() {
  const { channels } = useChannels();
  const queryClient = useQueryClient();
  const [state, setState] = useState({});
  const [saving, setSaving] = useState(null);
  const audioRef = useRef(null);
  const [previewState, setPreviewState] = useState({ id: null, phase: null });

  const previewVoice = async (c) => {
    if (previewState.id === c.id && previewState.phase === "playing") {
      audioRef.current?.pause();
      setPreviewState({ id: null, phase: null });
      return;
    }
    setPreviewState({ id: c.id, phase: "loading" });
    try {
      const { data } = await api.post("/tts/preview", { voice: c.voice, language: c.language, tone: c.tone });
      const audio = audioRef.current || (audioRef.current = new Audio());
      audio.src = `${MEDIA}${data.url}`;
      audio.onended = () => setPreviewState({ id: null, phase: null });
      audio.onpause = () => setPreviewState({ id: null, phase: null });
      audio.onerror = () => setPreviewState({ id: null, phase: null });
      await audio.play();
      setPreviewState({ id: c.id, phase: "playing" });
    } catch (e) {
      setPreviewState({ id: null, phase: null });
      toast.error(e?.response?.data?.detail || "Voice preview failed");
    }
  };

  useEffect(() => {
    const next = {};
    (channels || []).forEach((c) => { next[c.id] = { ...c }; });
    setState(next);
  }, [channels]);

  const set = (id, k, v) => setState((s) => ({ ...s, [id]: { ...s[id], [k]: v } }));

  const save = async (id) => {
    const c = state[id];
    setSaving(id);
    try {
      await api.put(`/channels/${id}`, {
        name: c.name, description: c.description, language: c.language, tone: c.tone,
        voice: c.voice, voice_speed: Number(c.voice_speed), music_mood: c.music_mood,
        music_volume: Number(c.music_volume), safety_level: c.safety_level,
        style_prefix: c.style_prefix, cta_text: c.cta_text, is_kids: !!c.is_kids,
        expressive_voice: c.expressive_voice !== false,
      });
      await queryClient.invalidateQueries({ queryKey: ['channels'] });
      toast.success(`${c.name} settings saved`);
    } catch (e) {
      toast.error("Save failed");
    } finally {
      setSaving(null);
    }
  };

  if (!Object.keys(state).length) return <div className="p-10 text-slate-500">Loading channels…</div>;

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div>
        <h1 className="font-display text-3xl font-extrabold tracking-tight text-slate-100 lg:text-4xl">Channels & Settings</h1>
        <p data-testid="channel-narration-default-policy" className="mt-1 text-sm text-slate-400">Local narration by default: Kokoro → XTTS → gTTS. Gemini runs only when you explicitly select a Gemini voice.</p>
        <p data-testid="channel-local-tts-language-note" className="mt-2 text-xs text-slate-500">Unsupported languages skip to the next engine. Bengali currently uses gTTS, which requires internet but no Gemini key. Existing story audio stays unchanged until regenerated.</p>
      </div>

      <Tabs defaultValue={Object.keys(state)[0]}>
        <TabsList className="h-auto w-full flex-wrap justify-start gap-1 border border-amber-500/20 bg-[#12141F]">
          {Object.values(state).map((c) => (
            <TabsTrigger key={c.id} data-testid={`channel-tab-${c.key}`} value={c.id} className="data-[state=active]:bg-amber-500/15 data-[state=active]:text-amber-300">
              {c.name}
            </TabsTrigger>
          ))}
        </TabsList>

        {Object.values(state).map((c) => (
          <TabsContent key={c.id} value={c.id}>
            <div data-testid="channel-editor" className="card-glow space-y-6 rounded-2xl border border-amber-500/10 bg-[#12141F] p-8">
              <div className="grid gap-5 md:grid-cols-2">
                <div><Label className="text-slate-400">Channel name</Label>
                  <Input data-testid="channel-name-input" value={c.name} onChange={(e) => set(c.id, "name", e.target.value)} className="mt-1.5 border-white/10 bg-black/30 text-slate-200" /></div>
                <div><Label className="text-slate-400">Narration language</Label>
                  <Select value={c.language} onValueChange={(v) => set(c.id, "language", v)}>
                    <SelectTrigger data-testid="channel-language-select" className="mt-1.5 border-white/10 bg-black/30 text-slate-200"><SelectValue /></SelectTrigger>
                    <SelectContent className="border-amber-500/20 bg-[#12141F]">
                      {LANGS.map((l) => <SelectItem key={l.value} value={l.value}>{l.label}</SelectItem>)}
                    </SelectContent>
                  </Select></div>
              </div>

              <div><Label className="flex items-center gap-2 text-slate-400"><Volume2 className="h-4 w-4 text-amber-400" /> Voice & tone direction</Label>
                <Textarea data-testid="channel-tone-input" value={c.tone} onChange={(e) => set(c.id, "tone", e.target.value)} className="mt-1.5 border-white/10 bg-black/30 text-slate-200" rows={2} />
                <div className="mt-3 grid gap-4 md:grid-cols-2">
                  <div>
                    <Label className="text-slate-400">TTS voice</Label>
                    <Select value={c.voice} onValueChange={(v) => set(c.id, "voice", v)}>
                      <SelectTrigger data-testid="channel-voice-select" className="mt-1.5 border-white/10 bg-black/30 text-slate-200"><SelectValue /></SelectTrigger>
                      <SelectContent className="border-amber-500/20 bg-[#12141F]">
                        {TTS_VOICES.map((v) => <SelectItem data-testid={`channel-voice-option-${v.replaceAll(':', '-').replaceAll('_', '-')}`} key={v} value={v}>{ttsVoiceLabel(v)}</SelectItem>)}
                      </SelectContent>
                    </Select>
                    <Button variant="outline" size="sm" data-testid={`channel-voice-preview-${c.id}`}
                      onClick={() => previewVoice(c)}
                      className="mt-2 w-full border-white/10 bg-black/30 text-xs text-slate-300 hover:bg-white/5">
                      {previewState.id === c.id && previewState.phase === "loading" ? <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
                        : previewState.id === c.id && previewState.phase === "playing" ? <Square className="mr-2 h-3 w-3" />
                        : <Play className="mr-2 h-3.5 w-3.5" />}
                      {previewState.id === c.id ? (previewState.phase === "playing" ? "Stop" : "Loading voice…") : "Preview voice"}
                    </Button>
                  </div>
                  <div>
                    <Label className="text-slate-400">Voice speed — {Number(c.voice_speed).toFixed(2)}×</Label>
                    <Slider data-testid="channel-voice-speed" value={[c.voice_speed]} onValueChange={([v]) => set(c.id, "voice_speed", v)} min={0.7} max={1.3} step={0.05} className="mt-3" />
                  </div>
                  <div className="flex items-center gap-3 rounded-xl border border-white/10 bg-black/30 px-4 py-2.5 md:col-span-2">
                    <Switch data-testid="channel-expressive-switch" checked={c.expressive_voice !== false} onCheckedChange={(v) => set(c.id, "expressive_voice", v)} />
                    <span data-testid="channel-expressive-local-policy" className="text-sm text-slate-300">Expressive narration — emotional pacing and voice dynamics on the selected engine. This switch does not enable Gemini.</span>
                  </div>
                </div>
              </div>

              <div><Label className="flex items-center gap-2 text-slate-400"><Music className="h-4 w-4 text-amber-400" /> Background music</Label>
                <div className="mt-2 grid gap-4 md:grid-cols-2">
                  <Select value={c.music_mood} onValueChange={(v) => set(c.id, "music_mood", v)}>
                    <SelectTrigger data-testid="channel-music-mood" className="border-white/10 bg-black/30 text-slate-200"><SelectValue /></SelectTrigger>
                    <SelectContent className="border-amber-500/20 bg-[#12141F]">
                      {MUSIC_MOODS.map((m) => <SelectItem key={m} value={m}>{m}</SelectItem>)}
                    </SelectContent>
                  </Select>
                  <div>
                    <Label className="text-slate-400">Music volume — {(c.music_volume * 100).toFixed(0)}%</Label>
                    <Slider data-testid="channel-music-volume" value={[c.music_volume]} onValueChange={([v]) => set(c.id, "music_volume", v)} min={0.05} max={0.4} step={0.01} className="mt-3" />
                  </div>
                </div>
              </div>

              <div><Label className="flex items-center gap-2 text-slate-400"><Shield className="h-4 w-4 text-amber-400" /> Safety guardrails</Label>
                <div className="mt-2 grid gap-4 md:grid-cols-2">
                  <Select value={c.safety_level} onValueChange={(v) => set(c.id, "safety_level", v)}>
                    <SelectTrigger data-testid="channel-safety-select" className="border-white/10 bg-black/30 text-slate-200"><SelectValue /></SelectTrigger>
                    <SelectContent className="border-amber-500/20 bg-[#12141F]">
                      <SelectItem value="strict_kids">Strict — Kids 7+ (COPPA)</SelectItem>
                      <SelectItem value="general">General — 13+</SelectItem>
                    </SelectContent>
                  </Select>
                  <div className="flex items-center gap-3 rounded-xl border border-white/10 bg-black/30 px-4 py-2.5">
                    <Switch data-testid="channel-kids-switch" checked={c.is_kids} onCheckedChange={(v) => set(c.id, "is_kids", v)} />
                    <span className="text-sm text-slate-300">Made for kids (age-appropriate QA + gentle spooks)</span>
                  </div>
                </div>
              </div>

              <div className="grid gap-5 md:grid-cols-2">
                <div><Label className="text-slate-400">Visual style prefix (used in every frame prompt)</Label>
                  <Textarea data-testid="channel-style-input" value={c.style_prefix} onChange={(e) => set(c.id, "style_prefix", e.target.value)} className="mt-1.5 border-white/10 bg-black/30 text-slate-200" rows={3} /></div>
                <div><Label className="text-slate-400">Call to action (lesson outro)</Label>
                  <Textarea data-testid="channel-cta-input" value={c.cta_text} onChange={(e) => set(c.id, "cta_text", e.target.value)} className="mt-1.5 border-white/10 bg-black/30 text-slate-200" rows={3} /></div>
              </div>

              <Button data-testid="channel-save-button" disabled={saving === c.id} onClick={() => save(c.id)} className="bg-amber-500 font-semibold text-[#090A0F] hover:bg-amber-400">
                <Save className="mr-2 h-4 w-4" /> {saving === c.id ? "Saving…" : "Save Channel Settings"}
              </Button>
            </div>
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
}
