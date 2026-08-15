/**
 * API client.
 *
 * The streaming endpoint is POST, so EventSource (which is GET-only) cannot be
 * used. Instead the response body is read as a stream and the SSE frames are
 * parsed by hand, which also keeps the request body JSON rather than smuggling a
 * question through the query string.
 */

import type { Quota, TraceEvent } from '../types/events'

export const API_BASE = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000').replace(
  /\/$/,
  '',
)

const BASE = API_BASE

export interface HealthResponse {
  status: string
  graph: { status: string; detail?: string }
  llm_configured: boolean
  embeddings_configured: boolean
  daily_query_limit: number
}

export interface ShowcaseExample {
  id: string
  query: string
  demonstrates: string
  precomputed: boolean
}

export class QuotaExceededError extends Error {
  constructor(readonly quota: Quota | null, message: string) {
    super(message)
    this.name = 'QuotaExceededError'
  }
}

async function getJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, init)
  if (!response.ok) {
    throw new Error(`${path} responded ${response.status}`)
  }
  return (await response.json()) as T
}

export const getHealth = () => getJson<HealthResponse>('/health')

export const getShowcase = () =>
  getJson<{ examples: ShowcaseExample[] }>('/showcase').then((body) => body.examples)

export const getQuota = () => getJson<Quota>('/quota')

/**
 * Wake a cold instance.
 *
 * Render's free tier spins the service down after fifteen minutes idle, so the
 * first request of a visit can take up to a minute. The static site is served
 * from a CDN and loads instantly, which lets the UI show real progress while the
 * backend boots rather than appearing broken.
 */
export async function waitForBackend(
  onAttempt?: (attempt: number) => void,
  maxAttempts = 40,
): Promise<HealthResponse> {
  let lastError: unknown
  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    onAttempt?.(attempt)
    try {
      return await getHealth()
    } catch (error) {
      lastError = error
      await new Promise((resolve) => setTimeout(resolve, 3000))
    }
  }
  throw lastError instanceof Error ? lastError : new Error('Backend did not respond')
}

interface StreamOptions {
  query: string
  sessionId: string | null
  signal?: AbortSignal
  onEvent: (event: TraceEvent) => void
}

/**
 * Run a query, invoking `onEvent` for each trace event as it arrives.
 */
export async function streamQuery({
  query,
  sessionId,
  signal,
  onEvent,
}: StreamOptions): Promise<void> {
  const response = await fetch(`${BASE}/ask/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, session_id: sessionId }),
    signal,
  })

  if (response.status === 429) {
    const body = await response.json().catch(() => null)
    const detail = body?.detail ?? {}
    throw new QuotaExceededError(
      detail.quota ?? null,
      detail.message ?? 'Daily demo limit reached.',
    )
  }
  if (!response.ok || !response.body) {
    throw new Error(`Request failed with status ${response.status}`)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })

    // Frames are separated by a blank line. Anything after the last separator is
    // an incomplete frame and stays buffered until the next chunk arrives.
    const frames = buffer.split('\n\n')
    buffer = frames.pop() ?? ''

    for (const frame of frames) {
      const parsed = parseFrame(frame)
      if (parsed) onEvent(parsed)
    }
  }
}

function parseFrame(frame: string): TraceEvent | null {
  const dataLine = frame
    .split('\n')
    .find((line) => line.startsWith('data: '))
  if (!dataLine) return null

  try {
    return JSON.parse(dataLine.slice(6)) as TraceEvent
  } catch {
    // A malformed frame should skip, not tear down the stream.
    return null
  }
}
