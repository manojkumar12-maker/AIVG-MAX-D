import { useEffect, useMemo, useState } from 'react'
import { Clock, ImageIcon, Loader2, RefreshCw, Sparkles } from 'lucide-react'
import backendClient, { getToken } from '../services/backendClient'
import { JobOutput } from '../components/JobOutput'
import { generationViewModel, shotImageHistory } from '../lib/shotImages'

/**
 * Image-generation area for one storyboard shot. Submits through the
 * existing /api/generate pipeline (JobManager), polls that job with the
 * existing listJobs endpoint, and attaches the finished output back onto
 * the shot so history is preserved.
 */
export default function ShotImagePanel({ film, scene, shot, onChanged, disabled }) {
  const [promptDraft, setPromptDraft] = useState('')
  const [negativeDraft, setNegativeDraft] = useState('')
  const [dirty, setDirty] = useState(false)
  const [meta, setMeta] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    setPromptDraft(shot.prompt || '')
    setNegativeDraft(shot.params?.negative_prompt || '')
    setDirty(false)
    let live = true
    backendClient.shotPrompt(film.id, scene.id, shot.id)
      .then((data) => { if (live) setMeta(data) })
      .catch(() => { if (live) setMeta(null) })
    return () => { live = false }
  }, [film.id, scene.id, shot.id, shot.prompt, shot.params])

  const generations = shot.generations || []
  const latest = generations[generations.length - 1]
  const view = generationViewModel(latest, null)
  const history = shotImageHistory(shot)
  const activeJobId = view.running ? view.jobId : null

  // Recover a running job after page reload: poll it and attach when done.
  useEffect(() => {
    if (!activeJobId) return
    let cancelled = false
    const tick = async () => {
      try {
        const job = await backendClient.getJob(activeJobId)
        if (cancelled) return
        if (job.status === 'completed' || job.status === 'failed' || job.status === 'cancelled') {
          await backendClient.attachShotJob(film.id, scene.id, shot.id, activeJobId)
          onChanged?.()
          return
        }
      } catch {
        // backend blip — keep polling until unmounted
      }
      if (!cancelled) timer = setTimeout(tick, 2500)
    }
    let timer = setTimeout(tick, 2500)
    return () => { cancelled = true; clearTimeout(timer) }
  }, [activeJobId, film.id, scene.id, shot.id, onChanged])

  const generate = async () => {
    setSubmitting(true)
    setError(null)
    try {
      const payload = { prompt: promptDraft, negative_prompt: negativeDraft }
      await backendClient.generateShotImage(film.id, scene.id, shot.id, payload)
      onChanged?.()
    } catch (err) {
      setError(err)
    } finally {
      setSubmitting(false)
    }
  }

  const retry = () => generate()

  return (
    <section className="space-y-3 rounded-2xl border border-border bg-card-bg p-4" aria-label={`Image generation for shot ${shot.id}`}>
      <div className="flex items-center justify-between gap-2">
        <h4 className="flex items-center gap-2 text-sm font-medium">
          <ImageIcon size={14} className="text-muted" /> Shot image
        </h4>
        {meta?.missing?.length > 0 && (
          <span className="rounded-md bg-white/5 px-2 py-0.5 text-[11px] text-muted" title={meta.missing.join(', ')}>
            missing: {meta.missing.join(', ')}
          </span>
        )}
      </div>

      <label className="block space-y-1">
        <span className="text-xs text-muted">Prompt {dirty && <span className="text-primary">(edited)</span>}</span>
        <textarea
          value={promptDraft}
          onChange={(e) => { setPromptDraft(e.target.value); setDirty(true) }}
          rows={3}
          className="w-full rounded-xl border border-border bg-panel-bg p-3 text-sm"
          placeholder={meta?.prompt || 'Describe the image for this shot'}
        />
      </label>
      <label className="block space-y-1">
        <span className="text-xs text-muted">Negative prompt</span>
        <input
          value={negativeDraft}
          onChange={(e) => { setNegativeDraft(e.target.value); setDirty(true) }}
          className="w-full rounded-xl border border-border bg-panel-bg px-3 py-2 text-sm"
          placeholder="Optional"
        />
      </label>
      {!dirty && meta?.context_used?.length > 0 && (
        <p className="text-[11px] text-muted">Context added from Film Bible: {meta.context_used.join(', ')}</p>
      )}

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          disabled={disabled || submitting || view.running || !promptDraft.trim()}
          onClick={generate}
          className="inline-flex items-center gap-1 rounded-lg bg-primary/20 px-3 py-1.5 text-xs text-primary disabled:opacity-40"
        >
          {submitting || view.running ? <Loader2 size={12} className="animate-spin" /> : <Sparkles size={12} />}
          {view.running ? 'Generating…' : latest ? 'Regenerate' : 'Generate'}
        </button>
        {view.failed && (
          <button
            type="button"
            disabled={disabled || submitting}
            onClick={retry}
            className="inline-flex items-center gap-1 rounded-lg border border-border px-3 py-1.5 text-xs text-secondary"
          >
            <RefreshCw size={12} /> Retry
          </button>
        )}
      </div>

      <ErrorInline error={error} />
      {view.failed && !error && (
        <p role="alert" className="rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-xs text-red-300">
          {view.error || 'Generation failed.'}
        </p>
      )}
      {view.running && <p className="flex items-center gap-2 text-xs text-muted"><Clock size={12} /> Job {view.jobId} in the existing generation queue.</p>}

      {view.completed && view.filename && (
        <img
          src={backendClient.outputUrl(view.filename, getToken())}
          alt={`Generated image for shot ${shot.id}`}
          width={512}
          height={512}
          loading="lazy"
          className="w-full max-w-sm rounded-xl border border-border"
        />
      )}

      {history.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs text-muted">History ({history.length}) — select the visual to use:</p>
          <ul className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            {history.map((img) => (
              <li key={img.id}>
                <button
                  type="button"
                  onClick={() => backendClient.selectShotImage(film.id, scene.id, shot.id, img.id).then(() => onChanged?.())}
                  aria-pressed={img.is_selected}
                  className={`block w-full overflow-hidden rounded-xl border-2 ${img.is_selected ? 'border-primary' : 'border-transparent'}`}
                >
                  <img
                    src={backendClient.outputUrl(img.filename, getToken())}
                    alt={`Generation ${img.id} for shot ${shot.id}`}
                    width={256}
                    height={256}
                    loading="lazy"
                    className="aspect-square w-full object-cover"
                  />
                  <span className="block px-1 py-0.5 text-[10px] text-muted">{img.is_selected ? 'Selected' : 'Select'}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}

function ErrorInline({ error }) {
  if (!error) return null
  const e = error.error || error
  return (
    <p role="alert" className="rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-xs text-red-300">
      {e.message || 'Something went wrong.'}
      {e.hint ? ` ${e.hint}` : ''}
    </p>
  )
}
