import { useCallback, useEffect, useState } from 'react'

import { ChatPanel } from './components/ChatPanel'
import { Composer } from './components/Composer'
import { TracePanel } from './components/TracePanel'
import { useConversation } from './hooks/useConversation'
import { currentGuest, signInAsGuest, type GuestSession } from './lib/guest'
import type { ShowcaseExample } from './lib/api'
import { resetLabel } from './lib/quota'
import { Landing } from './pages/Landing'
import type { Quota } from './types/events'

const DISCLAIMER =
  'Engineering demonstration, not medical advice. Consult a qualified professional.'

const CONSOLE_HASH = '#/console'

type View = 'landing' | 'console'

const viewFromLocation = (): View =>
  window.location.hash === CONSOLE_HASH ? 'console' : 'landing'

function Header({
  guest,
  quotaLabel,
  graphOnline,
  onReset,
  canReset,
  onLeave,
}: {
  guest: GuestSession | null
  quotaLabel: string
  graphOnline: boolean | null
  onReset: () => void
  canReset: boolean
  onLeave: () => void
}) {
  return (
    <header className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-[var(--color-line)] px-5 py-3">
      <div className="min-w-0">
        <h1 className="truncate text-sm font-semibold text-[var(--color-ink)]">
          Medical Agent
        </h1>
        <p className="truncate text-[11px] text-[var(--color-ink-faint)]">
          {guest ? (
            <>
              Signed in as guest{' '}
              <span className="font-mono text-[var(--color-ink-muted)]">{guest.id}</span>
            </>
          ) : (
            'Multi-agent clinical retrieval over a knowledge graph'
          )}
        </p>
      </div>

      <div className="ml-auto flex flex-wrap items-center gap-x-3 gap-y-1.5 text-[11px]">
        {graphOnline !== null && (
          <span
            className={
              graphOnline ? 'text-[var(--color-ink-faint)]' : 'text-[var(--color-warn)]'
            }
            title={
              graphOnline
                ? 'Knowledge graph reachable'
                : 'Knowledge graph unavailable; answers fall back to web search'
            }
          >
            graph {graphOnline ? 'online' : 'offline'}
          </span>
        )}
        <span className="font-mono text-[var(--color-ink-muted)]">{quotaLabel}</span>
        {canReset && (
          <button
            type="button"
            onClick={onReset}
            className="rounded border border-[var(--color-line)] px-2 py-1 text-[var(--color-ink-muted)] transition hover:text-[var(--color-ink)]"
          >
            New chat
          </button>
        )}
        <button
          type="button"
          onClick={onLeave}
          className="rounded border border-[var(--color-line)] px-2 py-1 text-[var(--color-ink-muted)] transition hover:text-[var(--color-ink)]"
        >
          Overview
        </button>
      </div>
    </header>
  )
}

function Waking({ attempt }: { attempt: number }) {
  return (
    <div className="flex h-full items-center justify-center px-6">
      <div className="max-w-sm text-center">
        <div className="mx-auto mb-4 flex gap-1.5">
          {[0, 1, 2].map((index) => (
            <span
              key={index}
              className="size-1.5 animate-dot rounded-full bg-[var(--color-accent)]"
              style={{ animationDelay: `${index * 0.2}s` }}
            />
          ))}
        </div>
        <p className="text-sm text-[var(--color-ink)]">Waking the backend</p>
        <p className="mt-2 text-xs leading-relaxed text-[var(--color-ink-faint)]">
          The API runs on a free instance that sleeps after fifteen minutes idle.
          A cold start takes up to a minute. This page is served from a CDN, which
          is why it loaded immediately.
        </p>
        {attempt > 3 && (
          <p className="mt-2.5 font-mono text-[10px] text-[var(--color-ink-faint)]">
            attempt {attempt}
          </p>
        )}
      </div>
    </div>
  )
}

function Offline() {
  return (
    <div className="flex h-full items-center justify-center px-6">
      <div className="max-w-sm text-center">
        <p className="text-sm text-[var(--color-ink)]">The backend is not responding</p>
        <p className="mt-2 text-xs leading-relaxed text-[var(--color-ink-faint)]">
          The free instance may be redeploying. Reload in a minute.
        </p>
      </div>
    </div>
  )
}

/**
 * Replaces the composer once the allowance is gone.
 *
 * It offers the pre-computed questions rather than only reporting the wall,
 * because those still run: they are answered from disk and never charged. On an
 * empty conversation the panel behind it is already listing them, so they are
 * offered here only once there is a conversation covering them up.
 */
function Spent({
  quota,
  examples,
  onPick,
}: {
  quota: Quota
  examples: ShowcaseExample[]
  onPick: (query: string) => void
}) {
  const free = examples.filter((example) => example.precomputed)

  return (
    <div className="border-t border-[var(--color-line)] bg-[var(--color-surface-raised)] px-5 py-4">
      <div className="mx-auto max-w-2xl">
        <p className="text-sm text-[var(--color-ink)]">
          That is all {quota.limit} questions for today.
        </p>
        <p className="mt-1.5 text-xs leading-relaxed text-[var(--color-ink-faint)]">
          The allowance resets at {resetLabel(quota.resets_at)}. These examples are
          answered from disk, so they still work and do not count against it.
        </p>

        {free.length > 0 && (
          <ul className="mt-3 flex flex-wrap gap-1.5">
            {free.map((example) => (
              <li key={example.id}>
                <button
                  type="button"
                  onClick={() => onPick(example.query)}
                  className="rounded-full border border-[var(--color-line)] px-2.5 py-1 text-[11px] text-[var(--color-ink-muted)] transition hover:border-[var(--color-accent)]/50 hover:text-[var(--color-ink)]"
                >
                  {example.query}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

function Console({ guest, onLeave }: { guest: GuestSession | null; onLeave: () => void }) {
  const {
    status,
    wakeAttempt,
    health,
    messages,
    liveTrace,
    quota,
    examples,
    error,
    send,
    reset,
  } = useConversation()

  const running = status === 'running'
  const lastTrace = [...messages].reverse().find((m) => m.trace)?.trace
  const trace = running || !lastTrace ? liveTrace : lastTrace

  const quotaLabel = quota
    ? `${quota.remaining}/${quota.limit} today`
    : health
      ? `${health.daily_query_limit}/day`
      : ''

  const graphOnline =
    trace.graphAvailable ?? (health ? health.graph.status === 'connected' : null)

  const spent = quota !== null && quota.remaining === 0

  return (
    <div className="flex h-full flex-col">
      <Header
        guest={guest}
        quotaLabel={quotaLabel}
        graphOnline={graphOnline ?? null}
        onReset={reset}
        canReset={messages.length > 0}
        onLeave={onLeave}
      />

      <main className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[1fr_320px]">
        <section className="flex min-h-0 flex-col border-r border-[var(--color-line)]">
          {status === 'waking' ? (
            <Waking attempt={wakeAttempt} />
          ) : status === 'offline' ? (
            <Offline />
          ) : (
            <>
              <ChatPanel
                messages={messages}
                running={running}
                examples={examples}
                onPick={send}
              />
              {error && !spent && (
                <div className="border-t border-[var(--color-line)] bg-[var(--color-surface-raised)] px-5 py-2.5">
                  <p className="mx-auto max-w-2xl text-xs text-[var(--color-warn)]">{error}</p>
                </div>
              )}
              {spent ? (
                <Spent
                  quota={quota}
                  examples={messages.length > 0 ? examples : []}
                  onPick={send}
                />
              ) : (
                <Composer
                  disabled={running}
                  placeholder={running ? 'Working...' : 'Can I take aspirin with warfarin?'}
                  onSubmit={send}
                />
              )}
            </>
          )}
        </section>

        {/* Hidden on narrow screens: the trace is supporting detail, and a
            320px rail would crowd the conversation on a phone. */}
        <div className="hidden min-h-0 lg:block">
          <TracePanel trace={trace} running={running} />
        </div>
      </main>

      <footer className="border-t border-[var(--color-line)] px-5 py-2 text-center text-[10px] text-[var(--color-ink-faint)]">
        {DISCLAIMER}
      </footer>
    </div>
  )
}

export default function App() {
  const [view, setView] = useState<View>(viewFromLocation)
  const [guest, setGuest] = useState<GuestSession | null>(currentGuest)

  useEffect(() => {
    const sync = () => setView(viewFromLocation())
    window.addEventListener('hashchange', sync)
    window.addEventListener('popstate', sync)
    return () => {
      window.removeEventListener('hashchange', sync)
      window.removeEventListener('popstate', sync)
    }
  }, [])

  // The landing page and the console sit on opposite grounds; the stylesheet
  // keys off this rather than each view painting its own full-page background.
  useEffect(() => {
    document.body.dataset.view = view
    window.scrollTo({ top: 0 })
  }, [view])

  // Deep links to the console skip the button, so mint the session here too.
  useEffect(() => {
    if (view === 'console' && !guest) setGuest(signInAsGuest())
  }, [view, guest])

  const enter = useCallback(() => {
    setGuest(signInAsGuest())
    window.location.hash = CONSOLE_HASH
  }, [])

  const leave = useCallback(() => {
    window.history.pushState(null, '', window.location.pathname + window.location.search)
    setView('landing')
  }, [])

  return view === 'console' ? (
    <Console guest={guest} onLeave={leave} />
  ) : (
    <Landing onEnter={enter} />
  )
}
