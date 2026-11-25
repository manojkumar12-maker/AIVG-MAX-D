export function Field({ label, htmlFor, hint, children }) {
  return (
    <div>
      <label htmlFor={htmlFor} className="mb-1 block text-xs font-medium uppercase tracking-wide text-muted">
        {label}
      </label>
      {children}
      {hint ? <p className="mt-1 text-xs text-muted">{hint}</p> : null}
    </div>
  )
}

export function Slider({ id, value, min, max, step = 1, onChange, disabled = false, disabledReason = 'Disabled', format }) {
  return (
    <div className="flex items-center gap-3">
      <input
        id={id}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        disabled={disabled}
        title={disabled ? disabledReason : undefined}
        aria-label={id}
        className="h-11 flex-1 disabled:opacity-50"
      />
      <span className="w-14 shrink-0 text-right text-sm text-secondary tabular-nums">
        {format ? format(value) : value}
      </span>
    </div>
  )
}

export function TextInput({ id, value, onChange, type = 'text', placeholder, disabled = false, disabledReason = 'Disabled', min, max, invalid = false }) {
  return (
    <input
      id={id}
      type={type}
      value={value}
      min={min}
      max={max}
      placeholder={placeholder}
      onChange={(e) => onChange(e.target.value)}
      disabled={disabled}
      title={disabled ? disabledReason : undefined}
      aria-invalid={invalid}
      className={`min-h-[44px] w-full rounded-xl border bg-panel-bg px-3 text-sm text-text placeholder:text-muted focus:border-primary focus:outline-none disabled:cursor-not-allowed disabled:opacity-50 ${
        invalid ? 'border-red-500/60' : 'border-border'
      }`}
    />
  )
}

export function Select({ id, value, onChange, options, disabled = false, disabledReason = 'Disabled' }) {
  return (
    <select
      id={id}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      disabled={disabled}
      title={disabled ? disabledReason : undefined}
      className="min-h-[44px] w-full rounded-xl border border-border bg-panel-bg px-3 text-sm text-text focus:border-primary focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
    >
      {options.map((opt) => (
        <option key={opt.value} value={opt.value}>
          {opt.label}
        </option>
      ))}
    </select>
  )
}

export function GenerateButton({ onClick, disabled, disabledReason, busy }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled || busy}
      title={disabledReason}
      className="flex min-h-[44px] w-full items-center justify-center gap-2 rounded-xl bg-primary text-sm font-semibold text-app-bg shadow-[0_0_20px_rgba(34,211,238,.4)] transition-colors duration-150 hover:bg-primary-hover disabled:cursor-not-allowed disabled:opacity-50 disabled:shadow-none"
    >
      {busy ? <Loader2 /> : null}
      {busy ? 'Submitting…' : 'Generate'}
    </button>
  )
}

function Loader2() {
  return (
    <span
      aria-hidden="true"
      className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-app-bg/40 border-t-app-bg"
    />
  )
}
