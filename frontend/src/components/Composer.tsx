import { useState, type FormEvent, type KeyboardEvent } from 'react'

interface Props {
  disabled: boolean
  placeholder: string
  onSubmit: (query: string) => void
}

export function Composer({ disabled, placeholder, onSubmit }: Props) {
  const [value, setValue] = useState('')

  const submit = (event: FormEvent) => {
    event.preventDefault()
    const trimmed = value.trim()
    if (!trimmed || disabled) return
    onSubmit(trimmed)
    setValue('')
  }

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      submit(event)
    }
  }

  return (
    <form
      onSubmit={submit}
      className="border-t border-[var(--color-line)] bg-[var(--color-surface)] px-5 py-3.5"
    >
      <div className="mx-auto flex max-w-2xl items-end gap-2">
        <textarea
          value={value}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={onKeyDown}
          disabled={disabled}
          rows={1}
          maxLength={1000}
          placeholder={placeholder}
          className="max-h-32 min-h-[42px] flex-1 resize-none rounded-lg border border-[var(--color-line)] bg-[var(--color-surface-raised)] px-3.5 py-2.5 text-sm text-[var(--color-ink)] placeholder:text-[var(--color-ink-faint)] focus:border-[var(--color-accent)]/60 focus:outline-none disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={disabled || !value.trim()}
          className="h-[42px] rounded-lg bg-[var(--color-accent)] px-4 text-sm font-medium text-[var(--color-surface)] transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-30"
        >
          Ask
        </button>
      </div>
    </form>
  )
}
