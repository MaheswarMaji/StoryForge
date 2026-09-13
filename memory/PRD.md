# PRD — StoryForge: AI-Powered Mythology & Folk Story Video Factory

## Original Problem Statement
Build a web application with an async job-processing backend that: (1) uploads scanned PDF books; (2) runs OCR supporting Bengali, Hindi/Devanagari and English; (3) uses an LLM to identify and segment short stories with title/source/page-range/metadata; (4) generates 60–120s narration scripts with Hook/Story/Twist/Climax/Action/Lesson beats in ~10s segments with visual prompts and a consistent character sheet; (5) narration audio per segment via TTS with Hindi/regional voices; (6) segment video generation from visual prompts; (7) stitched video with synced narration, royalty-free music, burned-in captions; (8) automated LLM QA (beats, consistency, pacing, safety); (9) title/description/hashtags/thumbnail + 9:16 export for Shorts/Reels; (10) review dashboard (approve/reject/request edits). Two configurable channels sharing one pipeline. Dashboards for production status, API cost per video, queue health.
Later additions: bulk story extraction with curation; direct YouTube/Instagram publishing; engagement agent (draft-only replies); third channel for public-interest news (Google News + policy screening); quota-aware model router with free open-source fallbacks; **Google-only login (Emergent Auth)**; **Improvement Coach feedback loop (max 2 rounds, keep-only-if-score-improves)**; **Admin Console (accounts, channels, video performance, views/subscribers, est. revenue, API spend)**; **Instagram credentials via Integrations UI**.

## User Choices (verbatim intent)
- "Give a login to the application and give option only login with google" → Emergent-managed Google OAuth, no other sign-in
- Instagram: "build the flow + a Settings page where I can enter them later" → /settings Integrations page, live-validated long-lived token, stored in db.settings
- Engagement: "Draft-only: generate replies in dashboard, human clicks Approve & Post"
- Feedback loop: "pinpoint exact scope of improvement by engaging an agent… such suggestions only twice maximum… only improve the overall score"
- "For image generation option for locally pulled Qwen-Image-2512 is also explored in case of all model failure"
- Free/open-source chain: Kokoro + XTTS v2 (TTS), FLUX.1/SDXL/SD3.5/Juggernaut via fal.ai/Replicate (images), Wan 2.1 + CogVideoX (video)

## Architecture
- Backend: FastAPI (/app/backend, port 8001, /api prefix), Mongo test_database (motor).
  - auth.py — Emergent Google OAuth session exchange, httpOnly cookie (7d), verify_auth dependency, first user = admin, ADMIN_EMAILS env override
  - admin.py — /api/admin/overview: accounts + per-owner stories, channels, published-video stats (live YT Data API), subscribers, est. revenue (YT_RPM_USD), API spend, 403 for non-admins
  - models.py — BaseDocument, Channel/Book/Story(owner_id, improvements)/Job/SocialComment
  - job_queue.py — Mongo priority queue: produce/publish/improve > script/segment_fix > ocr/segment > news/engagement; 2 workers; dedupe; recovery
  - pipeline.py — produce_video (editor fact-check → char sheet → TTS+frame+caption+ffmpeg segments → concat → music mix → end card → QA → metadata+thumbnail), improve_video (improvement coach), regenerate_segment; disk_guard
  - tasks.py — handlers: ocr, segment, script, produce, improve, publish (YT+IG), engagement, news
  - services/: ocr (tesseract hi/bn/eng, chunked, auto page-PNG cleanup), llm (ollama→hf-qwen prefer_local + gemini→openai→emergent→hf failover), gemini (REST text/TTS/image, circuit breaker), imagegen (nano-banana→gemini→openai→hf→procedural, 35s caps + 10-min dead-circuit), media (kokoro/xtts/gtts TTS, ken burns clips, concat, mood music, end card, thumbs), storyboard (ONE-image poster → local slicing, PIL fallback), router (chains: tts=kokoro→xtts→gtts→gemini→openai; image=openai→hf_flux→fal_flux→replicate_flux→emergent→gemini→qwen_local→procedural; video=gemini_veo→replicate_wan→fal_wan→kenburns), agents (story miner, scriptwriter, QA, metadata, editor/fact-checker, improvement coach), news, engagement (draft-only), social (YT OAuth upload/comments/stats/channel-info; IG publish via IG_STATE db-backed creds), storage (object storage)
- Frontend: React 19 + Tailwind + shadcn + recharts + sonner. Dark obsidian/amber cinematic theme. Playfair Display / Plus Jakarta Sans / Noto Devanagari/Bengali.
  - Pages: Login (/login), Dashboard, Upload, Library, Story Studio, News Desk, Engagement (/social), Channels (/channels), Integrations (/settings), Admin Console (/admin)
  - Auth: ProtectedRoute (3-state), AuthCallback (render-time session_id hash detection), axios withCredentials + 401 interceptor (skips /login to prevent reload loops)

## Implemented
- 2026-09-11/12 (session 1): full pipeline end-to-end, 3 channels, editor+fact-check agent, viral scorer, news desk, YouTube OAuth, engagement, 977-page Bhagwat ingest, 11/11 tests
- 2026-09-13 (session 4, current):
  - User's 3-part bug report fixed + verified (iteration_5: 13/13 backend, 100% frontend):
    - Image-less videos: diagnosed with live probes — Gemini image 429 (free-tier quota), OpenAI 429 zero credits, fal locked, universal key over budget → billing state, not code. CODE fix for the retry storm: imagegen caps every provider at 35s, single nano-banana attempt, and a 10-min dead-circuit after one full-chain failure (was 240s waits × retries = 8-10 min per image call)
    - Review tail slowness: QA + metadata now run in PARALLEL (gather); thumbnail reuses the hook slide (frames/00.png) with zero image-API calls (was a full dead-chain churn)
    - Engagement agent schedule: default 6h, configurable 0.25-72h live (GET/PUT /api/settings/scheduler + Settings UI 'Automation Schedule' card; periodic loop re-reads every cycle)
  - Storyboard one-shot mode hardened: poster+tiles cache → re-renders skip the AI call entirely; full storyboard render verified at 110-165s end-to-end (was 12+ min)
  - New keys applied (Gemini text works; OpenAI chat works via Gemini; image billing still exhausted)
  - Queue-pause flag now persists across restarts (hydrated from db.settings at startup)
- 2026-09-12 (session 3): app unlocked (optional Google login), slide/clip/storyboard modes, create-from-script page, 8 video types, script editor, API keys vault, flexible length, stop/pause, Ollama/Qwen wiring, admin console, Instagram integrations page, draft-only engagement, Improvement Coach, XTTS v2 verified live
- 2026-09-12 (session 2): Google-only login (now optional), Admin Console, Instagram Integrations page (live-validated), draft-only engagement, Improvement Coach (max 2 rounds, keep-only-if-score-improves), XTTS v2 verified live, qwen_local capability-gated provider, disk hardening (/app+/root share 9.8G; model caches moved to /var/cache)
- 2026-09-13 (later, same day): HF token added → HF image inference confirmed DEAD (410 deprecated / 404 router routes) but FREE hosted Qwen-72B text verified live (router.huggingface.co/v1/chat/completions); wired into llm.py: prefer_local chain (ollama → hf qwen → cloud) for engagement triage + hf as the final free fallback for every LLM call. Settings copy updated. (iteration_6: 9/9 backend + 100% frontend)
- Provider billing states (not code bugs): fal.ai account LOCKED (exhausted balance — fal.ai/dashboard/billing), Emergent universal key budget exceeded (Profile → Manage plan → Universal Key → Add Balance), OpenAI unfunded (chat+image), Gemini IMAGE quota exhausted on free tier (TEXT works). Until billing is enabled anywhere, videos use the local PIL storyboard poster + Kokoro/XTTS voice (110-165s per video, verified).

## Backlog / Next
- P1: Top up fal.ai balance + Emergent universal key → real AI frames/clips resume automatically via router
- P1: Connect Instagram: paste long-lived token + user ID in /settings (endpoints fully wired & validated)
- P1: YouTube OAuth consent (redirect URI whitelisted) → direct Shorts upload + live stats in Admin Console
- P2: A/B thumbnails; retention analytics learning loop; real payout data via YouTube Analytics API scope

## Test Credentials
See /app/memory/test_credentials.md. Sample PDFs: /app/backend/samples/*.pdf. Current story with produced video: 6aa57c1eaad23f394fffaa41 (approved, viral 84).
