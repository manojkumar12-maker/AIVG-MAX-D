import backendClient from './backendClient'

export const ERROR_COPY = {
  out_of_memory:
    'Your selected model or resolution exceeds available GPU memory. Try a lower resolution, a smaller model, or a low-VRAM preset.',
  oom:
    'Your selected model or resolution exceeds available GPU memory. Try a lower resolution, a smaller model, or a low-VRAM preset.',
  disconnected:
    'Your Colab runtime may have disconnected. Reconnect Colab and refresh the backend connection.',
  network:
    'Could not reach the backend. Check the tunnel URL and that the Colab runtime is running.',
  missing_model:
    'This workflow requires a model that is not installed.',
  missing_dependency:
    'Required ComfyUI node is missing. Install the dependency from the notebook and restart the backend.',
  auth: 'Your backend session token is invalid or expired.',
  invalid_token: 'Your backend session token is invalid or expired.',
  rate_limited: 'The backend is rate-limiting requests. Wait a moment and try again.',
  queue_full: 'The backend queue is full. Wait for running jobs to finish or cancel one.',
  validation: 'The backend rejected the request. Check your settings and try again.',
  backend_unavailable: 'The backend is starting up or unavailable. Try again shortly.',
  comfyui_error: 'ComfyUI reported an error while running the workflow.',
  timeout: 'The request timed out. The runtime may be busy or disconnected.',
}

export function friendlyError(err) {
  if (!err) return 'Unknown error.'
  if (err.code && ERROR_COPY[err.code]) {
    const hint = err.hint ? ` (${err.hint})` : ''
    return ERROR_COPY[err.code] + hint
  }
  const message = err.message || String(err)
  if (/out of memory|CUDA out of memory|OOM/i.test(message)) return ERROR_COPY.out_of_memory
  if (/ECONNREFUSED|network|fetch failed|disconnected/i.test(message)) return ERROR_COPY.disconnected
  return message
}

export function isDimensionValid(value, { min = 64, max = 4096 } = {}) {
  const n = Number(value)
  return Number.isFinite(n) && n >= min && n <= max && n % 8 === 0
}

export function validateGeneration(params, workflow) {
  const problems = []
  if (!params.prompt || !params.prompt.trim()) {
    problems.push('Enter a prompt before generating.')
  }
  if (workflow) {
    const maxW = workflow.max_width ?? Infinity
    const maxH = workflow.max_height ?? Infinity
    if (!isDimensionValid(params.width, { max: maxW })) {
      problems.push(`Width must be a multiple of 8 no greater than ${maxW}px.`)
    }
    if (!isDimensionValid(params.height, { max: maxH })) {
      problems.push(`Height must be a multiple of 8 no greater than ${maxH}px.`)
    }
    if (workflow.min_vram_gb && params.model) {
      const meta = params.model
      if (meta && meta.vram_gb && meta.vram_gb > workflow.min_vram_gb) {
        problems.push(`This workflow needs at least ${workflow.min_vram_gb}GB VRAM; the selected model requires ${meta.vram_gb}GB.`)
      }
    }
  }
  if (params.model && params.model.installed === false) {
    problems.push(`Model "${params.model.name || params.model.id}" is not installed. Install it from the Models page, then try again.`)
  }
  return problems
}

export function pickWorkflow(workflows, type, modelId) {
  if (!Array.isArray(workflows)) return null
  const matching = workflows.filter((w) => w.type === type)
  if (modelId) {
    const bound = matching.find((w) => w.requires_model === modelId)
    if (bound) return bound
  }
  return matching.find((w) => !w.needs_upload) || matching[0] || null
}

export function buildImagePayload({ prompt, negativePrompt, model, width, height, steps, cfg, seed, sampler, scheduler, batchSize, workflowId }) {
  return {
    workflow_id: workflowId || undefined,
    prompt,
    negative_prompt: negativePrompt,
    model: model?.id,
    width,
    height,
    steps,
    cfg,
    seed,
    sampler,
    scheduler,
    batch_size: batchSize,
  }
}

export function buildImageToImagePayload({ prompt, negativePrompt, image, strength, seed, steps, cfg, width, height, model, workflowId }) {
  return {
    workflow_id: workflowId || undefined,
    prompt,
    negative_prompt: negativePrompt,
    image,
    strength,
    seed,
    steps,
    cfg,
    width,
    height,
    model: model?.id,
  }
}

export function buildVideoPayload({ prompt, negativePrompt, width, height, frames, fps, seed, motionStrength, model, workflowId }) {
  return {
    workflow_id: workflowId || undefined,
    prompt,
    negative_prompt: negativePrompt,
    width,
    height,
    frames,
    fps,
    seed,
    motion_strength: motionStrength,
    model: model?.id,
  }
}

export function buildImageToVideoPayload({ prompt, image, motionPreset, seed, frames, fps, width, height, model, workflowId }) {
  return {
    workflow_id: workflowId || undefined,
    prompt,
    image,
    motion_preset: motionPreset,
    seed,
    frames,
    fps,
    width,
    height,
    model: model?.id,
  }
}

export async function submitGeneration(kind, payload) {
  switch (kind) {
    case 'image':
      return backendClient.generateImage(payload)
    case 'image_to_image':
      return backendClient.generateImageToImage(payload)
    case 'video':
      return backendClient.generateVideo(payload)
    case 'image_to_video':
      return backendClient.generateImageToVideo(payload)
    default:
      throw new Error(`Unknown generation kind: ${kind}`)
  }
}

const RUNNING_STATES = new Set(['queued', 'loading_model', 'generating', 'processing', 'saving'])

export function isRunning(status) {
  return RUNNING_STATES.has(status)
}

export async function pollJob(jobId, { onJob, shouldStop, signal } = {}) {
  let idleStart = Date.now()
  let lastNonRunning = null
  while (!(signal && signal.aborted) && !(shouldStop && shouldStop())) {
    try {
      const job = await backendClient.getJob(jobId)
      onJob?.(job)
      if (job.status === 'completed' || job.status === 'failed' || job.status === 'cancelled') {
        return job
      }
      idleStart = Date.now()
      lastNonRunning = null
    } catch (err) {
      // Keep polling through transient errors, but track how long we've been stuck.
      if (!lastNonRunning) lastNonRunning = Date.now()
      idleStart = Math.min(idleStart, lastNonRunning)
    }
    const idleMs = Date.now() - idleStart
    await new Promise((resolve) => setTimeout(resolve, idleMs > 120000 ? 5000 : 2000))
  }
  return null
}
