/**
 * Reads the org's resolved SMS module feature flags so `RoleSidebar` can hide
 * a disabled module's nav entry (DESIGN-SYSTEM.md §2.3: "Modules hidden by
 * feature flag or RBAC are removed from navigation, not disabled").
 *
 * Backed by the same endpoint the rest of the app already uses for this
 * (`services/organizations/orgs.ts` -> `GET /api/v1/orgs/slug/{slug}`, whose
 * handler attaches `config.resolved_features` via
 * `resolve_all_features()` -- see `src/services/orgs/orgs.py`
 * `_build_org_read_with_resolved`). That response shape is
 * `{ enabled, available, limit, required_plan }` per feature
 * (`src/security/features_utils/resolve.py::resolve_feature`).
 *
 * LIMITATION (documented, not papered over): that endpoint is looked up by
 * org **slug**, but the Keycloak dev token (see `./dev-token.ts`) only
 * carries a numeric `org_id` claim -- there is no endpoint in this codebase
 * that resolves an org by bare numeric id without already having a session
 * tied to it. So this reads the slug from `NEXT_PUBLIC_ORG_SLUG` (falling
 * back to `"demo"`, LearnHouse's seeded demo org) rather than deriving it
 * from the token. A real integration would either embed the slug as a
 * token claim or add a small `/orgs/by-id/{id}` lookup -- both are outside
 * this task's scope (no `sms_*` router or org-service changes).
 *
 * Fails open: if the org can't be resolved (wrong slug, offline, org has no
 * config yet), callers get `null` and should render every nav item rather
 * than hide the whole sidebar over a features fetch that didn't load.
 */

const BACKEND_URL = (process.env.NEXT_PUBLIC_LEARNHOUSE_BACKEND_URL || 'http://localhost:1338').replace(/\/+$/, '')
const ORG_SLUG = process.env.NEXT_PUBLIC_ORG_SLUG || 'demo'

export interface ResolvedFeature {
  enabled: boolean
  available: boolean
  limit: number
  required_plan: string | null
}

export type ResolvedFeatureMap = Record<string, ResolvedFeature>

export async function fetchOrgResolvedFeatures(orgSlug: string = ORG_SLUG): Promise<ResolvedFeatureMap | null> {
  try {
    const res = await fetch(`${BACKEND_URL}/api/v1/orgs/slug/${encodeURIComponent(orgSlug)}`, {
      headers: { Accept: 'application/json' },
      cache: 'no-store',
    })
    if (!res.ok) return null
    const org = await res.json()
    const resolved = org?.config?.config?.resolved_features ?? org?.config?.resolved_features
    if (!resolved || typeof resolved !== 'object') return null
    return resolved as ResolvedFeatureMap
  } catch {
    return null
  }
}

/** True unless the flag map is loaded AND explicitly marks the feature disabled. */
export function isFeatureEnabled(flags: ResolvedFeatureMap | null, featureKey: string | undefined): boolean {
  if (!featureKey) return true
  if (!flags) return true // fail open while unknown/loading -- see module doc
  const entry = flags[featureKey]
  if (!entry) return true // unknown feature key -- don't hide over a mapping gap
  return entry.enabled !== false
}
