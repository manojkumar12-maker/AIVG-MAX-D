# Phase 5.2 — Audio & Voice Data Foundation: findings

Date: 2026-11-26. Scope: data model + API only (no TTS, upload, playback).

## What was built
- `backend/adapter/audio.py`: pure normalization for Audio Bible (5 fields),
  per-character voice identity (8 fields + free-form `voice_id`), and audio cues
  (category in dialogue/ambience/foley/sfx/music; status planned/approved).
- `backend/adapter/films.py`: `audio` block in project.json; edit-only updates
  under the existing atomic write + lock; voice stored on continuity characters
  without touching visual canon; cue refs validated against real ids.
- `backend/adapter/main.py`: 7 auth-gated endpoints (bible GET/PUT, voice
  GET/PUT, cues GET/POST/PUT); 401/404/422 matching Phase 4 conventions.
- `backend/tests/test_audio.py`: 11 tests.

## Verification
- Baseline pytest: 70 passed → after change: 81 passed.
- `npm test`: pass 45 / fail 0 (npm process hangs after results; pre-existing).
- `npm run build`: clean.

## Design decisions and limitations
- Voice ids are free-form strings; no provider or model is bound (copyright /
  local-first policy). No voice cloning; upload stays image-only.
- Cue references are validated, never invented; partial cue updates never blank
  unsent fields; 200-cue cap per project.
- Not in scope and not verified: browser UI (no frontend surface this phase);
  no GPU or audio files are touched by this phase, so there are no generated
  artifacts to save — the tests are the reproducible output.
