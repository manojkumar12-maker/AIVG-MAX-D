import { Cpu, ExternalLink, AlertTriangle } from 'lucide-react'
import StudioShell from '../components/StudioShell'
import { EmptyState } from '../components/EmptyState'
import { formatBytes } from '../lib/format'

export function ModelsPage({ connection, models, loading }) {
  if (!connection.isConnected) {
    return (
      <StudioShell title="Models" description="Models installed on the connected backend.">
        <EmptyState
          icon={Cpu}
          title="Not connected"
          description="Connect a backend to see which models are installed and how much VRAM they need."
        />
      </StudioShell>
    )
  }

  if (loading) {
    return (
      <StudioShell title="Models" description="Models installed on the connected backend.">
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-24 animate-pulse rounded-2xl border border-border bg-card-bg" />
          ))}
        </div>
      </StudioShell>
    )
  }

  if (!models.length) {
    return (
      <StudioShell title="Models" description="Models installed on the connected backend.">
        <EmptyState
          icon={Cpu}
          title="No models reported"
          description="The backend did not report any models. Make sure the notebook finished installing models, then refresh the connection."
        />
      </StudioShell>
    )
  }

  return (
    <StudioShell title="Models" description="Models installed on the connected backend.">
      <div className="space-y-3">
        {models.map((m) => (
          <article key={m.id} className="rounded-2xl border border-border bg-card-bg p-4">
            <header className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-sm font-medium">{m.name || m.id}</h2>
              <span
                className={`rounded-md px-2 py-0.5 text-xs ${
                  m.installed ? 'bg-green-500/10 text-green-400' : 'bg-yellow-500/10 text-yellow-400'
                }`}
              >
                {m.installed ? 'Installed' : 'Not installed'}
              </span>
            </header>
            <dl className="mt-3 grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
              <div>
                <dt className="text-muted">Type</dt>
                <dd className="text-secondary">{m.type}</dd>
              </div>
              <div>
                <dt className="text-muted">VRAM</dt>
                <dd className="text-secondary">{m.vram_gb ? `${m.vram_gb} GB` : '—'}</dd>
              </div>
              <div>
                <dt className="text-muted">Disk</dt>
                <dd className="text-secondary">{m.disk_gb ? `${m.disk_gb} GB` : formatBytes(m.disk_bytes)}</dd>
              </div>
              <div>
                <dt className="text-muted">License</dt>
                <dd className="text-secondary">
                  {m.license_url ? (
                    <a href={m.license_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-primary hover:underline">
                      {m.license || 'View'} <ExternalLink size={11} aria-hidden="true" />
                    </a>
                  ) : (
                    m.license || '—'
                  )}
                </dd>
              </div>
            </dl>
            {Array.isArray(m.recommended_for) && m.recommended_for.length ? (
              <div className="mt-3 flex flex-wrap gap-1.5">
                {m.recommended_for.map((r) => (
                  <span key={r} className="rounded-md bg-panel-bg px-1.5 py-0.5 text-xs text-muted">
                    {r}
                  </span>
                ))}
              </div>
            ) : null}
            {!m.installed ? (
              <p className="mt-3 flex items-start gap-1.5 text-xs text-yellow-300">
                <AlertTriangle size={13} className="mt-0.5 shrink-0" aria-hidden="true" />
                Not installed. Install this model from the notebook to use it in generation.
              </p>
            ) : null}
          </article>
        ))}
      </div>
    </StudioShell>
  )
}

export default ModelsPage
