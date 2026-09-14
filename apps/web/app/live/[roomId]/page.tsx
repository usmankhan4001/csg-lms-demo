'use client'

/**
 * Live virtual classroom -- real WebRTC via LiveKit (see
 * `modules/sms/live-class/components/LiveClassRoom.tsx`), replacing a
 * fully mocked demo page (hardcoded participants, fake AI responses on a
 * setTimeout, no backend calls at all). The room is created by a teacher
 * from their dashboard (`app/(dashboard)/teacher/page.tsx`'s "Start Live
 * Class"); this page just joins whatever room the URL names.
 */

import { useParams } from 'next/navigation'
import { Loader2 } from 'lucide-react'
import { useSchoolSession } from '@/lib/api/useSchoolSession'
import { LiveClassRoom } from '@/modules/sms/live-class/components/LiveClassRoom'

export default function LiveClassroomPage() {
  const params = useParams()
  const roomName = (params?.roomId as string) || ''
  const { session, checked } = useSchoolSession()

  if (!checked) {
    return (
      <div className="flex h-screen items-center justify-center bg-neutral-950">
        <Loader2 className="size-6 animate-spin text-neutral-400" />
      </div>
    )
  }

  const isTeacher = session?.roles.includes('TEACHER') ?? false
  const participantId = session ? String(session.staff_id ?? session.student_id ?? '') : ''
  const homeHref = isTeacher ? '/teacher' : '/student'

  if (!session || !participantId) {
    return (
      <div className="flex h-screen items-center justify-center bg-neutral-950 text-center text-sm text-neutral-400">
        You need a school role linked to your account to join a live class.
      </div>
    )
  }

  return (
    <LiveClassRoom
      roomName={roomName}
      participantId={participantId}
      participantName={session.name ?? 'Participant'}
      isTeacher={isTeacher}
      onLeaveHref={homeHref}
    />
  )
}
