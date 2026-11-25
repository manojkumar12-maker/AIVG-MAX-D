import { useEffect, useState } from 'react'
import { Settings as SettingsIcon, Loader2 } from 'lucide-react'
import StudioShell from '../components/StudioShell'
import ConnectionPanel from '../components/ConnectionPanel'
import backendClient from '../services/backendClient'
import { friendlyError } from '../services/generationService'
import { useConnection } from '../hooks/useConnection'
import { EmptyState } from '../components/EmptyState'

export function SettingsPage({ connection, isConnected }) {
  const conn = connection || useConnection()
  const [settings, setSettings] = useState(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const [saved, setSaved] = useState(false)

  const connected = conn.isConnected

  useEffect(() => {
    let cancelled = false
    if (!connected) {
      setSettings(null)
      return undefined
    }
    backendClient
      .getSettings()
      .then((s) => {
        if (!cancelled) setSettings(s)
      })
      .catch((err) => {
        if (!cancelled) setError(friendlyError(err))
      })
    return () => {
      cancelled = true
    }
  }, [connected])

  const save = async (patch) => {
    const next = { ...settings, ...patch }
    setSettings(next)
    setSaving(true)
    setSaved(false)
    setError(null)
    try {
      const res = await backendClient.saveSettings({
        save_to_drive: Boolean(next.save_to_drive),
        low_vram: Boolean(next.low_vram),
        unload_after_job: Boolean(next.unload_after_job),
      })
      setSettings(res || next)
      setSaved(true)
    } catch (err) {
      setError(friendlyError(err))
    } finally {
      setSaving(false)
    }
  }

  const toggles = [
    {
      key: 'save_to_drive',
      label: 'Save outputs to Google Drive',
      description: 'Copy finished images and videos to your Drive when the notebook is connected to one.',
    },
    {
      key: 'low_vram',
      label: 'Low VRAM mode',
      description: 'Trade speed for stability on GPUs with limited memory.',
    },
    {
      key: 'unload_after_job',
      label: 'Unload model after each job',
      description: 'Free VRAM between jobs. Slower, but avoids out-of-memory on model switches.',
    },
  ]

  return (
    <StudioShell title="Settings" description="Backend preferences and connection settings.">
      <div className="grid gap-4 lg:grid-cols-2">
        <ConnectionPanel connection={conn} />

        <div className="space-y-3 rounded-2xl border border-border bg-card-bg p-4">
          <div className="flex items-center gap-2">
            <SettingsIcon size={16} className="text-primary" aria-hidden="true" />
            <h2 className="text-sm font-semibold">Backend settings</h2>
          </div>

          {!connected ? (
            <EmptyState
              title="Not connected"
              description="Connect a backend to read and change backend settings."
            />
          ) : settings === null && !error ? (
            <div className="flex items-center gap-2 p-4 text-sm text-secondary">
              <Loader2 size={16} className="animate-spin text-primary" aria-hidden="true" /> Loading settings…
            </div>
          ) : (
            <>
              {toggles.map((t) => (
                <label key={t.key} className="flex min-h-[44px] items-start gap-3 rounded-xl border border-border bg-panel-bg p-3 text-sm text-secondary">
                  <input
                    type="checkbox"
                    checked={Boolean(settings?.[t.key])}
                    onChange={(e) => save({ [t.key]: e.target.checked })}
                    disabled={saving}
                    className="mt-0.5 h-4 w-4 accent-primary"
                    title={saving ? 'Saving…' : t.label}
                  />
                  <span>
                    {t.label}
                    <span className="block text-xs text-muted">{t.description}</span>
                  </span>
                </label>
              ))}
              {saving ? <p className="text-xs text-muted">Saving…</p> : null}
              {saved ? <p className="text-xs text-green-400">Settings saved.</p> : null}
              {error ? (
                <p role="alert" className="text-xs text-red-400">
                  {error}
                </p>
              ) : null}
            </>
          )}
        </div>
      </div>
    </StudioShell>
  )
}

export default SettingsPage
