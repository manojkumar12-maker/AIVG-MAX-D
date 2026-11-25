import { useEffect, useMemo, useState } from 'react'
import { Dices, Wand2 } from 'lucide-react'
import StudioShell from '../components/StudioShell'
import PresetPicker from '../components/PresetPicker'
import { Field, Slider, TextInput, Select, GenerateButton } from '../components/controls'
import JobOutput from '../components/JobOutput'
import { EmptyState } from '../components/EmptyState'
import QueuePanel from '../components/QueuePanel'
import backendClient from '../services/backendClient'
import {
  buildImagePayload,
  submitGeneration,
  friendlyError,
  isDimensionValid,
  pollJob,
  validateGeneration,
  pickWorkflow,
} from '../services/generationService'
import { ASPECT_RATIOS, ASPECT_DIMENSIONS, QUALITY_PRESETS, snapTo8 } from '../config/presets'

const SAMPLERS = ['euler', 'euler_ancestral', 'dpmpp_2m', 'dpmpp_2m_sde', 'dpmpp_3m_sde', 'ddim', 'lcm', 'heun']
const SCHEDULERS = ['normal', 'karras', 'exponential', 'sgm_uniform', 'simple', 'beta']

export function ImageStudio({ connection, models, workflows, jobs, cancelJob, removeJob, retryJob }) {
  const connected = connection.isConnected
  const imageModels = useMemo(() => models.filter((m) => m.type === 'image' && m.installed), [models])
  const [modelId, setModelId] = useState('')
  const [prompt, setPrompt] = useState('')
  const [negativePrompt, setNegativePrompt] = useState('')
  const [aspect, setAspect] = useState('1:1')
  const [width, setWidth] = useState(1024)
  const [height, setHeight] = useState(1024)
  const [steps, setSteps] = useState(30)
  const [cfg, setCfg] = useState(7)
  const [seed, setSeed] = useState('')
  const [sampler, setSampler] = useState('dpmpp_2m')
  const [scheduler, setScheduler] = useState('karras')
  const [batchSize, setBatchSize] = useState(1)
  const [quality, setQuality] = useState('balanced')
  const [submitting, setSubmitting] = useState(false)
  const [errors, setErrors] = useState([])
  const [currentJob, setCurrentJob] = useState(null)

  useEffect(() => {
    if (!modelId && imageModels.length) setModelId(imageModels[0].id)
  }, [imageModels, modelId])

  const model = models.find((m) => m.id === modelId) || null
  const workflow = pickWorkflow(workflows, 'image', modelId)
  const maxW = workflow?.max_width ?? 4096
  const maxH = workflow?.max_height ?? 4096

  const applyAspect = (id) => {
    setAspect(id)
    if (ASPECT_DIMENSIONS[id]) {
      setWidth(snapTo8(Math.min(ASPECT_DIMENSIONS[id].width, maxW)))
      setHeight(snapTo8(Math.min(ASPECT_DIMENSIONS[id].height, maxH)))
    }
  }

  const applyQuality = (id) => {
    setQuality(id)
    const preset = QUALITY_PRESETS.find((p) => p.id === id)
    if (!preset) return
    setSteps(preset.steps)
    setCfg(preset.cfg)
    if (preset.resolutionScale !== 1) {
      setWidth((w) => snapTo8(w * preset.resolutionScale, maxW))
      setHeight((h) => snapTo8(h * preset.resolutionScale, maxH))
    }
  }

  const randomizeSeed = () => setSeed(String(Math.floor(Math.random() * 2 ** 31)))

  const dimensionInvalid = !isDimensionValid(width, { max: maxW }) || !isDimensionValid(height, { max: maxH })

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
      const payload = buildImagePayload({
        prompt: prompt.trim(),
        negativePrompt: negativePrompt.trim(),
        model,
        width: Number(width),
        height: Number(height),
        steps,
        cfg,
        seed: seed === '' ? -1 : Number(seed),
        sampler,
        scheduler,
        batchSize,
        workflowId: workflow?.id,
      })
      const res = await submitGeneration('image', payload)
      const jobId = res?.job_id
      if (jobId) {
        pollJob(jobId, { onJob: (j) => setCurrentJob(j) })
      }
    } catch (err) {
      setErrors([friendlyError(err)])
    } finally {
      setSubmitting(false)
    }
  }

  const settings = (
    <div className="space-y-4">
      <Field label="Prompt" htmlFor="img-prompt">
        <textarea
          id="img-prompt"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          rows={4}
          placeholder="Describe the image you want to generate…"
          disabled={!connected}
          title={connected ? 'Describe what to generate' : 'Connect a backend first'}
          className="w-full rounded-xl border border-border bg-panel-bg px-3 py-2 text-sm text-text placeholder:text-muted focus:border-primary focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
        />
      </Field>

      <Field label="Negative prompt" htmlFor="img-neg">
        <textarea
          id="img-neg"
          value={negativePrompt}
          onChange={(e) => setNegativePrompt(e.target.value)}
          rows={2}
          placeholder="What to avoid…"
          disabled={!connected}
          title={connected ? 'Describe what to avoid' : 'Connect a backend first'}
          className="w-full rounded-xl border border-border bg-panel-bg px-3 py-2 text-sm text-text placeholder:text-muted focus:border-primary focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
        />
      </Field>

      <Field label="Model" htmlFor="img-model" hint={imageModels.length === 0 ? 'No installed image models reported by this backend.' : undefined}>
        <Select
          id="img-model"
          value={modelId}
          onChange={setModelId}
          disabled={!connected || imageModels.length === 0}
          disabledReason={connected ? 'No installed image models available' : 'Connect a backend first'}
          options={
            imageModels.length
              ? imageModels.map((m) => ({ value: m.id, label: m.name || m.id }))
              : [{ value: '', label: 'No image models installed' }]
          }
        />
      </Field>

      <PresetPicker
        label="Aspect ratio"
        options={ASPECT_RATIOS}
        value={aspect}
        onChange={applyAspect}
        optionClassName="!min-h-[44px]"
      />

      <div className="grid grid-cols-2 gap-2">
        <Field label="Width" htmlFor="img-width" hint={`max ${maxW}`}>
          <TextInput id="img-width" type="number" value={width} onChange={(v) => { setWidth(Number(v)); setAspect('custom') }} disabled={!connected} invalid={dimensionInvalid} step={8} min={64} max={maxW} />
        </Field>
        <Field label="Height" htmlFor="img-height" hint={`max ${maxH}`}>
          <TextInput id="img-height" type="number" value={height} onChange={(v) => { setHeight(Number(v)); setAspect('custom') }} disabled={!connected} invalid={dimensionInvalid} step={8} min={64} max={maxH} />
        </Field>
      </div>
      {dimensionInvalid ? (
        <p className="text-xs text-red-400">Width and height must be multiples of 8 within the workflow maximum.</p>
      ) : null}

      <Field label={`Steps: ${steps}`} htmlFor="img-steps">
        <Slider id="img-steps" value={steps} min={1} max={100} onChange={setSteps} disabled={!connected} />
      </Field>

      <Field label={`CFG: ${cfg}`} htmlFor="img-cfg">
        <Slider id="img-cfg" value={cfg} min={1} max={20} step={0.5} onChange={setCfg} disabled={!connected} />
      </Field>

      <Field label="Seed" htmlFor="img-seed" hint="Leave empty for a random seed.">
        <div className="flex gap-2">
          <TextInput id="img-seed" type="number" value={seed} onChange={setSeed} placeholder="random" disabled={!connected} />
          <button
            type="button"
            onClick={randomizeSeed}
            disabled={!connected}
            title="Randomize seed"
            aria-label="Randomize seed"
            className="flex min-h-[44px] w-11 shrink-0 items-center justify-center rounded-xl border border-border text-secondary transition-colors duration-150 hover:text-primary disabled:opacity-50"
          >
            <Dices size={16} aria-hidden="true" />
          </button>
        </div>
      </Field>

      <Field label="Sampler" htmlFor="img-sampler">
        <Select
          id="img-sampler"
          value={sampler}
          onChange={setSampler}
          disabled={!connected}
          options={SAMPLERS.map((s) => ({ value: s, label: s }))}
        />
      </Field>

      <Field label="Scheduler" htmlFor="img-scheduler">
        <Select
          id="img-scheduler"
          value={scheduler}
          onChange={setScheduler}
          disabled={!connected}
          options={SCHEDULERS.map((s) => ({ value: s, label: s }))}
        />
      </Field>

      <Field label="Batch size" htmlFor="img-batch" hint="How many images per run (1–4).">
        <Select
          id="img-batch"
          value={String(batchSize)}
          onChange={(v) => setBatchSize(Number(v))}
          disabled={!connected}
          options={[1, 2, 3, 4].map((n) => ({ value: String(n), label: `${n}` }))}
        />
      </Field>

      <PresetPicker label="Quality" options={QUALITY_PRESETS} value={quality} onChange={applyQuality} />

      <GenerateButton
        onClick={handleGenerate}
        disabled={!connected}
        disabledReason={connected ? 'Adjust settings and generate' : 'Connect a backend, then generate your first image'}
        busy={submitting}
      />

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
    <StudioShell title="Image Studio" description="Generate images from text prompts on your own GPU or Colab runtime." settings={settings}>
      {currentJob ? (
        <JobOutput job={currentJob} />
      ) : (
        <EmptyState
          icon={Wand2}
          title="Nothing generated yet"
          description="Connect a backend, then generate your first image."
        />
      )}
      <div className="mt-4">
        <QueuePanel jobs={jobs} onCancel={cancelJob} onRemove={removeJob} onRetry={retryJob} />
      </div>
    </StudioShell>
  )
}

export default ImageStudio
