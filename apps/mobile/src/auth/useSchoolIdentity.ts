/**
 * The caller's school identity, resolved SERVER-SIDE via `GET /sms/me`.
 *
 * Why this exists alongside `useSessionSubject`: that hook reads convenience
 * claims out of the JWT, including `children_ids`. For a PARENT those claims
 * are client-supplied, and "which children am I allowed to see" is exactly
 * the question a client must never answer for itself. `GET /sms/me` resolves
 * the guardian->child link from the `StudentGuardian` table instead
 * (sms_identity.py, the PARENT branch of get_my_identity).
 *
 * The per-child endpoints are independently gated by
 * `require_own_student_or_privileged`, so this hook is about showing the
 * right thing, not about enforcement -- the server still refuses a child
 * that is not yours even if this list were wrong.
 */

import { useApiResource } from '@/api/useApiResource'
import { getMyIdentity } from '@/modules/sms/identity/api'
import type { MyIdentity } from '@/modules/sms/identity/types'

export function useSchoolIdentity() {
  const identity = useApiResource<MyIdentity>(() => getMyIdentity(), [], {
    cacheKey: 'school-identity-me',
    // A resolved identity is never "empty" in the zero-rows sense -- a parent
    // with no linked children still has roles, an org and a name -- so the
    // default array/object emptiness check would mislabel a valid response.
    isEmpty: () => false,
  })

  return {
    identity: identity.data,
    childrenIds: identity.data?.children_ids ?? [],
    status: identity.status,
    error: identity.error,
    sync: identity.sync,
    refetch: identity.refetch,
  }
}
