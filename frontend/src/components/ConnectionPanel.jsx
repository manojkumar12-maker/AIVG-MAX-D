import { useEffect, useState } from 'react'
import { Plug, PlugZap, ShieldCheck, Loader2 } from 'lucide-react'
import { useConnection, CONNECTION_STATES } from '../hooks/useConnection'
import ConnectionStatus from './ConnectionStatus'
import { useLocalStorage } from '../hooks/useLocalStorage'
import backendClient from '../services/backendClient'

const LABELS = {
  [CONNECTION_STATES.DISCONNECTED]: 'Disconnected',
  [CONNECTION_STATES.CONNECTING]: 'Connecting…',
  [CONNECTION_STATES.CONNECTED]: 'Connected',
  [CONNECTION_STATES.UNAVAILABLE]: 'Backend unavailable',
  [CONNECTION_STATES.AUTH_ERROR]: 'Authentication error',
}

export function ConnectionPanel({ connection }) {
  const { status, health, error, connect, disconnect, checkHealth } = connection
  const [baseUrl, setBaseUrl] = useLocalStorage('ogai.connectionForm.url', '')
  const [token, setToken] = useState('')
  const [rememberUrl, setRememberUrl] = useLocalStorage('ogai.connectionForm.rememberUrl', true)
  const [rememberToken, setRememberToken] = useState(false)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState(null)
  const [counts, setCounts] = useState({ models: null, workflows: null })

  useEffect(() => {
    if (status !== CONNECTION_STATES.CONNECTED) return
    let cancelled = false
    const load = async () => {
      const [models, workflows] = await Promise.all([
        backendClient.models().catch(() => null),
        backendClient.workflows().catch(() => null),
      ])
      if (cancelled) return
      setCounts({
        models: Array.isArray(models?.models) ? models.models.length : null,
        workflows: Array.isArray(workflows?.workflows) ? workflows.workflows.length : null,
      })
    }
    load()
    return () => {
      cancelled = true
    }
  }, [status, health])

  const busy = status === CONNECTION_STATES.CONNECTING

  const handleConnect = async () => {
    setTestResult(null)
    await connect({ baseUrl, token, rememberUrl, rememberToken })
  }

  const handleTest = async () => {
    setTesting(true)
    setTestResult(null)
    try {
      const data = await checkHealth()
      setTestResult(data ? 'Connection OK — backend reachable.' : 'Could not reach the backend.')
    } finally {
      setTesting(false)
    }
  }

  const connected = status === CONNECTION_STATES.CONNECTED

  return (
    <div className="space-y-3 rounded-2xl border border-border bg-card-bg p-4">
      <div className="flex items-center gap-2">
        <Plug size={16} className="text-primary" aria-hidden="true" />
        <h2 className="text-sm font-semibold">Backend Connection</h2>
      </div>

      <ConnectionStatus status={status} error={error} />

      <label className="block">
        <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-muted">Backend URL</span>
        <input
          type="url"
          inputMode="url"
          value={baseUrl}
          onChange={(e) => setBaseUrl(e.target.value)}
          placeholder="https://xxxx.trycloudflare.com"
          disabled={connected || busy}
          title={connected ? 'Disconnect before changing the URL' : 'Your Colab tunnel URL'}
          className="min-h-[44px] w-full rounded-xl border border-border bg-panel-bg px-3 text-sm text-text placeholder:text-muted transition-colors duration-150 focus:border-primary focus:outline-none disabled:opacity-50"
        />
      </label>

      <label className="block">
        <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-muted">Session token</span>
        <input
          type="password"
          value={token}
          onChange={(e) => setToken(e.target.value)}
          placeholder="Leave empty if the backend has no token"
          disabled={connected || busy}
          title={connected ? 'Disconnect before changing the token' : 'Token printed by the notebook, if any'}
          autoComplete="off"
          className="min-h-[44px] w-full rounded-xl border border-border bg-panel-bg px-3 text-sm text-text placeholder:text-muted transition-colors duration-150 focus:border-primary focus:outline-none disabled:opacity-50"
        />
      </label>

      <label className="flex min-h-[44px] items-center gap-2 text-sm text-secondary">
        <input
          type="checkbox"
          checked={rememberUrl}
          onChange={(e) => setRememberUrl(e.target.checked)}
          disabled={connected || busy}
          className="h-4 w-4 accent-primary"
        />
        Save backend URL on this device
      </label>

      <label className="flex min-h-[44px] items-start gap-2 text-sm text-secondary">
        <input
          type="checkbox"
          checked={rememberToken}
          onChange={(e) => setRememberToken(e.target.checked)}
          disabled={connected || busy}
          className="mt-0.5 h-4 w-4 accent-primary"
        />
        <span>
          Keep token for this browser session
          <span className="block text-xs text-muted">
            While checked, the token is stored in sessionStorage and cleared when you close this tab.
          </span>
        </span>
      </label>

      {error ? (
        <p role="alert" className="text-xs text-red-400">
          {error}
        </p>
      ) : null}

      <div className="grid grid-cols-2 gap-2">
        {connected ? (
          <button
            type="button"
            onClick={disconnect}
            className="col-span-2 min-h-[44px] rounded-xl border border-border bg-card-bg text-sm text-secondary transition-colors duration-150 hover:border-red-500/50 hover:text-red-400"
          >
            Disconnect
          </button>
        ) : (
          <button
            type="button"
            onClick={handleConnect}
            disabled={busy || !baseUrl.trim()}
            title={!baseUrl.trim() ? 'Enter your backend URL first' : 'Connect to the backend'}
            className="col-span-2 flex min-h-[44px] items-center justify-center gap-2 rounded-xl bg-primary text-sm font-medium text-app-bg transition-colors duration-150 hover:bg-primary-hover disabled:cursor-not-allowed disabled:opacity-50"
          >
            {busy ? <Loader2 size={16} className="animate-spin" aria-hidden="true" /> : <PlugZap size={16} aria-hidden="true" />}
            {busy ? 'Connecting…' : 'Connect'}
          </button>
        )}
        <button
          type="button"
          onClick={handleTest}
          disabled={testing || !baseUrl.trim()}
          title={!baseUrl.trim() ? 'Enter your backend URL first' : 'Check that the backend responds'}
          className="col-span-2 flex min-h-[44px] items-center justify-center gap-2 rounded-xl border border-border bg-card-bg text-sm text-secondary transition-colors duration-150 hover:text-text disabled:cursor-not-allowed disabled:opacity-50"
        >
          {testing ? <Loader2 size={16} className="animate-spin" aria-hidden="true" /> : <ShieldCheck size={16} aria-hidden="true" />}
          Test Connection
        </button>
      </div>

      {testResult ? <p className="text-xs text-secondary">{testResult}</p> : null}

      {connected && health ? (
        <dl className="mt-2 space-y-1.5 rounded-xl border border-border bg-panel-bg p-3 text-xs">
          <div className="flex justify-between gap-2">
            <dt className="text-muted">GPU</dt>
            <dd className="truncate text-secondary">{health.gpu_name || '—'}</dd>
          </div>
          <div className="flex justify-between gap-2">
            <dt className="text-muted">VRAM</dt>
            <dd className="text-secondary">{health.gpu_vram_gb ? `${health.gpu_vram_gb} GB` : '—'}</dd>
          </div>
          <div className="flex justify-between gap-2">
            <dt className="text-muted">ComfyUI</dt>
            <dd className={health.comfyui_online ? 'text-green-400' : 'text-red-400'}>
              {health.comfyui_online ? 'Online' : 'Offline'}
            </dd>
          </div>
          <div className="flex justify-between gap-2">
            <dt className="text-muted">Workflows</dt>
            <dd className="text-secondary">{counts.workflows ?? '—'}</dd>
          </div>
          <div className="flex justify-between gap-2">
            <dt className="text-muted">Models</dt>
            <dd className="text-secondary">{counts.models ?? '—'}</dd>
          </div>
          <div className="flex justify-between gap-2">
            <dt className="text-muted">Queue</dt>
            <dd className="text-secondary">
              {health.queue_size ?? '—'} queued · {health.active_jobs ?? '—'} active
            </dd>
          </div>
          {health.backend_version ? (
            <div className="flex justify-between gap-2">
              <dt className="text-muted">Version</dt>
              <dd className="truncate text-secondary">{health.backend_version}</dd>
            </div>
          ) : null}
        </dl>
      ) : null}
    </div>
  )
}

export default ConnectionPanel
