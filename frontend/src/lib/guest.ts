/**
 * Guest access.
 *
 * There are no accounts. Signing in as a guest mints a local identifier that
 * labels the visitor's session and survives a reload, nothing more.
 *
 * The daily allowance is deliberately not tied to it. The API counts questions
 * against the caller's address, so clearing this identifier - or opening a
 * private window - starts a new conversation, not a new allowance.
 */

const STORAGE_KEY = 'medical-agent.guest'

export interface GuestSession {
  id: string
  startedAt: string
}

const mintId = (): string =>
  `${Math.random().toString(36).slice(2, 8)}${Date.now().toString(36).slice(-3)}`

const isSession = (value: unknown): value is GuestSession =>
  typeof value === 'object' &&
  value !== null &&
  typeof (value as GuestSession).id === 'string' &&
  typeof (value as GuestSession).startedAt === 'string'

/** The stored guest, or null when there is none this browser will admit to. */
export function currentGuest(): GuestSession | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed: unknown = JSON.parse(raw)
    return isSession(parsed) ? parsed : null
  } catch {
    // Private browsing and storage-blocking extensions both throw here. A guest
    // who cannot be remembered is still a guest, so this is never fatal.
    return null
  }
}

/** Sign in, reusing the existing session when this browser already has one. */
export function signInAsGuest(): GuestSession {
  const existing = currentGuest()
  if (existing) return existing

  const session: GuestSession = { id: mintId(), startedAt: new Date().toISOString() }
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(session))
  } catch {
    // Not fatal: the session simply lasts until the tab closes.
  }
  return session
}
