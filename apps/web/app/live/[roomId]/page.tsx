'use client'

/**
 * Live virtual classroom -- real WebRTC via LiveKit (see
 * `modules/sms/live-class/components/LiveClassRoom.tsx`), replacing a
 * fully mocked demo page (hardcoded participants, fake AI responses on a
 * setTimeout, no backend calls at all). The room is created by a teacher
 * from their dashboard (`app/orgs/[orgslug]/dash/live-classes`); this page
 * just joins whatever room the URL names.
 *
 * WHERE "LEAVE" GOES. The two surviving shells are `dash/` for staff and
 * `(withmenu)/` for learners, reached as `/dash` and `/my-school` -- both
 * rewritten onto `/orgs/{slug}/...` by proxy.ts §11. The old `/teacher` and
 * `/student` targets were retired with the `app/(dashboard)/` portals, so
 * leaving a class used to dead-end on a 404. Which shell applies is the
 * session's access level (`lib/school-access.ts`), not a single role string:
 * testing `roles.includes('TEACHER')` sent every SCHOOL_ADMIN and STAFF host
 * to the learner shell.
 */

import { useParams } from 'next/navigation'
import { Loader2 } from 'lucide-react'
import { useSchoolSession } from '@/lib/api/useSchoolSession'
import { useSchoolAccess } from '@/lib/school-access'
import { useOrg } from '@/components/Contexts/OrgContext'
import { getUriWithOrg } from '@services/config/config'
import { LiveClassRoom } from '@/modules/sms/live-class/components/LiveClassRoom'

export default function LiveClassroomPage() {
  const params = useParams()
  const roomName = (params?.roomId as string) || ''
  const { session, checked } = useSchoolSession()
  const access = useSchoolAccess()
  // `/live/*` is a direct pass-through route (proxy.ts §5b), so it is not
  // wrapped in OrgContext and this is usually null. `getUriWithOrg` falls back
  // to a relative path when it is, which is correct: the browser is already on
  // the org's host and the tenant rewrite resolves it.
  const org = useOrg() as any

  if (!checked) {
    return (
      <div className="flex h-screen items-center justify-center bg-neutral-950">
        <Loader2 className="size-6 animate-spin text-neutral-400" />
      </div>
    )
  }

  const participantId = session ? String(session.staff_id ?? session.student_id ?? '') : ''

  if (!session || !participantId) {
    return (
      <div className="flex h-screen items-center justify-center bg-neutral-950 text-center text-sm text-neutral-400">
        You need a school role linked to your account to join a live class.
      </div>
    )
  }

  // Staff (teaching or back-office, admins included) live in the dash shell;
  // everyone else -- students and guardians -- in the learner shell.
  const isStaff = access.canTeach || access.canBackOffice
  const homeHref = getUriWithOrg(org?.slug ?? '', isStaff ? '/dash' : '/my-school')

  return (
    <LiveClassRoom
      roomName={roomName}
      participantId={participantId}
      participantName={session.name ?? 'Participant'}
      // A hint only: the server re-derives host status from the session's
      // teacher and the caller's roles, and the room renders from what it
      // grants. Sending the access level here keeps the request honest without
      // the UI ever trusting its own answer.
      isHost={isStaff}
      onLeaveHref={homeHref}
      orgId={session.org_id ?? undefined}
    />
  )
}
