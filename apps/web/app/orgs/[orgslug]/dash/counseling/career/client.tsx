'use client'

/**
 * Career guidance plans.
 *
 * Deliberately a SEPARATE screen from counselling sessions, mirroring the
 * backend: `sms_counseling.py:20-21` states career guidance "is NOT a
 * confidential clinical record and uses ordinary 403s", and
 * `list_career_plans` (`counseling.py:272`) applies no confidentiality
 * masking at all. Putting an advisory document on the same screen as clinical
 * notes would blur a boundary the backend draws explicitly -- and would imply
 * to a counsellor that a career plan carries the same protection, which it
 * does not.
 *
 * Generation is gated to staff (`CAREER_GUIDANCE_STAFF_ROLES`) and returns an
 * ordinary 403, so unlike the sessions screen this one CAN and SHOULD show a
 * permission message.
 */

import { useState } from 'react'
import { Compass } from 'lucide-react'
import {
  DashPageShell,
  EmptyState,
  LH_INPUT,
  LH_LABEL,
  LH_PRIMARY_BUTTON,
  LH_SECONDARY_BUTTON,
  SchoolDialog,
  SchoolField,
  SectionCard,
} from '@/components/widgets'
import { ApiError } from '@/lib/api/api-client'
import { useApiResource } from '@/lib/api/useApiResource'
import { generateCareerPlan, listCareerPlans } from '@/modules/sms/counseling/api'
import { formatDateTime, studentLabel } from '@/modules/sms/counseling/presentation'
import type { CareerGuidancePlanRead } from '@/modules/sms/counseling/types'

interface Props {
  org_id: number
  orgslug: string
}

export default function CareerGuidanceClient({ org_id }: Props) {
  const [studentInput, setStudentInput] = useState('')
  const [studentId, setStudentId] = useState<number | null>(null)
  const [generating, setGenerating] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const plans = useApiResource(
    () => listCareerPlans(studentId as number),
    [studentId],
    { skip: studentId === null, isEmpty: (d) => d.length === 0 }
  )

  function selectStudent(e: React.FormEvent) {
    e.preventDefault()
    const parsed = Number(studentInput.trim())
    if (!parsed || parsed < 1 || !Number.isInteger(parsed)) {
      setError('Enter a numeric student id.')
      return
    }
    setError(null)
    setStudentId(parsed)
  }

  async function handleGenerate(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (studentId === null) return
    const f = new FormData(e.currentTarget)
    const rawInterests = String(f.get('interests') ?? '').trim()
    setBusy(true)
    setError(null)
    try {
      await generateCareerPlan({
        student_id: studentId,
        interests: rawInterests
          ? rawInterests.split(',').map((s) => s.trim()).filter(Boolean)
          : null,
        extra_context: String(f.get('extra_context') ?? '').trim() || null,
      })
      setGenerating(false)
      plans.refetch()
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.status === 403
            ? 'Only counselling or teaching staff can generate a plan. This may also mean AI is not configured for this deployment.'
            : err.status === 502
              ? 'Plan generation failed. Nothing was saved — try again.'
              : err.message
          : 'Could not generate. Try again.'
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <DashPageShell
      module="counseling"
      title="Career guidance"
      description="Structured pathway plans grounded in a student's academic record. Advisory, not a confidential clinical record."
    >
      <SectionCard
        id="career-student"
        title="Choose a student"
        icon={<Compass className="size-4 text-gray-500" />}
      >
        <form onSubmit={selectStudent} className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1.5">
            <span className={LH_LABEL}>Student id</span>
            <input
              id="career-student-id"
              className={LH_INPUT}
              inputMode="numeric"
              placeholder="e.g. 37"
              value={studentInput}
              onChange={(e) => setStudentInput(e.target.value)}
            />
          </label>
          <button type="submit" id="career-student-go" className={LH_PRIMARY_BUTTON}>
            <span>View plans</span>
          </button>
          {studentId !== null && (
            <span className="text-sm text-gray-500">Showing {studentLabel(studentId)}</span>
          )}
        </form>
        {error && !generating && <p className="mt-2 text-sm text-rose-600">{error}</p>}
      </SectionCard>

      {studentId === null ? (
        <SectionCard title="Plans" icon={<Compass className="size-4 text-gray-500" />}>
          <EmptyState
            title="No student selected"
            description="Enter a student id above to see their career guidance plans."
          />
        </SectionCard>
      ) : (
        <SectionCard
          id="career-plans"
          title="Career guidance plans"
          icon={<Compass className="size-4 text-gray-500" />}
          state={plans.status}
          error={plans.error}
          onRetry={plans.refetch}
          emptyTitle="No plans generated yet"
          emptyDescription="Nobody has generated a career guidance plan for this student."
          action={
            <button
              type="button"
              id="career-generate"
              className={LH_SECONDARY_BUTTON}
              onClick={() => {
                setError(null)
                setGenerating(true)
              }}
            >
              <span>Generate a plan</span>
            </button>
          }
        >
          <div className="flex flex-col gap-4">
            {(plans.data ?? []).map((plan: CareerGuidancePlanRead) => (
              <article key={plan.id} className="rounded-xl bg-white p-4 nice-shadow">
                <header className="mb-3 flex items-baseline justify-between gap-3">
                  <h3 className="text-sm font-semibold text-gray-800">Plan #{plan.id}</h3>
                  <span className="text-xs text-gray-500">
                    {formatDateTime(plan.generated_at)}
                  </span>
                </header>

                {plan.suggested_pathways.length > 0 && (
                  <div className="mb-3">
                    <h4 className="mb-1 text-xs font-medium uppercase tracking-wide text-gray-500">
                      Suggested pathways
                    </h4>
                    <ul className="flex flex-col gap-2">
                      {plan.suggested_pathways.map((p, i) => (
                        <li key={i} className="text-sm">
                          <span className="font-medium text-gray-800">{p.pathway}</span>
                          <span className="block text-gray-600">{p.reasoning}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                <div className="mb-3">
                  <h4 className="mb-1 text-xs font-medium uppercase tracking-wide text-gray-500">
                    Reasoning
                  </h4>
                  <p className="text-sm text-gray-700">{plan.reasoning}</p>
                </div>

                {plan.next_steps.length > 0 && (
                  <div>
                    <h4 className="mb-1 text-xs font-medium uppercase tracking-wide text-gray-500">
                      Next steps
                    </h4>
                    <ul className="list-disc pl-5 text-sm text-gray-700">
                      {plan.next_steps.map((s, i) => (
                        <li key={i}>{s}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </article>
            ))}
          </div>
        </SectionCard>
      )}

      <SchoolDialog
        open={generating}
        onOpenChange={setGenerating}
        title="Generate a career guidance plan"
        description="Grounded in this student's most recent report card. Interests are optional but make the plan more specific."
        onSubmit={handleGenerate}
        footer={
          <button type="submit" disabled={busy} className={LH_PRIMARY_BUTTON}>
            <span>{busy ? 'Generating…' : 'Generate'}</span>
          </button>
        }
      >
        <SchoolField
          id="career-interests"
          label="Stated interests"
          help="Comma separated. Leave blank if the student has not said."
        >
          <input
            id="career-interests"
            name="interests"
            className={LH_INPUT}
            placeholder="robotics, biology, design"
          />
        </SchoolField>
        <SchoolField id="career-context" label="Additional context">
          <textarea id="career-context" name="extra_context" rows={3} className={LH_INPUT} />
        </SchoolField>
        {error && <p className="text-sm text-rose-600">{error}</p>}
      </SchoolDialog>
    </DashPageShell>
  )
}
