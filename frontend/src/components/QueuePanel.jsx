import { Ban, RotateCw, Trash2 } from 'lucide-react'
import { isRunning } from '../services/generationService'
import { formatElapsed } from '../lib/format'

const STATUS_LABELS = {
  queued: 'Waiting',
  loading_model: 'Loading model',
  generating: 'Generating',
  processing: 'Processing',
  saving: 'Saving',
  completed: 'Completed',
  failed: 'Failed',
  cancelled: 'Cancelled',
}

function groupOf(status) {
  if (status === 'queued') return 'waiting'
  if (isRunning(status)) return 'active'
  if (status === 'completed') return 'completed'
  if (status === 'failed') return 'failed'
  return 'cancelled'
}

export function QueuePanel({ jobs, onCancel, onRemove, onRetry }) {
  if (!jobs.length) {
    return (
      <div className="rounded-2xl border border-border bg-card-bg p-4 text-sm text-secondary">
        No jobs yet. Generate something and it will show up here.
      </div>
    )
  }

  const groups = { waiting: [], active: [], completed: [], failed: [], cancelled: [] }
  for (const job of jobs) groups[groupOf(job.status)].push(job)

  return (
    <div className="space-y-3">
      {Object.entries(groups).map(([key, list]) =>
        list.length ? (
          <section key={key}>
            <h3 className="mb-1.5 text-xs font-medium uppercase tracking-wide text-muted">
              {key} ({list.length})
            </h3>
            <ul className="space-y-1.5">
              {list.map((job) => (
                <li
                  key={job.job_id}
                  className="flex items-center gap-2 rounded-xl border border-border bg-card-bg p-2.5 text-sm"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="truncate text-secondary">{job.params?.prompt || 'Untitled job'}</span>
                      <span className="shrink-0 rounded-md bg-panel-bg px-1.5 py-0.5 text-xs text-muted">
                        {STATUS_LABELS[job.status] || job.status}
                      </span>
                    </div>
                    <div className="mt-0.5 text-xs text-muted">
                      {job.type || 'job'} · {formatElapsed(job.created_at) || ''} ·{' '}
                      {job.error ? 'Error' : job.outputs?.length ? `${job.outputs.length} output(s)` : 'No outputs yet'}
                    </div>
                  </div>
                  <div className="flex shrink-0 items-center gap-1">
                    {isRunning(job.status) ? (
                      <button
                        type="button"
                        onClick={() => onCancel(job.job_id)}
                        title="Cancel this job"
                        aria-label="Cancel job"
                        className="flex h-11 w-11 items-center justify-center rounded-lg text-secondary transition-colors duration-150 hover:bg-red-500/10 hover:text-red-400"
                      >
                        <Ban size={16} aria-hidden="true" />
                      </button>
                    ) : null}
                    {job.status === 'failed' || job.status === 'cancelled' ? (
                      <button
                        type="button"
                        onClick={() => onRetry(job)}
                        title="Retry this job with the same settings"
                        aria-label="Retry job"
                        className="flex h-11 w-11 items-center justify-center rounded-lg text-secondary transition-colors duration-150 hover:bg-primary/10 hover:text-primary"
                      >
                        <RotateCw size={16} aria-hidden="true" />
                      </button>
                    ) : null}
                    {!isRunning(job.status) ? (
                      <button
                        type="button"
                        onClick={() => onRemove(job.job_id)}
                        title="Remove this job from the queue list"
                        aria-label="Remove job"
                        className="flex h-11 w-11 items-center justify-center rounded-lg text-secondary transition-colors duration-150 hover:bg-border hover:text-text"
                      >
                        <Trash2 size={16} aria-hidden="true" />
                      </button>
                    ) : null}
                  </div>
                </li>
              ))}
            </ul>
          </section>
        ) : null
      )}
    </div>
  )
}

export default QueuePanel
