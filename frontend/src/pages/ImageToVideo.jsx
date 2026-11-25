import { useEffect, useMemo, useState } from 'react'
import { Dices, Clapperboard, AlertTriangle } from 'lucide-react'
import StudioShell from '../components/StudioShell'
import PresetPicker from '../components/PresetPicker'
import { Field, Slider, TextInput, Select, GenerateButton } from '../components/controls'
import ImageUploader from '../components/ImageUploader'
import JobOutput from '../components/JobOutput'
import { EmptyState } from '../components/EmptyState'
import QueuePanel from '../components/QueuePanel'
import {
  buildImageToVideoPayload,
  submitGeneration,
  friendlyError,
  isDimensionValid,
  pollJob,
  validateGeneration,
  pickWorkflow,
} from '../services/generationService'
import { CAMERA_MOVEMENTS, DURATION_PRESETS, SHORTS_PRESETS, framesForDuration, snapTo8 } from '../config/presets'

export function ImageToVideo({ connection, models, workflows, jobs, cancelJob, removeJob, retryJob }) {
  const connected = connection.isConnected
  const videoModels = useMemo(() => models.filter((m) => m.type === 'video' && m.installed), [models])
  const [modelId, setModelId] = useState('')
  const [image, setImage] = useState(null)
  const [prompt, setPrompt] = useState('')
  const [motionPreset, setMotionPreset] = useState('Static')
  const [durationSec, setDurationSec] = useState(4)
  const [fps, setFps] = useState(16)
  const [width, setWidth] = useState(576)
  const [height, setHeight] = useState(1024)
  const [seed, setSeed] = useState('')
  const [preset, setPreset] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [errors, setErrors] = useState([])
  const [currentJob, setCurrentJob] = useState(null)

  useEffect(() => {
    if (!modelId && videoModels.length) setModelId(videoModels[0].id)
  }, [videoModels, modelId])

  const model = models.find((m) => m.id === modelId) || null
  const workflow = pickWorkflow(workflows, 'image_to_video', modelId)
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
  }

  const handleGenerate = async () => {
    setErrors([])
    const problems = []
    if (!image) problems.push('Upload a start image first.')
    problems.push(...validateGeneration({ prompt, width: Number(width), height: Number(height), model }, workflow))
    if (problems.length) {
      setErrors(problems)
      return
    }
    setSubmitting(true)
    try {
      const payload = buildImageToVideoPayload({
        prompt: prompt.trim(),
        image,
        motionPreset,
        seed: seed === '' ? -1 : Number(seed),
        frames,
        fps,
        width: Number(width),
        height: Number(height),
        model,
        workflowId: workflow?.id,
      })
      const res = await submitGeneration('image_to_video', payload)
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
      <ImageUploader value={image} onChange={setImage} label="Start image" disabled={!connected} disabledReason={disabledReason} />

      <Field label="Prompt" htmlFor="i2v-prompt" hint="Describe the motion or scene continuation.">
        <textarea
          id="i2v-prompt"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          rows={4}
          placeholder="Animate this image…"
          disabled={!connected}
          title={connected ? 'Describe the motion' : 'Connect a backend first'}
          className="w-full rounded-xl border border-border bg-panel-bg px-3 py-2 text-sm text-text placeholder:text-muted focus:border-primary focus:outline-none disabled:opacity-50"
        />
      </Field>

      <Field label="Camera movement" htmlFor="i2v-motion">
        <Select
          id="i2v-motion"
          value={motionPreset}
          onChange={setMotionPreset}
          disabled={!connected}
          options={CAMERA_MOVEMENTS.map((m) => ({ value: m, label: m }))}
        />
      </Field>

      <Field label="Model" htmlFor="i2v-model">
        <Select
          id="i2v-model"
          value={modelId}
          onChange={setModelId}
          disabled={!connected || videoModels.length === 0}
          disabledReason={connected ? 'No installed video models available' : 'Connect a backend first'}
          options={videoModels.length ? videoModels.map((m) => ({ value: m.id, label: m.name || m.id })) : [{ value: '', label: 'No video models installed' }]}
        />
      </Field>

      {connected && videoModels.length === 0 ? (
        <div className="flex items-start gap-2 rounded-xl border border-yellow-500/30 bg-yellow-500/5 p-3 text-xs text-yellow-300">
          <AlertTriangle size={14} className="mt-0.5 shrink-0" aria-hidden="true" />
          <span>No video models are installed. Install one from the Models page, then restart the backend.</span>
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

      <div className="grid grid-cols-2 gap-2">
        <Field label="Width" htmlFor="i2v-width" hint={`max ${maxW}`}>
          <TextInput id="i2v-width" type="number" value={width} onChange={(v) => { setWidth(Number(v)); setPreset('') }} disabled={!connected} invalid={dimensionInvalid} step={8} min={64} max={maxW} />
        </Field>
        <Field label="Height" htmlFor="i2v-height" hint={`max ${maxH}`}>
          <TextInput id="i2v-height" type="number" value={height} onChange={(v) => { setHeight(Number(v)); setPreset('') }} disabled={!connected} invalid={dimensionInvalid} step={8} min={64} max={maxH} />
        </Field>
      </div>
      {dimensionInvalid ? <p className="text-xs text-red-400">Width and height must be multiples of 8 within the workflow maximum.</p> : null}

      <Field label="Seed" htmlFor="i2v-seed" hint="Leave empty for a random seed.">
        <div className="flex gap-2">
          <TextInput id="i2v-seed" type="number" value={seed} onChange={setSeed} placeholder="random" disabled={!connected} />
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
    <StudioShell title="Image to Video" description="Animate a still image with a prompt and camera movement." settings={settings}>
      {currentJob ? (
        <JobOutput job={currentJob} />
      ) : (
        <EmptyState icon={Clapperboard} title="No video yet" description="Upload a start image, connect a backend, then generate." />
      )}
      <div className="mt-4">
        <QueuePanel jobs={jobs} onCancel={cancelJob} onRemove={removeJob} onRetry={retryJob} />
      </div>
    </StudioShell>
  )
}

export default ImageToVideo
