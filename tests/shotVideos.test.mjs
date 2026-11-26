import test from 'node:test'
import assert from 'node:assert/strict'

import { isJobRunning, shotVideoViewModel, shotVideoHistory } from '../frontend/src/lib/shotVideos.js'

test('isJobRunning matches the backend JobManager running statuses', () => {
  for (const s of ['queued', 'loading_model', 'generating', 'processing', 'saving']) {
    assert.equal(isJobRunning(s), true, s)
  }
  for (const s of ['completed', 'failed', 'cancelled', undefined]) {
    assert.equal(isJobRunning(s), false, String(s))
  }
})

test('shotVideoViewModel prefers live job output and exposes failure', () => {
  const rec = { job_id: 'jv1', status: 'submitted', source_image_id: 'img1' }
  const running = shotVideoViewModel(rec, { status: 'generating' })
  assert.equal(running.running, true)
  assert.equal(running.completed, false)
  assert.equal(running.sourceImageId, 'img1')

  const done = shotVideoViewModel(rec, { status: 'completed', outputs: [{ filename: 'a.mp4' }] })
  assert.equal(done.completed, true)
  assert.equal(done.filename, 'a.mp4')

  const failed = shotVideoViewModel({ ...rec, status: 'failed', error: 'boom' }, null)
  assert.equal(failed.failed, true)
  assert.equal(failed.error, 'boom')
  assert.equal(failed.completed, false)
})

test('shotVideoHistory keeps every video and flags the selected one', () => {
  const shot = {
    videos: [
      { id: 'a', created_at: '2026-01-01T00:00:00Z', selected: false },
      { id: 'b', created_at: '2026-01-02T00:00:00Z', selected: true },
    ],
  }
  const history = shotVideoHistory(shot)
  assert.equal(history.length, 2) // nothing dropped
  assert.deepEqual(history.map((v) => v.id), ['b', 'a']) // newest first
  assert.equal(history[0].is_selected, true)
  assert.equal(history[1].is_selected, false)
  assert.deepEqual(shotVideoHistory(null), [])
})
