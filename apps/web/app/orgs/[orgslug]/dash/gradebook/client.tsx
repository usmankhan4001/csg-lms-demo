'use client'

/**
 * Gradebook, attached as a first-class Learnhouse dash module.
 *
 * The page sits under `dash/`, so it inherits ClientAdminLayout (left menu +
 * header) exactly like Courses or Playgrounds, and its nav entry is gated on
 * the real `sms_gradebook` feature toggle the backend already resolves into
 * `org.config.config.resolved_features`.
 *
 * `GradebookMatrix` is reused unchanged -- the module moved shells, it wasn't
 * rewritten. This page adds the campus -> section -> term scoping the matrix
 * needs, assessment-plan creation (without which the matrix has no columns to
 * mark against), and the report-card draft/send/PDF lifecycle.
 *
 * PDF export IS now wired, but only off a report card generated in-session:
 * `GET /report-card/{id}/pdf` keys on a persisted id, and the only endpoint
 * that yields one is the draft POST. See ReportCardPanel for the detail.
 */

import { useState } from 'react'
import { GraduationCap } from 'lucide-react'
import { DashPageShell, EmptyState, SectionCard } from '@/components/widgets'
import { apiGet } from '@/lib/api/api-client'
import { useApiResource } from '@/lib/api/useApiResource'
import { useSchoolSession } from '@/lib/api/useSchoolSession'
import { listAcademicTerms, listCampuses, listClassSections } from '@/modules/sms/campus/api'
import { listAssessmentPlans } from '@/modules/sms/gradebook/api'
import { AssessmentPlanDialog } from '@/modules/sms/gradebook/components/AssessmentPlanDialog'
import { GradebookMatrix } from '@/modules/sms/gradebook/components/GradebookMatrix'
import { ReportCardPanel } from '@/modules/sms/gradebook/components/ReportCardPanel'

interface GradebookDashClientProps {
  org_id: number
  orgslug: string
}

/** Learnhouse's own course list — assessment plans hang off a real course_id.
 *  Uses the SMS api client so the bearer token is attached the same way. */
interface OrgCourse {
  id: number
  name: string
}

export default function GradebookDashClient({ org_id, orgslug }: GradebookDashClientProps) {
  const { session, checked } = useSchoolSession()
  const [campusId, setCampusId] = useState<number | undefined>(undefined)
  const [sectionId, setSectionId] = useState<number | undefined>(undefined)
  const [termId, setTermId] = useState<number | undefined>(undefined)

  const campuses = useApiResource(() => listCampuses({ orgId: org_id, isActive: true }), [org_id], {
    isEmpty: (d) => d.length === 0,
  })

  // Default to the caller's own campus when they have one, else the first.
  const effectiveCampusId = campusId ?? session?.campus_id ?? campuses.data?.[0]?.id

  const sections = useApiResource(
    () => listClassSections(effectiveCampusId as number, { isActive: true }),
    [effectiveCampusId],
    { skip: effectiveCampusId === undefined, isEmpty: (d) => d.length === 0 }
  )

  const terms = useApiResource(
    () => listAcademicTerms({ campusId: effectiveCampusId }),
    [effectiveCampusId],
    { skip: effectiveCampusId === undefined, isEmpty: (d) => d.length === 0 }
  )

  const effectiveSectionId = sectionId ?? sections.data?.[0]?.id
  // Fall back to the caller's own term (students/teachers carry one) before
  // the first listed term, so the common case needs no interaction.
  const effectiveTermId = termId ?? session?.academic_term_id ?? terms.data?.[0]?.id

  const courses = useApiResource(
    () => apiGet<OrgCourse[]>(`/courses/org_slug/${orgslug}/page/1/limit/100?include_unpublished=true`),
    [orgslug],
    { isEmpty: (d) => d.length === 0 }
  )

  // Fetched here rather than inside the dialog so the running weight total is
  // computed from the same list the matrix draws its columns from.
  const plans = useApiResource(
    () => listAssessmentPlans({ academicTermId: effectiveTermId }),
    [effectiveTermId],
    { isEmpty: (d) => d.length === 0 }
  )

  // Bump to force the matrix to re-read plans after one is created.
  const [planVersion, setPlanVersion] = useState(0)

  return (
    <DashPageShell
      module="gradebook"
      title={"Gradebook"}
      description="Enter marks for a section and see weighted grades update as you type."
      action={
        <AssessmentPlanDialog
          sectionId={effectiveSectionId}
          academicTermId={effectiveTermId}
          courses={courses.data ?? []}
          existingPlans={plans.data ?? []}
          onCreated={() => {
            plans.refetch()
            setPlanVersion((v) => v + 1)
          }}
        />
      }
    >
      <SectionCard
        title="Choose a section"
        icon={<GraduationCap className="size-4 text-gray-500" />}
        state={
          campuses.status === 'loading' || sections.status === 'loading' ? 'loading' : campuses.status
        }
        error={campuses.error ?? sections.error}
        onRetry={campuses.refetch}
        emptyTitle="No campuses set up yet"
        emptyDescription="Add a campus and class sections before entering grades."
      >
        <div className="flex flex-wrap items-end gap-4">
          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-gray-500">Campus</span>
            <select
              id="gradebook-campus"
              className="px-3 py-2 bg-white nice-shadow rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-black focus:ring-offset-2 border-0"
              value={effectiveCampusId ?? ''}
              onChange={(e) => {
                setCampusId(Number(e.target.value))
                setSectionId(undefined)
                setTermId(undefined)
              }}
            >
              {(campuses.data ?? []).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>

          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-gray-500">Section</span>
            <select
              id="gradebook-section"
              className="px-3 py-2 bg-white nice-shadow rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-black focus:ring-offset-2 border-0"
              value={effectiveSectionId ?? ''}
              onChange={(e) => setSectionId(Number(e.target.value))}
              disabled={(sections.data ?? []).length === 0}
            >
              {(sections.data ?? []).map((s) => (
                <option key={s.id} value={s.id}>
                  {s.grade_level} — {s.section_name}
                </option>
              ))}
            </select>
          </label>

          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-gray-500">Term</span>
            <select
              id="gradebook-term"
              className="px-3 py-2 bg-white nice-shadow rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-black focus:ring-offset-2 border-0"
              value={effectiveTermId ?? ''}
              onChange={(e) => setTermId(Number(e.target.value))}
              disabled={(terms.data ?? []).length === 0}
            >
              {(terms.data ?? []).map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          </label>
        </div>
      </SectionCard>

      {effectiveSectionId !== undefined ? (
        <>
          <GradebookMatrix
            key={`matrix-${effectiveSectionId}-${effectiveTermId}-${planVersion}`}
            sectionId={effectiveSectionId}
            academicTermId={effectiveTermId}
            gradedBy={checked ? session?.staff_id ?? undefined : undefined}
            campusId={effectiveCampusId}
          />
          <ReportCardPanel sectionId={effectiveSectionId} academicTermId={effectiveTermId} />
        </>
      ) : (
        <SectionCard title="Gradebook" icon={<GraduationCap className="size-4 text-gray-500" />}>
          <EmptyState
            title="No section selected"
            description="Pick a campus and section above to start entering marks."
          />
        </SectionCard>
      )}
    </DashPageShell>
  )
}
