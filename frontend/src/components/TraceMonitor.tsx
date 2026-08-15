/**
 * The landing page's one moving part: a window cut into the paper, replaying
 * runs the deployed pipeline actually performed.
 *
 * It exists because the routing decision is the thing worth seeing and the
 * hardest thing to assert in a sentence. Watching one question collect two
 * agents and a generated Cypher query while another is refused outright makes
 * the argument on its own.
 */

import { useEffect, useState } from 'react'

import { usePrefersReducedMotion } from '../hooks/usePrefersReducedMotion'
import { OPENING_RUN, RECORDED_RUNS, type RunLine, type Tone } from '../lib/recordedRuns'

const REVEAL_MS = 360
const DWELL_MS = 3800

const seconds = (ms: number) => `${(ms / 1000).toFixed(1)}s`

const TONE: Record<Tone, string> = {
  plain: 'text-scope-ink',
  signal: 'text-signal',
  flag: 'text-scope-flag',
}

function Row({ label, value, tone = 'plain' }: RunLine) {
  return (
    <div className="monitor-line grid grid-cols-[4.75rem_1fr] items-baseline gap-3">
      <span className="text-[10px] uppercase tracking-[0.14em] text-scope-dim">{label}</span>
      <span className={`text-xs leading-relaxed ${TONE[tone]}`}>{value}</span>
    </div>
  )
}

export function TraceMonitor() {
  const reduced = usePrefersReducedMotion()
  const [active, setActive] = useState(OPENING_RUN)
  const [revealed, setRevealed] = useState(0)
  // A visitor who picks a run has taken over; the replay stops moving under them.
  const [replaying, setReplaying] = useState(true)

  const run = RECORDED_RUNS[active]!
  const blocks = 1 + run.lines.length + (run.reasoning ? 1 : 0) + 1

  useEffect(() => {
    if (reduced || !replaying) {
      setRevealed(blocks)
      return
    }

    setRevealed(0)
    let step = 0
    let advance: number | undefined

    const reveal = window.setInterval(() => {
      step += 1
      setRevealed(step)
      if (step < blocks) return

      window.clearInterval(reveal)
      advance = window.setTimeout(
        () => setActive((index) => (index + 1) % RECORDED_RUNS.length),
        DWELL_MS,
      )
    }, REVEAL_MS)

    return () => {
      window.clearInterval(reveal)
      if (advance !== undefined) window.clearTimeout(advance)
    }
  }, [active, blocks, reduced, replaying])

  const shown = (index: number) => index < revealed
  const reasoningAt = 1 + run.lines.length
  const answerAt = blocks - 1

  return (
    <figure
      aria-label="Recorded pipeline runs"
      className="overflow-hidden rounded-xl bg-scope font-mono shadow-[0_1.5rem_3rem_-1rem_oklch(0.24_0.03_172_/_0.45)] ring-1 ring-scope-line/70"
    >
      <figcaption className="flex items-center gap-2 border-b border-scope-line px-4 py-2.5 sm:px-5">
        <span className="size-1.5 shrink-0 animate-dot rounded-full bg-signal" />
        <span className="text-[10px] uppercase tracking-[0.16em] text-scope-dim">
          recorded run
        </span>
        <span className="ml-auto truncate text-[10px] text-scope-ink">{run.cost}</span>
      </figcaption>

      {/* Held open to the tallest run so advancing never reflows the page. */}
      <div className="min-h-[15.5rem] space-y-2 px-4 py-4 sm:min-h-[21.5rem] sm:px-5">
        {shown(0) && (
          <p className="monitor-line mb-3.5 flex gap-3 text-sm leading-snug text-scope-ink">
            <span aria-hidden className="select-none text-signal">
              &gt;
            </span>
            {run.query}
          </p>
        )}

        {run.lines.map((line, index) =>
          shown(index + 1) ? <Row key={line.label} {...line} /> : null,
        )}

        {run.reasoning && shown(reasoningAt) && (
          <div className="monitor-line grid grid-cols-[4.75rem_1fr] gap-3 pt-1">
            <span className="text-[10px] uppercase tracking-[0.14em] text-scope-dim">
              reasoning
            </span>
            <div className="text-xs text-scope-ink">
              <p>{run.reasoning.steps} steps</p>
              {/* Names are supporting detail. Dropping them on a phone keeps the
                  runs close enough in height that advancing barely reflows. */}
              <ol className="mt-1.5 hidden space-y-1 border-l border-scope-line pl-2.5 text-[11px] leading-relaxed text-scope-dim sm:block">
                {run.reasoning.shown.map((step) => (
                  <li key={step}>{step}</li>
                ))}
              </ol>
            </div>
          </div>
        )}

        {shown(answerAt) && (
          <div className="monitor-line grid grid-cols-[4.75rem_1fr] gap-3 pt-2">
            <span className="text-[10px] uppercase tracking-[0.14em] text-scope-dim">
              answer
            </span>
            <p className="text-[11px] leading-relaxed text-scope-ink/85">{run.answer}</p>
          </div>
        )}
      </div>

      <div className="flex items-center gap-3 border-t border-scope-line px-4 py-2.5 sm:px-5">
        <span className="truncate text-[10px] text-scope-dim">
          {seconds(run.latencyMs)} · {run.mode} · free tier
        </span>

        <div className="ml-auto flex shrink-0 items-center gap-1">
          {RECORDED_RUNS.map((option, index) => (
            <button
              key={option.id}
              type="button"
              onClick={() => {
                setReplaying(false)
                setActive(index)
              }}
              aria-label={`Show the run for: ${option.query}`}
              aria-current={index === active}
              className={`h-1 rounded-full transition-all ${
                index === active ? 'w-6 bg-signal' : 'w-3 bg-scope-line hover:bg-scope-dim'
              }`}
            />
          ))}
        </div>
      </div>
    </figure>
  )
}
