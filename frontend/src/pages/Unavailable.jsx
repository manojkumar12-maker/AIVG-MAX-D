import { CloudOff } from 'lucide-react'
import StudioShell from '../components/StudioShell'
import { EmptyState } from '../components/EmptyState'

export function Unavailable({ feature = 'This feature' }) {
  return (
    <StudioShell title={feature} description="Not available in the self-hosted edition.">
      <EmptyState
        icon={CloudOff}
        title="Unavailable — available in the cloud edition"
        description={`${feature} is part of the cloud edition of Open Generative AI and is not included in this self-hosted build. Use Image Studio, Video Studio, Image to Video or Image Editing instead.`}
      />
    </StudioShell>
  )
}

export default Unavailable
