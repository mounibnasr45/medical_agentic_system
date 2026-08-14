import { useCallback, useEffect, useRef, useState } from 'react'

import {
  getQuota,
  getShowcase,
  QuotaExceededError,
  streamQuery,
  waitForBackend,
  type HealthResponse,
  type ShowcaseExample,
} from '../lib/api'
import { answerFrom, applyEvent } from '../lib/trace'
import { emptyTrace, type Quota, type Trace } from '../types/events'

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  trace?: Trace
}

export type Status = 'waking' | 'ready' | 'running' | 'offline'

const newId = () => Math.random().toString(36).slice(2, 10)

export function useConversation() {
  const [status, setStatus] = useState<Status>('waking')
  const [wakeAttempt, setWakeAttempt] = useState(0)
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [liveTrace, setLiveTrace] = useState<Trace>(emptyTrace())
  const [quota, setQuota] = useState<Quota | null>(null)
  const [examples, setExamples] = useState<ShowcaseExample[]>([])
  const [error, setError] = useState<string | null>(null)

  const sessionId = useRef<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  // The static site is served from a CDN and paints immediately, so the backend
  // may still be starting. Wake it rather than failing the first query.
  useEffect(() => {
    let cancelled = false

    waitForBackend((attempt) => {
      if (!cancelled) setWakeAttempt(attempt)
    })
      .then((response) => {
        if (cancelled) return
        setHealth(response)
        setStatus('ready')
        void getShowcase().then(setExamples).catch(() => undefined)
        void getQuota().then(setQuota).catch(() => undefined)
      })
      .catch(() => {
        if (!cancelled) setStatus('offline')
      })

    return () => {
      cancelled = true
      abortRef.current?.abort()
    }
  }, [])

  const send = useCallback(
    async (query: string) => {
      const trimmed = query.trim()
      if (!trimmed || status === 'running' || status === 'waking') return

      setError(null)
      setStatus('running')
      setLiveTrace(emptyTrace())
      setMessages((current) => [
        ...current,
        { id: newId(), role: 'user', content: trimmed },
      ])

      const controller = new AbortController()
      abortRef.current = controller

      let trace = emptyTrace()
      let answer = ''

      try {
        await streamQuery({
          query: trimmed,
          sessionId: sessionId.current,
          signal: controller.signal,
          onEvent: (event) => {
            if (event.type === 'run_started') {
              const id = event.payload.session_id
              if (typeof id === 'string') sessionId.current = id
            }

            const text = answerFrom(event)
            if (text) answer = text

            trace = applyEvent(trace, event)
            setLiveTrace(trace)
          },
        })

        setMessages((current) => [
          ...current,
          {
            id: newId(),
            role: 'assistant',
            content: answer || 'No answer was produced.',
            trace,
          },
        ])
        void getQuota().then(setQuota).catch(() => undefined)
      } catch (caught) {
        if (controller.signal.aborted) return
        if (caught instanceof QuotaExceededError) {
          setError(caught.message)
          if (caught.quota) setQuota(caught.quota)
        } else {
          setError(caught instanceof Error ? caught.message : 'Request failed')
        }
      } finally {
        if (!controller.signal.aborted) setStatus('ready')
        abortRef.current = null
      }
    },
    [status],
  )

  const reset = useCallback(() => {
    abortRef.current?.abort()
    sessionId.current = null
    setMessages([])
    setLiveTrace(emptyTrace())
    setError(null)
    setStatus('ready')
  }, [])

  return {
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
  }
}
