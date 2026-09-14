/** Mirrors the payloads in `apps/api/src/routers/sms_school_setup.py`. */

/** What an organisation still lacks before it behaves like a school. */
export interface SchoolSetupStatus {
  org_id: number
  is_set_up: boolean
  /** Structural pieces still absent: 'campus' | 'academic_year' | 'academic_term' | 'school_admin'. */
  missing: string[]
  campus_count: number
  academic_year_count: number
  term_count: number
  school_admin_count: number
  /** False once set up, and false for anyone who may not run it. */
  may_run_setup: boolean
}

export interface TermPayload {
  name: string
  term_code?: string | null
  weight_percentage: number
  start_date?: string | null
  end_date?: string | null
}

export interface SchoolSetupRequest {
  org_id: number

  campus_name: string
  campus_code: string
  campus_timezone: string
  campus_address?: string | null

  academic_year_name: string
  academic_year_start?: string | null
  academic_year_end?: string | null
  terms: TermPayload[]

  admin_email?: string | null
  admin_first_name?: string | null
  admin_last_name: string

  crisis_resources?: Record<string, unknown> | null
  school_profile?: Record<string, unknown> | null
}

export interface SchoolSetupResponse {
  org_id: number
  campus_id: number
  academic_year_id: number
  term_ids: number[]
  admin_user_id: number | null
  /** True when the account was created here; false when an existing user was promoted. */
  admin_created: boolean
  settings_written: string[]
  /** Defaults that did not save. The school still exists — these are set manually. */
  settings_failed: string[]
}
