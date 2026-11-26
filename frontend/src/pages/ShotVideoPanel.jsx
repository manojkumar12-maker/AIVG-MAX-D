import { useEffect, useState } from 'react'
import { Clock, Film, Loader2, RefreshCw, Sparkles } from 'lucide-react'
import backendClient, { getToken } from '../services/backendClient'
import { shotVideoViewModel, shotVideoHistory } from '../lib/shotVideos'

/**
 * Video-generation area for one storyboard shot (Phase 3B). Animates the
 * shot's selected generated image through the existing image-to-video
 * pipeline: submits through /api/generate (JobManager), polls that job,
 * attaches the finished output so history is preserved, and lets the user
 * pick which video is the shot's preferred output.
 */
export default function ShotVideoPanel({ film, scene, shot, onChanged, disabled }) {
  const [promptDraft, setPromptDraft] = useState('')
  const [dirty, setDirty] = useState(false)
  const [meta, setMeta] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)

  const generations = shot.video_generations || []
  const latest = generations[generations.length - 1]
  const view = shotVideoViewModel(latest, null)
  const history = shotVideoHistory(shot)
  const selectedImage = (shot.images || []).find((i) => i.selected) || null
  const activeJobId = view.running ? view.jobId : null

  useEffect(() => {
    setPromptDraft(shot.prompt || '')
    setDirty(false)
    let live = true
    backendClient.shotVideoPrompt(film.id, scene.id, shot.id)
      .then((data) => { if (live) setMeta(data) })
      .catch(() => { if (live) setMeta(null) })
    return () => { live = false }
  }, [film.id, scene.id, shot.id, shot.prompt])

  // Recover a running video job after page reload: poll and attach when done.
  useEffect(() => {
    if (!activeJobId) return
    let cancelled = false
    const tick = async () => {
      try {
        const job = await backendClient.getJob(activeJobId)
        if (cancelled) return
        if (job.status === 'completed' || job.status === 'failed' || job.status === 'cancelled') {
          await backendClient.attachShotVideoJob(film.id, scene.id, shot.id, activeJobId)
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
      await backendClient.generateShotVideo(film.id, scene.id, shot.id,
        dirty ? { prompt: promptDraft } : {})
      onChanged?.()
    } catch (err) {
      setError(err)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section className="space-y-3 rounded-2xl border border-border bg-card-bg p-4" aria-label={`Video generation for shot ${shot.id}`}>
      <div className="flex items-center justify-between gap-2">
        <h4 className="flex items-center gap-2 text-sm font-medium">
          <Film size={14} className="text-muted" /> Shot video
        </h4>
        {meta?.missing?.length > 0 && (
          <span className="rounded-md bg-white/5 px-2 py-0.5 text-[11px] text-muted" title={meta.missing.join(', ')}>
            missing: {meta.missing.join(', ')}
          </span>
        )}
      </div>

      {selectedImage ? (
        <div className="flex items-center gap-3">
          <img
            src={backendClient.outputUrl(selectedImage.filename, getToken())}
            alt={`Start frame for shot ${shot.id}`}
            width={96}
            height={96}
            loading="lazy"
            className="h-16 w-16 rounded-lg border border-border object-cover"
          />
          <p className="text-xs text-muted">Start frame: the shot's selected image.</p>
        </div>
      ) : (
        <p className="text-xs text-muted">No selected image yet — generate and select a shot image first.</p>
      )}

      <label className="block space-y-1">
        <span className="text-xs text-muted">Motion prompt {dirty && <span className="text-primary">(edited)</span>}</span>
        <textarea
          value={promptDraft}
          onChange={(e) => { setPromptDraft(e.target.value); setDirty(true) }}
          rows={2}
          className="w-full rounded-xl border border-border bg-panel-bg p-3 text-sm"
          placeholder={meta?.prompt || 'Describe how the image should move'}
        />
      </label>
      {!dirty && meta?.motion && (
        <p className="text-[11px] text-muted">Camera/motion from shot: {meta.motion}</p>
      )}

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          disabled={disabled || submitting || view.running || !selectedImage}
          onClick={generate}
          className="inline-flex items-center gap-1 rounded-lg bg-primary/20 px-3 py-1.5 text-xs text-primary disabled:opacity-40"
        >
          {submitting || view.running ? <Loader2 size={12} className="animate-spin" /> : <Sparkles size={12} />}
          {view.running ? 'Generating…' : latest ? 'Regenerate video' : 'Generate video'}
        </button>
        {view.failed && (
          <button
            type="button"
            disabled={disabled || submitting}
            onClick={generate}
            className="inline-flex items-center gap-1 rounded-lg border border-border px-3 py-1.5 text-xs text-secondary"
          >
            <RefreshCw size={12} /> Retry
          </button>
        )}
      </div>

      <ErrorInline error={error} />
      {view.failed && !error && (
        <p role="alert" className="rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-xs text-red-300">
          {view.error || 'Video generation failed.'}
        </p>
      )}
      {view.running && <p className="flex items-center gap-2 text-xs text-muted"><Clock size={12} /> Job {view.jobId} in the existing generation queue.</p>}

      {view.completed && view.filename && (
        <video
          key={view.filename}
          src={backendClient.outputUrl(view.filename, getToken())}
          controls
          preload="metadata"
          className="w-full max-w-sm rounded-xl border border-border"
        />
      )}

      {history.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs text-muted">History ({history.length}) — select the video to use:</p>
          <ul className="space-y-2">
            {history.map((v) => (
              <li key={v.id}>
                <button
                  type="button"
                  onClick={() => backendClient.selectShotVideo(film.id, scene.id, shot.id, v.id).then(() => onChanged?.())}
                  aria-pressed={v.is_selected}
                  className={`block w-full overflow-hidden rounded-xl border-2 ${v.is_selected ? 'border-primary' : 'border-transparent'}`}
                >
                  <video
                    src={backendClient.outputUrl(v.filename, getToken())}
                    preload="metadata"
                    className="w-full max-w-sm"
                  />
                  <span className="block px-1 py-0.5 text-left text-[10px] text-muted">{v.is_selected ? 'Selected' : 'Select'}</span>
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
