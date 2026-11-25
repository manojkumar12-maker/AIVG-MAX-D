import { useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import StudioShell from '../components/StudioShell'
import Gallery from '../components/Gallery'

export function GalleryPage({ jobs, loading, removeJob, connection }) {
  const navigate = useNavigate()

  const outputs = useMemo(() => {
    const list = []
    for (const job of jobs || []) {
      for (const out of job.outputs || []) {
        list.push({
          ...out,
          job_id: job.job_id,
          prompt: job.params?.prompt || out.prompt || '',
          seed: job.params?.seed,
          created_at: out.created_at || job.finished_at || job.created_at,
        })
      }
    }
    return list
  }, [jobs])

  const handleUseAsReference = (out) => {
    navigate('/image-editing', { state: { reference: out.filename, prompt: out.prompt } })
  }

  const handleDelete = async (out) => {
    if (out.job_id) await removeJob(out.job_id)
  }

  return (
    <StudioShell title="Gallery" description="Everything you have generated on this backend.">
      <Gallery
        outputs={outputs}
        loading={connection.status === 'connecting'}
        onDelete={handleDelete}
        onUseAsReference={handleUseAsReference}
      />
    </StudioShell>
  )
}

export default GalleryPage
