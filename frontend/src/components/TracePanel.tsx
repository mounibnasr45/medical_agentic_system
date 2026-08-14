import {
  labelFor,
  STAGE_LABELS,
  TOOL_LABELS,
  type Trace,
  type ToolStatus,
} from '../types/events'

const ms = (value?: number) =>
  value === undefined ? '' : value >= 1000 ? `${(value / 1000).toFixed(1)}s` : `${value}ms`

function StatusDot({ status }: { status: ToolStatus | 'running' | 'done' | 'failed' }) {
  const colour =
    status === 'running'
      ? 'bg-[var(--color-accent)] animate-dot'
      : status === 'failed'
        ? 'bg-[var(--color-danger)]'
        : 'bg-[var(--color-ok)]'
  return <span className={`mt-1.5 size-1.5 shrink-0 rounded-full ${colour}`} />
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="border-b border-[var(--color-line)] px-4 py-3.5">
      <h3 className="mb-2.5 text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--color-ink-faint)]">
        {title}
      </h3>
      {children}
    </section>
  )
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-0.5 text-xs">
      <span className="text-[var(--color-ink-faint)]">{label}</span>
      <span className="text-right font-mono text-[var(--color-ink)]">{value}</span>
    </div>
  )
}

export function TracePanel({ trace, running }: { trace: Trace; running: boolean }) {
  const idle =
    !running &&
    !trace.router &&
    trace.stages.length === 0 &&
    trace.tools.length === 0 &&
    !trace.error

  return (
    <aside className="flex h-full min-h-0 flex-col bg-[var(--color-surface-sunken)]">
      <header className="flex items-center gap-2 border-b border-[var(--color-line)] px-4 py-3">
        <h2 className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--color-ink-muted)]">
          Pipeline
        </h2>
        {running && (
          <span className="ml-auto flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-wider text-[var(--color-accent)]">
            <span className="size-1.5 animate-dot rounded-full bg-[var(--color-accent)]" />
            live
          </span>
        )}
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {idle && (
          <p className="px-4 py-6 text-xs leading-relaxed text-[var(--color-ink-faint)]">
            Ask a question to see how it is routed, which agents are activated, and
            which sources are queried.
          </p>
        )}

        {trace.router && (
          <Section title="Router">
            <Field
              label="medical"
              value={trace.router.isMedical ? 'yes' : 'no'}
            />
            <Field label="intent" value={trace.router.intent} />
            <Field label="complexity" value={`${trace.router.complexity}/5`} />
            <Field
              label="confidence"
              value={trace.router.confidence.toFixed(2)}
            />
            <Field
              label="agents"
              value={trace.router.agents.length ? trace.router.agents.join(', ') : '—'}
            />
            {trace.router.useChainOfThought && <Field label="reasoning" value="chain of thought" />}
            {trace.router.reasoning && (
              <p className="mt-2 border-l-2 border-[var(--color-line)] pl-2.5 text-[11px] leading-relaxed text-[var(--color-ink-faint)]">
                {trace.router.reasoning}
              </p>
            )}
          </Section>
        )}

        {trace.stages.length > 0 && (
          <Section title="Stages">
            <ul className="space-y-1.5">
              {trace.stages.map((stage, index) => (
                <li key={`${stage.name}-${index}`} className="flex items-start gap-2 text-xs">
                  <StatusDot status={stage.status} />
                  <span className="flex-1 capitalize text-[var(--color-ink)]">
                    {labelFor(STAGE_LABELS, stage.name)}
                  </span>
                  <span className="font-mono text-[10px] text-[var(--color-ink-faint)]">
                    {ms(stage.elapsedMs)}
                  </span>
                </li>
              ))}
            </ul>
          </Section>
        )}

        {trace.tools.length > 0 && (
          <Section title="Tool calls">
            <ul className="space-y-1.5">
              {trace.tools.map((tool) => (
                <li key={tool.id} className="flex items-start gap-2 text-xs">
                  <StatusDot status={tool.status} />
                  <span className="flex-1 text-[var(--color-ink)]">
                    {labelFor(TOOL_LABELS, tool.tool)}
                    {tool.cached && (
                      <span className="ml-1.5 text-[10px] text-[var(--color-ink-faint)]">
                        cached
                      </span>
                    )}
                  </span>
                  <span className="font-mono text-[10px] text-[var(--color-ink-faint)]">
                    {ms(tool.elapsedMs)}
                  </span>
                </li>
              ))}
            </ul>
          </Section>
        )}

        {trace.cotSteps.length > 0 && (
          <Section title="Chain of thought">
            <ol className="space-y-2.5">
              {trace.cotSteps.map((step) => (
                <li key={step.index} className="text-xs">
                  <p className="font-medium text-[var(--color-ink)]">
                    <span className="mr-1.5 font-mono text-[10px] text-[var(--color-ink-faint)]">
                      {step.index}
                    </span>
                    {step.name}
                  </p>
                  {step.conclusion && (
                    <p className="mt-0.5 border-l-2 border-[var(--color-line)] pl-2.5 text-[11px] leading-relaxed text-[var(--color-ink-muted)]">
                      {step.conclusion}
                    </p>
                  )}
                </li>
              ))}
            </ol>
          </Section>
        )}

        {trace.error && (
          <Section title="Error">
            <p className="text-xs leading-relaxed text-[var(--color-danger)]">{trace.error}</p>
          </Section>
        )}
      </div>

      {trace.latencyMs !== undefined && (
        <footer className="flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-[var(--color-line)] px-4 py-2.5 font-mono text-[10px] text-[var(--color-ink-faint)]">
          <span>{ms(trace.latencyMs)}</span>
          {trace.processingMode && <span>{trace.processingMode.toLowerCase()}</span>}
          {!!trace.sourcesUsed?.length && <span>{trace.sourcesUsed.length} sources</span>}
          {typeof trace.confidence === 'number' && (
            <span>conf {trace.confidence.toFixed(2)}</span>
          )}
          {trace.fromShowcase && <span>precomputed</span>}
          {trace.fromCache && <span>cached</span>}
          <span className={trace.graphAvailable ? '' : 'text-[var(--color-warn)]'}>
            graph {trace.graphAvailable ? 'online' : 'offline'}
          </span>
        </footer>
      )}
    </aside>
  )
}
