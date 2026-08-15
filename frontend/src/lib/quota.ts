/** Wording for the daily allowance, shared by the landing page and the console. */

import type { Quota } from '../types/events'

export const remainingLabel = (quota: Quota): string =>
  `${quota.remaining} of ${quota.limit} left today`

/**
 * When the allowance comes back.
 *
 * The server resets on UTC midnight, which is the honest answer, but a visitor
 * wants to know what that means where they are - so give both.
 */
export function resetLabel(iso: string): string {
  const at = new Date(iso)
  if (Number.isNaN(at.getTime())) return 'midnight UTC'

  const local = at.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  return `midnight UTC, which is ${local} where you are`
}
