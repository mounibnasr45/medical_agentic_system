/**
 * Mirrors medical_agent/utils/events.py.
 *
 * The backend emits these as Server-Sent Events while a query runs. Changing the
 * Python EventType enum means changing this union, and the compiler will point at
 * every render path that needs updating.
 */

export type EventType =
  | 'run_started'
  | 'router_completed'
  | 'rejected'
  | 'stage_started'
  | 'stage_completed'
  | 'tool_started'
  | 'tool_completed'
  | 'cot_step'
  | 'answer'
  | 'run_completed'
  | 'error'

export interface TraceEvent {
  id: string
  ts: number
  type: EventType
  payload: Record<string, unknown>
}

export interface RouterDecision {
  isMedical: boolean
  intent: string
  complexity: number
  confidence: number
  agents: string[]
  tools: string[]
  useChainOfThought: boolean
  reasoning: string
}

export type ToolStatus = 'running' | 'ok' | 'failed'

export interface ToolCall {
  id: string
  tool: string
  status: ToolStatus
  elapsedMs?: number
  cached?: boolean
  confidence?: number
}

export interface StageRecord {
  name: string
  status: 'running' | 'done' | 'failed'
  elapsedMs?: number
  detail?: string
}

export interface CotStep {
  index: number
  name: string
  reasoning: string
  conclusion: string
}

export interface Quota {
  limit: number
  used: number
  remaining: number
  resets_at: string
}

/** Everything the trace panel renders for one query. */
export interface Trace {
  router?: RouterDecision
  stages: StageRecord[]
  tools: ToolCall[]
  cotSteps: CotStep[]
  processingMode?: string
  latencyMs?: number
  sourcesUsed?: string[]
  confidence?: number | null
  graphAvailable?: boolean
  fromCache?: boolean
  fromShowcase?: boolean
  error?: string
}

export const emptyTrace = (): Trace => ({
  stages: [],
  tools: [],
  cotSteps: [],
})

/** Human-readable labels for the identifiers the backend emits. */
export const TOOL_LABELS: Record<string, string> = {
  graph_db: 'Knowledge graph',
  cypher: 'Generated Cypher',
  cypher_exec: 'Cypher execution',
  cypher_guard: 'Read-only guard',
  web: 'Web search',
  web_search: 'Web search',
}

export const STAGE_LABELS: Record<string, string> = {
  quota: 'Quota',
  crew: 'Agent crew',
  parallel_retrieval: 'Parallel retrieval',
  router: 'Router',
}

export const labelFor = (labels: Record<string, string>, key: string): string =>
  labels[key] ?? key.replace(/_/g, ' ')
