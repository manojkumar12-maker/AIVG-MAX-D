import { useCallback, useEffect, useRef, useState } from 'react'
import { ImagePlus, UploadCloud, X, Loader2 } from 'lucide-react'
import backendClient from '../services/backendClient'
import { friendlyError } from '../services/generationService'

export function ImageUploader({ value, onChange, label = 'Image', disabled = false, disabledReason = 'Connect a backend first.' }) {
  const inputRef = useRef(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [dragging, setDragging] = useState(false)
  const [localFile, setLocalFile] = useState(null)

  useEffect(() => {
    if (!localFile) return undefined
    const url = URL.createObjectURL(localFile)
    return () => URL.revokeObjectURL(url)
  }, [localFile])

  const handleFile = useCallback(
    async (file) => {
      if (!file) return
      if (!file.type.startsWith('image/')) {
        setError('Only image files are accepted.')
        return
      }
      setError(null)
      if (disabled) {
        setError(disabledReason)
        return
      }
      setBusy(true)
      try {
        const res = await backendClient.upload(file)
        setLocalFile(file)
        onChange?.(res?.filename || res?.url)
      } catch (err) {
        setError(friendlyError(err))
      } finally {
        setBusy(false)
      }
    },
    [disabled, disabledReason, onChange]
  )

  useEffect(() => {
    if (!value) setLocalFile(null)
  }, [value])

  useEffect(() => {
    const onPaste = (e) => {
      if (disabled || busy) return
      const item = Array.from(e.clipboardData?.files || []).find((f) => f.type.startsWith('image/'))
      if (item) {
        e.preventDefault()
        handleFile(item)
      }
    }
    window.addEventListener('paste', onPaste)
    return () => window.removeEventListener('paste', onPaste)
  }, [disabled, busy, handleFile])

  const hasPreview = Boolean(value)

  return (
    <div>
      <div className="mb-1.5 text-xs font-medium uppercase tracking-wide text-muted">{label}</div>
      {hasPreview ? (
        <div className="relative overflow-hidden rounded-xl border border-border bg-card-bg">
          {localFile ? (
            <img src={URL.createObjectURL(localFile)} alt="Uploaded reference" className="max-h-48 w-full object-contain" />
          ) : (
            <div className="p-4 text-sm text-secondary">Uploaded: {value}</div>
          )}
          <div className="flex items-center justify-between gap-2 p-2">
            <button
              type="button"
              className="min-h-[44px] flex-1 rounded-lg border border-border px-3 text-xs text-secondary transition-colors duration-150 hover:bg-border hover:text-text disabled:opacity-50"
              onClick={() => inputRef.current?.click()}
              disabled={disabled || busy}
              title={disabled ? disabledReason : 'Replace this image'}
            >
              Replace
            </button>
            <button
              type="button"
              className="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg border border-border text-secondary transition-colors duration-150 hover:bg-red-500/10 hover:text-red-400 disabled:opacity-50"
              onClick={() => onChange?.(null)}
              disabled={disabled || busy}
              title="Remove this image"
              aria-label="Remove image"
            >
              <X size={16} aria-hidden="true" />
            </button>
          </div>
        </div>
      ) : (
        <div
          role="button"
          tabIndex={0}
          onClick={() => !disabled && !busy && inputRef.current?.click()}
          onKeyDown={(e) => {
            if ((e.key === 'Enter' || e.key === ' ') && !disabled && !busy) {
              e.preventDefault()
              inputRef.current?.click()
            }
          }}
          onDragOver={(e) => {
            e.preventDefault()
            if (!disabled) setDragging(true)
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault()
            setDragging(false)
            if (!disabled) handleFile(e.dataTransfer.files?.[0])
          }}
          className={`flex min-h-[44px] cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border border-dashed p-6 text-center transition-colors duration-150 ${
            dragging ? 'border-primary bg-primary/5' : 'border-border bg-card-bg hover:border-muted'
          } ${disabled ? 'cursor-not-allowed opacity-50' : ''}`}
          aria-disabled={disabled}
        >
          {busy ? (
            <Loader2 size={20} className="animate-spin text-primary" aria-hidden="true" />
          ) : (
            <ImagePlus size={20} className="text-muted" aria-hidden="true" />
          )}
          <div className="text-sm text-secondary">
            {busy ? 'Uploading…' : 'Drop an image, paste, or click to upload'}
          </div>
          <div className="flex items-center gap-1 text-xs text-muted">
            <UploadCloud size={12} aria-hidden="true" /> Image files only
          </div>
        </div>
      )}
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        capture="environment"
        className="hidden"
        onChange={(e) => {
          handleFile(e.target.files?.[0])
          e.target.value = ''
        }}
      />
      {error ? <p className="mt-2 text-xs text-red-400">{error}</p> : null}
    </div>
  )
}

export default ImageUploader
