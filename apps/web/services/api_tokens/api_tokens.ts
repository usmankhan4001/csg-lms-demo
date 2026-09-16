import { getAPIUrl } from '@services/config/config'
import {
  RequestBodyWithAuthHeader,
  getResponseMetadata,
  apiFetch,
} from '@services/utils/ts/requests'

export interface StandardCRUDPermissions {
  action_create: boolean
  action_read: boolean
  action_update: boolean
  action_delete: boolean
}

// Types - API Token access covers both native LMS resources and SMS/EMS modules
export interface APITokenRights {
  // LMS Native Resources
  courses: {
    action_create: boolean
    action_read: boolean
    action_read_own: boolean
    action_update: boolean
    action_update_own: boolean
    action_delete: boolean
    action_delete_own: boolean
  }
  activities: StandardCRUDPermissions
  assignments: StandardCRUDPermissions
  coursechapters: StandardCRUDPermissions
  folders: StandardCRUDPermissions
  media: StandardCRUDPermissions
  certifications: StandardCRUDPermissions
  usergroups: StandardCRUDPermissions
  payments: StandardCRUDPermissions
  search: {
    action_read: boolean
  }

  // SMS Academic & Curriculum
  sms_academic?: StandardCRUDPermissions
  sms_admissions?: StandardCRUDPermissions
  sms_attendance?: StandardCRUDPermissions
  sms_gradebook?: StandardCRUDPermissions
  sms_exams?: StandardCRUDPermissions

  // SMS Financials & HR
  sms_fees?: StandardCRUDPermissions
  sms_financials?: StandardCRUDPermissions
  sms_payroll?: StandardCRUDPermissions
  sms_hr?: StandardCRUDPermissions

  // Pastoral, Safety & Compliance
  sms_pastoral?: StandardCRUDPermissions
  sms_counseling?: StandardCRUDPermissions
  sms_cognia?: StandardCRUDPermissions
  sms_library?: StandardCRUDPermissions
  sms_transport?: StandardCRUDPermissions

  // Governance & AI
  ai_tutor?: StandardCRUDPermissions
  ems_roles?: StandardCRUDPermissions
  webhooks?: StandardCRUDPermissions
}

export interface APIToken {
  id: number
  token_uuid: string
  name: string
  description: string | null
  token_prefix: string
  org_id: number
  rights: APITokenRights | null
  scopes?: string[] | null
  created_by_user_id: number
  creation_date: string
  update_date: string
  last_used_at: string | null
  expires_at: string | null
  is_active: boolean
}

export interface APITokenCreateRequest {
  name: string
  description?: string | null
  rights?: APITokenRights | null
  scopes?: string[] | null
  expires_at?: string | null
}

export interface APITokenUpdateRequest {
  name?: string
  description?: string | null
  rights?: APITokenRights | null
  scopes?: string[] | null
  expires_at?: string | null
}

export interface APITokenCreatedResponse extends APIToken {
  token: string // The full token (only shown once!)
}

const emptyCrud = (): StandardCRUDPermissions => ({
  action_create: false,
  action_read: false,
  action_update: false,
  action_delete: false,
})

const fullCrud = (): StandardCRUDPermissions => ({
  action_create: true,
  action_read: true,
  action_update: true,
  action_delete: true,
})

const readOnlyCrud = (): StandardCRUDPermissions => ({
  action_create: false,
  action_read: true,
  action_update: false,
  action_delete: false,
})

// Default rights template with all permissions disabled
export const getDefaultRights = (): APITokenRights => ({
  courses: {
    action_create: false,
    action_read: false,
    action_read_own: false,
    action_update: false,
    action_update_own: false,
    action_delete: false,
    action_delete_own: false,
  },
  activities: emptyCrud(),
  assignments: emptyCrud(),
  coursechapters: emptyCrud(),
  folders: emptyCrud(),
  media: emptyCrud(),
  certifications: emptyCrud(),
  usergroups: emptyCrud(),
  payments: emptyCrud(),
  search: {
    action_read: false,
  },
  sms_academic: emptyCrud(),
  sms_admissions: emptyCrud(),
  sms_attendance: emptyCrud(),
  sms_gradebook: emptyCrud(),
  sms_exams: emptyCrud(),
  sms_fees: emptyCrud(),
  sms_financials: emptyCrud(),
  sms_payroll: emptyCrud(),
  sms_hr: emptyCrud(),
  sms_pastoral: emptyCrud(),
  sms_counseling: emptyCrud(),
  sms_cognia: emptyCrud(),
  sms_library: emptyCrud(),
  sms_transport: emptyCrud(),
  ai_tutor: emptyCrud(),
  ems_roles: emptyCrud(),
  webhooks: emptyCrud(),
})

// Full permissions template
export const getFullRights = (): APITokenRights => ({
  courses: {
    action_create: true,
    action_read: true,
    action_read_own: true,
    action_update: true,
    action_update_own: true,
    action_delete: true,
    action_delete_own: true,
  },
  activities: fullCrud(),
  assignments: fullCrud(),
  coursechapters: fullCrud(),
  folders: fullCrud(),
  media: fullCrud(),
  certifications: fullCrud(),
  usergroups: fullCrud(),
  payments: fullCrud(),
  search: {
    action_read: true,
  },
  sms_academic: fullCrud(),
  sms_admissions: fullCrud(),
  sms_attendance: fullCrud(),
  sms_gradebook: fullCrud(),
  sms_exams: fullCrud(),
  sms_fees: fullCrud(),
  sms_financials: fullCrud(),
  sms_payroll: fullCrud(),
  sms_hr: fullCrud(),
  sms_pastoral: fullCrud(),
  sms_counseling: fullCrud(),
  sms_cognia: fullCrud(),
  sms_library: fullCrud(),
  sms_transport: fullCrud(),
  ai_tutor: fullCrud(),
  ems_roles: fullCrud(),
  webhooks: fullCrud(),
})

// Read-only permissions template
export const getReadOnlyRights = (): APITokenRights => ({
  courses: {
    action_create: false,
    action_read: true,
    action_read_own: true,
    action_update: false,
    action_update_own: false,
    action_delete: false,
    action_delete_own: false,
  },
  activities: readOnlyCrud(),
  assignments: readOnlyCrud(),
  coursechapters: readOnlyCrud(),
  folders: readOnlyCrud(),
  media: readOnlyCrud(),
  certifications: readOnlyCrud(),
  usergroups: readOnlyCrud(),
  payments: readOnlyCrud(),
  search: {
    action_read: true,
  },
  sms_academic: readOnlyCrud(),
  sms_admissions: readOnlyCrud(),
  sms_attendance: readOnlyCrud(),
  sms_gradebook: readOnlyCrud(),
  sms_exams: readOnlyCrud(),
  sms_fees: readOnlyCrud(),
  sms_financials: readOnlyCrud(),
  sms_payroll: readOnlyCrud(),
  sms_hr: readOnlyCrud(),
  sms_pastoral: readOnlyCrud(),
  sms_counseling: readOnlyCrud(),
  sms_cognia: readOnlyCrud(),
  sms_library: readOnlyCrud(),
  sms_transport: readOnlyCrud(),
  ai_tutor: readOnlyCrud(),
  ems_roles: readOnlyCrud(),
  webhooks: readOnlyCrud(),
})

/**
 * Derives comprehensive OAuth2/URN scopes from the rights configuration
 */
export function deriveScopesFromRights(rights: APITokenRights): string[] {
  const scopes: string[] = []

  // Check if everything is enabled -> "*"
  const isFull = (r?: StandardCRUDPermissions) =>
    r?.action_create && r?.action_read && r?.action_update && r?.action_delete

  if (
    rights.courses.action_create &&
    rights.courses.action_read &&
    isFull(rights.sms_academic) &&
    isFull(rights.sms_fees) &&
    isFull(rights.sms_admissions) &&
    isFull(rights.sms_gradebook)
  ) {
    return ['*']
  }

  // Academic
  if (rights.courses.action_read || rights.sms_academic?.action_read) scopes.push('academic:read', 'courses:read')
  if (rights.courses.action_create || rights.sms_academic?.action_create) scopes.push('academic:write', 'courses:write')
  if (rights.sms_attendance?.action_read) scopes.push('attendance:read')
  if (rights.sms_attendance?.action_create || rights.sms_attendance?.action_update) scopes.push('attendance:write', 'attendance:bulk')
  if (rights.sms_gradebook?.action_read) scopes.push('gradebook:read')
  if (rights.sms_gradebook?.action_create || rights.sms_gradebook?.action_update) scopes.push('gradebook:write')
  if (rights.sms_exams?.action_read) scopes.push('exams:read')
  if (rights.sms_exams?.action_create || rights.sms_exams?.action_update) scopes.push('exams:write', 'exams:psychometrics')

  // RevOps
  if (rights.sms_admissions?.action_read) scopes.push('admissions:read')
  if (rights.sms_admissions?.action_create || rights.sms_admissions?.action_update) scopes.push('admissions:write', 'admissions:matriculate')

  // Financials & HR
  if (rights.sms_fees?.action_read) scopes.push('fees:read')
  if (rights.sms_fees?.action_create || rights.sms_fees?.action_update) scopes.push('fees:write', 'fees:collect')
  if (rights.sms_financials?.action_read) scopes.push('financials:read')
  if (rights.sms_financials?.action_create || rights.sms_financials?.action_update) scopes.push('financials:write')
  if (rights.sms_payroll?.action_read) scopes.push('payroll:read')
  if (rights.sms_payroll?.action_create || rights.sms_payroll?.action_update) scopes.push('payroll:write', 'payroll:approve')

  // Pastoral & Compliance
  if (rights.sms_pastoral?.action_read) scopes.push('pastoral:read')
  if (rights.sms_pastoral?.action_create || rights.sms_pastoral?.action_update) scopes.push('pastoral:write', 'crisis:alert')
  if (rights.sms_cognia?.action_read) scopes.push('cognia:read')
  if (rights.sms_cognia?.action_create || rights.sms_cognia?.action_update) scopes.push('cognia:write', 'cognia:verify')

  // Identity & Clinical
  if (rights.usergroups?.action_read) scopes.push('users:read')
  if (rights.usergroups?.action_create) scopes.push('users:write', 'guardians:manage')
  if (rights.sms_counseling?.action_read || rights.sms_counseling?.action_create) scopes.push('clinical:restricted')

  return Array.from(new Set(scopes))
}

/**
 * List all API tokens for an organization
 */
export async function listAPITokens(
  orgId: number,
  accessToken: string
): Promise<APIToken[]> {
  const url = `${getAPIUrl()}orgs/${orgId}/api-tokens`
  return apiFetch(url, accessToken)
}

/**
 * Get a specific API token by UUID
 */
export async function getAPIToken(
  orgId: number,
  tokenUuid: string,
  accessToken: string
): Promise<APIToken> {
  const url = `${getAPIUrl()}orgs/${orgId}/api-tokens/${tokenUuid}`
  return apiFetch(url, accessToken)
}

/**
 * Create a new API token
 * Returns the full token value - this is the ONLY time it will be shown!
 */
export async function createAPIToken(
  orgId: number,
  data: APITokenCreateRequest,
  accessToken: string
) {
  // Automatically derive scopes if not explicitly provided
  const payload = {
    ...data,
    scopes: data.scopes || (data.rights ? deriveScopesFromRights(data.rights) : ['*']),
  }

  const result = await fetch(
    `${getAPIUrl()}orgs/${orgId}/api-tokens`,
    RequestBodyWithAuthHeader('POST', payload, null, accessToken)
  )
  const res = await getResponseMetadata(result)
  return res
}

/**
 * Update an API token
 */
export async function updateAPIToken(
  orgId: number,
  tokenUuid: string,
  data: APITokenUpdateRequest,
  accessToken: string
) {
  const payload = {
    ...data,
    scopes: data.scopes || (data.rights ? deriveScopesFromRights(data.rights) : undefined),
  }

  const result = await fetch(
    `${getAPIUrl()}orgs/${orgId}/api-tokens/${tokenUuid}`,
    RequestBodyWithAuthHeader('PUT', payload, null, accessToken)
  )
  const res = await getResponseMetadata(result)
  return res
}

/**
 * Revoke an API token
 */
export async function revokeAPIToken(
  orgId: number,
  tokenUuid: string,
  accessToken: string
) {
  const result = await fetch(
    `${getAPIUrl()}orgs/${orgId}/api-tokens/${tokenUuid}`,
    RequestBodyWithAuthHeader('DELETE', null, null, accessToken)
  )
  const res = await getResponseMetadata(result)
  return res
}

/**
 * Regenerate an API token secret
 * Returns the new full token value - this is the ONLY time it will be shown!
 */
export async function regenerateAPIToken(
  orgId: number,
  tokenUuid: string,
  accessToken: string
) {
  const result = await fetch(
    `${getAPIUrl()}orgs/${orgId}/api-tokens/${tokenUuid}/regenerate`,
    RequestBodyWithAuthHeader('POST', null, null, accessToken)
  )
  const res = await getResponseMetadata(result)
  return res
}

/**
 * Fetch OpenAPI specification from the backend
 */
export async function fetchOpenAPISpec(accessToken?: string) {
  const urls = [
    `${getAPIUrl()}openapi.json`,
    '/api/v1/openapi.json',
    '/openapi.json',
  ]

  const headers: Record<string, string> = {
    'Accept': 'application/json',
  }
  if (accessToken) {
    headers['Authorization'] = `Bearer ${accessToken}`
  }

  let lastError: Error | null = null

  for (const url of urls) {
    try {
      const response = await fetch(url, {
        method: 'GET',
        headers,
        credentials: 'include',
      })

      if (response.ok) {
        const data = await response.json()
        if (data && (data.openapi || data.swagger || data.paths)) {
          return data
        }
      }
    } catch (err: any) {
      lastError = err
    }
  }

  throw lastError || new Error('Failed to fetch OpenAPI spec')
}
