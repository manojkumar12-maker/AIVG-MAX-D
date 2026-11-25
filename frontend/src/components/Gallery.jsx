import { useEffect, useMemo, useState } from 'react'
import { Copy, Download, Search, Trash2, Wand2, X, Info } from 'lucide-react'
import backendClient, { getToken } from '../services/backendClient'
import { formatBytes, formatDate } from '../lib/format'
import { EmptyState } from './EmptyState'
import { Spinner } from './Spinner'

function outputSrc(filename) {
  return backendClient.outputUrl(filename, getToken())
}

export function Gallery({ outputs, loading, onDelete, onUseAsReference }) {
  const [filter, setFilter] = useState('all')
  const [query, setQuery] = useState('')
  const [sort, setSort] = useState('newest')
  const [preview, setPreview] = useState(null)

  const filtered = useMemo(() => {
    let list = [...(outputs || [])]
    if (filter !== 'all') list = list.filter((o) => o.type === filter)
    const q = query.trim().toLowerCase()
    if (q) list = list.filter((o) => (o.prompt || '').toLowerCase().includes(q))
    list.sort((a, b) => {
      const ta = Date.parse(a.created_at || a.finished_at || 0) || 0
      const tb = Date.parse(b.created_at || b.finished_at || 0) || 0
      return sort === 'newest' ? tb - ta : ta - tb
    })
    return list
  }, [outputs, filter, query, sort])

  useEffect(() => {
    if (!preview) return undefined
    const onKey = (e) => {
      if (e.key === 'Escape') setPreview(null)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [preview])

  if (loading) {
    return (
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="aspect-square animate-pulse rounded-xl border border-border bg-card-bg" />
        ))}
      </div>
    )
  }

  if (!outputs?.length) {
    return (
      <EmptyState
        icon={Wand2}
        title="No outputs yet"
        description="Connect a backend, then generate your first image or video — finished results appear here."
      />
    )
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative min-w-0 flex-1">
          <Search size={14} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" aria-hidden="true" />
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search prompts…"
            aria-label="Search prompts"
            className="min-h-[44px] w-full rounded-xl border border-border bg-card-bg pl-9 pr-3 text-sm text-text placeholder:text-muted focus:border-primary focus:outline-none"
          />
        </div>
        <select
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          aria-label="Filter by type"
          className="min-h-[44px] rounded-xl border border-border bg-card-bg px-3 text-sm text-secondary focus:border-primary focus:outline-none"
        >
          <option value="all">All types</option>
          <option value="image">Images</option>
          <option value="video">Videos</option>
        </select>
        <select
          value={sort}
          onChange={(e) => setSort(e.target.value)}
          aria-label="Sort order"
          className="min-h-[44px] rounded-xl border border-border bg-card-bg px-3 text-sm text-secondary focus:border-primary focus:outline-none"
        >
          <option value="newest">Newest first</option>
          <option value="oldest">Oldest first</option>
        </select>
      </div>

      {filtered.length === 0 ? (
        <EmptyState title="No matches" description="Nothing matches this filter or search. Try clearing the search box." />
      ) : (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {filtered.map((out, i) => (
            <figure
              key={`${out.job_id || i}-${out.filename}`}
              className="group overflow-hidden rounded-xl border border-border bg-card-bg transition-colors duration-150 hover:border-muted"
            >
              <button
                type="button"
                onClick={() => setPreview(out)}
                className="block w-full"
                title="Open fullscreen preview"
              >
                {out.type === 'video' ? (
                  <video src={outputSrc(out.filename)} className="aspect-square w-full object-cover" preload="metadata" muted />
                ) : (
                  <img src={outputSrc(out.filename)} alt={out.prompt || 'Generated output'} loading="lazy" className="aspect-square w-full object-cover" />
                )}
              </button>
              <figcaption className="space-y-1 p-2">
                <p className="line-clamp-2 min-h-[2.2em] text-xs text-secondary">{out.prompt || 'No prompt'}</p>
                <div className="flex items-center gap-1">
                  <button
                    type="button"
                    onClick={() => setPreview(out)}
                    title="View metadata"
                    aria-label="View metadata"
                    className="flex h-11 w-11 items-center justify-center rounded-lg text-muted transition-colors duration-150 hover:text-primary"
                  >
                    <Info size={15} aria-hidden="true" />
                  </button>
                  <a
                    href={outputSrc(out.filename)}
                    download={out.filename}
                    title="Download this output"
                    aria-label="Download output"
                    className="flex h-11 w-11 items-center justify-center rounded-lg text-muted transition-colors duration-150 hover:text-primary"
                  >
                    <Download size={15} aria-hidden="true" />
                  </a>
                  <button
                    type="button"
                    onClick={() => navigator.clipboard?.writeText(out.prompt || '')}
                    title="Copy prompt to clipboard"
                    aria-label="Copy prompt"
                    disabled={!out.prompt}
                    className="flex h-11 w-11 items-center justify-center rounded-lg text-muted transition-colors duration-150 hover:text-primary disabled:opacity-40"
                  >
                    <Copy size={15} aria-hidden="true" />
                  </button>
                  {out.type === 'image' && onUseAsReference ? (
                    <button
                      type="button"
                      onClick={() => onUseAsReference(out)}
                      title="Use as reference in Image Editing"
                      aria-label="Use as reference"
                      className="flex h-11 w-11 items-center justify-center rounded-lg text-muted transition-colors duration-150 hover:text-primary"
                    >
                      <Wand2 size={15} aria-hidden="true" />
                    </button>
                  ) : null}
                  {onDelete ? (
                    <button
                      type="button"
                      onClick={() => onDelete(out)}
                      title="Delete this job and its outputs"
                      aria-label="Delete output"
                      className="flex h-11 w-11 items-center justify-center rounded-lg text-muted transition-colors duration-150 hover:bg-red-500/10 hover:text-red-400"
                    >
                      <Trash2 size={15} aria-hidden="true" />
                    </button>
                  ) : null}
                </div>
              </figcaption>
            </figure>
          ))}
        </div>
      )}

      {preview ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/90 p-4"
          role="dialog"
          aria-modal="true"
          aria-label="Output preview"
          onClick={() => setPreview(null)}
        >
          <div className="max-h-full w-full max-w-3xl overflow-auto rounded-2xl border border-border bg-card-bg p-4" onClick={(e) => e.stopPropagation()}>
            <div className="mb-3 flex items-center justify-between gap-2">
              <h3 className="truncate text-sm font-medium text-text">{preview.prompt || 'Output'}</h3>
              <button
                type="button"
                onClick={() => setPreview(null)}
                title="Close preview"
                aria-label="Close preview"
                className="flex h-11 w-11 items-center justify-center rounded-lg text-secondary transition-colors duration-150 hover:text-text"
              >
                <X size={18} aria-hidden="true" />
              </button>
            </div>
            {preview.type === 'video' ? (
              <video src={outputSrc(preview.filename)} controls className="max-h-[60vh] w-full rounded-xl bg-black" />
            ) : (
              <img src={outputSrc(preview.filename)} alt={preview.prompt || 'Generated output'} className="max-h-[60vh] w-full rounded-xl object-contain" />
            )}
            <dl className="mt-3 grid grid-cols-2 gap-2 text-xs">
              <div>
                <dt className="text-muted">Filename</dt>
                <dd className="break-all text-secondary">{preview.filename}</dd>
              </div>
              <div>
                <dt className="text-muted">Type</dt>
                <dd className="text-secondary">{preview.type}</dd>
              </div>
              <div>
                <dt className="text-muted">Size</dt>
                <dd className="text-secondary">{formatBytes(preview.size_bytes)}</dd>
              </div>
              <div>
                <dt className="text-muted">Dimensions</dt>
                <dd className="text-secondary">{preview.width && preview.height ? `${preview.width}×${preview.height}` : '—'}</dd>
              </div>
              {preview.duration ? (
                <div>
                  <dt className="text-muted">Duration</dt>
                  <dd className="text-secondary">{preview.duration}s</dd>
                </div>
              ) : null}
              <div>
                <dt className="text-muted">Created</dt>
                <dd className="text-secondary">{formatDate(preview.created_at || preview.finished_at)}</dd>
              </div>
              {preview.seed != null ? (
                <div>
                  <dt className="text-muted">Seed</dt>
                  <dd className="text-secondary">{preview.seed}</dd>
                </div>
              ) : null}
              <div className="col-span-2">
                <dt className="text-muted">Prompt</dt>
                <dd className="text-secondary">{preview.prompt || '—'}</dd>
              </div>
            </dl>
            <div className="mt-3 flex flex-wrap gap-2">
              <a
                href={outputSrc(preview.filename)}
                download={preview.filename}
                className="flex min-h-[44px] items-center gap-2 rounded-xl bg-primary px-4 text-sm font-medium text-app-bg transition-colors duration-150 hover:bg-primary-hover"
              >
                <Download size={15} aria-hidden="true" /> Download
              </a>
              <button
                type="button"
                onClick={() => navigator.clipboard?.writeText(preview.prompt || '')}
                disabled={!preview.prompt}
                title={preview.prompt ? 'Copy prompt to clipboard' : 'No prompt to copy'}
                className="flex min-h-[44px] items-center gap-2 rounded-xl border border-border px-4 text-sm text-secondary transition-colors duration-150 hover:text-text disabled:opacity-50"
              >
                <Copy size={15} aria-hidden="true" /> Copy prompt
              </button>
              {preview.type === 'image' && onUseAsReference ? (
                <button
                  type="button"
                  onClick={() => {
                    onUseAsReference(preview)
                    setPreview(null)
                  }}
                  className="flex min-h-[44px] items-center gap-2 rounded-xl border border-border px-4 text-sm text-secondary transition-colors duration-150 hover:text-text"
                >
                  <Wand2 size={15} aria-hidden="true" /> Use as reference
                </button>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}

export default Gallery
