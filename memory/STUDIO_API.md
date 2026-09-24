# StoryForge ↔ server27 Studio (proposed, not live)

## Installation boundary
The user has Python generation scripts/workers on server27, but no unified HTTP API yet. This workspace supplies the caller/adapter only, not an installation on that server. Install a service reachable from the StoryForge backend, check the available port, then save the full API base URL (ending `/api/v1`) in Integrations → Media Engines. Add STUDIO_API_TOKEN in the server-side API vault (or backend environment). No token is embedded in frontend code. For container deployments, use a service address instead of the application's own localhost. Put both services behind a trusted network; do not expose the unauthenticated legacy app settings publicly without access control.

## Required endpoints
- `GET /capabilities`: **provisional response extension** `{ "operations": ["generate_image", "generate_video"] }` (`supported_operations` also accepted). No guessed capability is assumed when absent.
- `POST /assets`: multipart `file`, up to 50 MB through the app; response `{asset_id, media_type, status}`. Stable versioned asset IDs. `ready` means upload preparation complete, NOT character production QC approval.
- `POST /characters`: app forwards saved definition/reference IDs plus the unabridged `consistency_sheet`; response schema is not agreed, therefore shown to operator without assuming approval or automatically changing character mapping.
- `POST /jobs`: JSON + `Idempotency-Key`; must return the SAME remote job for repeated key/body submissions, including after caller timeout. Response `{job_id, status}`.
- `GET /jobs/{job_id}`: queued/running/succeeded/review_required/blocked/failed/cancelled. `production_pass` must be literal true for production use. `qc` is an object. `error` or `message` carries useful failure details.
- `POST /jobs/{job_id}/cancel`: JSON acknowledgement; cancellation is a request, UI polls actual resulting status.
- `GET /artifacts/{artifact_id}/content`: authenticated image bytes or MP4. Redirects are rejected to avoid forwarding bearer credentials to another host.

## Full request
Base user contract: operation, project_id, shot_id, character{id, version, orientation}, references{appearance_asset_id, environment_asset_id, master_frame_asset_id, motion_asset_id, ...}, direction{action,camera,preserve_environment}, output{width,height,fps,frame_count}, budget{max_generation_attempts:1}.

**Proposed extensions requiring agreement in the server implementation:**
- `consistency_sheet`: full stored object, not summarized/truncated (anchor, text, version, locks)
- `scene`: full original narration, dialogue and visual descriptions from that segment
- `lora_ids`: registered LoRA identifiers
- `direction.action`: full continuity prompt; optional operator camera/composition fields preserved
- For successful artifact selection, `role` must be `output`, `final` or `production`; `preview` is never accepted even if a file exists

Studio must reject unprepared/unregistered character assets, unsupported frame counts/resolutions, missing required references and budget excess with explicit messages. Current adapter asks for 480×832, 16fps and frame_count derived from segment duration; the server must declare/validate its worker limits. Adjust before live generation if workers only support fixed frame counts (e.g. 49).

## Story reference mapping
`studio` stores common character/references/direction/lora_ids. `studio_segments` maps zero-based segment index strings to shot-specific overrides, e.g. an approved back-three-quarter view or motion driver. Uploaded approved frame becomes master_frame_asset_id for video, character reference becomes appearance_asset_id for images. Existing environment/motion/mask reference keys remain intact. Upload responses show stable IDs for mapping; arbitrary sheet upload alone is never claimed production-ready.

## Job safety and recovery
Full payload hash includes all text/versions/references and Studio base URL. Job records are persisted before remote submission. Same app-job replay uses the same idempotency key; retries of pending/review/QC-blocked requests reuse the retained remote ID. Explicit regeneration after a successful job creates a fresh attempt. Deadline/network failures never mark unknown remote work approved. QC is resolved at Studio; Poll Studio refreshes status, and Retry Production integrates only eligible output. Stop attempts to cancel the active remote job.

## Verification boundary
Tests exercise mocked HTTP responses and real Mongo persistence with isolated test rows, including review-required rejection, strict QC boolean, replay keys and artifacts. A live end-to-end server27 test is pending installation, credentials and final contract agreement. No production Studio result is fabricated.