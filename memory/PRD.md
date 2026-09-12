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
  - services/: ocr (tesseract hi/bn/eng, chunked, auto page-PNG cleanup), llm (gpt-5.4 + failover), gemini (REST text/TTS/image, circuit breaker), imagegen (nano-banana→gemini→openai→procedural mandala frames), media (kokoro/gtts/openai TTS, ken burns clips, concat, mood music, end card, thumbs), router (chains: tts=gemini→kokoro→xtts→gtts→openai; image=fal_flux→replicate_flux→emergent→gemini→openai→qwen_local→procedural; video=fal wan→fal cogvideox-5b→replicate wan→kenburns), agents (story miner, scriptwriter, QA, metadata, editor/fact-checker, improvement coach), news, engagement (draft-only), social (YT OAuth upload/comments/stats/channel-info; IG publish via IG_STATE db-backed creds), storage (object storage)
- Frontend: React 19 + Tailwind + shadcn + recharts + sonner. Dark obsidian/amber cinematic theme. Playfair Display / Plus Jakarta Sans / Noto Devanagari/Bengali.
  - Pages: Login (/login), Dashboard, Upload, Library, Story Studio, News Desk, Engagement (/social), Channels (/channels), Integrations (/settings), Admin Console (/admin)
  - Auth: ProtectedRoute (3-state), AuthCallback (render-time session_id hash detection), axios withCredentials + 401 interceptor (skips /login to prevent reload loops)

## Implemented
- 2026-09-11/12 (session 1): full pipeline end-to-end, 3 channels, editor+fact-check agent, viral scorer, news desk, YouTube OAuth, engagement, 977-page Bhagwat ingest, 11/11 tests
- 2026-09-12 (session 2, this fork):
  - Google-only login (Emergent Auth) gating all API routes; login page (STABLE — fixed the reload-loop flicker: axios 401 interceptor + login-page guard); user chip + logout in header; ProtectedRoute/AuthCallback race-safe flow
  - Admin Console: /api/admin/overview + /admin UI (accounts/roles, channels, video performance w/ live YT stats, subscribers, est. revenue, API spend); first Google user auto-admin (nyai.deepak@gmail.com is admin); 403 for others
  - Instagram: Integrations page with live Graph-API validation on save (fake tokens 400), disconnect, status badges; publish flow uses db-backed creds + PUBLIC_BASE_URL video URL
  - Engagement agent now DRAFT-ONLY: drafts stored unposted; "Approve & Post" + edit in dashboard
  - Improvement Coach: POST /stories/{id}/improve (max 2 rounds, 409 when exhausted); agent pinpoints weakest scope, applies ≤3 chunk edits + optional hook, re-renders (cache-aware), re-assesses, auto-reverts script if score doesn't improve; history UI with before→after badges
  - TTS chain: XTTS v2 added (coqui-tts, verified live: 8.5s Hindi WAV on CPU; model cached at /var/cache/tts-data via symlink, transformers pinned <5, torchaudio+torchcodec CPU)
  - Image chain: qwen_local provider added (capability-gated: needs CUDA or 40GB+ RAM — reports capable=false here, falls through instantly); fal video chain extended with CogVideoX-5b
  - Disk hardening: found /app+/root share ONE 9.8G volume; cleaned 600MB stale OCR page renders + pip cache; disk_guard() sweeps tmp/page-PNGs and fails loudly under 600MB; XTTS model relocated off the small volume
  - Testing: 30/30 backend pytest cases (iteration_2.json) incl. auth gating, admin 200/403, IG validation, draft-only engagement, improve guards; frontend screens verified via Playwright screenshots (desktop)
- Provider billing states (not code bugs): fal.ai account LOCKED (exhausted balance — needs top-up at fal.ai/dashboard/billing), Emergent universal key budget exceeded (Profile → Manage plan → Universal Key → Add Balance), OpenAI key unfunded, Gemini key cyclically rate-limited. Until topped up, images render as procedural mandala art + Ken Burns motion; when any provider recovers the router picks it up automatically.

## Backlog / Next
- P1: Top up fal.ai balance + Emergent universal key → real AI frames/clips resume automatically via router
- P1: Connect Instagram: paste long-lived token + user ID in /settings (endpoints fully wired & validated)
- P1: YouTube OAuth consent (redirect URI whitelisted) → direct Shorts upload + live stats in Admin Console
- P2: A/B thumbnails; retention analytics learning loop; real payout data via YouTube Analytics API scope

## Test Credentials
See /app/memory/test_credentials.md. Sample PDFs: /app/backend/samples/*.pdf. Current story with produced video: 6aa57c1eaad23f394fffaa41 (approved, viral 84).
