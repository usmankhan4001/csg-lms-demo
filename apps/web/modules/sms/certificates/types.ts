/** Mirrors `apps/api/src/schemas/sms_certificates.py`. */

export interface CertificateTemplate {
  id: number
  org_id: number | null
  title: string
  description: string | null
  layout_type: string
  background_url: string | null
  border_style: string
  issuer_name: string
  issuer_title: string
  is_active: boolean
  created_at: string
}

export interface CertificateTemplateCreate {
  title: string
  description?: string
  layout_type?: string
  background_url?: string
  border_style?: string
  issuer_name: string
  issuer_title: string
}

export interface IssueCertificatePayload {
  template_id: number
  student_id: number
  recipient_name: string
  recipient_email?: string
  title: string
  honors?: string
  issue_date: string
  expiry_date?: string
}

export interface IssuedCertificate {
  id: number
  org_id: number | null
  template_id: number
  student_id: number
  recipient_name: string
  recipient_email: string | null
  title: string
  honors: string | null
  issue_date: string
  expiry_date: string | null
  verification_hash: string
  /**
   * Both nullable, and the UI must say so rather than showing a broken link.
   * A certificate row can exist before its PDF or QR image has been produced.
   */
  qr_code_data_url: string | null
  pdf_storage_url: string | null
  is_revoked: boolean
  created_at: string
}

export interface PublicCertificateVerification {
  is_valid: boolean
  recipient_name: string
  title: string
  honors: string | null
  issue_date: string
  issuer_name: string
  issuer_title: string
  is_revoked: boolean
  revocation_reason: string | null
}

export const LAYOUT_TYPES = ['landscape', 'portrait'] as const
export const BORDER_STYLES = ['classic_gold', 'modern_minimal', 'academic_navy'] as const
