/**
 * Real calls against `apps/api/src/routers/sms_certificates.py`, mounted at
 * `/api/v1/sms/certificates` (prefix on the APIRouter, `sms_certificates.py:25`).
 *
 * WHAT THE API ENFORCES:
 *
 *   create_template POST /templates         [SUPER_ADMIN, SCHOOL_ADMIN]
 *   issue           POST /issue             [SUPER_ADMIN, SCHOOL_ADMIN, TEACHER]
 *   list_templates  GET  /templates         any authenticated principal
 *   list_issued     GET  /issued            any authenticated principal
 *   verify          GET  /verify/{hash}     NO AUTHENTICATION AT ALL
 *
 * Note the split: designing a template is admin-only, but ISSUING one is open
 * to teachers. So the Templates screen shows a 403 honestly to a teacher who
 * tries to create, while the Issue action stays available to them.
 *
 * THERE IS NO REVOKE ENDPOINT. `IssuedCertificate.is_revoked` can be READ and
 * displayed but cannot be set through the API -- there is no route for it and
 * no service method. The Issued screen therefore shows revocation state and
 * offers no control to change it; offering a button that cannot work is worse
 * than offering none.
 */

import { apiGet, apiPost, toQueryString } from '@/lib/api/api-client'
import type {
  CertificateTemplate,
  CertificateTemplateCreate,
  IssueCertificatePayload,
  IssuedCertificate,
  PublicCertificateVerification,
} from './types'

const BASE = '/sms/certificates'

export function listTemplates(): Promise<CertificateTemplate[]> {
  return apiGet<CertificateTemplate[]>(`${BASE}/templates`)
}

export function createTemplate(
  payload: CertificateTemplateCreate
): Promise<CertificateTemplate> {
  return apiPost<CertificateTemplate>(`${BASE}/templates`, payload)
}

export function issueCertificate(
  payload: IssueCertificatePayload
): Promise<IssuedCertificate> {
  return apiPost<IssuedCertificate>(`${BASE}/issue`, payload)
}

export function listIssuedCertificates(studentId?: number): Promise<IssuedCertificate[]> {
  return apiGet<IssuedCertificate[]>(`${BASE}/issued${toQueryString({ student_id: studentId })}`)
}

/**
 * The PUBLIC verification endpoint -- the same call an employer or university
 * makes with a code from a printed certificate. Exposed inside the dashboard
 * so staff can confirm what an outside party would actually see, rather than
 * assuming it works.
 *
 * Returns 404 for an unknown code, which `useApiResource` surfaces as
 * `kind: 'not_found'`; that is a legitimate answer ("no such certificate"),
 * not an error to retry.
 */
export function verifyCertificate(hash: string): Promise<PublicCertificateVerification> {
  return apiGet<PublicCertificateVerification>(`${BASE}/verify/${encodeURIComponent(hash)}`)
}
