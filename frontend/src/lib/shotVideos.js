// Pure helpers for the shot video-generation UI (Phase 3B). Framework-free so
// tests can exercise them under node --test, like the other src/lib modules.

import { isJobRunning } from './shotImages.js'

export { isJobRunning }

/**
 * View-model for one shot video-generation record. Prefers a live job from
 * the poller over the persisted record so a page reload recovers state.
 */
export function shotVideoViewModel(generation, liveJob) {
  const job = liveJob
    ? { status: liveJob.status, error: liveJob.error, outputs: liveJob.outputs }
    : null
  const status = job?.status || generation?.status || 'submitted'
  const filename = generation?.output?.filename || job?.outputs?.[0]?.filename || null
  return {
    jobId: generation?.job_id || null,
    status,
    running: isJobRunning(status),
    completed: status === 'completed' && !!filename,
    failed: status === 'failed',
    filename,
    error: job?.error || generation?.error || null,
    sourceImageId: generation?.source_image_id || null,
  }
}

/**
 * Ordered video history for the shot: newest first, each flagged whether it
 * is the shot's currently selected video.
 */
export function shotVideoHistory(shot) {
  if (!shot) return []
  const videos = shot.videos || []
  const selectedId = videos.find((v) => v.selected)?.id || null
  return videos
    .slice()
    .sort((a, b) => String(b.created_at || '').localeCompare(String(a.created_at || '')))
    .map((v) => ({ ...v, is_selected: v.id === selectedId }))
}
