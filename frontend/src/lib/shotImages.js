// Pure helpers for the shot image-generation UI (Phase 3A). Kept framework-free
// so tests/shotImages.test.js can exercise them under node --test, like the
// other src/lib modules.

// Job statuses come from the backend's JobManager STATUS_ORDER.
const RUNNING = ['queued', 'loading_model', 'generating', 'processing', 'saving']

export function isJobRunning(status) {
  return RUNNING.includes(status)
}

/**
 * Pick the job view-model for a shot generation record. Prefers a live job
 * from the poller over the persisted record so a page reload recovers state.
 */
export function generationViewModel(generation, liveJob) {
  const job = liveJob || (generation?.job_id ? { job_id: generation.job_id, status: generation.status, error: generation.error } : null)
  const status = job?.status || generation?.status || 'submitted'
  return {
    jobId: generation?.job_id || job?.job_id || null,
    status,
    running: isJobRunning(status),
    completed: status === 'completed' && !!(generation?.output?.filename || job?.outputs?.[0]?.filename),
    failed: status === 'failed',
    filename: generation?.output?.filename || job?.outputs?.[0]?.filename || null,
    error: job?.error || generation?.error || null,
    prompt: generation?.prompt || '',
  }
}

/**
 * Ordered history for the shot: newest generation first, with each image
 * flagged whether it is the shot's currently selected visual.
 */
export function shotImageHistory(shot) {
  if (!shot) return []
  const selectedId = (shot.images || []).find((i) => i.selected)?.id || null
  return (shot.images || [])
    .slice()
    .sort((a, b) => String(b.created_at || '').localeCompare(String(a.created_at || '')))
    .map((img) => ({ ...img, is_selected: img.id === selectedId }))
}
