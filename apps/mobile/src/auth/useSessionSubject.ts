import { useAuth } from './AuthContext';

/**
 * Convenience accessor for the CSG-LMS dev convenience claims
 * (`subject_id`/`section_id`/`academic_term_id`/`children_ids`) described in
 * `apps/api/src/core/dev_tokens.py` — "my" student_id/staff_id/teacher_id
 * depending on role, since no `sms_*` endpoint resolves that from the JWT
 * server-side today. Mirrors how `apps/web/lib/api/dev-token.ts`'s decoded
 * claims are consumed by the web dashboards.
 */
export function useSessionSubject() {
  const { session } = useAuth();
  const claims = session?.claims;
  return {
    subjectId: claims?.subject_id ?? null,
    sectionId: claims?.section_id ?? null,
    academicTermId: claims?.academic_term_id ?? null,
    campusId: claims?.campus_id ?? null,
    orgId: claims?.org_id ?? null,
    childrenIds: claims?.children_ids ?? null,
    name: claims?.name ?? null,
    email: claims?.email ?? null,
  };
}
