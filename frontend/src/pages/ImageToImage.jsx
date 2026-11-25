import { useEffect, useMemo, useState } from 'react'
import { Dices, Wand2 } from 'lucide-react'
import StudioShell from '../components/StudioShell'
import { Field, Slider, TextInput, Select, GenerateButton } from '../components/controls'
import ImageUploader from '../components/ImageUploader'
import JobOutput from '../components/JobOutput'
import { EmptyState } from '../components/EmptyState'
import QueuePanel from '../components/QueuePanel'
import {
  buildImageToImagePayload,
  submitGeneration,
  friendlyError,
  isDimensionValid,
  pollJob,
  validateGeneration,
  pickWorkflow,
} from '../services/generationService'
import { snapTo8 } from '../config/presets'

export function ImageToImage({ connection, models, workflows, jobs, cancelJob, removeJob, retryJob }) {
  const connected = connection.isConnected
  const imageModels = useMemo(() => models.filter((m) => m.type === 'image' && m.installed), [models])
  const [modelId, setModelId] = useState('')
  const [prompt, setPrompt] = useState('')
  const [negativePrompt, setNegativePrompt] = useState('')
  const [image, setImage] = useState(null)
  const [strength, setStrength] = useState(0.65)
  const [seed, setSeed] = useState('')
  const [steps, setSteps] = useState(30)
  const [cfg, setCfg] = useState(7)
  const [width, setWidth] = useState(1024)
  const [height, setHeight] = useState(1024)
  const [submitting, setSubmitting] = useState(false)
  const [errors, setErrors] = useState([])
  const [currentJob, setCurrentJob] = useState(null)

  useEffect(() => {
    if (!modelId && imageModels.length) setModelId(imageModels[0].id)
  }, [imageModels, modelId])

  const model = models.find((m) => m.id === modelId) || null
  const workflow = pickWorkflow(workflows, 'image_to_image', modelId)
  const maxW = workflow?.max_width ?? 4096
  const maxH = workflow?.max_height ?? 4096
  const dimensionInvalid = !isDimensionValid(width, { max: maxW }) || !isDimensionValid(height, { max: maxH })

  const handleGenerate = async () => {
    setErrors([])
    const problems = []
    if (!image) problems.push('Upload a reference image first.')
    problems.push(
      ...validateGeneration({ prompt, width: Number(width), height: Number(height), model }, workflow)
    )
    if (problems.length) {
      setErrors(problems)
      return
    }
    setSubmitting(true)
    try {
      const payload = buildImageToImagePayload({
        prompt: prompt.trim(),
        negativePrompt: negativePrompt.trim(),
        image,
        strength,
        seed: seed === '' ? -1 : Number(seed),
        steps,
        cfg,
        width: Number(width),
        height: Number(height),
        model,
        workflowId: workflow?.id,
      })
      const res = await submitGeneration('image_to_image', payload)
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
      <ImageUploader value={image} onChange={setImage} label="Reference image" disabled={!connected} disabledReason={disabledReason} />

      <Field label="Prompt" htmlFor="i2i-prompt" hint="Describe the edit or the target image.">
        <textarea
          id="i2i-prompt"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          rows={4}
          placeholder="Restyle this image…"
          disabled={!connected}
          title={connected ? 'Describe the edit' : 'Connect a backend first'}
          className="w-full rounded-xl border border-border bg-panel-bg px-3 py-2 text-sm text-text placeholder:text-muted focus:border-primary focus:outline-none disabled:opacity-50"
        />
      </Field>

      <Field label="Negative prompt" htmlFor="i2i-neg">
        <textarea
          id="i2i-neg"
          value={negativePrompt}
          onChange={(e) => setNegativePrompt(e.target.value)}
          rows={2}
          placeholder="What to avoid…"
          disabled={!connected}
          title={connected ? 'Describe what to avoid' : 'Connect a backend first'}
          className="w-full rounded-xl border border-border bg-panel-bg px-3 py-2 text-sm text-text placeholder:text-muted focus:border-primary focus:outline-none disabled:opacity-50"
        />
      </Field>

      <Field label={`Strength: ${strength.toFixed(2)}`} htmlFor="i2i-strength" hint="Low = closer to the original, high = more creative freedom.">
        <Slider id="i2i-strength" value={strength} min={0} max={1} step={0.05} onChange={setStrength} disabled={!connected} format={(v) => v.toFixed(2)} />
      </Field>

      <Field label="Model" htmlFor="i2i-model" hint={imageModels.length === 0 ? 'No installed image models reported by this backend.' : undefined}>
        <Select
          id="i2i-model"
          value={modelId}
          onChange={setModelId}
          disabled={!connected || imageModels.length === 0}
          disabledReason={connected ? 'No installed image models available' : 'Connect a backend first'}
          options={imageModels.length ? imageModels.map((m) => ({ value: m.id, label: m.name || m.id })) : [{ value: '', label: 'No image models installed' }]}
        />
      </Field>

      <div className="grid grid-cols-2 gap-2">
        <Field label="Width" htmlFor="i2i-width" hint={`max ${maxW}`}>
          <TextInput id="i2i-width" type="number" value={width} onChange={(v) => setWidth(Number(v))} disabled={!connected} invalid={dimensionInvalid} step={8} min={64} max={maxW} />
        </Field>
        <Field label="Height" htmlFor="i2i-height" hint={`max ${maxH}`}>
          <TextInput id="i2i-height" type="number" value={height} onChange={(v) => setHeight(Number(v))} disabled={!connected} invalid={dimensionInvalid} step={8} min={64} max={maxH} />
        </Field>
      </div>
      {dimensionInvalid ? <p className="text-xs text-red-400">Width and height must be multiples of 8 within the workflow maximum.</p> : null}

      <Field label={`Steps: ${steps}`} htmlFor="i2i-steps">
        <Slider id="i2i-steps" value={steps} min={1} max={100} onChange={setSteps} disabled={!connected} />
      </Field>

      <Field label={`CFG: ${cfg}`} htmlFor="i2i-cfg">
        <Slider id="i2i-cfg" value={cfg} min={1} max={20} step={0.5} onChange={setCfg} disabled={!connected} />
      </Field>

      <Field label="Seed" htmlFor="i2i-seed" hint="Leave empty for a random seed.">
        <div className="flex gap-2">
          <TextInput id="i2i-seed" type="number" value={seed} onChange={setSeed} placeholder="random" disabled={!connected} />
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
    <StudioShell title="Image Editing" description="Reframe and restyle an existing image with a prompt." settings={settings}>
      {currentJob ? (
        <JobOutput job={currentJob} />
      ) : (
        <EmptyState icon={Wand2} title="Nothing edited yet" description="Upload a reference image, connect a backend, then generate." />
      )}
      <div className="mt-4">
        <QueuePanel jobs={jobs} onCancel={cancelJob} onRemove={removeJob} onRetry={retryJob} />
      </div>
    </StudioShell>
  )
}

export default ImageToImage
