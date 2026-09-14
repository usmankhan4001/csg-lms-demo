'use client'

/**
 * A student_id -> display name map.
 *
 * WHY THIS EXISTS, and why it is a workaround rather than the fix:
 * `StudentEnrollmentRead` (`apps/api/src/db/sms_campus.py:350`) exposes
 * `student_id`, `section_id`, `academic_year_id` and `roll_number` -- and no
 * joined display name. So every screen built on the roster alone can only
 * render "Student #37", which is unusable for taking a register or entering
 * marks.
 *
 * `GET /sms/identity/people?role=STUDENT` DOES return names
 * (`SchoolPersonRead`, `sms_identity.py:353`) and its role gate includes
 * TEACHER (`:383`), so a teacher taking roll-call can legitimately fetch it.
 * This joins the two client-side.
 *
 * The real fix is for the enrolment endpoint to join `User` itself: this costs
 * an extra round-trip, and it resolves names for people holding a STUDENT role
 * grant in the campus, so an enrolled student missing that grant still falls
 * back to their id rather than silently disappearing.
 */

import { useMemo } from 'react'
import { useApiResource } from '@/lib/api/useApiResource'
import { listSchoolPeople } from '@/modules/sms/campus/api'

export interface StudentNames {
  names: Map<number, string>
  /** True while the lookup is in flight -- rows render ids until it resolves. */
  loading: boolean
  /** Non-null when the lookup failed; callers should say so rather than pretend. */
  error: Error | null
}

export function useStudentNames(campusId?: number): StudentNames {
  const people = useApiResource(
    () => listSchoolPeople('STUDENT', campusId),
    [campusId],
    { skip: campusId === undefined, isEmpty: (d) => d.length === 0 }
  )

  const names = useMemo(() => {
    const map = new Map<number, string>()
    for (const p of people.data ?? []) {
      if (p.name) map.set(p.user_id, p.name)
    }
    return map
  }, [people.data])

  return {
    names,
    loading: people.status === 'loading',
    error: people.error ?? null,
  }
}
