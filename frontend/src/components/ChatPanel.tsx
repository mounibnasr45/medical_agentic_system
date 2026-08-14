import { useEffect, useRef } from 'react'
import Markdown from 'react-markdown'

import type { Message } from '../hooks/useConversation'
import type { ShowcaseExample } from '../lib/api'

interface Props {
  messages: Message[]
  running: boolean
  examples: ShowcaseExample[]
  onPick: (query: string) => void
}

function Empty({ examples, onPick }: { examples: ShowcaseExample[]; onPick: (q: string) => void }) {
  return (
    <div className="mx-auto max-w-xl px-6 py-10">
      <h2 className="text-lg font-medium text-[var(--color-ink)]">
        Ask a clinical question
      </h2>
      <p className="mt-2 text-sm leading-relaxed text-[var(--color-ink-muted)]">
        Questions are routed by a model that decides how many agents to run and
        which sources to query. Watch the pipeline panel while it works.
      </p>

      {examples.length > 0 && (
        <div className="mt-7">
          <p className="mb-2.5 text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--color-ink-faint)]">
            Examples
          </p>
          <ul className="space-y-1.5">
            {examples.map((example) => (
              <li key={example.id}>
                <button
                  type="button"
                  onClick={() => onPick(example.query)}
                  className="w-full rounded-lg border border-[var(--color-line)] bg-[var(--color-surface-raised)] px-3.5 py-2.5 text-left transition hover:border-[var(--color-accent)]/50"
                >
                  <span className="block text-sm text-[var(--color-ink)]">
                    {example.query}
                  </span>
                  <span className="mt-0.5 flex items-center gap-2 text-[11px] text-[var(--color-ink-faint)]">
                    {example.demonstrates}
                    {example.precomputed && (
                      <span className="rounded-sm bg-[var(--color-surface-sunken)] px-1.5 py-px font-mono text-[9px] uppercase tracking-wide">
                        free
                      </span>
                    )}
                  </span>
                </button>
              </li>
            ))}
          </ul>
          <p className="mt-2.5 text-[11px] leading-relaxed text-[var(--color-ink-faint)]">
            Examples marked free are pre-computed and do not count against the
            daily limit.
          </p>
        </div>
      )}
    </div>
  )
}

function Bubble({ message }: { message: Message }) {
  if (message.role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-br-sm bg-[var(--color-surface-raised)] px-3.5 py-2.5 text-sm text-[var(--color-ink)]">
          {message.content}
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-[92%]">
      <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--color-ink-faint)]">
        Assistant
      </p>
      <div className="prose-answer text-sm text-[var(--color-ink-muted)]">
        <Markdown>{message.content}</Markdown>
      </div>
    </div>
  )
}

function Working() {
  return (
    <div className="flex items-center gap-2 text-xs text-[var(--color-ink-faint)]">
      <span className="size-1.5 animate-dot rounded-full bg-[var(--color-accent)]" />
      Agents are working. Progress is shown in the pipeline panel.
    </div>
  )
}

export function ChatPanel({ messages, running, examples, onPick }: Props) {
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages.length, running])

  if (messages.length === 0 && !running) {
    return (
      <div className="min-h-0 flex-1 overflow-y-auto">
        <Empty examples={examples} onPick={onPick} />
      </div>
    )
  }

  return (
    <div className="min-h-0 flex-1 overflow-y-auto">
      <div className="mx-auto flex max-w-2xl flex-col gap-5 px-5 py-6">
        {messages.map((message) => (
          <Bubble key={message.id} message={message} />
        ))}
        {running && <Working />}
        <div ref={endRef} />
      </div>
    </div>
  )
}
