'use client'

/**
 * Issued certificates, issuing, and the public verification check.
 *
 * THERE IS NO REVOKE ENDPOINT. `is_revoked` is readable on every issued
 * certificate but no route sets it (`sms_certificates.py` has five routes and
 * none of them revoke, and `CertificateService` has no revoke method). So this
 * screen SHOWS revocation state and offers no control to change it. A sibling
 * lane built a Suspensions tab, found the same write-only asymmetry in reverse,
 * and removed it; the principle is the same — a control that cannot work is
 * worse than no control, because the user cannot tell whether it failed.
 *
 * The verification panel calls the PUBLIC endpoint — the same request an
 * employer or university makes with a code from a printed certificate. It is
 * here so staff can confirm what an outside party actually sees rather than
 * assuming the chain works.
 */

import { useState } from 'react'
import { BadgeCheck, ScrollText, ShieldQuestion } from 'lucide-react'

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
import {
  issueCertificate,
  listIssuedCertificates,
  listTemplates,
  verifyCertificate,
} from '@/modules/sms/certificates/api'
import type {
  CertificateTemplate,
  IssuedCertificate,
  PublicCertificateVerification,
} from '@/modules/sms/certificates/types'

export default function IssuedCertificatesClient({
  org_id,
  orgslug,
}: {
  org_id: number
  orgslug: string
}) {
  void org_id
  void orgslug

  const [issueOpen, setIssueOpen] = useState(false)

  const issued = useApiResource<IssuedCertificate[]>(() => listIssuedCertificates(), [])
  const templates = useApiResource<CertificateTemplate[]>(() => listTemplates(), [])
  const rows = issued.data ?? []

  const tableState: DataTableState =
    issued.status === 'loading'
      ? 'loading'
      : issued.status === 'error'
        ? 'error'
        : rows.length === 0
          ? 'empty'
          : 'success'

  const columns: DataTableColumn<IssuedCertificate>[] = [
    {
      key: 'recipient',
      header: 'Recipient',
      render: (row) => (
        <div className="min-w-0">
          <div className="font-medium truncate">{row.recipient_name}</div>
          <div className="text-xs text-gray-500 truncate">{row.title}</div>
        </div>
      ),
    },
    {
      key: 'issued',
      header: 'Issued',
      render: (row) => <span className="tabular-nums">{row.issue_date}</span>,
    },
    {
      key: 'honors',
      header: 'Honours',
      render: (row) =>
        row.honors ? (
          <StatusChip label={row.honors} tone="positive" />
        ) : (
          <span className="text-xs text-gray-500">—</span>
        ),
    },
    {
      key: 'pdf',
      header: 'PDF',
      render: (row) =>
        row.pdf_storage_url ? (
          <a
            href={row.pdf_storage_url}
            target="_blank"
            rel="noreferrer"
            className="text-sm underline"
          >
            Open
          </a>
        ) : (
          // Nullable in the schema: a row can exist before its PDF is produced.
          // Saying so beats rendering a dead link.
          <span className="text-xs text-gray-500">Not generated</span>
        ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (row) =>
        row.is_revoked ? (
          <StatusChip label="Revoked" tone="critical" />
        ) : (
          <StatusChip label="Valid" tone="positive" />
        ),
    },
  ]

  return (
    <DashPageShell
      title="Issued certificates"
      description="Every certificate this school has issued, and the code a third party verifies it with."
      module="certificates"
      action={
        <button
          type="button"
          id="certificates-issue"
          className={LH_PRIMARY_BUTTON}
          onClick={() => setIssueOpen(true)}
          disabled={(templates.data ?? []).length === 0}
          title={
            (templates.data ?? []).length === 0
              ? 'Create a template before issuing a certificate'
              : undefined
          }
        >
          Issue certificate
        </button>
      }
    >
      <SectionCard
        title="Issued"
        description={
          issued.status === 'success' && rows.length > 0 ? `${rows.length} issued` : undefined
        }
      >
        <DataTable<IssuedCertificate>
          columns={columns}
          rows={rows}
          rowKey={(row) => row.id}
          state={tableState}
          error={issued.error}
          onRetry={issued.refetch}
          emptyIcon={ScrollText}
          emptyTitle="No certificates issued"
          emptyDescription="Nothing has been issued yet. Certificates appear here once staff award them from a template."
        />
      </SectionCard>

      <VerifyPanel />

      <IssueDialog
        open={issueOpen}
        onOpenChange={setIssueOpen}
        templates={templates.data ?? []}
        onIssued={() => {
          setIssueOpen(false)
          issued.refetch()
        }}
      />
    </DashPageShell>
  )
}

/**
 * Deliberately not wired to `useApiResource`: this is a one-shot lookup driven
 * by a button, and a 404 ("no such certificate") is a legitimate ANSWER rather
 * than an error state to retry.
 */
function VerifyPanel() {
  const [code, setCode] = useState('')
  const [checking, setChecking] = useState(false)
  const [result, setResult] = useState<PublicCertificateVerification | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  async function check() {
    setChecking(true)
    setResult(null)
    setMessage(null)
    try {
      setResult(await verifyCertificate(code.trim()))
    } catch (err) {
      setMessage(
        err instanceof ApiError && err.kind === 'not_found'
          ? 'No certificate matches that code. This is what an outside party would see.'
          : err instanceof ApiError
            ? err.message
            : 'Could not check that code.'
      )
    } finally {
      setChecking(false)
    }
  }

  return (
    <SectionCard
      title="Verify a code"
      description="Runs the same public check an employer or university would. Nothing here is recorded."
    >
      <div className="flex flex-col gap-3">
        <div className="flex flex-wrap items-end gap-2">
          <div className="min-w-[16rem] flex-1">
            <label className="sr-only" htmlFor="certificates-verify-code">
              Verification code
            </label>
            <input
              id="certificates-verify-code"
              className={LH_INPUT}
              value={code}
              onChange={(e) => setCode(e.target.value)}
              placeholder="Paste the code printed on the certificate"
            />
          </div>
          <button
            type="button"
            id="certificates-verify-submit"
            className={LH_SECONDARY_BUTTON}
            onClick={check}
            disabled={checking || !code.trim()}
          >
            {checking ? 'Checking…' : 'Check'}
          </button>
        </div>

        {result ? (
          <div className="rounded-md border border-gray-200 p-3 text-sm">
            <p className="mb-2 flex items-center gap-2 font-medium">
              {result.is_revoked ? (
                <>
                  <ShieldQuestion className="size-4 text-red-600" />
                  Revoked certificate
                </>
              ) : result.is_valid ? (
                <>
                  <BadgeCheck className="size-4 text-emerald-600" />
                  Valid certificate
                </>
              ) : (
                <>
                  <ShieldQuestion className="size-4 text-amber-600" />
                  Not valid
                </>
              )}
            </p>
            <dl className="grid grid-cols-2 gap-2">
              <div>
                <dt className="text-gray-500">Recipient</dt>
                <dd>{result.recipient_name}</dd>
              </div>
              <div>
                <dt className="text-gray-500">Award</dt>
                <dd>{result.title}</dd>
              </div>
              <div>
                <dt className="text-gray-500">Issued</dt>
                <dd className="tabular-nums">{result.issue_date}</dd>
              </div>
              <div>
                <dt className="text-gray-500">Signed by</dt>
                <dd>
                  {result.issuer_name} — {result.issuer_title}
                </dd>
              </div>
            </dl>
            {result.is_revoked && result.revocation_reason ? (
              <p className="mt-2 text-red-700">{result.revocation_reason}</p>
            ) : null}
          </div>
        ) : null}

        {message ? <p className="text-sm text-gray-600">{message}</p> : null}
      </div>
    </SectionCard>
  )
}

function IssueDialog({
  open,
  onOpenChange,
  templates,
  onIssued,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  templates: CertificateTemplate[]
  onIssued: () => void
}) {
  const [templateId, setTemplateId] = useState('')
  const [studentId, setStudentId] = useState('')
  const [title, setTitle] = useState('')
  const [honors, setHonors] = useState('')
  const [issueDate, setIssueDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const students = useApiResource<SchoolPerson[]>(() => listSchoolPeople('STUDENT'), [])
  const chosen = (students.data ?? []).find((p) => String(p.user_id) === studentId)

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!chosen) return
    setSaving(true)
    setError(null)
    try {
      await issueCertificate({
        template_id: Number(templateId),
        student_id: chosen.user_id,
        // The name printed on the certificate comes from the picked student,
        // not a free-text box, so a typo cannot produce a certificate in a
        // name the school has no record of.
        recipient_name: chosen.name ?? `Student #${chosen.user_id}`,
        recipient_email: chosen.email ?? undefined,
        title: title.trim(),
        honors: honors.trim() || undefined,
        issue_date: issueDate,
      })
      setTitle('')
      setHonors('')
      onIssued()
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.kind === 'permission_denied'
            ? 'Your role cannot issue certificates.'
            : err.message
          : 'Could not issue this certificate.'
      )
    } finally {
      setSaving(false)
    }
  }

  return (
    <SchoolDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Issue a certificate"
      description="Issued certificates carry a verification code and cannot be revoked from here."
      onSubmit={submit}
      footer={
        <>
          <button
            type="button"
            id="certificates-issue-cancel"
            className={LH_SECONDARY_BUTTON}
            onClick={() => onOpenChange(false)}
          >
            Cancel
          </button>
          <button
            type="submit"
            id="certificates-issue-submit"
            className={LH_PRIMARY_BUTTON}
            disabled={saving || !templateId || !chosen || !title.trim()}
          >
            {saving ? 'Issuing…' : 'Issue certificate'}
          </button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <SchoolField id="issue-template" label="Template" required>
          <select
            id="issue-template"
            className={LH_INPUT}
            value={templateId}
            onChange={(e) => setTemplateId(e.target.value)}
          >
            <option value="">Choose a template…</option>
            {templates.map((t) => (
              <option key={t.id} value={t.id}>
                {t.title}
              </option>
            ))}
          </select>
        </SchoolField>

        <SchoolField
          id="issue-student"
          label="Student"
          required
          help="The printed name comes from this record, not from typing."
        >
          <select
            id="issue-student"
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

        <SchoolField id="issue-title" label="Award title" required>
          <input
            id="issue-title"
            className={LH_INPUT}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Outstanding Achievement in Mathematics"
          />
        </SchoolField>

        <SchoolField id="issue-honors" label="Honours">
          <input
            id="issue-honors"
            className={LH_INPUT}
            value={honors}
            onChange={(e) => setHonors(e.target.value)}
            placeholder="With Distinction"
          />
        </SchoolField>

        <SchoolField id="issue-date" label="Issue date" required>
          <input
            id="issue-date"
            type="date"
            className={LH_INPUT}
            value={issueDate}
            onChange={(e) => setIssueDate(e.target.value)}
          />
        </SchoolField>

        {error ? <p className="text-sm text-red-600">{error}</p> : null}
      </div>
    </SchoolDialog>
  )
}
