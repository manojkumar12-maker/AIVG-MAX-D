import { useEffect, useState } from 'react'
import { BookOpen, CheckCircle2, ChevronDown, Film, Loader2, RefreshCw, Undo2, Wand2 } from 'lucide-react'
import StudioShell from '../components/StudioShell'
import { EmptyState } from '../components/EmptyState'
import ShotImagePanel from './ShotImagePanel'
import ShotVideoPanel from './ShotVideoPanel'
import ContinuityPanel from './ContinuityPanel'
import { backendClient } from '../services/backendClient'

const STAGES = [
  { kind: 'concept', label: 'Concept', hint: 'One creative concept from the Film Bible.' },
  { kind: 'treatment', label: 'Treatment', hint: 'Synopsis, characters and acts.' },
  { kind: 'screenplay', label: 'Screenplay', hint: 'Numbered scenes with sluglines.' },
  { kind: 'scene_breakdown', label: 'Scene Breakdown', hint: 'Production breakdown per scene.' },
  { kind: 'storyboard', label: 'Storyboard', hint: 'Panels per scene with shot prompts.' },
]

const STAGE_ORDER = Object.fromEntries(STAGES.map((s, i) => [s.kind, i]))

function ErrorNote({ error }) {
  if (!error) return null
  const e = error.error || error
  return (
    <p role="alert" className="rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-xs text-red-300">
      {e.message || 'Something went wrong.'}
      {e.hint ? ` ${e.hint}` : ''}
    </p>
  )
}

function ArtifactPanel({ film, kind, label, hint, exists, onAction, busy }) {
  const [open, setOpen] = useState(kind === 'concept')
  const [artifact, setArtifact] = useState(null)
  const [missing, setMissing] = useState(false)
  const [pending, setPending] = useState(false)

  const load = async () => {
    setMissing(false)
    try {
      setArtifact(await backendClient.getArtifact(film.id, kind))
    } catch {
      setArtifact(null)
      setMissing(true)
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [film.id, film.updated_at])

  const act = (fn) => async () => {
    setPending(true)
    try {
      await fn()
      await load()
    } finally {
      setPending(false)
    }
  }

  const approved = artifact?.status === 'approved'
  const locked = approved

  return (
    <section className="rounded-2xl border border-border bg-card-bg">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        className="flex w-full items-center justify-between gap-2 p-4 text-left"
      >
        <span>
          <span className="text-sm font-medium">{label}</span>
          <span className="mt-0.5 block text-xs text-muted">{hint}</span>
        </span>
        <span className="flex items-center gap-2">
          {approved && <CheckCircle2 size={16} className="text-green-400" aria-label="approved" />}
          {artifact && (
            <span className="rounded-md bg-white/5 px-2 py-0.5 text-xs text-secondary">v{artifact.version}</span>
          )}
          <ChevronDown size={16} className={`text-muted transition-transform ${open ? 'rotate-180' : ''}`} />
        </span>
      </button>
      {open && (
        <div className="space-y-3 border-t border-border p-4">
          {missing || !exists ? (
            <p className="text-xs text-muted">Not generated yet.</p>
          ) : artifact ? (
            <pre className="max-h-64 overflow-auto whitespace-pre-wrap break-words rounded-xl bg-black/30 p-3 text-xs text-secondary">
              {JSON.stringify(artifact.data, null, 1)}
            </pre>
          ) : null}
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={busy || pending || locked}
              onClick={act(() => backendClient.generateStage(film.id, kind, { brief: '' }))}
              className="inline-flex items-center gap-1 rounded-lg bg-primary/20 px-3 py-1.5 text-xs text-primary disabled:opacity-40"
            >
              {busy || pending ? <Loader2 size={12} className="animate-spin" /> : <Wand2 size={12} />}
              {artifact ? 'Regenerate' : 'Generate'}
            </button>
            {artifact && !approved && (
              <button
                type="button"
                disabled={busy || pending}
                onClick={act(() => backendClient.approveArtifact(film.id, kind))}
                className="inline-flex items-center gap-1 rounded-lg bg-green-500/20 px-3 py-1.5 text-xs font-semibold text-green-200"
              >
                <CheckCircle2 size={12} /> Approve
              </button>
            )}
            {approved && (
              <button
                type="button"
                disabled={busy || pending}
                onClick={act(() => backendClient.unapproveArtifact(film.id, kind))}
                className="inline-flex items-center gap-1 rounded-lg bg-yellow-500 px-3 py-1.5 text-xs font-semibold text-black"
              >
                <Undo2 size={12} /> Unapprove
              </button>
            )}
            {artifact && artifact.versions?.length > 1 && (
              <select
                aria-label="Artifact version"
                value={artifact.active_version ?? artifact.version}
                disabled={busy || pending}
                onChange={(e) => act(() => backendClient.activateArtifactVersion(film.id, kind, Number(e.target.value)))()}
                className="rounded-lg border border-border bg-card-bg px-2 py-1 text-xs"
              >
                {artifact.versions.map((v) => (
                  <option key={v.version} value={v.version}>
                    v{v.version} · {v.source}
                  </option>
                ))}
              </select>
            )}
          </div>
        </div>
      )}
    </section>
  )
}

function ShotList({ film, onChanged, disabled }) {
  const [project, setProject] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let live = true
    backendClient.getFilm(film.id)
      .then((data) => { if (live) setProject(data.project || data) })
      .catch((err) => { if (live) setError(err) })
    return () => { live = false }
  }, [film.id, film.updated_at])

  if (error) return <ErrorNote error={error} />
  const scenes = project?.scenes || []
  if (scenes.length === 0) {
    return <p className="text-xs text-muted">No scenes yet — apply the scene breakdown to create shots.</p>
  }
  return (
    <div className="space-y-3">
      <h3 className="text-sm font-medium">Shots & image generation</h3>
      {scenes.flatMap((scene) => (scene.shots || []).map((shot) => (
        <div key={shot.id} className="space-y-2">
          <p className="text-xs text-secondary">Scene “{scene.title}” · shot {shot.id} <span className="text-muted">({shot.status})</span></p>
          <ShotImagePanel film={film} scene={scene} shot={shot} onChanged={onChanged} disabled={disabled} />
          <ShotVideoPanel film={film} scene={scene} shot={shot} onChanged={onChanged} disabled={disabled} />
        </div>
      )))}
    </div>
  )
}

export default function CreativeStudio({ connection }) {
  const [films, setFilms] = useState([])
  const [activeId, setActiveId] = useState(null)
  const [title, setTitle] = useState('')
  const [logline, setLogline] = useState('')
  const [provider, setProvider] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)
  const [artifactKinds, setArtifactKinds] = useState([])

  const active = films.find((f) => f.id === activeId) || null

  const refresh = async () => {
    try {
      const { projects } = await backendClient.listFilms()
      setFilms(projects)
      if (!activeId && projects.length) setActiveId(projects[0].id)
      if (activeId || projects.length) {
        const id = activeId || projects[0].id
        const { artifacts } = await backendClient.listArtifacts(id)
        setArtifactKinds(artifacts.map((a) => a.kind))
      } else {
        setArtifactKinds([])
      }
    } catch (err) {
      setError(err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (connection.isConnected) {
      refresh()
      backendClient.llmProvider().then(setProvider).catch(() => setProvider(null))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connection.isConnected])

  const withAction = (fn) => async () => {
    setBusy(true)
    setError(null)
    try {
      await fn()
      await refresh()
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  if (!connection.isConnected) {
    return (
      <StudioShell title="Creative Studio" description="Plan films with LLM agents before generating anything on the GPU.">
        <EmptyState
          icon={BookOpen}
          title="Not connected"
          description="Connect a backend to plan films: concept, treatment, screenplay, scene breakdown and storyboard."
        />
      </StudioShell>
    )
  }

  return (
    <StudioShell title="Creative Studio" description="Plan films with LLM agents before generating anything on the GPU.">
      <div className="space-y-4">
        {provider && (
          <p className="text-xs text-muted">
            LLM provider: <span className="text-secondary">{provider.provider}</span>
            {provider.provider === 'mock' && ' (offline mock — set OGAI_LLM_PROVIDER / OGAI_LLM_API_KEY for real generation)'}
          </p>
        )}

        <div className="flex flex-wrap items-center gap-2">
          <select
            aria-label="Active film project"
            value={activeId || ''}
            onChange={(e) => setActiveId(e.target.value)}
            className="rounded-lg border border-border bg-card-bg px-3 py-2 text-sm"
          >
            {films.length === 0 && <option value="">No projects yet</option>}
            {films.map((f) => (
              <option key={f.id} value={f.id}>
                {f.title}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={withAction(refresh)}
            className="inline-flex items-center gap-1 rounded-lg border border-border px-3 py-2 text-xs text-secondary"
          >
            <RefreshCw size={12} /> Refresh
          </button>
        </div>

        <form
          className="flex flex-wrap gap-2"
          onSubmit={(e) => {
            e.preventDefault()
            if (!title.trim()) return
            withAction(async () => {
              const project = await backendClient.createFilm({ title, bible: { logline } })
              setTitle('')
              setLogline('')
              setActiveId(project.id)
            })()
          }}
        >
          <input
            aria-label="New project title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="New film title"
            className="min-w-40 flex-1 rounded-lg border border-border bg-card-bg px-3 py-2 text-sm"
          />
          <input
            aria-label="Logline"
            value={logline}
            onChange={(e) => setLogline(e.target.value)}
            placeholder="Logline (optional)"
            className="min-w-40 flex-[2] rounded-lg border border-border bg-card-bg px-3 py-2 text-sm"
          />
          <button type="submit" className="inline-flex items-center gap-1 rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-500">
            <Film size={14} /> Create
          </button>
        </form>

        <ErrorNote error={error} />

        {active && (
          <div className="space-y-3">
            {STAGES.sort((a, b) => STAGE_ORDER[a.kind] - STAGE_ORDER[b.kind]).map((s) => (
              <ArtifactPanel key={s.kind} film={active} exists={artifactKinds.includes(s.kind)} {...s} onAction={withAction} busy={busy} />
            ))}
            {active.approved_shots === 0 && (
              <button
                type="button"
                disabled={busy}
                onClick={withAction(() => backendClient.applyBreakdown(active.id))}
                className="inline-flex items-center gap-1 rounded-lg bg-primary/20 px-3 py-2 text-xs text-primary"
              >
                Apply scene breakdown to project scenes
              </button>
            )}
            <section className="rounded-2xl border border-border bg-card-bg p-4">
              <h3 className="mb-1 text-sm font-medium">Visual Continuity</h3>
              <p className="mb-3 text-xs text-muted">
                Film canon used when assembling shot prompts. Editing never triggers generation.
              </p>
              <ContinuityPanel filmId={active.id} api={backendClient} />
            </section>
            <ShotList film={active} onChanged={withAction(refresh)} disabled={busy} />
          </div>
        )}
      </div>
    </StudioShell>
  )
}
