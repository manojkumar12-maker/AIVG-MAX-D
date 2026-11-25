import { useCallback, useEffect, useRef, useState } from 'react'
import backendClient, { getBaseUrl, getToken } from '../services/backendClient'
import { isRunning } from '../services/generationService'

/**
 * Polls a set of running jobs. Pass initial job ids (usually the full
 * /api/jobs list is polled instead); returns { jobs, refresh, cancel, remove, retry }.
 */
export function useJobPolling({ intervalMs = 2000, backoffMs = 5000, idleThresholdMs = 120000, connected = false } = {}) {
  const [jobs, setJobs] = useState([])
  const [loading, setLoading] = useState(false)
  const pollTimer = useRef(null)
  const wsRef = useRef(null)
  const wsTimer = useRef(null)
  const cancelledRef = useRef(false)
  const lastRunningAt = useRef(Date.now())

  const applyJobs = useCallback((list) => {
    if (!Array.isArray(list)) return
    setJobs(list)
    if (list.some((j) => isRunning(j.status))) {
      lastRunningAt.current = Date.now()
    }
  }, [])

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const data = await backendClient.listJobs()
      applyJobs(Array.isArray(data?.jobs) ? data.jobs : [])
    } catch {
      // transient — keep last known jobs
    } finally {
      setLoading(false)
    }
  }, [applyJobs])

  // Live updates over /ws/jobs; on close (backend without WS, network blip)
  // reconnect with a delay. Polling keeps running as a safety net regardless.
  useEffect(() => {
    let open = true
    if (!connected) return () => { open = false }
    const connect = () => {
      if (!open) return
      const base = getBaseUrl() || window.location.origin
      const url = `${base.replace(/^http/, 'ws')}/ws/jobs?token=${encodeURIComponent(getToken() || '')}`
      let ws
      try {
        ws = new WebSocket(url)
      } catch {
        wsTimer.current = setTimeout(connect, backoffMs)
        return
      }
      wsRef.current = ws
      ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data)
          if (msg.event === 'job_update' && msg.job) {
            setJobs((prev) => {
              const next = prev.some((j) => j.job_id === msg.job.job_id)
                ? prev.map((j) => (j.job_id === msg.job.job_id ? msg.job : j))
                : [...prev, msg.job]
              applyJobs(next)
              return next
            })
          }
        } catch {
          // malformed frame — ignore
        }
      }
      ws.onclose = () => {
        if (open) wsTimer.current = setTimeout(connect, backoffMs)
      }
      ws.onerror = () => ws.close()
    }
    connect()
    return () => {
      open = false
      if (wsTimer.current) clearTimeout(wsTimer.current)
      if (wsRef.current) { wsRef.current.onclose = null; wsRef.current.close() }
    }
  }, [backoffMs, applyJobs, connected])

  useEffect(() => {
    cancelledRef.current = false
    const tick = async () => {
      if (cancelledRef.current) return
      const data = await backendClient.listJobs().catch(() => null)
      if (cancelledRef.current) return
      if (data && Array.isArray(data.jobs)) {
        setJobs(data.jobs)
        if (data.jobs.some((j) => isRunning(j.status))) {
          lastRunningAt.current = Date.now()
        }
      }
      const idleMs = Date.now() - lastRunningAt.current
      const interval = idleMs > idleThresholdMs ? backoffMs : intervalMs
      pollTimer.current = setTimeout(tick, interval)
    }
    tick()
    return () => {
      cancelledRef.current = true
      if (pollTimer.current) clearTimeout(pollTimer.current)
    }
  }, [intervalMs, backoffMs, idleThresholdMs, applyJobs])

  const cancel = useCallback(
    async (id) => {
      try {
        await backendClient.cancelJob(id)
      } catch {
        // ignore; job list will reflect state
      }
      await refresh()
    },
    [refresh]
  )

  const remove = useCallback(
    async (id) => {
      try {
        await backendClient.deleteJob(id)
      } catch {
        // ignore
      }
      await refresh()
    },
    [refresh]
  )

  const retry = useCallback(
    async (job) => {
      const params = job?.params || {}
      const kind = job?.type || 'image'
      const client = backendClient
      try {
        let res = null
        if (kind === 'image' || kind === 'image_to_image' || kind === 'video' || kind === 'image_to_video') {
          if (kind === 'image') res = await client.generateImage(params)
          else if (kind === 'image_to_image') res = await client.generateImageToImage(params)
          else if (kind === 'video') res = await client.generateVideo(params)
          else res = await client.generateImageToVideo(params)
        } else {
          res = await client.generateImage({ ...params, workflow_id: undefined })
        }
        await refresh()
        return res?.job_id || null
      } catch {
        return null
      }
    },
    [refresh]
  )

  return { jobs, loading, refresh, cancel, remove, retry }
}

export default useJobPolling
