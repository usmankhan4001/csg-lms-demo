'use client'

/**
 * First-run school setup.
 *
 * An organisation created through Learnhouse's own wizard has no campus, no
 * academic year and — the part that actually locks people out — no school
 * role for anyone, because `principal.roles` is built exclusively from
 * `SMSUserRole` rows. This screen is where that gets fixed.
 *
 * It renders a STATUS first rather than jumping straight to a form, because
 * the honest answer to "what is wrong with my school" is a list of what is
 * missing. A brand-new tenant shows "not set up yet" and names the four
 * pieces — never four reassuring zeros that read as "nothing to do".
 */

import { useCallback, useMemo, useState } from 'react'
import { Plus, School, Trash2 } from 'lucide-react'

import {
  EmptyState,
  LH_INPUT,
  LH_LABEL,
  LH_PRIMARY_BUTTON,
  LH_SECONDARY_BUTTON,
  SectionCard,
  StatusChip,
} from '@/components/widgets'
import { ApiError } from '@/lib/api/api-client'
import { useApiResource } from '@/lib/api/useApiResource'

import { getSchoolSetupStatus, runSchoolSetup } from '../api'
import type { SchoolSetupResponse, TermPayload } from '../types'

const MISSING_LABELS: Record<string, string> = {
  campus: 'A campus',
  academic_year: 'An academic year',
  academic_term: 'At least one term',
  school_admin: 'A school administrator',
}

interface TermDraft extends TermPayload {
  /** Stable key for React, so removing a row does not re-key the others. */
  key: string
}

function newTerm(index: number): TermDraft {
  return {
    key: `term-${Date.now()}-${index}`,
    name: '',
    term_code: '',
    weight_percentage: 50,
    start_date: '',
    end_date: '',
  }
}

export function SchoolSetupPanel({ orgId }: { orgId: number }) {
  const status = useApiResource(
    () => getSchoolSetupStatus(orgId),
    [orgId],
    // The payload is always a populated object, so the default "empty object"
    // heuristic would never fire — but say so explicitly rather than relying
    // on that. There is no empty state here: an unconfigured school is a
    // *result*, not an absence.
    { isEmpty: () => false }
  )

  const [campusName, setCampusName] = useState('')
  const [campusCode, setCampusCode] = useState('')
  const [timezone, setTimezone] = useState('Asia/Karachi')
  const [yearName, setYearName] = useState('')
  const [yearStart, setYearStart] = useState('')
  const [yearEnd, setYearEnd] = useState('')
  const [terms, setTerms] = useState<TermDraft[]>([newTerm(0), newTerm(1)])
  const [adminEmail, setAdminEmail] = useState('')
  const [adminFirst, setAdminFirst] = useState('')
  const [adminLast, setAdminLast] = useState('')
  const [emergencyNumber, setEmergencyNumber] = useState('')

  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<ApiError | Error | null>(null)
  const [result, setResult] = useState<SchoolSetupResponse | null>(null)

  const updateTerm = useCallback(
    (key: string, patch: Partial<TermPayload>) => {
      setTerms((rows) =>
        rows.map((r) => (r.key === key ? { ...r, ...patch } : r))
      )
    },
    []
  )

  const canSubmit = useMemo(() => {
    if (submitting) return false
    if (!campusName.trim() || !campusCode.trim() || !yearName.trim()) return false
    if (terms.length === 0) return false
    if (terms.some((t) => !t.name.trim())) return false
    // The founding admin is optional, but a half-filled one is not: an email
    // with no first name creates an account that shows as "Unnamed" on every
    // register and report card.
    if (adminEmail.trim() && !adminFirst.trim()) return false
    return true
  }, [submitting, campusName, campusCode, yearName, terms, adminEmail, adminFirst])

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    if (!canSubmit) return

    setSubmitting(true)
    setSubmitError(null)
    try {
      const response = await runSchoolSetup({
        org_id: orgId,
        campus_name: campusName.trim(),
        campus_code: campusCode.trim(),
        campus_timezone: timezone.trim() || 'UTC',
        academic_year_name: yearName.trim(),
        academic_year_start: yearStart || null,
        academic_year_end: yearEnd || null,
        terms: terms.map((t) => ({
          name: t.name.trim(),
          term_code: t.term_code?.trim() || null,
          weight_percentage: Number(t.weight_percentage) || 0,
          start_date: t.start_date || null,
          end_date: t.end_date || null,
        })),
        admin_email: adminEmail.trim() || null,
        admin_first_name: adminFirst.trim() || null,
        admin_last_name: adminLast.trim(),
        crisis_resources: emergencyNumber.trim()
          ? { emergency_number: emergencyNumber.trim() }
          : null,
        school_profile: null,
      })
      setResult(response)
      status.refetch()
    } catch (err) {
      setSubmitError(err instanceof Error ? err : new Error(String(err)))
    } finally {
      setSubmitting(false)
    }
  }

  // ---- Loading / error / offline / permission-denied ----------------------

  if (status.status === 'loading') {
    return <SectionCard title="School setup" state="loading" loadingRows={4} />
  }

  if (status.status === 'error') {
    const err = status.error
    if (err?.kind === 'permission_denied') {
      return (
        <SectionCard title="School setup">
          <EmptyState
            icon={School}
            title="You do not have access to this school's setup"
            description="Ask a super admin, or whoever created this organisation, to complete setup."
          />
        </SectionCard>
      )
    }
    if (err?.kind === 'network') {
      return (
        <SectionCard title="School setup">
          <EmptyState
            icon={School}
            tone="critical"
            title="You appear to be offline"
            description="Setup needs a connection so it can create the campus, year and administrator together."
            action={{ label: 'Try again', onClick: status.refetch }}
          />
        </SectionCard>
      )
    }
    return (
      <SectionCard
        title="School setup"
        state="error"
        error={err}
        onRetry={status.refetch}
      />
    )
  }

  const state = status.data

  // ---- Already set up -----------------------------------------------------

  if (state?.is_set_up && !result) {
    return (
      <SectionCard
        title="School setup"
        description="This school is configured."
        action={<StatusChip tone="positive" label="Set up" />}
      >
        <dl className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-4">
          <Stat label="Campuses" value={state.campus_count} />
          <Stat label="Academic years" value={state.academic_year_count} />
          <Stat label="Terms" value={state.term_count} />
          <Stat label="Administrators" value={state.school_admin_count} />
        </dl>
        <p className="mt-4 text-sm text-gray-500">
          Add further campuses, years and staff from the Settings, People and
          Roles tabs. Setup itself runs once.
        </p>
      </SectionCard>
    )
  }

  // ---- Success ------------------------------------------------------------

  if (result) {
    return (
      <SectionCard
        title="School setup"
        description="Your school is ready."
        action={<StatusChip tone="positive" label="Complete" />}
      >
        <ul className="flex flex-col gap-2 text-sm text-gray-700">
          <li>Campus and academic year created, with {result.term_ids.length} term{result.term_ids.length === 1 ? '' : 's'}.</li>
          {result.admin_user_id !== null && (
            <li>
              {result.admin_created
                ? 'The founding administrator account was created.'
                : 'An existing account was made a school administrator.'}{' '}
              No password was set — they choose their own.
            </li>
          )}
          {result.settings_failed.length > 0 && (
            <li className="text-amber-700">
              These defaults could not be saved and need setting manually:{' '}
              {result.settings_failed.join(', ')}. Your school is otherwise
              complete.
            </li>
          )}
        </ul>
      </SectionCard>
    )
  }

  // ---- Not set up: the form ----------------------------------------------

  const missing = state?.missing ?? []

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-6">
      <SectionCard
        title="This school is not set up yet"
        description="Until these exist, registers, timetables and report cards have nothing to attach to."
        action={<StatusChip tone="caution" label="Not set up" />}
      >
        <ul className="flex flex-col gap-1.5 text-sm text-gray-700">
          {missing.map((key) => (
            <li key={key}>{MISSING_LABELS[key] ?? key} is missing.</li>
          ))}
        </ul>
        {state?.may_run_setup === false && (
          <p className="mt-4 text-sm text-gray-500">
            You can see what is missing, but only a super admin or the owner of
            this organisation can complete setup.
          </p>
        )}
      </SectionCard>

      <fieldset disabled={state?.may_run_setup === false} className="contents">
        <SectionCard title="Campus" description="Where this school teaches. You can add more later.">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field id="setup-campus-name" label="Campus name" required>
              <input
                id="setup-campus-name"
                className={LH_INPUT}
                value={campusName}
                onChange={(e) => setCampusName(e.target.value)}
                placeholder="Lighthouse Main Campus"
              />
            </Field>
            <Field
              id="setup-campus-code"
              label="Campus code"
              required
              help="A short code shown on registers and report cards."
            >
              <input
                id="setup-campus-code"
                className={LH_INPUT}
                value={campusCode}
                onChange={(e) => setCampusCode(e.target.value)}
                placeholder="MAIN"
              />
            </Field>
            <Field id="setup-timezone" label="Time zone" help="Registers are timestamped in this zone.">
              <input
                id="setup-timezone"
                className={LH_INPUT}
                value={timezone}
                onChange={(e) => setTimezone(e.target.value)}
                placeholder="Asia/Karachi"
              />
            </Field>
          </div>
        </SectionCard>

        <SectionCard
          title="Academic year"
          description="Sections, enrolments and report cards are all scoped to a year, which is what makes rolling over to the next one possible."
        >
          <div className="grid gap-4 sm:grid-cols-3">
            <Field id="setup-year-name" label="Year name" required>
              <input
                id="setup-year-name"
                className={LH_INPUT}
                value={yearName}
                onChange={(e) => setYearName(e.target.value)}
                placeholder="2026-2027"
              />
            </Field>
            <Field id="setup-year-start" label="Starts">
              <input
                id="setup-year-start"
                type="date"
                className={LH_INPUT}
                value={yearStart}
                onChange={(e) => setYearStart(e.target.value)}
              />
            </Field>
            <Field id="setup-year-end" label="Ends">
              <input
                id="setup-year-end"
                type="date"
                className={LH_INPUT}
                value={yearEnd}
                onChange={(e) => setYearEnd(e.target.value)}
              />
            </Field>
          </div>
        </SectionCard>

        <SectionCard
          title="Terms"
          description="Report card weighting divides across these. Most schools use two."
          action={
            <button
              type="button"
              className={LH_SECONDARY_BUTTON}
              onClick={() => setTerms((rows) => [...rows, newTerm(rows.length)])}
            >
              <Plus className="h-4 w-4" /> Add term
            </button>
          }
        >
          <div className="flex flex-col gap-4">
            {terms.map((term, index) => (
              <div
                key={term.key}
                className="grid gap-3 rounded-lg border border-gray-200 p-4 sm:grid-cols-5"
              >
                <Field id={`setup-term-name-${term.key}`} label={`Term ${index + 1} name`} required>
                  <input
                    id={`setup-term-name-${term.key}`}
                    className={LH_INPUT}
                    value={term.name}
                    onChange={(e) => updateTerm(term.key, { name: e.target.value })}
                    placeholder="Term 1"
                  />
                </Field>
                <Field id={`setup-term-code-${term.key}`} label="Code">
                  <input
                    id={`setup-term-code-${term.key}`}
                    className={LH_INPUT}
                    value={term.term_code ?? ''}
                    onChange={(e) => updateTerm(term.key, { term_code: e.target.value })}
                    placeholder="T1"
                  />
                </Field>
                <Field id={`setup-term-weight-${term.key}`} label="Weight %">
                  <input
                    id={`setup-term-weight-${term.key}`}
                    type="number"
                    min={0}
                    max={100}
                    className={LH_INPUT}
                    value={term.weight_percentage}
                    onChange={(e) =>
                      updateTerm(term.key, {
                        weight_percentage: Number(e.target.value),
                      })
                    }
                  />
                </Field>
                <Field id={`setup-term-start-${term.key}`} label="Starts">
                  <input
                    id={`setup-term-start-${term.key}`}
                    type="date"
                    className={LH_INPUT}
                    value={term.start_date ?? ''}
                    onChange={(e) => updateTerm(term.key, { start_date: e.target.value })}
                  />
                </Field>
                <div className="flex items-end gap-2">
                  <Field id={`setup-term-end-${term.key}`} label="Ends">
                    <input
                      id={`setup-term-end-${term.key}`}
                      type="date"
                      className={LH_INPUT}
                      value={term.end_date ?? ''}
                      onChange={(e) => updateTerm(term.key, { end_date: e.target.value })}
                    />
                  </Field>
                  {terms.length > 1 && (
                    <button
                      type="button"
                      aria-label={`Remove term ${index + 1}`}
                      className="mb-1 rounded-md p-2 text-gray-400 hover:bg-gray-100 hover:text-rose-600"
                      onClick={() =>
                        setTerms((rows) => rows.filter((r) => r.key !== term.key))
                      }
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </SectionCard>

        <SectionCard
          title="Founding administrator"
          description="The first person who can run this school. No password is set here — they receive an invitation and choose their own."
        >
          <div className="grid gap-4 sm:grid-cols-3">
            <Field id="setup-admin-email" label="Email">
              <input
                id="setup-admin-email"
                type="email"
                className={LH_INPUT}
                value={adminEmail}
                onChange={(e) => setAdminEmail(e.target.value)}
                placeholder="head@school.example.com"
              />
            </Field>
            <Field
              id="setup-admin-first"
              label="First name"
              required={Boolean(adminEmail.trim())}
            >
              <input
                id="setup-admin-first"
                className={LH_INPUT}
                value={adminFirst}
                onChange={(e) => setAdminFirst(e.target.value)}
              />
            </Field>
            <Field id="setup-admin-last" label="Last name">
              <input
                id="setup-admin-last"
                className={LH_INPUT}
                value={adminLast}
                onChange={(e) => setAdminLast(e.target.value)}
              />
            </Field>
          </div>
        </SectionCard>

        <SectionCard
          title="Crisis support"
          description="Shown to a student who discloses self-harm. Left blank, the system tells them honestly that your school has not added its local numbers — it will never guess a helpline."
        >
          <div className="grid gap-4 sm:grid-cols-2">
            <Field
              id="setup-emergency"
              label="Local emergency number"
              help="You can add named helplines later under Settings."
            >
              <input
                id="setup-emergency"
                className={LH_INPUT}
                value={emergencyNumber}
                onChange={(e) => setEmergencyNumber(e.target.value)}
                placeholder="1122"
              />
            </Field>
          </div>
        </SectionCard>

        {submitError && (
          <div
            role="alert"
            className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800"
          >
            {submitError.message}
            <p className="mt-1 text-rose-700">
              Nothing was created — fix the above and submit again.
            </p>
          </div>
        )}

        <div className="flex items-center gap-3">
          <button type="submit" className={LH_PRIMARY_BUTTON} disabled={!canSubmit}>
            {submitting ? 'Setting up…' : 'Set up this school'}
          </button>
          <span className="text-sm text-gray-500">
            Everything above is created together, or not at all.
          </span>
        </div>
      </fieldset>
    </form>
  )
}

function Field({
  id,
  label,
  required,
  help,
  children,
}: {
  id: string
  label: string
  required?: boolean
  help?: string
  children: React.ReactNode
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className={LH_LABEL}>
        {label}
        {required && <span className="ml-0.5 text-rose-500">*</span>}
      </label>
      {children}
      {help && <p className="text-xs text-gray-500">{help}</p>}
    </div>
  )
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex flex-col">
      <dt className="text-xs uppercase tracking-wide text-gray-500">{label}</dt>
      <dd className="text-lg font-semibold tabular-nums text-gray-900">{value}</dd>
    </div>
  )
}
