import test from 'node:test'
import assert from 'node:assert/strict'

import { isJobRunning, generationViewModel, shotImageHistory } from '../frontend/src/lib/shotImages.js'

test('isJobRunning matches the backend JobManager running statuses', () => {
  for (const s of ['queued', 'loading_model', 'generating', 'processing', 'saving']) {
    assert.equal(isJobRunning(s), true, s)
  }
  for (const s of ['completed', 'failed', 'cancelled', undefined]) {
    assert.equal(isJobRunning(s), false, String(s))
  }
})

test('generationViewModel prefers live job output and exposes failure', () => {
  const rec = { job_id: 'j1', status: 'submitted', prompt: 'p' }
  const running = generationViewModel(rec, { job_id: 'j1', status: 'generating' })
  assert.equal(running.running, true)
  assert.equal(running.completed, false)

  const done = generationViewModel(rec, { job_id: 'j1', status: 'completed', outputs: [{ filename: 'a.png' }] })
  assert.equal(done.completed, true)
  assert.equal(done.filename, 'a.png')

  const failed = generationViewModel({ ...rec, status: 'failed', error: 'boom' }, null)
  assert.equal(failed.failed, true)
  assert.equal(failed.error, 'boom')
  assert.equal(failed.completed, false)
})

test('shotImageHistory keeps every image and flags the selected one', () => {
  const shot = {
    images: [
      { id: 'a', created_at: '2026-01-01T00:00:00Z', selected: false },
      { id: 'b', created_at: '2026-01-02T00:00:00Z', selected: true },
    ],
  }
  const history = shotImageHistory(shot)
  assert.equal(history.length, 2) // nothing dropped
  assert.deepEqual(history.map((i) => i.id), ['b', 'a']) // newest first
  assert.equal(history[0].is_selected, true)
  assert.equal(history[1].is_selected, false)
  assert.deepEqual(shotImageHistory(null), [])
})
