import { useEffect, useState } from 'react'
import backendClient from '../services/backendClient'
import { CONNECTION_STATES } from './useConnection'

export function useBackendData(connection) {
  const { isConnected, status } = connection
  const [models, setModels] = useState([])
  const [workflows, setWorkflows] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    if (!isConnected) {
      setModels([])
      setWorkflows([])
      setError(null)
      return undefined
    }
    setLoading(true)
    Promise.all([backendClient.models().catch(() => null), backendClient.workflows().catch(() => null)])
      .then(([m, w]) => {
        if (cancelled) return
        setModels(Array.isArray(m?.models) ? m.models : [])
        setWorkflows(Array.isArray(w?.workflows) ? w.workflows : [])
        setError(!m && !w ? 'Could not load models and workflows from the backend.' : null)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [isConnected, status])

  return { models, workflows, loading, error }
}

export default useBackendData
