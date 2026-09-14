import { useAuth } from './AuthContext';

/**
 * "Who am I, in school terms" — resolved SERVER-SIDE.
 *
 * This used to read CSG convenience claims (`subject_id`, `section_id`,
 * `children_ids`, ...) out of the dev JWT. A real Learnhouse access token
 * carries none of them — its payload is `{sub, purpose, amr, exp, iat, type}`
 * — so every one of those reads would now return null and the screens built on
 * them would render empty.
 *
 * The values come from `GET /sms/me` instead, captured into the session at
 * sign-in. That is also the more defensible source: `children_ids` in
 * particular must never be client-supplied, because "which children may I see"
 * is precisely the question a client must not answer for itself. The server
 * resolves it from the `StudentGuardian` table and re-checks it on every
 * per-child endpoint.
 *
 * `subjectId` is role-dependent, matching what the old claim meant: a student's
 * own `student_id`, or a teacher's / staff member's `staff_id`.
 */
export function useSessionSubject() {
  const { session } = useAuth();
  const identity = session?.identity;
  const role = session?.role;

  const subjectId =
    role === 'STUDENT'
      ? identity?.student_id ?? null
      : role === 'TEACHER' || role === 'STAFF'
        ? identity?.staff_id ?? null
        : null;

  return {
    subjectId,
    sectionId: identity?.section_id ?? null,
    academicTermId: identity?.academic_term_id ?? null,
    campusId: identity?.campus_id ?? null,
    orgId: identity?.org_id ?? null,
    childrenIds: identity?.children_ids ?? null,
    name: identity?.name ?? null,
    email: identity?.email ?? null,
  };
}
