import { useEffect, useState } from 'react'
import { Sliders, X } from 'lucide-react'

/**
 * Studio shell: page header, settings panel (right column on desktop,
 * bottom drawer on mobile) and the main output area.
 */
export function StudioShell({ title, description, settings, children }) {
  const [drawerOpen, setDrawerOpen] = useState(false)

  return (
    <div className="flex min-h-[calc(100vh-3.5rem)] flex-col lg:h-[calc(100vh-0rem)] lg:flex-row">
      <section className="flex min-w-0 flex-1 flex-col overflow-y-auto p-4 lg:h-full" aria-label={`${title} output`}>
        <header className="header-gradient mb-4 rounded-2xl border border-border px-4 py-3">
          <h1 className="text-lg font-semibold">{title}</h1>
          {description ? <p className="mt-0.5 text-sm text-secondary">{description}</p> : null}
        </header>
        <div className="min-w-0 flex-1">{children}</div>
      </section>

      {/* Desktop settings column */}
      <aside className="hidden w-96 shrink-0 overflow-y-auto border-l border-border bg-panel-bg p-4 lg:block" aria-label="Generation settings">
        {settings}
      </aside>

      {/* Mobile settings drawer handle (bottom safe area) */}
      <div className="fixed inset-x-0 bottom-0 z-40 border-t border-border bg-panel-bg p-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] lg:hidden">
        <button
          type="button"
          onClick={() => setDrawerOpen(true)}
          className="flex min-h-[44px] w-full items-center justify-center gap-2 rounded-xl bg-primary text-sm font-medium text-app-bg transition-colors duration-150 hover:bg-primary-hover"
        >
          <Sliders size={16} aria-hidden="true" /> Generation settings
        </button>
      </div>

      {drawerOpen ? (
        <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true" aria-label="Generation settings">
          <div className="absolute inset-0 bg-black/70" onClick={() => setDrawerOpen(false)} aria-hidden="true" />
          <div className="absolute inset-x-0 bottom-0 max-h-[85vh] overflow-y-auto rounded-t-2xl border-t border-border bg-panel-bg p-4 pb-[max(1rem,env(safe-area-inset-bottom))]">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-sm font-semibold">Generation settings</h2>
              <button
                type="button"
                onClick={() => setDrawerOpen(false)}
                title="Close settings"
                aria-label="Close settings"
                className="flex h-11 w-11 items-center justify-center rounded-xl text-secondary transition-colors duration-150 hover:bg-card-bg hover:text-text"
              >
                <X size={20} aria-hidden="true" />
              </button>
            </div>
            {settings}
          </div>
        </div>
      ) : null}
    </div>
  )
}

export default StudioShell
