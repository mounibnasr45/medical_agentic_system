/**
 * Folds the event stream into the state the trace panel renders.
 *
 * Kept as a pure function so the reduction is independent of React and of the
 * transport: given the same events it always produces the same trace.
 */

import type { CotStep, Trace, TraceEvent } from '../types/events'

const str = (value: unknown, fallback = ''): string =>
  typeof value === 'string' ? value : fallback

const num = (value: unknown): number | undefined =>
  typeof value === 'number' ? value : undefined

const strArray = (value: unknown): string[] =>
  Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : []

export function applyEvent(trace: Trace, event: TraceEvent): Trace {
  const p = event.payload

  switch (event.type) {
    case 'router_completed':
      return {
        ...trace,
        router: {
          isMedical: p.is_medical === true,
          intent: str(p.intent, 'unknown'),
          complexity: num(p.complexity) ?? 0,
          confidence: num(p.confidence) ?? 0,
          agents: strArray(p.required_agents),
          tools: strArray(p.suggested_tools),
          useChainOfThought: p.use_chain_of_thought === true,
          reasoning: str(p.reasoning),
        },
      }

    case 'stage_started': {
      const name = str(p.stage, 'stage')
      if (trace.stages.some((s) => s.name === name && s.status === 'running')) return trace
      return { ...trace, stages: [...trace.stages, { name, status: 'running' }] }
    }

    case 'stage_completed': {
      const name = str(p.stage, 'stage')
      const status = p.ok === false ? 'failed' : 'done'
      const elapsedMs = num(p.elapsed_ms)
      const existing = trace.stages.findIndex((s) => s.name === name && s.status === 'running')

      if (existing === -1) {
        return { ...trace, stages: [...trace.stages, { name, status, elapsedMs }] }
      }
      const stages = [...trace.stages]
      stages[existing] = { ...stages[existing]!, status, elapsedMs }
      return { ...trace, stages }
    }

    case 'tool_started': {
      const tool = str(p.tool, 'tool')
      return {
        ...trace,
        tools: [...trace.tools, { id: event.id, tool, status: 'running' }],
      }
    }

    case 'tool_completed': {
      const tool = str(p.tool, 'tool')
      // Match the most recent running call for this tool; a query can call the
      // same tool more than once.
      const index = [...trace.tools]
        .reverse()
        .findIndex((t) => t.tool === tool && t.status === 'running')

      const resolved = {
        status: (p.ok === false ? 'failed' : 'ok') as 'ok' | 'failed',
        elapsedMs: num(p.elapsed_ms),
        cached: p.cached === true,
        confidence: num(p.confidence),
      }

      if (index === -1) {
        return { ...trace, tools: [...trace.tools, { id: event.id, tool, ...resolved }] }
      }
      const forward = trace.tools.length - 1 - index
      const tools = [...trace.tools]
      tools[forward] = { ...tools[forward]!, ...resolved }
      return { ...trace, tools }
    }

    case 'cot_step': {
      const step: CotStep = {
        index: num(p.index) ?? trace.cotSteps.length + 1,
        name: str(p.name),
        reasoning: str(p.reasoning),
        conclusion: str(p.conclusion),
      }
      if (trace.cotSteps.some((s) => s.index === step.index)) return trace
      return { ...trace, cotSteps: [...trace.cotSteps, step] }
    }

    case 'run_completed':
      return {
        ...trace,
        processingMode: str(p.processing_mode, trace.processingMode ?? ''),
        latencyMs: num(p.latency_ms),
        sourcesUsed: strArray(p.sources_used),
        confidence: num(p.confidence) ?? null,
        graphAvailable: p.graph_available === true,
        fromCache: p.from_cache === true,
        fromShowcase: p.from_showcase === true,
        // Anything still marked running at completion never reported back.
        stages: trace.stages.map((s) =>
          s.status === 'running' ? { ...s, status: 'done' as const } : s,
        ),
      }

    case 'error':
      return { ...trace, error: str(p.message, 'Unknown error') }

    default:
      return trace
  }
}

/** Extract the answer text from an event, if it carries one. */
export const answerFrom = (event: TraceEvent): string | null =>
  event.type === 'answer' || event.type === 'rejected'
    ? str(event.payload.text) || str(event.payload.message) || null
    : null
