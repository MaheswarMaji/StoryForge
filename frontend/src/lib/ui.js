export const BEATS = [
  { key: "hook", label: "Hook", hint: "0–10s · grab attention", cls: "beat-hook", text: "text-amber-300", border: "border-amber-600/50" },
  { key: "story", label: "Story", hint: "setup · characters · conflict", cls: "beat-story", text: "text-blue-300", border: "border-blue-600/50" },
  { key: "twist", label: "Twist", hint: "the unexpected turn", cls: "beat-twist", text: "text-purple-300", border: "border-purple-600/50" },
  { key: "climax", label: "Climax", hint: "highest tension", cls: "beat-climax", text: "text-red-300", border: "border-red-600/50" },
  { key: "action", label: "Action", hint: "resolution unfolds", cls: "beat-action", text: "text-emerald-300", border: "border-emerald-600/50" },
  { key: "lesson", label: "Lesson", hint: "moral + CTA", cls: "beat-lesson", text: "text-teal-300", border: "border-teal-600/50" },
];

export const beatMeta = (k) => BEATS.find((b) => b.key === k) || BEATS[1];

export const STATUS = {
  draft: { label: "Draft", cls: "bg-slate-800 text-slate-300 border-slate-600" },
  scripting: { label: "Scripting", cls: "bg-blue-950 text-blue-300 border-blue-700" },
  script_ready: { label: "Script Ready", cls: "bg-indigo-950 text-indigo-300 border-indigo-700" },
  rendering: { label: "Rendering", cls: "bg-amber-950 text-amber-300 border-amber-600 animate-pulse" },
  qa_failed: { label: "QA Flagged", cls: "bg-orange-950 text-orange-300 border-orange-700" },
  in_review: { label: "In Review", cls: "bg-purple-950 text-purple-300 border-purple-600" },
  approved: { label: "Approved", cls: "bg-emerald-950 text-emerald-300 border-emerald-600" },
  rejected: { label: "Rejected", cls: "bg-rose-950 text-rose-300 border-rose-600" },
  edits_requested: { label: "Edits Requested", cls: "bg-yellow-950 text-yellow-300 border-yellow-700" },
  failed: { label: "Failed", cls: "bg-red-950 text-red-300 border-red-700" },
};

export const BOOK_STATUS = {
  uploaded: { label: "Uploaded", cls: "bg-slate-800 text-slate-300 border-slate-600" },
  ocr_running: { label: "OCR Running", cls: "bg-amber-950 text-amber-300 border-amber-600 animate-pulse" },
  segmenting: { label: "Finding Stories", cls: "bg-purple-950 text-purple-300 border-purple-600 animate-pulse" },
  ocr_done: { label: "OCR Done", cls: "bg-blue-950 text-blue-300 border-blue-700" },
  segmented: { label: "Segmented", cls: "bg-emerald-950 text-emerald-300 border-emerald-600" },
  ocr_failed: { label: "OCR Failed", cls: "bg-red-950 text-red-300 border-red-700" },
  failed: { label: "Failed", cls: "bg-red-950 text-red-300 border-red-700" },
};

export const statusMeta = (s) => STATUS[s] || BOOK_STATUS[s] || { label: s, cls: "bg-slate-800 text-slate-300 border-slate-600" };

export const PIPELINE_STEPS = [
  { key: "script", label: "Script" },
  { key: "voice", label: "Voices" },
  { key: "frames", label: "Frames" },
  { key: "clips", label: "Clips" },
  { key: "stitch", label: "Stitch" },
  { key: "qa", label: "QA" },
  { key: "review", label: "Review" },
];

export const TTS_VOICES = [
  "gemini:Charon", "gemini:Kore", "gemini:Puck", "gemini:Leda", "gemini:Aoede",
  "gemini:Fenrir", "gemini:Zephyr", "onyx", "coral", "fable", "nova", "ash", "sage", "shimmer", "alloy", "echo",
];
export const MUSIC_MOODS = ["devotional", "suspense", "horror", "moral", "action", "sad", "happy"];
export const LANGS = [
  { value: "hi", label: "Hindi / Devanagari" },
  { value: "bn", label: "Bengali" },
  { value: "en", label: "English" },
];

export const jobDuration = (j) => {
  if (!j?.started_at) return null;
  const end = j.finished_at ? new Date(j.finished_at) : new Date();
  return Math.max(0, Math.round((end - new Date(j.started_at)) / 1000));
};
