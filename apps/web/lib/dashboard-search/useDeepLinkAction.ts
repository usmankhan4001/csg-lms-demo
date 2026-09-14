'use client'

/**
 * Reads a deep-linked action off the URL so a page can open the surface the
 * Ctrl+K palette asked for.
 *
 * Why the URL and not a context/event bus: the palette is global, so an
 * action nearly always targets a page the user is not on yet. A callback
 * would have to navigate and then race the destination's mount. A query
 * param is already part of the navigation, so the page reads it on its first
 * render with no coordination, no provider, and no ordering assumption. It
 * also survives a reload and can be pasted to a colleague.
 *
 * The param is stripped immediately after being consumed, so a refresh does
 * not reopen a dialog the user already dismissed, and the "opened from the
 * palette" state never lingers in a shared link.
 */

import { useEffect, useState } from 'react'
import { usePathname, useRouter, useSearchParams } from 'next/navigation'
import { ACTION_QUERY_PARAM } from './types'

/**
 * Returns true once when the current URL requests `actionKey`.
 *
 * Usage: `const openNow = useDeepLinkAction('new-structure')` and seed the
 * dialog's open state from it.
 */
export function useDeepLinkAction(actionKey: string): boolean {
  const searchParams = useSearchParams()
  const router = useRouter()
  const pathname = usePathname()
  const requested = searchParams?.get(ACTION_QUERY_PARAM) === actionKey
  const [consumed, setConsumed] = useState(false)

  useEffect(() => {
    if (!requested || consumed) return
    setConsumed(true)

    // Drop the param without adding a history entry, so Back still goes to
    // wherever the user actually came from rather than re-triggering.
    const next = new URLSearchParams(searchParams?.toString() ?? '')
    next.delete(ACTION_QUERY_PARAM)
    const qs = next.toString()
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false })
  }, [requested, consumed, pathname, router, searchParams])

  return requested
}
