import { History } from 'lucide-react'
import StudioShell from '../components/StudioShell'
import QueuePanel from '../components/QueuePanel'
import { EmptyState } from '../components/EmptyState'
import { formatBytes, formatDate } from '../lib/format'

export function HistoryPage({ jobs, cancelJob, removeJob, retryJob, connection }) {
  if (!jobs.length) {
    return (
      <StudioShell title="History" description="Past and present generation jobs on this backend.">
        <EmptyState
          icon={History}
          title="No job history yet"
          description="Connect a backend and run a generation — each job with its parameters, status and outputs is listed here."
        />
      </StudioShell>
    )
  }

  return (
    <StudioShell title="History" description="Past and present generation jobs on this backend.">
      <div className="space-y-3">
        {jobs.map((job) => (
          <article key={job.job_id} className="rounded-2xl border border-border bg-card-bg p-4">
            <header className="flex flex-wrap items-center justify-between gap-2">
              <div className="min-w-0">
                <h2 className="truncate text-sm font-medium">{job.params?.prompt || 'Untitled job'}</h2>
                <p className="mt-0.5 text-xs text-muted">
                  {job.type || 'job'} · created {formatDate(job.created_at)} ·{' '}
                  {job.outputs?.length
                    ? job.outputs.map((o) => `${o.width || '?'}×${o.height || '?'} ${formatBytes(o.size_bytes)}`).join(', ')
                    : 'no outputs'}
                </p>
              </div>
              <span
                className={`shrink-0 rounded-md px-2 py-0.5 text-xs ${
                  job.status === 'completed'
                    ? 'bg-green-500/10 text-green-400'
                    : job.status === 'failed'
                      ? 'bg-red-500/10 text-red-400'
                      : 'bg-border text-secondary'
                }`}
              >
                {job.status}
              </span>
            </header>
            {job.error ? <p className="mt-2 text-xs text-red-400">{job.error}</p> : null}
            <div className="mt-3 flex flex-wrap gap-2 text-xs">
              {job.params
                ? Object.entries(job.params)
                    .filter(([, v]) => v !== undefined && v !== null && v !== '')
                    .slice(0, 8)
                    .map(([k, v]) => (
                      <span key={k} className="rounded-md bg-panel-bg px-1.5 py-0.5 text-muted">
                        {k}: {String(v)}
                      </span>
                    ))
                : null}
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              {['queued', 'loading_model', 'generating', 'processing', 'saving'].includes(job.status) ? (
                <button
                  type="button"
                  onClick={() => cancelJob(job.job_id)}
                  className="min-h-[44px] rounded-xl border border-border px-3 text-xs text-secondary transition-colors duration-150 hover:border-red-500/50 hover:text-red-400"
                >
                  Cancel
                </button>
              ) : null}
              {job.status === 'failed' || job.status === 'cancelled' ? (
                <button
                  type="button"
                  onClick={() => retryJob(job)}
                  className="min-h-[44px] rounded-xl border border-border px-3 text-xs text-secondary transition-colors duration-150 hover:text-primary"
                >
                  Retry
                </button>
              ) : null}
              <button
                type="button"
                onClick={() => removeJob(job.job_id)}
                className="min-h-[44px] rounded-xl border border-border px-3 text-xs text-secondary transition-colors duration-150 hover:text-text"
              >
                Remove
              </button>
            </div>
          </article>
        ))}
      </div>
    </StudioShell>
  )
}

export default HistoryPage
