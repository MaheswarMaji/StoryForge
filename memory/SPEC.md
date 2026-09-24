# StoryForge Imported App

## Scope

StoryForge is an AI-powered mythology and folk-story video factory imported from the public repository `MaheswarMaji/StoryForge` without feature changes.

## Key flows

- Production dashboard at `/dashboard` with stories, videos, spend, queue, and pipeline status.
- PDF upload and OCR workflow for creating story projects.
- Script creation, story library, story detail, video production, news desk, social engagement, channels, integrations, settings, and admin routes.
- Each script segment can be edited directly and has independent AI regeneration controls for script, narration voice, and image/video clip. Script regeneration updates the segment text and prompt without automatically spending on media; voice and visual regeneration rebuild the affected segment and re-stitch the master video.
- Human Review → Request Edits requires notes and queues an AI revision job. The job applies targeted changes to affected segments, invalidates their cached media, records the request, and leaves the story ready for re-rendering.
- The Character & Style Consistency Sheet is editable and becomes a locked canonical continuity bible. Saving it preserves narration audio, marks all character references/frames/clips stale, and forces visual regeneration on the next render.
- Every visual prompt receives the full, untruncated continuity bible before the scene prompt. Storyboard mode uses one cohesive contact sheet with the same reference image; slide frames require a reference-aware provider; clip mode animates the approved frame locally rather than allowing text-to-video identity drift.
- Quality policy: the pipeline fails with a retryable error when reference-aware image generation is unavailable instead of silently substituting Pexels/procedural imagery that breaks character or illustration-style continuity.
- Create from Script detects numbered Hindi or English scene blocks. Supplied Visual and Narration/Voiceover/Dialogue content is parsed deterministically into matching segments and preserved verbatim; its Consistency Bible becomes the locked character sheet. No script-generation job is created for structured input. Unstructured prompts retain the existing AI script fallback.
- Emergent-managed Google OAuth session flow under `/api/auth/*`.

## Verification state

- Public `GET /api/` responds with the StoryForge health message.
- Public dashboard loads at `/dashboard`.
- Unauthenticated dashboard calls to `/api/auth/me` return `401`, which is the expected signed-out state.

## Credentials

No seeded test accounts or static credentials are present in the imported repository.