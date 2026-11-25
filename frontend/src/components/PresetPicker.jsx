export function PresetPicker({ label, options, value, onChange, className = '', optionClassName = '' }) {
  return (
    <div className={className}>
      {label ? (
        <div className="mb-1.5 text-xs font-medium uppercase tracking-wide text-muted">{label}</div>
      ) : null}
      <div className="flex flex-wrap gap-1.5" role="group" aria-label={label || 'Presets'}>
        {options.map((opt) => {
          const id = typeof opt === 'string' ? opt : opt.id
          const label2 = typeof opt === 'string' ? opt : opt.label
          const active = value === id
          return (
            <button
              key={id}
              type="button"
              aria-pressed={active}
              title={typeof opt === 'object' ? opt.description : undefined}
              onClick={() => onChange(id)}
              className={`min-h-[44px] rounded-xl border px-3 text-sm transition-colors duration-150 ${
                active
                  ? 'border-primary bg-primary/10 text-primary shadow-[0_0_20px_rgba(34,211,238,.4)]'
                  : 'border-border bg-card-bg text-secondary hover:border-muted hover:text-text'
              } ${optionClassName}`}
            >
              {label2}
            </button>
          )
        })}
      </div>
    </div>
  )
}

export default PresetPicker
