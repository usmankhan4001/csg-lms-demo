'use client'

/**
 * Alumni register.
 *
 * WHY THIS ROUTE EXISTS AT ALL: both sidebars have linked `/dash/alumni`
 * (DashLeftMenu.tsx:684, DashMobileMenu.tsx) while the route directory did
 * not exist, so every administrator who clicked Alumni got a 404. A linked
 * route that 404s reads as a broken product, which is worse than an absent
 * feature.
 *
 * WHAT THE API LIMITS US TO -- all three endpoints, no more:
 *   GET  /profiles    list, filterable by year / industry / mentor
 *   POST /profiles    staff-only create
 *   POST /milestones  staff-only, read back nested on GET /profiles
 *
 * There is NO PATCH and NO DELETE, so this screen offers no edit or remove
 * affordance. A button that 404s is worse than a button that is absent.
 */

import { useMemo, useState } from 'react'
import { GraduationCap, Trophy } from 'lucide-react'

import {
  DashPageShell,
  DataTable,
  SchoolDialog,
  SchoolField,
  SectionCard,
  StatusChip,
  LH_INPUT,
  LH_LABEL,
  LH_PRIMARY_BUTTON,
  LH_SECONDARY_BUTTON,
  type DataTableColumn,
  type DataTableState,
} from '@/components/widgets'
import { useApiResource } from '@/lib/api/useApiResource'
import {
  addAlumniMilestone,
  createAlumniProfile,
  listAlumniProfiles,
} from '@/modules/sms/alumni/api'
import type { AlumniProfile } from '@/modules/sms/alumni/types'
import { useSchoolSession } from '@/lib/api/useSchoolSession'

/** Roles the API accepts on POST /profiles and POST /milestones. */
const WRITE_ROLES = ['SUPER_ADMIN', 'SCHOOL_ADMIN', 'STAFF']

export default function AlumniDashClient({
  org_id,
  orgslug,
}: {
  org_id: number
  orgslug: string
}) {
  void org_id
  void orgslug

  const { session } = useSchoolSession()
  const canWrite = (session?.roles ?? []).some((r) => WRITE_ROLES.includes(r))

  const [graduationYear, setGraduationYear] = useState<string>('')
  const [industry, setIndustry] = useState<string>('')
  const [mentorOnly, setMentorOnly] = useState(false)
  const [addOpen, setAddOpen] = useState(false)
  const [milestoneFor, setMilestoneFor] = useState<AlumniProfile | null>(null)

  const parsedYear = graduationYear.trim() === '' ? undefined : Number(graduationYear)
  const yearIsValid = parsedYear === undefined || Number.isFinite(parsedYear)

  const alumni = useApiResource<AlumniProfile[]>(
    () =>
      listAlumniProfiles({
        graduation_year: yearIsValid ? parsedYear : undefined,
        industry: industry.trim() || undefined,
        willing_to_mentor: mentorOnly ? true : undefined,
      }),
    [parsedYear, industry, mentorOnly, yearIsValid]
  )

  const rows = alumni.data ?? []
  const filtered = graduationYear.trim() !== '' || industry.trim() !== '' || mentorOnly

  // Describes the ROWS ON SCREEN, never the school. With a filter applied,
  // "4 open to mentoring" would otherwise read as the school's total.
  const mentorsOnScreen = useMemo(
    () => rows.filter((r) => r.willing_to_mentor).length,
    [rows]
  )

  const tableState: DataTableState =
    alumni.status === 'loading'
      ? 'loading'
      : alumni.status === 'error'
        ? 'error'
        : rows.length === 0
          ? 'empty'
          : 'success'

  const columns: DataTableColumn<AlumniProfile>[] = [
    {
      key: 'user',
      header: 'Alumnus',
      // The API returns only user_id -- there is no name field on
      // AlumniProfileRead -- so this cannot show a person's name without a
      // second lookup the endpoint does not offer. Showing the reference
      // honestly beats inventing a label.
      render: (row) => <span className="tabular-nums">User #{row.user_id}</span>,
    },
    {
      key: 'graduated',
      header: 'Graduated',
      render: (row) => <span className="tabular-nums">{row.graduation_year}</span>,
    },
    {
      key: 'award',
      header: 'Award',
      render: (row) => <span>{row.degree_or_diploma}</span>,
    },
    {
      key: 'now',
      header: 'Now',
      render: (row) => {
        const bits = [row.job_title, row.current_company].filter(Boolean)
        if (bits.length === 0) {
          return <span className="text-neutral-400">Not recorded</span>
        }
        return <span>{bits.join(' · ')}</span>
      },
    },
    {
      key: 'industry',
      header: 'Industry',
      render: (row) =>
        row.industry ? (
          <span>{row.industry}</span>
        ) : (
          <span className="text-neutral-400">Not recorded</span>
        ),
    },
    {
      key: 'mentor',
      header: 'Mentoring',
      render: (row) =>
        row.willing_to_mentor ? (
          <StatusChip tone="positive" label="Open to mentoring" />
        ) : (
          <span className="text-neutral-400">Not offered</span>
        ),
    },
    {
      key: 'milestones',
      header: 'Milestones',
      render: (row) =>
        row.milestones.length === 0 ? (
          <span className="text-neutral-400">None recorded</span>
        ) : (
          <span className="tabular-nums">{row.milestones.length}</span>
        ),
    },
    {
      key: 'actions',
      header: '',
      render: (row) => (
        <button
          type="button"
          id={`alumni-open-${row.id}`}
          className={LH_SECONDARY_BUTTON}
          onClick={() => setMilestoneFor(row)}
        >
          {canWrite ? 'Milestones' : 'View milestones'}
        </button>
      ),
    },
  ]

  return (
    <DashPageShell
      title="Alumni"
      description="Former students, where they went, and who is open to mentoring."
      module="alumni"
      action={
        canWrite ? (
          <button
            type="button"
            id="alumni-add-profile"
            className={LH_PRIMARY_BUTTON}
            onClick={() => setAddOpen(true)}
          >
            Add alumnus
          </button>
        ) : undefined
      }
    >
      <SectionCard
        title="Register"
        description={
          alumni.status === 'success' && rows.length > 0
            ? `${rows.length} shown · ${mentorsOnScreen} open to mentoring`
            : undefined
        }
        action={
          <div className="flex flex-wrap items-center gap-2">
            <label className="sr-only" htmlFor="alumni-filter-year">
              Filter by graduation year
            </label>
            <input
              id="alumni-filter-year"
              className={LH_INPUT}
              inputMode="numeric"
              placeholder="Year"
              value={graduationYear}
              onChange={(e) => setGraduationYear(e.target.value)}
            />

            <label className="sr-only" htmlFor="alumni-filter-industry">
              Filter by industry
            </label>
            <input
              id="alumni-filter-industry"
              className={LH_INPUT}
              placeholder="Industry"
              value={industry}
              onChange={(e) => setIndustry(e.target.value)}
            />

            <label className="flex items-center gap-2 text-sm text-neutral-600">
              <input
                id="alumni-filter-mentor"
                type="checkbox"
                checked={mentorOnly}
                onChange={(e) => setMentorOnly(e.target.checked)}
              />
              Mentors only
            </label>
          </div>
        }
      >
        {!yearIsValid && (
          <p className="mb-3 text-sm text-amber-700">
            &ldquo;{graduationYear}&rdquo; is not a year, so the year filter is being
            ignored.
          </p>
        )}

        <DataTable<AlumniProfile>
          columns={columns}
          rows={rows}
          rowKey={(row) => row.id}
          state={tableState}
          error={alumni.error}
          onRetry={alumni.refetch}
          emptyIcon={GraduationCap}
          emptyTitle={filtered ? 'No alumni match this filter' : 'No alumni recorded yet'}
          // NOT "0 alumni". A school that has never filled in this register has
          // no alumni RECORD -- it certainly has former students.
          emptyDescription={
            filtered
              ? 'Clear the filters to see the whole register.'
              : 'Nobody has been added to the register yet. That is not the same as the school having no former students — they appear here once staff record them.'
          }
        />
      </SectionCard>

      <AddAlumnusDialog
        open={addOpen}
        onOpenChange={setAddOpen}
        onCreated={() => {
          setAddOpen(false)
          alumni.refetch()
        }}
      />

      <MilestonesDialog
        profile={milestoneFor}
        canWrite={canWrite}
        onOpenChange={(open) => {
          if (!open) setMilestoneFor(null)
        }}
        onAdded={() => {
          setMilestoneFor(null)
          alumni.refetch()
        }}
      />
    </DashPageShell>
  )
}

/** Staff-only. Mirrors AlumniProfileCreate exactly; no field the API ignores. */
function AddAlumnusDialog({
  open,
  onOpenChange,
  onCreated,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onCreated: () => void
}) {
  const [userId, setUserId] = useState('')
  const [graduationYear, setGraduationYear] = useState('')
  const [degree, setDegree] = useState('')
  const [company, setCompany] = useState('')
  const [jobTitle, setJobTitle] = useState('')
  const [industry, setIndustry] = useState('')
  const [linkedin, setLinkedin] = useState('')
  const [willingToMentor, setWillingToMentor] = useState(false)
  const [mentorshipTopics, setMentorshipTopics] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setError(null)

    const uid = Number(userId)
    const year = Number(graduationYear)
    if (!Number.isFinite(uid) || uid <= 0) {
      setError('A numeric user id is required — it links the record to a real account.')
      return
    }
    if (!Number.isFinite(year)) {
      setError('Graduation year must be a number.')
      return
    }

    setSubmitting(true)
    try {
      await createAlumniProfile({
        user_id: uid,
        graduation_year: year,
        degree_or_diploma: degree.trim(),
        current_company: company.trim() || null,
        job_title: jobTitle.trim() || null,
        industry: industry.trim() || null,
        linkedin_url: linkedin.trim() || null,
        willing_to_mentor: willingToMentor,
        mentorship_topics: mentorshipTopics.trim() || null,
      })
      onCreated()
    } catch (err) {
      // The API answers 409 when a profile already exists for this user.
      setError(err instanceof Error ? err.message : 'Could not add this alumnus.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <SchoolDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Add alumnus"
      description="Records a former student. This cannot be edited afterwards — the API has no update endpoint — so check the details before saving."
      onSubmit={submit}
      footer={
        <div className="flex items-center justify-end gap-2">
          <button
            type="button"
            id="alumni-add-cancel"
            className={LH_SECONDARY_BUTTON}
            onClick={() => onOpenChange(false)}
          >
            Cancel
          </button>
          <button
            type="submit"
            id="alumni-add-submit"
            className={LH_PRIMARY_BUTTON}
            disabled={submitting}
          >
            {submitting ? 'Saving…' : 'Add alumnus'}
          </button>
        </div>
      }
    >
      {error && <p className="mb-3 text-sm text-red-600">{error}</p>}

      <div className="grid gap-3 sm:grid-cols-2">
        <SchoolField
          id="alumni-user-id"
          label="User id"
          required
          help="The account this record belongs to."
        >
          <input
            id="alumni-user-id"
            className={LH_INPUT}
            inputMode="numeric"
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
            required
          />
        </SchoolField>

        <SchoolField id="alumni-grad-year" label="Graduation year" required>
          <input
            id="alumni-grad-year"
            className={LH_INPUT}
            inputMode="numeric"
            value={graduationYear}
            onChange={(e) => setGraduationYear(e.target.value)}
            required
          />
        </SchoolField>
      </div>

      <SchoolField id="alumni-degree" label="Degree or diploma" required>
        <input
          id="alumni-degree"
          className={LH_INPUT}
          value={degree}
          onChange={(e) => setDegree(e.target.value)}
          required
        />
      </SchoolField>

      <div className="grid gap-3 sm:grid-cols-2">
        <SchoolField id="alumni-job-title" label="Job title">
          <input
            id="alumni-job-title"
            className={LH_INPUT}
            value={jobTitle}
            onChange={(e) => setJobTitle(e.target.value)}
          />
        </SchoolField>

        <SchoolField id="alumni-company" label="Company">
          <input
            id="alumni-company"
            className={LH_INPUT}
            value={company}
            onChange={(e) => setCompany(e.target.value)}
          />
        </SchoolField>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <SchoolField id="alumni-industry" label="Industry">
          <input
            id="alumni-industry"
            className={LH_INPUT}
            value={industry}
            onChange={(e) => setIndustry(e.target.value)}
          />
        </SchoolField>

        <SchoolField id="alumni-linkedin" label="LinkedIn URL">
          <input
            id="alumni-linkedin"
            className={LH_INPUT}
            value={linkedin}
            onChange={(e) => setLinkedin(e.target.value)}
          />
        </SchoolField>
      </div>

      <div className="mt-1">
        <label className={LH_LABEL} htmlFor="alumni-mentor">
          <span className="flex items-center gap-2">
            <input
              id="alumni-mentor"
              type="checkbox"
              checked={willingToMentor}
              onChange={(e) => setWillingToMentor(e.target.checked)}
            />
            Open to mentoring current students
          </span>
        </label>
      </div>

      {willingToMentor && (
        <SchoolField
          id="alumni-mentor-topics"
          label="Mentoring topics"
          help="What they are happy to be asked about."
        >
          <input
            id="alumni-mentor-topics"
            className={LH_INPUT}
            value={mentorshipTopics}
            onChange={(e) => setMentorshipTopics(e.target.value)}
          />
        </SchoolField>
      )}
    </SchoolDialog>
  )
}

/**
 * Shows the milestones already recorded against one alumnus, and (for staff)
 * lets another be added. Both halves matter: POST /milestones would otherwise
 * be a write nobody can read back from this screen.
 */
function MilestonesDialog({
  profile,
  canWrite,
  onOpenChange,
  onAdded,
}: {
  profile: AlumniProfile | null
  canWrite: boolean
  onOpenChange: (open: boolean) => void
  onAdded: () => void
}) {
  const [title, setTitle] = useState('')
  const [date, setDate] = useState('')
  const [description, setDescription] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!profile) return
    setError(null)
    setSubmitting(true)
    try {
      await addAlumniMilestone({
        alumni_id: profile.id,
        title: title.trim(),
        description: description.trim() || null,
        milestone_date: date,
      })
      setTitle('')
      setDate('')
      setDescription('')
      onAdded()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not add this milestone.')
    } finally {
      setSubmitting(false)
    }
  }

  const milestones = profile?.milestones ?? []

  return (
    <SchoolDialog
      open={profile !== null}
      onOpenChange={onOpenChange}
      title={profile ? `Milestones — User #${profile.user_id}` : 'Milestones'}
      description={
        profile
          ? `${profile.degree_or_diploma}, ${profile.graduation_year}`
          : undefined
      }
      onSubmit={canWrite ? submit : undefined}
      footer={
        <div className="flex items-center justify-end gap-2">
          <button
            type="button"
            id="alumni-milestone-close"
            className={LH_SECONDARY_BUTTON}
            onClick={() => onOpenChange(false)}
          >
            Close
          </button>
          {canWrite && (
            <button
              type="submit"
              id="alumni-milestone-submit"
              className={LH_PRIMARY_BUTTON}
              disabled={submitting}
            >
              {submitting ? 'Saving…' : 'Add milestone'}
            </button>
          )}
        </div>
      }
    >
      {milestones.length === 0 ? (
        <p className="mb-4 flex items-center gap-2 text-sm text-neutral-500">
          <Trophy className="size-4" aria-hidden />
          {/* Not "0 milestones" -- nothing recorded, which is not the same as
              nothing achieved. */}
          Nothing recorded for this alumnus yet.
        </p>
      ) : (
        <ul className="mb-4 space-y-2">
          {milestones.map((m) => (
            <li key={m.id} className="rounded-md border border-neutral-200 p-3">
              <div className="flex items-baseline justify-between gap-3">
                <span className="font-medium">{m.title}</span>
                <span className="tabular-nums text-xs text-neutral-500">
                  {m.milestone_date}
                </span>
              </div>
              {m.description && (
                <p className="mt-1 text-sm text-neutral-600">{m.description}</p>
              )}
            </li>
          ))}
        </ul>
      )}

      {canWrite && (
        <>
          {error && <p className="mb-3 text-sm text-red-600">{error}</p>}

          <SchoolField id="alumni-milestone-title" label="Milestone" required>
            <input
              id="alumni-milestone-title"
              className={LH_INPUT}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
            />
          </SchoolField>

          <SchoolField
            id="alumni-milestone-date"
            label="Date"
            required
            help="When it happened."
          >
            <input
              id="alumni-milestone-date"
              className={LH_INPUT}
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              required
            />
          </SchoolField>

          <SchoolField id="alumni-milestone-description" label="Detail">
            <input
              id="alumni-milestone-description"
              className={LH_INPUT}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </SchoolField>
        </>
      )}
    </SchoolDialog>
  )
}
