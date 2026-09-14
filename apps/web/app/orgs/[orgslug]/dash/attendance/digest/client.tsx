'use client'

/**
 * Family digest preview: exactly what a parent receives this week.
 *
 * WHY THIS IS A STAFF SCREEN. The digest is mailed to guardians, and until now
 * nobody inside the school could see what it said. A form tutor asked "what did
 * we tell this family?" had no answer. This is that answer -- a preview, not a
 * second copy of the truth.
 *
 * WHY IT LIVES UNDER ATTENDANCE. The digest is overwhelmingly an attendance
 * report (rate, classes attended, classes total) plus tutor activity, and the
 * at-risk queue next door is where a member of staff is already thinking about
 * one named child. It is a tab rather than a sidebar entry because the menu had
 * grown to 55 entries and was rebuilt to one per module.
 *
 * ABSENT DATA IS NOT ZERO, and this endpoint is unusually careful about it:
 * `attendance_rate` arrives as a STRING carrying "Not recorded" when no
 * register was taken. It is rendered verbatim rather than parsed to a number,
 * precisely so it cannot be coerced into "0%" on the way to the screen. A
 * parent reading 0% concludes their child attended nothing; the truth is that
 * nobody marked a register.
 *
 * Fields this digest does NOT carry -- assignment counts, average score,
 * strengths, growth areas, teacher praise -- were removed from the API rather
 * than faked, after it shipped a hardcoded "96.0%" and invented praise
 * identical for every child. Nothing here re-adds them.
 */

import { useState } from 'react'
import { CalendarRange, Mail, MessageSquareText } from 'lucide-react'
import {
  DashPageShell,
  EmptyState,
  LH_INPUT,
  LH_PRIMARY_BUTTON,
  SectionCard,
  StatGrid,
  StatusChip,
} from '@/components/widgets'
import { useApiResource } from '@/lib/api/useApiResource'
import { useSchoolSession } from '@/lib/api/useSchoolSession'
import { useStudentNames } from '@/modules/sms/attendance/useStudentNames'
import { getParentWeeklyDigest } from '@/modules/sms/parent-digest/api'

interface DigestClientProps {
  org_id: number
  orgslug: string
}

/**
 * The API sends "Not recorded" (or any other prose) rather than a number when
 * a rate cannot be computed. Detecting that lets the tile drop its positive
 * tone -- styling absent data as good news is how a reassuring fiction starts.
 */
function isRecordedRate(rate: string): boolean {
  return /\d/.test(rate)
}

export default function DigestClient({ org_id }: DigestClientProps) {
  const { session } = useSchoolSession()
  const [studentInput, setStudentInput] = useState('')
  const [studentId, setStudentId] = useState<number | undefined>(undefined)

  const names = useStudentNames(session?.campus_id ?? undefined)

  const digest = useApiResource(
    () => getParentWeeklyDigest(studentId as number),
    [studentId],
    { skip: studentId === undefined }
  )

  const d = digest.data
  const recorded = d ? isRecordedRate(d.attendance_rate) : false
  const studentLabel =
    studentId !== undefined ? names.names.get(studentId) ?? `Student #${studentId}` : null

  function onLookup(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const parsed = Number(studentInput.trim())
    if (Number.isInteger(parsed) && parsed > 0) setStudentId(parsed)
  }

  return (
    <DashPageShell
      module="attendance"
      title="Family digest"
      description="The weekly summary a guardian receives, exactly as they see it."
    >
      <SectionCard
        title="Choose a student"
        icon={<Mail className="size-4 text-gray-500" />}
      >
        <form onSubmit={onLookup} className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-gray-500">Student ID</span>
            <input
              id="digest-student-id"
              className={LH_INPUT}
              inputMode="numeric"
              placeholder="e.g. 37"
              value={studentInput}
              onChange={(e) => setStudentInput(e.target.value)}
            />
          </label>
          <button id="digest-lookup" type="submit" className={LH_PRIMARY_BUTTON}>
            <span>Preview digest</span>
          </button>
        </form>
        {names.error && (
          <p className="mt-3 text-xs text-amber-600">
            Student names could not be loaded, so results show IDs.
          </p>
        )}
      </SectionCard>

      {studentId === undefined ? (
        <SectionCard title="Digest" icon={<Mail className="size-4 text-gray-500" />}>
          <EmptyState
            title="No student selected"
            description="Enter a student ID above to see the digest their guardian receives this week."
          />
        </SectionCard>
      ) : (
        <>
          <StatGrid
            state={digest.status === 'loading' ? 'loading' : 'success'}
            columns={4}
            items={[
              {
                label: 'Attendance this week',
                // Rendered verbatim: the API sends "Not recorded" rather than a
                // number when no register was taken, and that distinction is
                // the whole point.
                value: d?.attendance_rate ?? '—',
                icon: CalendarRange,
                tone: d ? (recorded ? 'positive' : 'neutral') : 'neutral',
                hint: d && !recorded ? 'No register was taken for this week' : undefined,
              },
              {
                label: 'Classes attended',
                value: d ? `${d.classes_attended} of ${d.total_classes}` : '—',
                icon: CalendarRange,
                tone: 'neutral',
              },
              {
                label: 'Tutor sessions',
                value: d?.tutor_sessions ?? '—',
                icon: MessageSquareText,
                tone: 'neutral',
              },
              {
                label: 'Topics explored',
                value: d?.ai_tutor_topics_explored.length ?? '—',
                icon: MessageSquareText,
                tone: 'neutral',
              },
            ]}
          />

          <SectionCard
            id="digest-body"
            title={studentLabel ? `Digest — ${studentLabel}` : 'Digest'}
            icon={<Mail className="size-4 text-gray-500" />}
            state={digest.status}
            error={digest.error}
            onRetry={digest.refetch}
            emptyTitle="No digest for this student"
            emptyDescription="Nothing has been generated for this week yet."
          >
            {d && (
              <div className="flex flex-col gap-4">
                <div className="flex flex-wrap items-center gap-2">
                  <StatusChip
                    label={`Week of ${d.week_start} to ${d.week_end}`}
                    tone="neutral"
                  />
                  {!recorded && (
                    <StatusChip label="Attendance not recorded" tone="caution" />
                  )}
                </div>

                <div className="rounded-xl bg-white nice-shadow p-4">
                  <p className="text-xs font-medium uppercase tracking-wide text-gray-500">
                    What the guardian reads
                  </p>
                  <p className="mt-2 text-sm leading-relaxed text-gray-800">
                    {d.conversational_summary}
                  </p>
                </div>

                <div>
                  <p className="text-xs font-medium uppercase tracking-wide text-gray-500">
                    AI tutor topics
                  </p>
                  {d.ai_tutor_topics_explored.length > 0 ? (
                    <div className="mt-2 flex flex-wrap gap-2">
                      {d.ai_tutor_topics_explored.map((t) => (
                        <StatusChip key={t} label={t} tone="neutral" />
                      ))}
                    </div>
                  ) : (
                    <p className="mt-2 text-sm text-gray-500">
                      No tutor activity this week. This is an absence of sessions, not a
                      score.
                    </p>
                  )}
                </div>

                <p className="text-xs text-gray-400">
                  Generated {d.generated_at}. This digest reports attendance and AI tutor
                  activity only — it carries no grades, assignment counts or teacher
                  commentary, because the school has no source for those figures.
                </p>
              </div>
            )}
          </SectionCard>
        </>
      )}
    </DashPageShell>
  )
}
