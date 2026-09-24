# StoryForge Imported App

## Scope

StoryForge is an AI-powered mythology and folk-story video factory imported from the public repository `MaheswarMaji/StoryForge` without feature changes.

## Key flows

- Production dashboard at `/dashboard` with stories, videos, spend, queue, and pipeline status.
- PDF upload and OCR workflow for creating story projects.
- Script creation, story library, story detail, video production, news desk, social engagement, channels, integrations, settings, and admin routes.
- Emergent-managed Google OAuth session flow under `/api/auth/*`.

## Verification state

- Public `GET /api/` responds with the StoryForge health message.
- Public dashboard loads at `/dashboard`.
- Unauthenticated dashboard calls to `/api/auth/me` return `401`, which is the expected signed-out state.

## Credentials

No seeded test accounts or static credentials are present in the imported repository.