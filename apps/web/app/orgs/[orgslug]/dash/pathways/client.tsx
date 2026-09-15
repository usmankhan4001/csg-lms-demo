'use client'

/**
 * Curricular pathways — the course bundles a student follows toward a
 * qualification.
 *
 * `/dash/pathways` has been linked from BOTH sidebars (DashLeftMenu.tsx:772,
 * DashMobileMenu.tsx:347) with no route behind it, so every click 404'd.
 *
 * Creating a pathway is `[SUPER_ADMIN, SCHOOL_ADMIN]`; enrolling a student is
 * `[SUPER_ADMIN, SCHOOL_ADMIN, TEACHER, STAFF]`. The screen is visible to
 * anyone the sidebar lets in (`canTeach`) and refuses honestly on write.
 */

import { useState } from 'react'
import { Compass } from 'lucide-react'

import {
  DashPageShell,
  DataTable,
  SchoolDialog,
  SchoolField,
  SectionCard,
  StatusChip,
  LH_INPUT,
  LH_PRIMARY_BUTTON,
  LH_SECONDARY_BUTTON,
  type DataTableColumn,
  type DataTableState,
} from '@/components/widgets'
import { useApiResource } from '@/lib/api/useApiResource'
import { ApiError } from '@/lib/api/api-client'
import { listSchoolPeople, type SchoolPerson } from '@/modules/sms/campus/api'
import { createPathway, enrollStudent, listPathways } from '@/modules/sms/pathways/api'
import type { CurricularPathway } from '@/modules/sms/pathways/types'

export default function PathwaysDashClient({
  org_id,
  orgslug,
}: {
  org_id: number
  orgslug: string
}) {
  void org_id
  void orgslug

  const [createOpen, setCreateOpen] = useState(false)
  const [enrollFor, setEnrollFor] = useState<CurricularPathway | null>(null)

  const pathways = useApiResource<CurricularPathway[]>(() => listPathways(), [])
  const rows = pathways.data ?? []

  const tableState: DataTableState =
    pathways.status === 'loading'
      ? 'loading'
      : pathways.status === 'error'
        ? 'error'
        : rows.length === 0
          ? 'empty'
          : 'success'

  const columns: DataTableColumn<CurricularPathway>[] = [
    {
      key: 'name',
      header: 'Pathway',
      render: (row) => (
        <div className="min-w-0">
          <div className="font-medium truncate">{row.name}</div>
          <div className="text-xs text-gray-500 truncate">{row.code}</div>
        </div>
      ),
    },
    {
      key: 'credits',
      header: 'Credits required',
      render: (row) => <span className="tabular-nums">{row.required_credits}</span>,
    },
    {
      key: 'courses',
      header: 'Courses',
      render: (row) =>
        row.courses.length > 0 ? (
          <span className="tabular-nums">{row.courses.length}</span>
        ) : (
          // An empty bundle is a half-built pathway, not a valid one -- a
          // student enrolled on it has nothing to study.
          <span className="text-xs text-amber-700">None added</span>
        ),
    },
    {
      key: 'active',
      header: 'Status',
      render: (row) =>
        row.is_active ? (
          <StatusChip label="Active" tone="positive" />
        ) : (
          <StatusChip label="Inactive" tone="neutral" />
        ),
    },
    {
      key: 'enroll',
      header: '',
      render: (row) => (
        <button
          type="button"
          className={LH_SECONDARY_BUTTON}
          onClick={() => setEnrollFor(row)}
        >
          Enrol student
        </button>
      ),
    },
  ]

  return (
    <DashPageShell
      title="Pathways"
      description="Course bundles a student follows toward a qualification."
      module="pathways"
      action={
        <button
          type="button"
          id="pathways-new"
          className={LH_PRIMARY_BUTTON}
          onClick={() => setCreateOpen(true)}
        >
          New pathway
        </button>
      }
    >
      <SectionCard
        title="Pathways"
        description={
          pathways.status === 'success' && rows.length > 0
            ? `${rows.length} defined`
            : undefined
        }
      >
        <DataTable<CurricularPathway>
          columns={columns}
          rows={rows}
          rowKey={(row) => row.id}
          state={tableState}
          error={pathways.error}
          onRetry={pathways.refetch}
          emptyIcon={Compass}
          emptyTitle="No pathways defined"
          emptyDescription="A pathway groups the courses a student must complete. Create one to start enrolling students onto it."
        />
      </SectionCard>

      <CreatePathwayDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onCreated={() => {
          setCreateOpen(false)
          pathways.refetch()
        }}
      />

      <EnrollDialog pathway={enrollFor} onClose={() => setEnrollFor(null)} />
    </DashPageShell>
  )
}

function CreatePathwayDialog({
  open,
  onOpenChange,
  onCreated,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onCreated: () => void
}) {
  const [name, setName] = useState('')
  const [code, setCode] = useState('')
  const [description, setDescription] = useState('')
  const [credits, setCredits] = useState('30')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      await createPathway({
        name: name.trim(),
        code: code.trim(),
        description: description.trim() || undefined,
        required_credits: Number(credits) || 0,
      })
      setName('')
      setCode('')
      setDescription('')
      onCreated()
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.kind === 'permission_denied'
            ? 'Creating a pathway is restricted to school administrators.'
            : err.message
          : 'Could not create this pathway.'
      )
    } finally {
      setSaving(false)
    }
  }

  return (
    <SchoolDialog
      open={open}
      onOpenChange={onOpenChange}
      title="New pathway"
      description="Courses are attached to the pathway after it exists."
      onSubmit={submit}
      footer={
        <>
          <button
            type="button"
            id="pathways-create-cancel"
            className={LH_SECONDARY_BUTTON}
            onClick={() => onOpenChange(false)}
          >
            Cancel
          </button>
          <button
            type="submit"
            id="pathways-create-submit"
            className={LH_PRIMARY_BUTTON}
            disabled={saving || !name.trim() || !code.trim()}
          >
            {saving ? 'Creating…' : 'Create pathway'}
          </button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <SchoolField id="pathway-name" label="Name" required>
          <input
            id="pathway-name"
            className={LH_INPUT}
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Pre-Medical Sciences"
          />
        </SchoolField>

        <SchoolField id="pathway-code" label="Code" required>
          <input
            id="pathway-code"
            className={LH_INPUT}
            value={code}
            onChange={(e) => setCode(e.target.value)}
            placeholder="PMS"
          />
        </SchoolField>

        <SchoolField id="pathway-description" label="Description">
          <input
            id="pathway-description"
            className={LH_INPUT}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </SchoolField>

        <SchoolField
          id="pathway-credits"
          label="Credits required"
          help="Used to describe the pathway. Credit COMPLETION is not tracked by this system."
        >
          <input
            id="pathway-credits"
            type="number"
            min={0}
            className={LH_INPUT}
            value={credits}
            onChange={(e) => setCredits(e.target.value)}
          />
        </SchoolField>

        {error ? <p className="text-sm text-red-600">{error}</p> : null}
      </div>
    </SchoolDialog>
  )
}

function EnrollDialog({
  pathway,
  onClose,
}: {
  pathway: CurricularPathway | null
  onClose: () => void
}) {
  const [studentId, setStudentId] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState(false)

  const students = useApiResource<SchoolPerson[]>(() => listSchoolPeople('STUDENT'), [])

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!pathway) return
    setSaving(true)
    setError(null)
    setDone(false)
    try {
      await enrollStudent({ student_id: Number(studentId), pathway_id: pathway.id })
      setDone(true)
      setStudentId('')
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.kind === 'permission_denied'
            ? 'Your role cannot enrol students onto a pathway.'
            : err.message
          : 'Could not enrol this student.'
      )
    } finally {
      setSaving(false)
    }
  }

  return (
    <SchoolDialog
      open={pathway !== null}
      onOpenChange={(open) => {
        if (!open) {
          setDone(false)
          onClose()
        }
      }}
      title={pathway ? `Enrol onto ${pathway.name}` : 'Enrol student'}
      description="Records the enrolment. Progress toward the credit total is not tracked."
      onSubmit={submit}
      footer={
        <>
          <button
            type="button"
            id="pathways-enroll-cancel"
            className={LH_SECONDARY_BUTTON}
            onClick={onClose}
          >
            Close
          </button>
          <button
            type="submit"
            id="pathways-enroll-submit"
            className={LH_PRIMARY_BUTTON}
            disabled={saving || !studentId}
          >
            {saving ? 'Enrolling…' : 'Enrol student'}
          </button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <SchoolField id="enroll-student" label="Student" required>
          <select
            id="enroll-student"
            className={LH_INPUT}
            value={studentId}
            onChange={(e) => setStudentId(e.target.value)}
            disabled={students.status === 'loading' || students.status === 'error'}
          >
            <option value="">
              {students.status === 'loading' ? 'Loading students…' : 'Choose a student…'}
            </option>
            {(students.data ?? []).map((p) => (
              <option key={p.user_id} value={p.user_id}>
                {p.name ?? `Student #${p.user_id}`}
              </option>
            ))}
          </select>
        </SchoolField>

        {pathway && pathway.courses.length === 0 ? (
          <p className="text-sm text-amber-700">
            This pathway has no courses attached yet, so an enrolled student will have
            nothing to study on it.
          </p>
        ) : null}

        {done ? <p className="text-sm text-emerald-700">Student enrolled.</p> : null}
        {error ? <p className="text-sm text-red-600">{error}</p> : null}
      </div>
    </SchoolDialog>
  )
}
