import { ChatPanel } from './components/ChatPanel'
import { Composer } from './components/Composer'
import { TracePanel } from './components/TracePanel'
import { useConversation } from './hooks/useConversation'

const DISCLAIMER =
  'Engineering demonstration, not medical advice. Consult a qualified professional.'

function Header({
  quotaLabel,
  graphOnline,
  onReset,
  canReset,
}: {
  quotaLabel: string
  graphOnline: boolean | null
  onReset: () => void
  canReset: boolean
}) {
  return (
    <header className="flex items-center gap-3 border-b border-[var(--color-line)] px-5 py-3">
      <div className="min-w-0">
        <h1 className="truncate text-sm font-semibold text-[var(--color-ink)]">
          Medical Agent
        </h1>
        <p className="truncate text-[11px] text-[var(--color-ink-faint)]">
          Multi-agent clinical retrieval over a knowledge graph
        </p>
      </div>

      <div className="ml-auto flex items-center gap-3 text-[11px]">
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

export default function App() {
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
    trace.graphAvailable ??
    (health ? health.graph.status === 'connected' : null)

  return (
    <div className="flex h-full flex-col">
      <Header
        quotaLabel={quotaLabel}
        graphOnline={graphOnline ?? null}
        onReset={reset}
        canReset={messages.length > 0}
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
              {error && (
                <div className="border-t border-[var(--color-line)] bg-[var(--color-surface-raised)] px-5 py-2.5">
                  <p className="mx-auto max-w-2xl text-xs text-[var(--color-warn)]">{error}</p>
                </div>
              )}
              <Composer
                disabled={running}
                placeholder={
                  running ? 'Working...' : 'Can I take aspirin with warfarin?'
                }
                onSubmit={send}
              />
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
