import { useCallback, useEffect, useRef, useState } from 'react'
import backendClient, { setConnection, clearToken, getBaseUrl, isAuthErrorStatus } from '../services/backendClient'

export const CONNECTION_STATES = {
  DISCONNECTED: 'disconnected',
  CONNECTING: 'connecting',
  CONNECTED: 'connected',
  UNAVAILABLE: 'unavailable',
  AUTH_ERROR: 'auth_error',
}

const HEALTH_POLL_MS = 15000
const IDLE_POLL_MS = 30000
const IDLE_THRESHOLD_MS = 5 * 60 * 1000

export function useConnection() {
  const [status, setStatus] = useState(CONNECTION_STATES.DISCONNECTED)
  const [health, setHealth] = useState(null)
  const [error, setError] = useState(null)
  const [lastActivity, setLastActivity] = useState(Date.now())
  const mounted = useRef(true)
  const lastActivityRef = useRef(Date.now())

  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
    }
  }, [])

  const markActivity = useCallback(() => {
    lastActivityRef.current = Date.now()
    setLastActivity(Date.now())
  }, [])

  const checkHealth = useCallback(async () => {
    if (!getBaseUrl()) return null
    try {
      const data = await backendClient.health()
      if (!mounted.current) return null
      setHealth(data)
      setError(null)
      setStatus(CONNECTION_STATES.CONNECTED)
      return data
    } catch (err) {
      if (!mounted.current) return null
      if (err && isAuthErrorStatus(err.status)) {
        setStatus(CONNECTION_STATES.AUTH_ERROR)
        setError('Your backend session token is invalid or expired.')
      } else {
        setStatus(CONNECTION_STATES.UNAVAILABLE)
        setError('Backend unavailable. Check the tunnel URL and the Colab runtime.')
      }
      return null
    }
  }, [])

  const connect = useCallback(
    async ({ baseUrl, token, rememberUrl, rememberToken }) => {
      setConnection({ baseUrl, token: token || null })
      if (!rememberUrl) {
        // Keep in memory for this session but don't persist to localStorage.
        try {
          localStorage.removeItem('ogai.backendUrl')
        } catch {
          // ignore
        }
      }
      if (!rememberToken) {
        try {
          sessionStorage.removeItem('ogai.sessionToken')
        } catch {
          // ignore
        }
      }
      if (rememberToken && token) {
        try {
          sessionStorage.setItem('ogai.sessionToken', token)
        } catch {
          // ignore
        }
      }
      setStatus(CONNECTION_STATES.CONNECTING)
      setError(null)
      markActivity()
      const data = await checkHealth()
      if (!data && mounted.current) {
        // keep the state set by checkHealth (unavailable/auth error)
      }
      return data
    },
    [checkHealth, markActivity]
  )

  const disconnect = useCallback(() => {
    clearToken()
    setConnection({ baseUrl: null, token: null })
    try {
      localStorage.removeItem('ogai.backendUrl')
      sessionStorage.removeItem('ogai.sessionToken')
    } catch {
      // ignore
    }
    setHealth(null)
    setError(null)
    setStatus(CONNECTION_STATES.DISCONNECTED)
  }, [])

  // Auto-connect from stored URL on mount.
  useEffect(() => {
    if (getBaseUrl()) {
      setStatus(CONNECTION_STATES.CONNECTING)
      checkHealth()
    }
  }, [checkHealth])

  // Poll /health while connected; back off when idle.
  useEffect(() => {
    if (status !== CONNECTION_STATES.CONNECTED) return undefined
    let cancelled = false
    let timer = null
    const tick = async () => {
      if (cancelled) return
      const idleMs = Date.now() - lastActivityRef.current
      const interval = idleMs > IDLE_THRESHOLD_MS ? IDLE_POLL_MS : HEALTH_POLL_MS
      await checkHealth()
      if (!cancelled) timer = setTimeout(tick, interval)
    }
    timer = setTimeout(tick, HEALTH_POLL_MS)
    return () => {
      cancelled = true
      if (timer) clearTimeout(timer)
    }
  }, [status, checkHealth])

  // React to auth/backend-down events dispatched by the client.
  useEffect(() => {
    const onAuth = () => {
      setStatus(CONNECTION_STATES.AUTH_ERROR)
      setError('Your backend session token is invalid or expired.')
    }
    const onDown = () => {
      setStatus(CONNECTION_STATES.UNAVAILABLE)
      setError('Backend unavailable. Check the tunnel URL and the Colab runtime.')
    }
    window.addEventListener('ogai:auth-required', onAuth)
    window.addEventListener('ogai:backend-down', onDown)
    return () => {
      window.removeEventListener('ogai:auth-required', onAuth)
      window.removeEventListener('ogai:backend-down', onDown)
    }
  }, [])

  return {
    status,
    health,
    error,
    connect,
    disconnect,
    checkHealth,
    markActivity,
    isConnected: status === CONNECTION_STATES.CONNECTED,
  }
}

export default useConnection
