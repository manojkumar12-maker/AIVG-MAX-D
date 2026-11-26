import { useEffect, useState } from 'react'
import { Loader2, Save } from 'lucide-react'

function Field({ label, value, onChange, textarea = false }) {
  const cls = 'w-full rounded-md border border-white/10 bg-black/30 px-2 py-1.5 text-sm text-white/90 outline-none focus:border-white/30'
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-white/60">{label}</span>
      {textarea
        ? <textarea className={cls} rows={2} value={value} onChange={(e) => onChange(e.target.value)} />
        : <input className={cls} value={value} onChange={(e) => onChange(e.target.value)} />}
    </label>
  )
}

function ListEditor({ title, items, fields, onChange }) {
  const update = (i, field, value) => {
    const next = items.map((it, idx) => (idx === i ? { ...it, [field]: value } : it))
    onChange(next)
  }
  return (
    <section className="rounded-lg border border-white/10 bg-white/5 p-3">
      <header className="mb-2 flex items-center justify-between">
        <h4 className="text-sm font-semibold text-white/80">{title}</h4>
        <button
          type="button"
          className="rounded-md border border-white/15 px-2 py-0.5 text-xs text-white/70 hover:bg-white/10"
          onClick={() => onChange([...items, { id: '', ...Object.fromEntries(fields.map((f) => [f, ''])) }])}
        >
          + Add
        </button>
      </header>
      {items.length === 0 && <p className="text-xs text-white/40">None defined.</p>}
      <div className="space-y-2">
        {items.map((item, i) => (
          <div key={i} className="flex flex-wrap items-end gap-2">
            {fields.map((f) => (
              <Field
                key={f}
                label={f}
                value={item[f] || ''}
                onChange={(v) => update(i, f, v)}
              />
            ))}
            <button
              type="button"
              aria-label={`Remove ${title} entry`}
              className="rounded-md border border-white/15 px-2 py-1 text-xs text-white/60 hover:bg-white/10"
              onClick={() => onChange(items.filter((_, idx) => idx !== i))}
            >
              ✕
            </button>
          </div>
        ))}
      </div>
    </section>
  )
}

/**
 * Film-level continuity editor (Phase 4). Edit-only: saving canon never
 * triggers any generation work.
 */
export default function ContinuityPanel({ filmId, api, onSaved }) {
  const [data, setData] = useState(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    let live = true
    setData(null)
    setError(null)
    api.getFilmContinuity(filmId)
      .then((res) => { if (live) setData(res.continuity) })
      .catch((err) => { if (live) setError(err) })
    return () => { live = false }
  }, [filmId, api])

  const save = async () => {
    setSaving(true)
    setError(null)
    setSaved(false)
    try {
      const res = await api.updateFilmContinuity(filmId, data)
      setData(res.continuity)
      setSaved(true)
      onSaved?.(res.continuity)
    } catch (err) {
      setError(err)
    } finally {
      setSaving(false)
    }
  }

  if (error && !data) {
    return <p className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">{error.error || 'Failed to load continuity.'}</p>
  }
  if (!data) {
    return <p className="flex items-center gap-2 p-3 text-sm text-white/50"><Loader2 className="animate-spin" size={14} /> Loading continuity…</p>
  }

  return (
    <div className="space-y-3" data-testid="continuity-panel">
      <section className="rounded-lg border border-white/10 bg-white/5 p-3">
        <Field label="Visual style (supplements the Film Bible style guide)" textarea
          value={data.style || ''} onChange={(v) => setData({ ...data, style: v })} />
      </section>
      <ListEditor title="Characters" items={data.characters || []} fields={['name', 'appearance']}
        onChange={(characters) => setData({ ...data, characters })} />
      <ListEditor title="Wardrobe" items={data.wardrobe || []} fields={['label', 'description']}
        onChange={(wardrobe) => setData({ ...data, wardrobe })} />
      <ListEditor title="Props" items={data.props || []} fields={['label', 'description']}
        onChange={(props) => setData({ ...data, props })} />
      <ListEditor title="Locations" items={data.locations || []} fields={['label', 'description']}
        onChange={(locations) => setData({ ...data, locations })} />

      {error && <p className="text-sm text-red-300">{error.error || 'Save failed.'}</p>}
      {saved && <p className="text-sm text-emerald-300">Continuity saved.</p>}
      <button
        type="button"
        onClick={save}
        disabled={saving}
        className="inline-flex items-center gap-2 rounded-lg bg-white/10 px-3 py-1.5 text-sm font-medium text-white hover:bg-white/20 disabled:opacity-50"
      >
        {saving ? <Loader2 className="animate-spin" size={14} /> : <Save size={14} />} Save continuity
      </button>
    </div>
  )
}
