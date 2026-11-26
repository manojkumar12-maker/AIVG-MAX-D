# Phase 5.3 — Dialogue pipeline: findings & implementation report

Date: 2026-11-26. Audit first, then implementation, tests and verification.

## Verification (this turn)
- `python -m pytest backend/tests -q`: 93 passed (81 before, +12 dialogue tests).
- `npm test`: pass 45 / fail 0; `npm run build`: clean.
- Bugs found and fixed during verification: a self-deadlock (calling
  `add_version`/`get_artifact` while holding the store's non-reentrant lock)
  and test-side wrong route/response-shape assumptions.
- Targeted re-investigation (Phase 5.3 verification spec): the two previously
  failing tests (`test_replace_dialogue_never_touches_approved`,
  `test_update_dialogue_line_partial`) pass now — both failed mid-development
  on the lock self-deadlock, whose fix is in place; `llm.py` has zero diff;
  locking audit clean (all dialogue store methods use the lock-free
  `_artifact_entry` under the lock, `add_version` outside); `_write` is atomic;
  API-level idempotent re-extraction now covered by a test asserting exactly
  one dialogue version after a repeated extract.

## Source audit
The screenplay artifact (`creative.py`) carries no dialogue fields — spoken
text exists only inside scene `summary`/`purpose`/`continuity_notes`. Dialogue
is therefore LLM-assisted extraction with hard verbatim verification.

## 1. Current screenplay/artifact structure

The screenplay artifact (`creative.py:83`, validator at `creative.py:149`,
mock output `llm.py:97`) is JSON: `{"title", "logline", "scenes":
[{"number", "slugline", "location", "interior_exterior", "time_of_day",
"summary", "purpose", "characters" (names), "mood",
"estimated_duration_seconds", "story_beat", "continuity_notes"}]}`.

**There is no dialogue field anywhere in the schema** — no character-labeled
lines, no dialogue blocks, no narration. Spoken content can only appear inside
free-text `summary`/`purpose`/`continuity_notes`.

## 2. Existing approval/versioning behavior

`films.py:589-733`: every artifact kind has versions (`draft`/`approved`),
an `active` and an `approved_version`. `add_version` and `edit_artifact`
refuse to touch an approved artifact (must unapprove first), so approval can
never be silently replaced. Generic endpoints already exist:
`POST /api/films/{id}/artifacts/{kind}/approve` and `/unapprove`
(`main.py:652-664`), plus activate-version and edit. `ARTIFACT_KINDS`
(`films.py:24`) gates all of it.

## 3. Integration of dialogue extraction

Adding `"dialogue"` to `ARTIFACT_KINDS` reuses the entire versioning,
approval, edit and history system — no second store. Screenplay source is
referenced by artifact version. Project scenes link to screenplay scenes via
`scene["breakdown"]["number"]` (`apply_breakdown`, `films.py:736-762`);
scenes created manually have no such link and stay unresolved.

Because the source has no verbatim dialogue text, LLM-assisted extraction is
required, with a hard verification rule: every extracted line's text must
appear verbatim (whitespace/case-normalized) inside its scene's
summary/purpose/continuity_notes of the referenced screenplay version.
Unverifiable lines are dropped and reported — never invented or paraphrased.

## 4. Proposed minimal dialogue structure

Stored as the `dialogue` artifact's data:
`{"source_screenplay_version": int, "lines": [...]}` with each line:
`{id (deterministic: hash of source version + scene number + order +
normalized text), scene_number, scene_id, character_id, speaker_name, text,
line_type ("dialogue"|"voiceover"), delivery_note, emotion, notes,
speaker_resolved}`. Emotion from a fixed set + blank; delivery is a free
annotation. Speaker resolution matches continuity canon names exactly;
unresolved stays empty and is reported.

## 5. Ambiguities / blockers

- The screenplay cannot supply verbatim quotes; extraction therefore depends
  on quotes being present in summary text. Lines without a verbatim source
  span cannot be extracted — this is a limitation of the current format, not
  of the pipeline. Fixing it belongs to screenplay generation (out of scope).
- "Custom emotion" is allowed as a short single-word field; anything else is
  rejected rather than stored unchecked.
- Approval gate: `approve` for kind `dialogue` must reject when any line has
  an unresolved scene/speaker reference (new small branch in the generic
  endpoint).
