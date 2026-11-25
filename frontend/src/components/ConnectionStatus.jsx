import { CONNECTION_STATES } from '../hooks/useConnection'

const DOT_STYLES = {
  [CONNECTION_STATES.DISCONNECTED]: 'bg-muted',
  [CONNECTION_STATES.CONNECTING]: 'bg-yellow-400 animate-pulse',
  [CONNECTION_STATES.CONNECTED]: 'bg-green-400',
  [CONNECTION_STATES.UNAVAILABLE]: 'bg-red-400',
  [CONNECTION_STATES.AUTH_ERROR]: 'bg-red-400',
}

const LABELS = {
  [CONNECTION_STATES.DISCONNECTED]: 'Disconnected',
  [CONNECTION_STATES.CONNECTING]: 'Connecting…',
  [CONNECTION_STATES.CONNECTED]: 'Connected',
  [CONNECTION_STATES.UNAVAILABLE]: 'Backend unavailable',
  [CONNECTION_STATES.AUTH_ERROR]: 'Authentication error',
}

export function ConnectionStatus({ status, error, onOpen }) {
  return (
    <button
      type="button"
      onClick={onOpen}
      title={error || LABELS[status] || 'Connection status'}
      className="flex w-full items-center gap-2 rounded-xl border border-transparent px-3 py-2.5 text-left text-sm text-secondary transition-colors duration-150 hover:bg-card-bg hover:text-text disabled:cursor-not-allowed"
      disabled={!onOpen}
    >
      <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${DOT_STYLES[status] || 'bg-muted'}`} aria-hidden="true" />
      <span className="truncate">{LABELS[status] || 'Disconnected'}</span>
    </button>
  )
}

export default ConnectionStatus
