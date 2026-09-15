'use client'

/**
 * Invigilation incidents — what a human wrote down about an exam room.
 *
 * THIS IS NOT PROCTORING. The API docstring is explicit that no monitoring of
 * any kind is performed, and nothing on this screen implies otherwise: there
 * is no camera, no flagging, no automated suspicion. An incident exists only
 * because an invigilator chose to record it, and it is shown as their account
 * of events, attributed and timestamped.
 *
 * Severity is a UI convention (the API takes any short string, default
 * "INFO") kept to a fixed set so a school's records stay sortable. It is
 * deliberately NOT presented as a verdict — "MAJOR" describes what was
 * written down, not a finding against a candidate.
 */

import { useState } from 'react'
import { ClipboardList, ShieldAlert } from 'lucide-react'
import {
  DashPageShell,
  DataTable,
  LH_INPUT,
  LH_PRIMARY_BUTTON,
  LH_SECONDARY_BUTTON,
  SchoolDialog,
  SchoolField,
  SectionCard,
  StatusChip,
} from '@/components/widgets'
import { useApiResource } from '@/lib/api/useApiResource'
import { useSchoolSession } from '@/lib/api/useSchoolSession'
import { listClassSections } from '@/modules/sms/campus/api'
import { listExamIncidents, listExamSittings, listExams, logExamIncident } from '@/modules/sms/exams/api'
import { EXAM_INCIDENT_SEVERITIES, type ExamIncidentSeverity } from '@/modules/sms/exams/types'

interface Props {
  org_id: number
  orgslug: string
}

export default function ExamIncidentsClient({ org_id }: Props) {
  const { session } = useSchoolSession()
  const campusId = session?.campus_id ?? undefined

  const [examId, setExamId] = useState<number | undefined>(undefined)
  const [open, setOpen] = useState(false)
  const [severity, setSeverity] = useState<ExamIncidentSeverity>('INFO')
  const [description, setDescription] = useState('')
  const [sectionId, setSectionId] = useState('')
  const [studentId, setStudentId] = useState('')
  const [busy, setBusy] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  const exams = useApiResource(() => listExams({ campusId }), [campusId], {
    isEmpty: (d) => d.length === 0,
  })
  const effectiveExamId = examId ?? exams.data?.[0]?.id

  const incidents = useApiResource(
    () => listExamIncidents(effectiveExamId as number),
    [effectiveExamId],
    { skip: effectiveExamId === undefined, isEmpty: (d) => d.length === 0 }
  )

  const sittings = useApiResource(
    () => listExamSittings(effectiveExamId as number),
    [effectiveExamId],
    { skip: effectiveExamId === undefined, isEmpty: (d) => d.length === 0 }
  )

  const sections = useApiResource(
    () => listClassSections(campusId as number, { isActive: true }),
    [campusId],
    { skip: campusId === undefined, isEmpty: (d) => d.length === 0 }
  )

  const sectionName = (id: number | null) =>
    id === null
      ? 'Whole exam'
      : ((() => {
      const sec = sections.data?.find((s) => s.id === id)
      // ClassSectionRead has no single `name`: a section is its grade plus its
      // letter, e.g. "Grade 9 A". Joining them here keeps the label the same
      // shape a school says out loud.
      return sec ? `${sec.grade_level} ${sec.section_name}`.trim() : `Section ${id}`
    })())

  async function handleLog(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setFormError(null)
    if (description.trim().length === 0) {
      setFormError('Describe what was observed. An incident with no account of it is not a record.')
      return
    }
    if (effectiveExamId === undefined) {
      setFormError('Choose an exam first.')
      return
    }
    setBusy(true)
    try {
      await logExamIncident(effectiveExamId, {
        description: description.trim(),
        severity,
        // Both optional. An incident about the room as a whole names no
        // student, and attributing one to a candidate who was not involved is
        // worse than leaving it unattributed.
        section_id: sectionId ? Number(sectionId) : null,
        student_id: studentId ? Number(studentId) : null,
      })
      setOpen(false)
      setDescription('')
      setSectionId('')
      setStudentId('')
      setSeverity('INFO')
      incidents.refetch()
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Could not record that incident.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <DashPageShell
      module="exams"
      title="Invigilation incidents"
      description="What invigilators recorded in the exam room. Written by people, not observed by software."
    >
      <div className="flex flex-wrap items-end gap-4">
        <label className="flex flex-col gap-1.5">
          <span className="text-xs font-medium text-gray-500">Exam</span>
          <select
            id="incidents-exam"
            className={LH_INPUT}
            value={effectiveExamId ?? ''}
            onChange={(e) => setExamId(Number(e.target.value))}
            disabled={(exams.data ?? []).length === 0}
          >
            {(exams.data ?? []).map((ex) => (
              <option key={ex.id} value={ex.id}>
                {ex.title}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          id="incidents-log"
          className={LH_PRIMARY_BUTTON}
          onClick={() => setOpen(true)}
          disabled={effectiveExamId === undefined}
        >
          Log an incident
        </button>
      </div>

      <SectionCard
        title="Recorded incidents"
        description="Most exams have none. An empty list is the normal, good outcome."
        icon={<ClipboardList className="size-4 text-gray-500" />}
        state={
          exams.status === 'empty'
            ? 'empty'
            : incidents.status === 'loading'
              ? 'loading'
              : incidents.status === 'error'
                ? 'error'
                : incidents.status === 'empty'
                  ? 'empty'
                  : 'success'
        }
        error={incidents.error}
        onRetry={incidents.refetch}
        emptyTitle={exams.status === 'empty' ? 'No exams yet' : 'Nothing recorded'}
        emptyDescription={
          exams.status === 'empty'
            ? 'Create an exam before recording what happened in its rooms.'
            : 'No invigilator has recorded anything for this exam. That is the expected result, not a gap in the data.'
        }
      >
        <DataTable
          columns={[
            {
              key: 'when',
              header: 'Recorded',
              render: (r) => new Date(r.reported_at).toLocaleString(),
            },
            {
              key: 'severity',
              header: 'Severity',
              render: (r) => <StatusChip label={r.severity} />,
            },
            { key: 'where', header: 'Section', render: (r) => sectionName(r.section_id) },
            {
              key: 'who',
              header: 'Candidate',
              // "Not attributed" is a real and often correct state: an incident
              // about the room names no student.
              render: (r) =>
                r.student_id === null ? (
                  <span className="text-gray-500">Not attributed</span>
                ) : (
                  <span className="tabular-nums">{r.student_id}</span>
                ),
            },
            {
              key: 'what',
              header: 'What was recorded',
              render: (r) => <span className="whitespace-pre-wrap">{r.description}</span>,
            },
          ]}
          rows={incidents.data ?? []}
          rowKey={(r) => r.id}
        />
      </SectionCard>

      <SchoolDialog
        open={open}
        onOpenChange={setOpen}
        title="Log an invigilation incident"
        description="Your written account of something observed in the room."
        onSubmit={handleLog}
        footer={
          <>
            <button type="button" className={LH_SECONDARY_BUTTON} onClick={() => setOpen(false)}>
              Cancel
            </button>
            <button type="submit" className={LH_PRIMARY_BUTTON} disabled={busy}>
              {busy ? 'Recording…' : 'Record incident'}
            </button>
          </>
        }
      >
        <SchoolField id="incident-severity" label="Severity" required>
          <select
            id="incident-severity"
            className={LH_INPUT}
            value={severity}
            onChange={(e) => setSeverity(e.target.value as ExamIncidentSeverity)}
          >
            {EXAM_INCIDENT_SEVERITIES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </SchoolField>
        <SchoolField
          id="incident-description"
          label="What was observed"
          required
          help="Write what happened, not what you concluded from it."
        >
          <textarea
            id="incident-description"
            className={LH_INPUT}
            rows={4}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="e.g. Candidate asked to leave the room at 10:20 and returned at 10:28, accompanied."
          />
        </SchoolField>
        <SchoolField
          id="incident-section"
          label="Section"
          help="Optional. Leave blank if this concerns the whole exam rather than one room."
        >
          <select
            id="incident-section"
            className={LH_INPUT}
            value={sectionId}
            onChange={(e) => setSectionId(e.target.value)}
          >
            <option value="">Whole exam</option>
            {(sittings.data ?? []).map((s) => (
              <option key={s.id} value={s.section_id}>
                {sectionName(s.section_id)}
                {s.room_number ? ` — ${s.room_number}` : ''}
              </option>
            ))}
          </select>
        </SchoolField>
        <SchoolField
          id="incident-student"
          label="Candidate"
          help="Optional. Leave blank unless the record is about one candidate."
        >
          <input
            id="incident-student"
            type="number"
            min={1}
            className={LH_INPUT}
            value={studentId}
            onChange={(e) => setStudentId(e.target.value)}
            placeholder="Student ID"
          />
        </SchoolField>
        <p className="flex items-start gap-2 text-xs text-gray-500">
          <ShieldAlert className="mt-0.5 size-3.5 shrink-0" />
          This is your record of events, not a finding. It is stored against your name and the time
          you wrote it.
        </p>
        {formError && <p className="text-sm text-red-600">{formError}</p>}
      </SchoolDialog>
    </DashPageShell>
  )
}
