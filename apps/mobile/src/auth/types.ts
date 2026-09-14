/**
 * Mirrors `SchoolRole` (`apps/api/src/db/sms_identity.py`), as returned by
 * `GET /sms/me` (`apps/api/src/routers/sms_identity.py`).
 *
 * NOTE: roles no longer come from the token. A real Learnhouse access token's
 * payload is `{sub, purpose, amr, exp, iat, type}` with `sub` being the user's
 * email -- verified against the running API -- so there is no `realm_access`
 * claim to read a role out of, and none of the CSG convenience claims
 * (`subject_id`, `section_id`, `children_ids`, ...) the dev token used to
 * carry. All of that is resolved server-side by `GET /sms/me` instead, which
 * is the correct place for it: "which roles do I hold" and "which children are
 * mine" are questions a client must never answer for itself.
 */

import type { MyIdentity } from '@/modules/sms/identity/types';

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
  /**
   * Epoch ms at which the access token stops being accepted, or null when the
   * server did not say. Checked locally on restore so an expired session sends
   * the user to sign-in rather than into a shell that 401s on every screen.
   */
  expiresAt: number | null;
  /** Resolved server-side by `GET /sms/me` -- see the note at the top of this file. */
  identity: MyIdentity;
  /**
   * The persona shell to render. Picked from `identity.roles` at sign-in.
   * A user may hold several roles (an admin who also teaches); the first one
   * this app has a shell for wins.
   */
  role: MobileRole;
}
