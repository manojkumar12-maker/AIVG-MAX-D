import { useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { ImageIcon, Film, Clapperboard, Wand2, Images, History, Cpu, Settings, AudioLines, UserRound, Bot, Menu, X, BookOpen } from 'lucide-react'

export const NAV_ITEMS = [
  { to: '/', label: 'Image Studio', icon: ImageIcon },
  { to: '/video', label: 'Video Studio', icon: Film },
  { to: '/image-to-video', label: 'Image to Video', icon: Clapperboard },
  { to: '/image-editing', label: 'Image Editing', icon: Wand2 },
  { to: '/gallery', label: 'Gallery', icon: Images },
  { to: '/history', label: 'History', icon: History },
  { to: '/creative', label: 'Creative Studio', icon: BookOpen },
  { to: '/models', label: 'Models', icon: Cpu },
  { to: '/settings', label: 'Settings', icon: Settings },
]

export const NAV_UNAVAILABLE = [
  { to: '/unavailable/audio', label: 'Audio', icon: AudioLines, feature: 'Audio' },
  { to: '/unavailable/lip-sync', label: 'Lip Sync', icon: UserRound, feature: 'Lip Sync' },
  { to: '/unavailable/agents', label: 'Agents', icon: Bot, feature: 'Agents' },
]

export function Sidebar({ connection, footer }) {
  const [open, setOpen] = useState(false)
  const navigate = useNavigate()

  const navClass = ({ isActive }) =>
    `flex min-h-[44px] items-center gap-3 rounded-xl px-3 text-sm transition-colors duration-150 ${
      isActive ? 'bg-primary/10 text-primary' : 'text-secondary hover:bg-card-bg hover:text-text'
    }`

  const unavailableClass = 'flex min-h-[44px] items-center gap-3 rounded-xl px-3 text-sm text-muted transition-colors duration-150 hover:bg-card-bg'

  const content = (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2 px-4 py-4">
        <div className="h-8 w-8 rounded-xl bg-gradient-to-br from-primary to-accent" aria-hidden="true" />
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold">Open Generative AI</div>
          <div className="truncate text-xs text-muted">Self-Hosted AI Creative Studio</div>
        </div>
      </div>
      <nav aria-label="Main" className="flex-1 space-y-1 overflow-y-auto px-3 py-2">
        {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
          <NavLink key={to} to={to} end={to === '/'} className={navClass} onClick={() => setOpen(false)}>
            <Icon size={17} aria-hidden="true" /> {label}
          </NavLink>
        ))}
        <div className="px-3 pb-1 pt-4 text-xs font-medium uppercase tracking-wide text-muted">Cloud edition only</div>
        {NAV_UNAVAILABLE.map(({ to, label, icon: Icon }) => (
          <NavLink key={to} to={to} className={unavailableClass} onClick={() => setOpen(false)}>
            <Icon size={17} aria-hidden="true" /> {label}
          </NavLink>
        ))}
      </nav>
      <div className="border-t border-border p-3">{footer}</div>
    </div>
  )

  return (
    <>
      {/* Desktop sidebar */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 border-r border-border bg-panel-bg lg:block">{content}</aside>

      {/* Mobile top bar with hamburger */}
      <header className="header-gradient fixed inset-x-0 top-0 z-40 flex h-14 items-center justify-between border-b border-border bg-panel-bg px-3 lg:hidden">
        <div className="flex items-center gap-2">
          <div className="h-7 w-7 rounded-lg bg-gradient-to-br from-primary to-accent" aria-hidden="true" />
          <span className="truncate text-sm font-semibold">Open Generative AI</span>
        </div>
        <button
          type="button"
          onClick={() => setOpen(true)}
          title="Open navigation menu"
          aria-label="Open navigation menu"
          aria-expanded={open}
          className="flex h-11 w-11 items-center justify-center rounded-xl text-secondary transition-colors duration-150 hover:bg-card-bg hover:text-text"
        >
          <Menu size={20} aria-hidden="true" />
        </button>
      </header>

      {/* Mobile drawer */}
      {open ? (
        <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true">
          <div className="absolute inset-0 bg-black/70" onClick={() => setOpen(false)} aria-hidden="true" />
          <div className="absolute inset-y-0 left-0 w-72 max-w-[85vw] border-r border-border bg-panel-bg">
            <button
              type="button"
              onClick={() => setOpen(false)}
              title="Close menu"
              aria-label="Close menu"
              className="absolute right-2 top-2 flex h-11 w-11 items-center justify-center rounded-xl text-secondary transition-colors duration-150 hover:bg-card-bg hover:text-text"
            >
              <X size={20} aria-hidden="true" />
            </button>
            {content}
          </div>
        </div>
      ) : null}
    </>
  )
}

export default Sidebar
