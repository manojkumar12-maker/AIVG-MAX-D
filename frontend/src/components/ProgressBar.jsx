import { formatElapsed } from '../lib/format'

/**
 * Determinate-only progress bar. Never invents a percentage: when `progress`
 * is null or undefined it renders the status label and elapsed time instead.
 */
export function ProgressBar({ progress, stage, status, startedAt }) {
  const hasProgress = typeof progress === 'number' && Number.isFinite(progress)
  const pct = hasProgress ? Math.min(100, Math.max(0, Math.round(progress * 100))) : null

  return (
    <div className="w-full" role="status" aria-live="polite">
      {hasProgress ? (
        <div
          className="h-2 w-full overflow-hidden rounded-full bg-border"
          role="progressbar"
          aria-valuenow={pct}
          aria-valuemin={0}
          aria-valuemax={100}
        >
          <div
            className="h-full rounded-full bg-gradient-to-r from-primary to-accent transition-[width] duration-200"
            style={{ width: `${pct}%` }}
          />
        </div>
      ) : (
        <div className="h-2 w-full overflow-hidden rounded-full bg-border">
          <div className="h-full w-1/3 animate-pulse rounded-full bg-gradient-to-r from-primary to-accent" />
        </div>
      )}
      <div className="mt-1 flex items-center justify-between text-xs text-secondary">
        <span>{stage || status || 'Working…'}</span>
        <span>
          {pct !== null ? `${pct}%` : null}
          {startedAt ? ` · ${formatElapsed(startedAt)}` : ''}
        </span>
      </div>
    </div>
  )
}

export default ProgressBar
