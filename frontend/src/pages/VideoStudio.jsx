import { useEffect, useMemo, useState } from 'react'
import { Dices, Film, AlertTriangle } from 'lucide-react'
import StudioShell from '../components/StudioShell'
import PresetPicker from '../components/PresetPicker'
import { Field, Slider, TextInput, Select, GenerateButton } from '../components/controls'
import JobOutput from '../components/JobOutput'
import { EmptyState } from '../components/EmptyState'
import QueuePanel from '../components/QueuePanel'
import {
  buildVideoPayload,
  submitGeneration,
  friendlyError,
  isDimensionValid,
  pollJob,
  validateGeneration,
  pickWorkflow,
} from '../services/generationService'
import { QUALITY_PRESETS, SHORTS_PRESETS, DURATION_PRESETS, framesForDuration, snapTo8 } from '../config/presets'

export function VideoStudio({ connection, models, workflows, jobs, cancelJob, removeJob, retryJob }) {
  const connected = connection.isConnected
  const videoModels = useMemo(() => models.filter((m) => m.type === 'video' && m.installed), [models])
  const [modelId, setModelId] = useState('')
  const [prompt, setPrompt] = useState('')
  const [negativePrompt, setNegativePrompt] = useState('')
  const [durationSec, setDurationSec] = useState(4)
  const [fps, setFps] = useState(16)
  const [width, setWidth] = useState(576)
  const [height, setHeight] = useState(1024)
  const [seed, setSeed] = useState('')
  const [motionStrength, setMotionStrength] = useState(0.7)
  const [quality, setQuality] = useState('balanced')
  const [preset, setPreset] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [errors, setErrors] = useState([])
  const [currentJob, setCurrentJob] = useState(null)

  useEffect(() => {
    if (!modelId && videoModels.length) setModelId(videoModels[0].id)
  }, [videoModels, modelId])

  const model = models.find((m) => m.id === modelId) || null
  const workflow = pickWorkflow(workflows, 'video', modelId)
  const maxW = workflow?.max_width ?? 1280
  const maxH = workflow?.max_height ?? 1280
  const frames = framesForDuration(durationSec, fps)
  const dimensionInvalid = !isDimensionValid(width, { max: maxW }) || !isDimensionValid(height, { max: maxH })

  const applyShorts = (id) => {
    setPreset(id)
    const p = SHORTS_PRESETS.find((s) => s.id === id)
    if (!p || p.kind !== 'video') return
    setWidth(snapTo8(Math.min(p.width, maxW), maxW))
    setHeight(snapTo8(Math.min(p.height, maxH), maxH))
    setFps(16)
    if (!videoModels.length) return
  }

  const applyQuality = (id) => {
    setQuality(id)
    const q = QUALITY_PRESETS.find((p) => p.id === id)
    if (!q) return
    setMotionStrength(0.7)
  }

  const handleGenerate = async () => {
    setErrors([])
    const problems = validateGeneration(
      { prompt, width: Number(width), height: Number(height), model },
      workflow
    )
    if (problems.length) {
      setErrors(problems)
      return
    }
    setSubmitting(true)
    try {
      const payload = buildVideoPayload({
        prompt: prompt.trim(),
        negativePrompt: negativePrompt.trim(),
        width: Number(width),
        height: Number(height),
        frames,
        fps,
        seed: seed === '' ? -1 : Number(seed),
        motionStrength,
        model,
        workflowId: workflow?.id,
      })
      const res = await submitGeneration('video', payload)
      const jobId = res?.job_id
      if (jobId) pollJob(jobId, { onJob: (j) => setCurrentJob(j) })
    } catch (err) {
      setErrors([friendlyError(err)])
    } finally {
      setSubmitting(false)
    }
  }

  const disabledReason = connected ? 'Adjust settings and generate' : 'Connect a backend, then generate'

  const settings = (
    <div className="space-y-4">
      <Field label="Prompt" htmlFor="vid-prompt">
        <textarea
          id="vid-prompt"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          rows={4}
          placeholder="Describe the video…"
          disabled={!connected}
          title={connected ? 'Describe the video' : 'Connect a backend first'}
          className="w-full rounded-xl border border-border bg-panel-bg px-3 py-2 text-sm text-text placeholder:text-muted focus:border-primary focus:outline-none disabled:opacity-50"
        />
      </Field>

      <Field label="Negative prompt" htmlFor="vid-neg">
        <textarea
          id="vid-neg"
          value={negativePrompt}
          onChange={(e) => setNegativePrompt(e.target.value)}
          rows={2}
          placeholder="What to avoid…"
          disabled={!connected}
          title={connected ? 'Describe what to avoid' : 'Connect a backend first'}
          className="w-full rounded-xl border border-border bg-panel-bg px-3 py-2 text-sm text-text placeholder:text-muted focus:border-primary focus:outline-none disabled:opacity-50"
        />
      </Field>

      <Field label="Model" htmlFor="vid-model">
        <Select
          id="vid-model"
          value={modelId}
          onChange={setModelId}
          disabled={!connected || videoModels.length === 0}
          disabledReason={connected ? 'No installed video models available' : 'Connect a backend first'}
          options={videoModels.length ? videoModels.map((m) => ({ value: m.id, label: m.name || m.id })) : [{ value: '', label: 'No video models installed' }]}
        />
      </Field>

      {!connected ? null : videoModels.length === 0 ? (
        <div className="flex items-start gap-2 rounded-xl border border-yellow-500/30 bg-yellow-500/5 p-3 text-xs text-yellow-300">
          <AlertTriangle size={14} className="mt-0.5 shrink-0" aria-hidden="true" />
          <span>
            No video models are installed on this backend. Open the Models page, install a video model from the
            notebook, and restart the backend.
          </span>
        </div>
      ) : null}

      <PresetPicker
        label="Duration"
        options={DURATION_PRESETS.map((d) => ({ id: String(d.seconds), label: `${d.seconds}s`, description: `About ${framesForDuration(d.seconds, d.fps)} frames at ${d.fps}fps` }))}
        value={String(durationSec)}
        onChange={(id) => {
          const d = DURATION_PRESETS.find((x) => String(x.seconds) === id)
          if (d) {
            setDurationSec(d.seconds)
            setFps(d.fps)
          }
        }}
      />

      <Field label={`FPS: ${fps}`} htmlFor="vid-fps">
        <Slider id="vid-fps" value={fps} min={8} max={30} onChange={setFps} disabled={!connected} />
      </Field>

      <Field label="Frames" htmlFor="vid-frames" hint={`Computed from duration × fps (${durationSec}s × ${fps}fps).`}>
        <TextInput id="vid-frames" type="number" value={frames} disabled disabledReason="Frames are derived from duration and FPS" />
      </Field>

      <div className="grid grid-cols-2 gap-2">
        <Field label="Width" htmlFor="vid-width" hint={`max ${maxW}`}>
          <TextInput id="vid-width" type="number" value={width} onChange={(v) => { setWidth(Number(v)); setPreset('') }} disabled={!connected} invalid={dimensionInvalid} step={8} min={64} max={maxW} />
        </Field>
        <Field label="Height" htmlFor="vid-height" hint={`max ${maxH}`}>
          <TextInput id="vid-height" type="number" value={height} onChange={(v) => { setHeight(Number(v)); setPreset('') }} disabled={!connected} invalid={dimensionInvalid} step={8} min={64} max={maxH} />
        </Field>
      </div>
      {dimensionInvalid ? <p className="text-xs text-red-400">Width and height must be multiples of 8 within the workflow maximum.</p> : null}

      <Field label={`Motion strength: ${motionStrength.toFixed(2)}`} htmlFor="vid-motion">
        <Slider id="vid-motion" value={motionStrength} min={0} max={1} step={0.05} onChange={setMotionStrength} disabled={!connected} format={(v) => v.toFixed(2)} />
      </Field>

      <Field label="Seed" htmlFor="vid-seed" hint="Leave empty for a random seed.">
        <div className="flex gap-2">
          <TextInput id="vid-seed" type="number" value={seed} onChange={setSeed} placeholder="random" disabled={!connected} />
          <button
            type="button"
            onClick={() => setSeed(String(Math.floor(Math.random() * 2 ** 31)))}
            disabled={!connected}
            title="Randomize seed"
            aria-label="Randomize seed"
            className="flex min-h-[44px] w-11 shrink-0 items-center justify-center rounded-xl border border-border text-secondary transition-colors duration-150 hover:text-primary disabled:opacity-50"
          >
            <Dices size={16} aria-hidden="true" />
          </button>
        </div>
      </Field>

      <PresetPicker label="Quality" options={QUALITY_PRESETS} value={quality} onChange={applyQuality} />

      <PresetPicker
        label="YouTube Shorts"
        options={SHORTS_PRESETS.filter((p) => p.kind === 'video')}
        value={preset}
        onChange={applyShorts}
      />

      <GenerateButton onClick={handleGenerate} disabled={!connected} disabledReason={disabledReason} busy={submitting} />

      {errors.length > 0 ? (
        <ul role="alert" className="space-y-1 rounded-xl border border-red-500/30 bg-red-500/5 p-3 text-xs text-red-300">
          {errors.map((e, i) => (
            <li key={i}>{e}</li>
          ))}
        </ul>
      ) : null}
    </div>
  )

  return (
    <StudioShell title="Video Studio" description="Generate short videos from text prompts." settings={settings}>
      {currentJob ? (
        <JobOutput job={currentJob} />
      ) : (
        <EmptyState icon={Film} title="No video yet" description="Connect a backend, then generate your first video." />
      )}
      <div className="mt-4">
        <QueuePanel jobs={jobs} onCancel={cancelJob} onRemove={removeJob} onRetry={retryJob} />
      </div>
    </StudioShell>
  )
}

export default VideoStudio
