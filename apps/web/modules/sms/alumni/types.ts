/**
 * Mirrors `apps/api/src/schemas/sms_alumni.py`.
 *
 * NOTE ON WHAT THE API DOES NOT OFFER: `AlumniProfileUpdate` exists in the
 * schema module and is imported by both the router and the service, but NO
 * endpoint consumes it -- there is no PATCH. A profile can be created and
 * never corrected, so this client deliberately offers no edit affordance:
 * a disabled "Edit" button, or one that 404s, is worse than none.
 */

export interface AlumniMilestone {
  id: number
  alumni_id: number
  title: string
  description: string | null
  /** ISO date, `YYYY-MM-DD`. Stored as a string by the API, not a datetime. */
  milestone_date: string
  created_at: string
}

export interface AlumniProfile {
  id: number
  org_id: number | null
  campus_id: number | null
  user_id: number
  graduation_year: number
  degree_or_diploma: string
  current_company: string | null
  job_title: string | null
  industry: string | null
  higher_ed_institution: string | null
  higher_ed_major: string | null
  linkedin_url: string | null
  location_city: string | null
  location_country: string | null
  willing_to_mentor: boolean
  mentorship_topics: string | null
  created_at: string
  /**
   * Returned nested by `GET /profiles` (alumni.py `list_profiles` issues a
   * per-profile query). So a milestone written through `POST /milestones` IS
   * readable back -- this module is not write-only.
   */
  milestones: AlumniMilestone[]
}

export interface AlumniProfileCreate {
  user_id: number
  graduation_year: number
  degree_or_diploma: string
  current_company?: string | null
  job_title?: string | null
  industry?: string | null
  higher_ed_institution?: string | null
  higher_ed_major?: string | null
  linkedin_url?: string | null
  location_city?: string | null
  location_country?: string | null
  willing_to_mentor?: boolean
  mentorship_topics?: string | null
}

export interface AlumniMilestoneCreate {
  alumni_id: number
  title: string
  description?: string | null
  milestone_date: string
}

export interface AlumniFilters {
  graduation_year?: number
  industry?: string
  willing_to_mentor?: boolean
}
