import { useEffect, useState } from 'react'

import { TraceMonitor } from '../components/TraceMonitor'
import { API_BASE, getQuota } from '../lib/api'
import { remainingLabel, resetLabel } from '../lib/quota'
import type { Quota } from '../types/events'

const DOCS_URL = `${API_BASE}/docs`
const REPO_URL = 'https://github.com/mounibnasr45/medical_agentic_system'

const STAGES = [
  {
    name: 'route',
    detail:
      'One deterministic call returns a plan: intent, complexity, which agents to run, and how many tool iterations each gets. Non-medical questions stop here.',
  },
  {
    name: 'select a mode',
    detail:
      'Interaction questions fan out to every source at once and merge the results with per-source confidence. Everything else runs the crew in sequence.',
  },
  {
    name: 'retrieve',
    detail:
      'Hybrid graph search, model-written Cypher for multi-hop traversals, and web search. Results are cached per tool for an hour.',
  },
  {
    name: 'reason',
    detail:
      'When the router asked for it, the findings are worked through explicit steps, and each step is published as it is reached.',
  },
  {
    name: 'respond',
    detail:
      'The answer streams back next to the trace that produced it, including which sources were used and whether the graph was reachable.',
  },
]

const DECISIONS = [
  {
    forcedBy: 'a 512 MB tier',
    title: 'Embeddings became an API call.',
    detail:
      'The original sentence-transformers embedder pulled in torch: roughly 2.5 GB of image and over 500 MB resident, on an instance with 512 MB. Moving embeddings to Gemini was the difference between deployable and not.',
  },
  {
    forcedBy: 'a database that sleeps',
    title: 'The graph degrades instead of failing.',
    detail:
      'AuraDB Free pauses after three days idle. Graph access goes through a gateway that tracks availability and refuses to retry inside a cooldown, so one paused database cannot add a connection timeout to every request. Agents answer from web search and say that graph verification was unavailable.',
  },
  {
    forcedBy: 'model-written queries',
    title: 'Generated Cypher is treated as hostile.',
    detail:
      'It is written by a model from a stranger’s text and then run against the database, so a prompt-injected DETACH DELETE is a real risk. Every generated query passes a write-clause denylist and executes with read routing. Both, because either alone is one bug away from a wiped graph.',
  },
  {
    forcedBy: 'a silent failure',
    title: 'All graph work runs on one event loop.',
    detail:
      'Neo4j’s async driver binds its locks to the loop that opened the connection pool, and this process has several. Because graph tools degrade rather than raise, a cross-loop call failed silently: the agent simply answered from web search instead. A single long-lived loop owns every graph coroutine.',
  },
  {
    forcedBy: 'an unstable API',
    title: 'The trace comes from the tools, not the framework.',
    detail:
      'Each tool publishes to a request-scoped event bus rather than a CrewAI callback. CrewAI runs synchronously in a worker thread and context variables do not cross that boundary on their own, so the pipeline copies the context explicitly.',
  },
]

/**
 * The visitor's live allowance.
 *
 * Fetched in the background and never blocking: the page is served from a CDN
 * and paints at once, while the API sleeps after fifteen minutes idle and can
 * take a cold minute to answer. Until it does, the page states the standing
 * limit instead of a live count.
 */
function useAllowance(): Quota | null {
  const [quota, setQuota] = useState<Quota | null>(null)

  useEffect(() => {
    let cancelled = false
    let timer: number | undefined
    let attempt = 0

    const poll = () => {
      getQuota()
        .then((next) => {
          if (!cancelled) setQuota(next)
        })
        .catch(() => {
          attempt += 1
          if (!cancelled && attempt < 10) timer = window.setTimeout(poll, 4000)
        })
    }

    poll()
    return () => {
      cancelled = true
      if (timer !== undefined) window.clearTimeout(timer)
    }
  }, [])

  return quota
}

function EnterButton({
  onEnter,
  className = '',
}: {
  onEnter: () => void
  className?: string
}) {
  return (
    <button
      type="button"
      onClick={onEnter}
      className={`rounded-md bg-methylene px-4 py-2 text-sm font-medium text-drape transition hover:brightness-115 ${className}`}
    >
      Continue as guest
    </button>
  )
}

function Allowance({ quota }: { quota: Quota | null }) {
  const spent = quota?.remaining === 0

  return (
    <aside className="self-start rounded-xl border border-drape-edge bg-drape p-5 sm:p-6">
      <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-graphite-faint">
        Your allowance
      </p>

      {quota ? (
        <>
          <p
            className={`display mt-3 text-5xl leading-none ${spent ? 'text-flag' : 'text-graphite'}`}
          >
            {quota.remaining}
            <span className="text-2xl text-graphite-faint">&thinsp;/&thinsp;{quota.limit}</span>
          </p>
          <p className="mt-3 text-[13px] leading-relaxed text-graphite-soft">
            {spent
              ? 'questions left today. The example questions still work and cost nothing.'
              : 'questions left today.'}{' '}
            Resets at {resetLabel(quota.resets_at)}.
          </p>
        </>
      ) : (
        <>
          <p className="display mt-3 text-5xl leading-none text-graphite-faint">5</p>
          <p className="mt-3 text-[13px] leading-relaxed text-graphite-soft">
            questions a day. Your live count is on its way — the API sleeps after fifteen
            minutes idle, and this page did not wait for it to wake.
          </p>
        </>
      )}
    </aside>
  )
}

export function Landing({ onEnter }: { onEnter: () => void }) {
  const quota = useAllowance()

  return (
    <div className="min-h-full">
      <header className="sticky top-0 z-20 border-b border-drape-edge/70 bg-drape/85 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center gap-4 px-5 py-3 sm:px-8">
          <span className="display text-base text-graphite">Medical Agent</span>
          <span className="hidden font-mono text-[11px] text-graphite-faint sm:inline">
            {quota ? remainingLabel(quota) : 'five questions a day'}
          </span>
          <EnterButton onEnter={onEnter} className="ml-auto" />
        </div>
      </header>

      <main>
        <section className="mx-auto max-w-6xl px-5 pt-14 pb-16 sm:px-8 sm:pt-20 lg:pb-24">
          <div className="grid items-start gap-12 lg:grid-cols-[minmax(0,1fr)_minmax(0,27rem)] lg:gap-14">
            <div>
              <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-methylene">
                Multi-agent clinical retrieval
              </p>

              <h1 className="display mt-5 text-[clamp(2.5rem,6vw,4.35rem)] leading-[0.98] text-graphite">
                Every question is routed before any of it runs.
              </h1>

              <div className="mt-7 max-w-xl space-y-4 text-[15px] leading-relaxed text-graphite-soft">
                <p>
                  A model reads the question first and decides what it deserves: whether it is
                  medical at all, how complex it is, which of three agents to activate, and
                  which sources they may use. A definition lookup gets one agent. A drug
                  interaction gets two, working across a knowledge graph, generated Cypher and
                  web search. Anything out of scope is refused before a single agent starts.
                </p>
                <p>
                  The panel replays four runs the deployed system actually performed. In the
                  console you watch your own question take the same path, decision by
                  decision, while it happens.
                </p>
              </div>

              <div className="mt-9 flex flex-wrap items-center gap-x-6 gap-y-3">
                <EnterButton onEnter={onEnter} />
                <a
                  href={DOCS_URL}
                  target="_blank"
                  rel="noreferrer"
                  className="text-sm text-graphite-soft underline decoration-drape-edge underline-offset-4 transition hover:decoration-methylene hover:text-graphite"
                >
                  Read the API docs
                </a>
              </div>

              <p className="mt-4 font-mono text-[11px] leading-relaxed text-graphite-faint">
                No sign-up · five questions a day · the examples are free
              </p>
            </div>

            <div className="lg:pt-1">
              <TraceMonitor />
            </div>
          </div>
        </section>

        <section className="border-y border-drape-edge/70 bg-drape-deep">
          <div className="mx-auto max-w-6xl px-5 py-14 sm:px-8 sm:py-16">
            <h2 className="display text-2xl text-graphite sm:text-3xl">How a query flows</h2>
            <p className="mt-2.5 max-w-2xl text-sm leading-relaxed text-graphite-soft">
              Each stage publishes its own events, so the console shows this happening rather
              than describing it afterwards.
            </p>

            {/* Ordered because the pipeline is: position carries the sequence,
                which is why there is a rail and no numerals. */}
            <ol className="relative mt-10 grid gap-8 sm:grid-cols-2 lg:grid-cols-5 lg:gap-6">
              <span
                aria-hidden
                className="absolute inset-x-0 top-0 hidden h-px bg-drape-edge lg:block"
              />
              {STAGES.map((stage) => (
                <li key={stage.name} className="relative lg:pt-7">
                  <span
                    aria-hidden
                    className="absolute left-0 top-0 hidden size-[7px] -translate-y-1/2 rounded-full bg-methylene lg:block"
                  />
                  <h3 className="flex items-center gap-2 text-sm font-semibold text-graphite">
                    <span
                      aria-hidden
                      className="size-[6px] shrink-0 rounded-full bg-methylene lg:hidden"
                    />
                    {stage.name}
                  </h3>
                  <p className="mt-2 text-[13px] leading-relaxed text-graphite-soft">
                    {stage.detail}
                  </p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section className="mx-auto max-w-6xl px-5 py-16 sm:px-8 sm:py-20">
          <h2 className="display text-2xl text-graphite sm:text-3xl">What is underneath</h2>
          <p className="mt-2.5 max-w-2xl text-sm leading-relaxed text-graphite-soft">
            Five decisions that shaped the build, each labelled with the constraint that
            forced it.
          </p>

          <div className="mt-10 grid gap-x-10 gap-y-9 md:grid-cols-2 lg:grid-cols-3">
            {DECISIONS.map((decision) => (
              <article key={decision.title}>
                <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-methylene">
                  {decision.forcedBy}
                </p>
                <h3 className="mt-2 text-[15px] font-semibold leading-snug text-graphite">
                  {decision.title}
                </h3>
                <p className="mt-2 text-[13px] leading-relaxed text-graphite-soft">
                  {decision.detail}
                </p>
              </article>
            ))}
          </div>
        </section>

        <section className="border-t border-drape-edge/70 bg-drape-deep">
          <div className="mx-auto max-w-6xl px-5 py-16 sm:px-8 sm:py-20">
            <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,21rem)] lg:gap-16">
              <div>
                <h2 className="display text-2xl text-graphite sm:text-3xl">Guest access</h2>

                <div className="mt-5 max-w-xl space-y-4 text-sm leading-relaxed text-graphite-soft">
                  <p>
                    There is no sign-up and nothing to confirm. Continue as a guest and the
                    console opens on an empty conversation.
                  </p>
                  <p>
                    Each visitor gets five questions a day. Every question spends real model
                    credit on a demo running on a free instance and one personal API key, so
                    the limit is a spending ceiling rather than a plan.
                  </p>
                  <p>
                    The count follows the network address a request arrives from, not the
                    browser, so a private window continues on the same allowance rather than
                    starting a fresh one.
                  </p>
                  <p>
                    The four example questions are answered from a file on disk. They return
                    at once, cost nothing and never touch the allowance — enough to watch the
                    whole pipeline work without spending a question on it.
                  </p>
                </div>

                <EnterButton onEnter={onEnter} className="mt-8" />
              </div>

              <Allowance quota={quota} />
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-drape-edge/70">
        <div className="mx-auto max-w-6xl px-5 py-9 sm:px-8">
          <p className="max-w-2xl text-xs leading-relaxed text-graphite-faint">
            Engineering demonstration, not medical advice. The graph holds a small curated drug
            dataset rather than a clinical knowledge base, and no answer here has been reviewed
            by a clinician.
          </p>
          <div className="mt-5 flex flex-wrap items-center gap-x-6 gap-y-2 font-mono text-[11px] text-graphite-soft">
            <a
              href={DOCS_URL}
              target="_blank"
              rel="noreferrer"
              className="underline decoration-drape-edge underline-offset-4 transition hover:decoration-methylene hover:text-graphite"
            >
              API docs
            </a>
            <a
              href={REPO_URL}
              target="_blank"
              rel="noreferrer"
              className="underline decoration-drape-edge underline-offset-4 transition hover:decoration-methylene hover:text-graphite"
            >
              Source
            </a>
            <span className="text-graphite-faint">Built by Mounib Nasr</span>
          </div>
        </div>
      </footer>
    </div>
  )
}
