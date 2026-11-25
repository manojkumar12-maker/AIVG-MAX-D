export function EmptyState({ icon: Icon, title, description, action }) {
  return (
    <div className="panel-gradient flex flex-col items-center justify-center rounded-2xl border border-border p-8 text-center">
      {Icon ? (
        <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-card-bg text-primary">
          <Icon size={24} aria-hidden="true" />
        </div>
      ) : null}
      <h3 className="text-base font-medium text-text">{title}</h3>
      {description ? <p className="mt-2 max-w-sm text-sm text-secondary">{description}</p> : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  )
}

export default EmptyState
