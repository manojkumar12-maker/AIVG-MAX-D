const BACKEND_URL_KEY = 'ogai.backendUrl'
const SESSION_TOKEN_KEY = 'ogai.sessionToken'

const DEFAULT_TIMEOUT = 30000
const UPLOAD_TIMEOUT = 300000

// HTTP status semantics: these codes mean the session token is missing,
// invalid or expired — the client reports them as an auth problem.
export const HTTP_UNAUTHORIZED = 401
export const HTTP_FORBIDDEN = 403

export function isAuthErrorStatus(status) {
  return status === HTTP_UNAUTHORIZED || status === HTTP_FORBIDDEN
}

let state = {
  baseUrl: null,
  token: null,
}

function normalizeBaseUrl(url) {
  if (!url) return null
  return String(url).trim().replace(/\/+$/, '') || null
}

function restore() {
  try {
    const stored = localStorage.getItem(BACKEND_URL_KEY)
    if (stored) state.baseUrl = normalizeBaseUrl(stored)
    state.token = sessionStorage.getItem(SESSION_TOKEN_KEY)
  } catch {
    // storage unavailable (private mode) — stay in-memory only
  }
}
restore()

function persist() {
  try {
    if (state.baseUrl) {
      localStorage.setItem(BACKEND_URL_KEY, state.baseUrl)
    } else {
      localStorage.removeItem(BACKEND_URL_KEY)
    }
    if (state.token) {
      sessionStorage.setItem(SESSION_TOKEN_KEY, state.token)
    } else {
      sessionStorage.removeItem(SESSION_TOKEN_KEY)
    }
  } catch {
    // ignore storage failures
  }
}

export function getBaseUrl() {
  return state.baseUrl
}

export function getToken() {
  return state.token
}

export function setConnection({ baseUrl = state.baseUrl, token = state.token } = {}) {
  state.baseUrl = normalizeBaseUrl(baseUrl)
  state.token = token || null
  persist()
}

export function clearToken() {
  state.token = null
  persist()
}

export function isConnected() {
  return Boolean(state.baseUrl)
}

function friendlyError(status, body) {
  const code = body?.error?.code || ''
  const message = body?.error?.message || `Request failed with status ${status}`
  return { status, code, message, hint: body?.error?.hint }
}

async function request(path, { method = 'GET', body, formData, timeout = DEFAULT_TIMEOUT, auth = true } = {}) {
  if (!state.baseUrl) {
    throw new Error('No backend URL configured. Connect a backend first.')
  }
  const headers = {}
  if (auth && state.token) headers['X-Session-Token'] = state.token
  if (body !== undefined) headers['Content-Type'] = 'application/json'

  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(new DOMException('Timeout', 'TimeoutError')), timeout)
  try {
    const res = await fetch(`${state.baseUrl}${path}`, {
      method,
      headers,
      body: formData ?? (body !== undefined ? JSON.stringify(body) : undefined),
      signal: controller.signal,
    })
    let data = null
    const text = await res.text()
    if (text) {
      try {
        data = JSON.parse(text)
      } catch {
        data = text
      }
    }
    if (!res.ok) {
      if (isAuthErrorStatus(res.status)) {
        window.dispatchEvent(new CustomEvent('ogai:auth-required', { detail: { status: res.status } }))
      }
      throw friendlyError(res.status, data)
    }
    return data
  } catch (err) {
    if (err.name === 'TimeoutError' || (err instanceof DOMException && err.name === 'TimeoutError')) {
      throw { status: 0, code: 'timeout', message: 'The backend did not respond in time.', hint: 'The Colab runtime may be busy or disconnected.' }
    }
    if (err instanceof TypeError) {
      window.dispatchEvent(new CustomEvent('ogai:backend-down', { detail: { reason: String(err.message || err) } }))
      throw { status: 0, code: 'network', message: 'Could not reach the backend.', hint: 'Check the tunnel URL and that the Colab runtime is running.' }
    }
    throw err
  } finally {
    clearTimeout(timer)
  }
}

export const backendClient = {
  health() {
    return request('/health', { auth: false, timeout: 10000 })
  },

  status() {
    return request('/health', { auth: false, timeout: 10000 })
  },

  capabilities() {
    return request('/api/capabilities')
  },

  models() {
    return request('/api/models')
  },

  workflows() {
    return request('/api/workflows')
  },

  generateImage(payload) {
    return request('/api/generate/image', { method: 'POST', body: payload })
  },

  generateImageToImage(payload) {
    return request('/api/generate/image-to-image', { method: 'POST', body: payload })
  },

  generateVideo(payload) {
    return request('/api/generate/video', { method: 'POST', body: payload })
  },

  generateImageToVideo(payload) {
    return request('/api/generate/image-to-video', { method: 'POST', body: payload })
  },

  getJob(id) {
    return request(`/api/jobs/${encodeURIComponent(id)}`)
  },

  listJobs() {
    return request('/api/jobs')
  },

  cancelJob(id) {
    return request(`/api/jobs/${encodeURIComponent(id)}/cancel`, { method: 'POST' })
  },

  deleteJob(id) {
    return request(`/api/jobs/${encodeURIComponent(id)}`, { method: 'DELETE' })
  },

  upload(file) {
    const formData = new FormData()
    formData.append('file', file)
    return request('/api/upload', { method: 'POST', formData, timeout: UPLOAD_TIMEOUT })
  },

  getSettings() {
    return request('/api/settings')
  },

  listFilms() {
    return request('/api/films')
  },

  createFilm(payload) {
    return request('/api/films', { method: 'POST', body: payload })
  },

  getFilm(id) {
    return request(`/api/films/${encodeURIComponent(id)}`)
  },

  deleteFilm(id) {
    return request(`/api/films/${encodeURIComponent(id)}`, { method: 'DELETE' })
  },

  llmProvider() {
    return request('/api/llm/provider')
  },

  generateStage(filmId, stage, payload = {}) {
    return request(`/api/films/${encodeURIComponent(filmId)}/generate/${stage}`, {
      method: 'POST',
      body: payload,
      timeout: 300000,
    })
  },

  listArtifacts(filmId) {
    return request(`/api/films/${encodeURIComponent(filmId)}/artifacts`)
  },

  getArtifact(filmId, kind) {
    return request(`/api/films/${encodeURIComponent(filmId)}/artifacts/${kind}`)
  },

  approveArtifact(filmId, kind) {
    return request(`/api/films/${encodeURIComponent(filmId)}/artifacts/${kind}/approve`, { method: 'POST' })
  },

  unapproveArtifact(filmId, kind) {
    return request(`/api/films/${encodeURIComponent(filmId)}/artifacts/${kind}/unapprove`, { method: 'POST' })
  },

  activateArtifactVersion(filmId, kind, version) {
    return request(`/api/films/${encodeURIComponent(filmId)}/artifacts/${kind}/versions/${version}/activate`, {
      method: 'POST',
    })
  },

  applyBreakdown(filmId) {
    return request(`/api/films/${encodeURIComponent(filmId)}/apply-breakdown`, { method: 'POST' })
  },

  saveSettings(payload) {
    return request('/api/settings', { method: 'POST', body: payload })
  },

  outputUrl(filename, token) {
    const base = state.baseUrl || ''
    const params = new URLSearchParams()
    if (token) params.set('token', token)
    const qs = params.toString()
    return `${base}/api/output/${encodeURIComponent(filename)}${qs ? `?${qs}` : ''}`
  },
}

export default backendClient
