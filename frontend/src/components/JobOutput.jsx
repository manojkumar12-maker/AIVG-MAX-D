import { AlertTriangle, Loader2 } from 'lucide-react'
import backendClient, { getToken } from '../services/backendClient'
import ProgressBar from './ProgressBar'
import { formatBytes } from '../lib/format'

export function JobOutput({ job }) {
  if (!job) return null
  const running = ['queued', 'loading_model', 'generating', 'processing', 'saving'].includes(job.status)

  return (
    <div className="space-y-3 rounded-2xl border border-border bg-card-bg p-4">
      {running ? (
        <div className="flex items-start gap-3">
          <Loader2 size={18} className="mt-0.5 animate-spin text-primary" aria-hidden="true" />
          <div className="min-w-0 flex-1">
            <ProgressBar
              progress={job.progress}
              stage={job.stage}
              status={job.status === 'queued' ? 'Waiting in queue' : job.status}
              startedAt={job.started_at || job.created_at}
            />
          </div>
        </div>
      ) : null}

      {job.status === 'failed' ? (
        <div className="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/5 p-3 text-sm text-red-300" role="alert">
          <AlertTriangle size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
          <div>
            <p>{job.error || 'Generation failed.'}</p>
          </div>
        </div>
      ) : null}

      {job.status === 'cancelled' ? <p className="text-sm text-secondary">This job was cancelled.</p> : null}

      {job.outputs?.length ? (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {job.outputs.map((out) => (
            <figure key={out.filename} className="overflow-hidden rounded-xl border border-border bg-panel-bg">
              {out.type === 'video' ? (
                <video src={backendClient.outputUrl(out.filename, getToken())} controls className="w-full bg-black" />
              ) : (
                <img
                  src={backendClient.outputUrl(out.filename, getToken())}
                  alt={out.prompt || 'Generated output'}
                  className="w-full object-contain"
                />
              )}
              <figcaption className="flex items-center justify-between gap-2 p-2 text-xs text-muted">
                <span className="truncate">{out.filename}</span>
                <span className="shrink-0">{formatBytes(out.size_bytes)}</span>
              </figcaption>
            </figure>
          ))}
        </div>
      ) : null}
    </div>
  )
}

export default JobOutput
