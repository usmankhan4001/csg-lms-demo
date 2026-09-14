'use client'

/**
 * One application, whole: the applicant, their documents, their assessment,
 * and the decision trail on a single screen — which is what the office
 * actually needs to answer "where is this, and why".
 *
 * Permission-denied is handled explicitly rather than as a generic error:
 * these records hold a child's birth certificate and medical history, and a
 * caller without admissions access should be told plainly that this is
 * restricted, not shown a retry button that will never work.
 */

import Link from 'next/link'
import { ArrowLeft, IdCard, Send, UserRound } from 'lucide-react'
import {
  DashPageShell,
  EmptyState,
  LH_INPUT,
  LH_SECONDARY_BUTTON,
  SectionCard,
  StatusChip,
} from '@/components/widgets'
import { useApiResource } from '@/lib/api/useApiResource'
import { useSchoolSession } from '@/lib/api/useSchoolSession'
import { getApplicationDetail, setApplicationStatus, submitApplication } from '@/modules/sms/admissions/api'
import { AssessmentPanel } from '@/modules/sms/admissions/components/AssessmentPanel'
import { DecisionPanel } from '@/modules/sms/admissions/components/DecisionPanel'
import { DocumentsPanel } from '@/modules/sms/admissions/components/DocumentsPanel'
import {
  STATUS_LABEL,
  STATUS_TONE,
  TERMINAL_STATUSES,
  formatContact,
  formatDate,
  formatDateTime,
} from '@/modules/sms/admissions/presentation'
import type { ApplicationStatus } from '@/modules/sms/admissions/types'
import { useState } from 'react'

interface Props {
  org_id: number
  orgslug: string
  applicationId: number
}

const STATUSES: ApplicationStatus[] = [
  'DRAFT',
  'SUBMITTED',
  'DOCUMENTS_PENDING',
  'UNDER_REVIEW',
  'ASSESSMENT_SCHEDULED',
  'ASSESSED',
  'OFFERED',
  'ACCEPTED',
  'ENROLLED',
  'REJECTED',
  'WITHDRAWN',
]

export default function ApplicationDetailClient({ applicationId }: Props) {
  const { session } = useSchoolSession()
  const [busy, setBusy] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)

  const detail = useApiResource(() => getApplicationDetail(applicationId), [applicationId], {
    isEmpty: () => false,
  })

  // Verification and decisions are SUPER_ADMIN/SCHOOL_ADMIN server-side
  // (_ADMISSIONS_LEAD). Mirroring that here hides controls the caller cannot
  // use, rather than offering a button that 403s.
  const roles = session?.roles ?? []
  const canLead = roles.includes('SUPER_ADMIN') || roles.includes('SCHOOL_ADMIN')

  if (detail.error?.kind === 'permission_denied') {
    return (
      <DashPageShell title="Application" description="Restricted">
        <EmptyState
          tone="caution"
          title="Restricted"
          description="Applications hold a family's identity and medical documents. Only admissions staff and school leadership can open them."
        />
      </DashPageShell>
    )
  }

  if (detail.error?.kind === 'not_found') {
    return (
      <DashPageShell title="Application" description="Not found">
        <EmptyState
          title="Application not found"
          description="It may have been removed, or it belongs to another campus."
        />
      </DashPageShell>
    )
  }

  const data = detail.data
  const app = data?.application

  async function runAction(fn: () => Promise<unknown>, failure: string) {
    setBusy(true)
    setActionError(null)
    try {
      await fn()
      detail.refetch()
    } catch {
      setActionError(failure)
    } finally {
      setBusy(false)
    }
  }

  return (
    <DashPageShell
      title={app ? app.student_name : 'Application'}
      description={
        app
          ? `${app.application_number} · applying for ${app.grade_applying_for}`
          : 'Loading application…'
      }
      breadcrumbs={
        <Link
          href="/dash/admissions/applications"
          className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-900"
        >
          <ArrowLeft className="size-3.5" /> All applications
        </Link>
      }
      action={
        app && !TERMINAL_STATUSES.includes(app.status) ? (
          <div className="flex items-center gap-2">
            <select
              id="application-status"
              aria-label="Application status"
              className={LH_INPUT}
              value={app.status}
              disabled={busy}
              onChange={(e) =>
                runAction(
                  () => setApplicationStatus(applicationId, { status: e.target.value as ApplicationStatus }),
                  'Could not change the status.'
                )
              }
            >
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {STATUS_LABEL[s]}
                </option>
              ))}
            </select>
            {app.status === 'DRAFT' && (
              <button
                type="button"
                id="submit-application"
                className={LH_SECONDARY_BUTTON}
                disabled={busy}
                onClick={() =>
                  runAction(() => submitApplication(applicationId), 'Could not submit the application.')
                }
              >
                <Send className="size-4" /> <span>Submit</span>
              </button>
            )}
          </div>
        ) : undefined
      }
    >
      <SectionCard
        id="applicant"
        title="Applicant"
        icon={<UserRound className="size-4 text-gray-500" />}
        state={detail.status === 'loading' ? 'loading' : detail.status === 'error' ? 'error' : 'success'}
        error={detail.error}
        onRetry={detail.refetch}
      >
        {app && (
          <>
            {actionError && <p className="mb-3 text-sm text-rose-600">{actionError}</p>}
            <dl className="grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2 lg:grid-cols-3">
              <Field label="Status">
                <StatusChip label={STATUS_LABEL[app.status]} tone={STATUS_TONE[app.status]} />
              </Field>
              <Field label="Date of birth">{formatDate(app.date_of_birth)}</Field>
              <Field label="Grade applying for">{app.grade_applying_for}</Field>
              <Field label="Guardian">{app.guardian_name}</Field>
              <Field label="Guardian contact">
                {formatContact(app.guardian_email, app.guardian_phone)}
              </Field>
              <Field label="Submitted">{formatDateTime(app.submitted_at)}</Field>
              <Field label="Enquiry">
                {/* An application need not come from a lead — a walk-in family
                    may never have been tracked. Say so rather than implying a
                    missing link. */}
                {app.lead_id ? (
                  <Link
                    href={`/dash/admissions/leads/${app.lead_id}`}
                    className="text-sm text-gray-900 hover:underline"
                  >
                    Lead #{app.lead_id}
                  </Link>
                ) : (
                  <span className="text-sm text-gray-500">Applied directly</span>
                )}
              </Field>
              <Field label="Enrolled student">
                {app.enrolled_student_id ? (
                  <span className="inline-flex items-center gap-1 text-sm">
                    <IdCard className="size-3.5 text-gray-400" /> #{app.enrolled_student_id}
                  </span>
                ) : (
                  <span className="text-sm text-gray-500">Not yet on roll</span>
                )}
              </Field>
              <Field label="Notes">
                {app.notes ? (
                  <span className="text-sm text-gray-700">{app.notes}</span>
                ) : (
                  <span className="text-sm text-gray-400">None</span>
                )}
              </Field>
            </dl>
          </>
        )}
      </SectionCard>

      {data && (
        <>
          <DocumentsPanel
            applicationId={applicationId}
            documents={data.documents}
            missingTypes={data.missing_document_types}
            documentsComplete={data.documents_complete}
            canVerify={canLead}
            onChanged={detail.refetch}
          />

          <AssessmentPanel
            applicationId={applicationId}
            assessments={data.assessments}
            onChanged={detail.refetch}
          />

          <DecisionPanel
            applicationId={applicationId}
            decisions={data.decisions}
            status={data.application.status}
            canDecide={canLead}
            onChanged={detail.refetch}
          />
        </>
      )}
    </DashPageShell>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <dt className="text-xs font-medium uppercase tracking-wide text-gray-400">{label}</dt>
      <dd className="text-sm text-gray-800">{children}</dd>
    </div>
  )
}
