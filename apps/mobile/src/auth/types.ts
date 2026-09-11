/**
 * Mirrors `src.core.keycloak_auth.KeycloakRole` (`apps/api/src/core/keycloak_auth.py`)
 * and the dev convenience claims minted by `mint_dev_keycloak_token`
 * (`apps/api/src/core/dev_tokens.py`) / read back by
 * `apps/web/lib/api/dev-token.ts`'s `DevSessionClaims`.
 */

export type KeycloakRole =
  | 'SUPER_ADMIN'
  | 'SCHOOL_ADMIN'
  | 'TEACHER'
  | 'STUDENT'
  | 'PARENT'
  | 'STAFF'
  | 'PSYCHOLOGIST';

/**
 * Roles this mobile app has a real navigation shell + screens for, per
 * DESIGN-SYSTEM.md §2.3 ("mobile-relevant personas"). `SCHOOL_ADMIN` is
 * web-only by explicit product decision; `SUPER_ADMIN`/`PSYCHOLOGIST` have no
 * mobile IA defined in this pass either.
 */
export type MobileRole = 'STUDENT' | 'TEACHER' | 'PARENT' | 'STAFF';

export const MOBILE_SUPPORTED_ROLES: MobileRole[] = ['STUDENT', 'TEACHER', 'PARENT', 'STAFF'];

export function isMobileRole(role: string | undefined | null): role is MobileRole {
  return !!role && (MOBILE_SUPPORTED_ROLES as string[]).includes(role);
}

/** Decoded (NOT signature-verified — see token.ts) JWT payload claims. */
export interface SessionClaims {
  sub: string;
  email?: string | null;
  name?: string | null;
  org_id?: number | null;
  campus_id?: number | null;
  /** CSG-LMS dev convenience claim: "my" student_id / staff_id / teacher_id. */
  subject_id?: number | null;
  section_id?: number | null;
  academic_term_id?: number | null;
  children_ids?: number[] | null;
  realm_access?: { roles?: string[] };
  exp?: number;
  iat?: number;
  [key: string]: unknown;
}

export interface Session {
  token: string;
  claims: SessionClaims;
  role: KeycloakRole;
}
