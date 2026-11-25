import { createElement } from 'react'
import { HashRouter, Route, Routes } from 'react-router-dom'
import { useConnection } from './hooks/useConnection'
import { useBackendData } from './hooks/useBackendData'
import { useJobPolling } from './hooks/useJobPolling'
import Sidebar, { NAV_ITEMS, NAV_UNAVAILABLE } from './components/Sidebar'
import ConnectionPanel from './components/ConnectionPanel'
import ConnectionStatus from './components/ConnectionStatus'
import ImageStudio from './pages/ImageStudio'
import VideoStudio from './pages/VideoStudio'
import ImageToImage from './pages/ImageToImage'
import ImageToVideo from './pages/ImageToVideo'
import GalleryPage from './pages/GalleryPage'
import HistoryPage from './pages/HistoryPage'
import ModelsPage from './pages/ModelsPage'
import CreativeStudio from './pages/CreativeStudio'
import SettingsPage from './pages/SettingsPage'
import Unavailable from './pages/Unavailable'
import { Navigate } from 'react-router-dom'

function NotFound() {
  return <Navigate to="/" replace />
}

export default function App() {
  const connection = useConnection()
  const backendData = useBackendData(connection)
  const { jobs, refresh, cancel, remove, retry } = useJobPolling({ connected: connection.isConnected })

  const studioContext = {
    connection,
    ...backendData,
    jobs,
    refreshJobs: refresh,
    cancelJob: cancel,
    removeJob: remove,
    retryJob: retry,
  }

  const studio = (Element) => createElement(Element, studioContext)

  const footer = (
    <div className="space-y-2">
      <ConnectionStatus status={connection.status} error={connection.error} onOpen={() => {}} />
    </div>
  )

  return (
    <HashRouter>
      <div className="min-h-screen bg-app-bg">
        <Sidebar connection={connection} footer={footer} />
        <main className="min-h-screen pb-14 pt-14 lg:pb-0 lg:pl-64">
          <Routes>
            <Route path="/" element={studio(ImageStudio)} />
            <Route path="/video" element={studio(VideoStudio)} />
            <Route path="/image-editing" element={studio(ImageToImage)} />
            <Route path="/image-to-video" element={studio(ImageToVideo)} />
            <Route path="/gallery" element={studio(GalleryPage)} />
            <Route path="/history" element={studio(HistoryPage)} />
            <Route path="/models" element={studio(ModelsPage)} />
            <Route path="/creative" element={studio(CreativeStudio)} />
            <Route path="/settings" element={studio(SettingsPage)} />
            {NAV_UNAVAILABLE.map(({ to, feature }) => (
              <Route key={to} path={to} element={<Unavailable feature={feature} />} />
            ))}
            <Route path="*" element={<NotFound />} />
          </Routes>
        </main>
      </div>
    </HashRouter>
  )
}

export { NAV_ITEMS }
