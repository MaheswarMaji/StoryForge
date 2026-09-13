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
- 2026-09-12 (session 3, current): 
  - **App unlocked** — mandatory sign-in wall removed (user was locked out); Google sign-in is now OPTIONAL (Sign in chip → /login); only /api/admin/* still requires an admin session (401/403 enforced)
  - **Two production modes** (per-story): slide-based (image slides + infographics + narration) and AI-clip mode; image chain priority OpenAI → HF FLUX.1-schnell → fal.ai; video chain priority Gemini Veo (LRO REST) → Replicate (Wan 2.1) → fal.ai (Wan/CogVideoX); Ken Burns + procedural frames remain the never-fail local fallback; FREE TTS first (kokoro → xtts → gtts, per-type voice specs like kokoro:hm_omega)
  - **Create from Script/Prompt** (/create): paste script or idea → 8 video-type registry (mythology_moral, folk_horror, motivational, kids_fables, educational, business, farming, tech) auto-selects voice/music/tone/style via auto-seeded channels (vt-*); flexible length 30–240s (chunks cap raised to 24)
  - **Script review & edit before media generation**: PATCH /stories/{id}/script with inline editor UI (voiceover/visual/video_prompt), cache-aware (edited segments re-render)
  - **Progress tracker**: Script → Voices → Media → Compiled → QA → Review → Uploaded (+ published status)
  - **API Keys Vault** in Settings: all 11 keys user-configurable (masked, allow-listed, hot-applied to env, persisted in db.settings, reloaded at startup)
  - Testing: iteration_3 = 21/21 backend + 100% frontend testids
- 2026-09-12 (session 2): Google-only login (now optional), Admin Console, Instagram Integrations page (live-validated), draft-only engagement, Improvement Coach (max 2 rounds, keep-only-if-score-improves), XTTS v2 verified live, qwen_local capability-gated provider, disk hardening (/app+/root share 9.8G; model caches moved to /var/cache)
- Provider billing states (not code bugs): fal.ai account LOCKED (exhausted balance — fal.ai/dashboard/billing), Emergent universal key budget exceeded, OpenAI unfunded, Gemini cyclic rate limits. HF_TOKEN/REPLICATE_API_TOKEN unset → add in Settings → API Keys. Until quotas recover, videos render with procedural mandala frames + Ken Burns and Kokoro/gTTS voice.

## Backlog / Next
- P1: Top up fal.ai balance + Emergent universal key → real AI frames/clips resume automatically via router
- P1: Connect Instagram: paste long-lived token + user ID in /settings (endpoints fully wired & validated)
- P1: YouTube OAuth consent (redirect URI whitelisted) → direct Shorts upload + live stats in Admin Console
- P2: A/B thumbnails; retention analytics learning loop; real payout data via YouTube Analytics API scope

## Test Credentials
See /app/memory/test_credentials.md. Sample PDFs: /app/backend/samples/*.pdf. Current story with produced video: 6aa57c1eaad23f394fffaa41 (approved, viral 84).
