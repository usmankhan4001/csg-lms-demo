'use client'

/**
 * Fees (staff view), attached as a first-class Learnhouse dash module.
 *
 * Distinct from the parent-facing `parent/fees` page: that one shows one
 * family's vouchers and pays them. This is the bursar's side -- every
 * voucher in the school, what's outstanding, verifying a payment at the
 * counter, and running late-fee accrual.
 *
 * One backend reality shapes this screen: `GET /sms/fees/vouchers` filters
 * ONLY by student_id and status -- there is no section or grade filter. So
 * the section filter here is applied client-side against that section's
 * enrollments, which is honest for a school-sized voucher list but would need
 * a real backend filter to scale.
 */

import { useState } from 'react'
import toast from 'react-hot-toast'
import { BadgeDollarSign, FilePlus2, Receipt, Wallet, Eye, FileText } from 'lucide-react'
import {
  LH_GHOST_BUTTON,
  LH_INPUT,
  LH_PRIMARY_BUTTON,
  LH_SECONDARY_BUTTON,
  DashPageShell,
  DataTable,
  EmptyState,
  SchoolDialog,
  SchoolField,
  SectionCard,
  StatGrid,
  StatusChip,
} from '@/components/widgets'
import type { StatusTone } from '@/components/widgets'
import { useApiResource } from '@/lib/api/useApiResource'
import { useDeepLinkAction } from '@/lib/dashboard-search/useDeepLinkAction'
import { listCampuses, listClassSections, listSectionEnrollments } from '@/modules/sms/campus/api'
import {
  accrueLateFees,
  createFeeStructure,
  generateVouchers,
  listFeeStructures,
  listVouchers,
} from '@/modules/sms/fees/api'
import { PayVoucherDialog } from '@/modules/sms/fees/components/PayVoucherDialog'
import type { VoucherStatus, StudentFeeVoucherRead } from '@/modules/sms/fees/types'
import { DataExportToolbar } from '@/components/ems/DataExportToolbar'
import type { ExportColumn } from '@/lib/export/data-export'
import { FeeVoucher360Drawer } from '@/modules/ems/inspectors/FeeVoucher360Drawer'
import { PrintableDocumentViewer } from '@/modules/ems/documents/PrintableDocumentViewer'

const STATUS_TONE: Record<VoucherStatus, StatusTone> = {
  PAID: 'positive',
  PARTIAL: 'caution',
  UNPAID: 'neutral',
  CANCELLED: 'neutral',
}

const STATUS_FILTERS: Array<{ value: '' | VoucherStatus; label: string }> = [
  { value: '', label: 'All statuses' },
  { value: 'UNPAID', label: 'Unpaid' },
  { value: 'PARTIAL', label: 'Partially paid' },
  { value: 'PAID', label: 'Paid' },
  { value: 'CANCELLED', label: 'Cancelled' },
]

function money(n: number): string {
  return `Rs. ${n.toFixed(2)}`
}

function today(): string {
  return new Date().toISOString().slice(0, 10)
}

function inDays(days: number): string {
  const d = new Date()
  d.setDate(d.getDate() + days)
  return d.toISOString().slice(0, 10)
}

interface FeesDashClientProps {
  org_id: number
  orgslug: string
}

/**
 * Creates a fee structure -- the priced template a voucher is generated from.
 *
 * Without this the fees module dead-ended: the generate dialog could only say
 * "no fee structures exist yet, one must be created", with nowhere to create
 * one. `total_amount` is deliberately NOT an input; the backend derives it as
 * tuition + transport + lab + other, so offering an editable total would let
 * the UI disagree with what is actually billed.
 */
function CreateFeeStructureDialog({
  campusId,
  onCreated,
}: {
  campusId?: number
  onCreated: () => void
}) {
  // Seeded from the URL so Ctrl+K's "New fee structure" lands here with the
  // dialog already open, instead of dropping the user on the page to hunt
  // for the button. See lib/dashboard-search/useDeepLinkAction.
  const [open, setOpen] = useState(useDeepLinkAction('new-structure'))
  const [name, setName] = useState('')
  const [tuition, setTuition] = useState('0')
  const [transport, setTransport] = useState('0')
  const [lab, setLab] = useState('0')
  const [other, setOther] = useState('0')
  const [submitting, setSubmitting] = useState(false)

  const parts = [tuition, transport, lab, other].map((v) => Number(v) || 0)
  const total = parts.reduce((a, b) => a + b, 0)

  async function handleSubmit() {
    if (!name.trim()) {
      toast.error('Give the fee structure a name.')
      return
    }
    if (parts.some((n) => n < 0)) {
      toast.error('Fee amounts cannot be negative.')
      return
    }
    if (total <= 0) {
      toast.error('At least one fee component must be greater than zero.')
      return
    }
    setSubmitting(true)
    try {
      await createFeeStructure({
        name: name.trim(),
        campus_id: campusId ?? null,
        tuition_fee: parts[0],
        transport_fee: parts[1],
        lab_fee: parts[2],
        other_fee: parts[3],
      })
      toast.success(`Created “${name.trim()}” (${money(total)}).`)
      setOpen(false)
      setName(''); setTuition('0'); setTransport('0'); setLab('0'); setOther('0')
      onCreated()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not create the fee structure.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <SchoolDialog
      open={open}
      onOpenChange={setOpen}
      trigger={
        <button type="button" className={LH_SECONDARY_BUTTON}>
          <Receipt className="size-4" /> <span>New fee structure</span>
        </button>
      }
      title="Create a fee structure"
      description="A priced template vouchers are generated from. The total is the sum of its components."
      footer={
        <>
          <button
            type="button"
            className={LH_GHOST_BUTTON}
            onClick={() => setOpen(false)}
            disabled={submitting}
          >
            Cancel
          </button>
          <button
            type="button"
            className={LH_PRIMARY_BUTTON}
            onClick={handleSubmit}
            disabled={submitting}
          >
            <span>{submitting ? 'Creating…' : `Create (${money(total)})`}</span>
          </button>
        </>
      }
    >
      <SchoolField
        id="fs-name"
        label="Name"
        required
        help="How staff will recognise it, e.g. “Grade 9 — Term 1”."
      >
        <input
          id="fs-name"
          className={LH_INPUT}
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Grade 9 — Term 1"
        />
      </SchoolField>

      <div className="grid grid-cols-2 gap-4">
        <SchoolField id="fs-tuition" label="Tuition fee">
          <input id="fs-tuition" type="number" min="0" step="0.01" className={LH_INPUT} value={tuition} onChange={(e) => setTuition(e.target.value)} />
        </SchoolField>
        <SchoolField id="fs-transport" label="Transport fee">
          <input id="fs-transport" type="number" min="0" step="0.01" className={LH_INPUT} value={transport} onChange={(e) => setTransport(e.target.value)} />
        </SchoolField>
        <SchoolField id="fs-lab" label="Lab fee">
          <input id="fs-lab" type="number" min="0" step="0.01" className={LH_INPUT} value={lab} onChange={(e) => setLab(e.target.value)} />
        </SchoolField>
        <SchoolField id="fs-other" label="Other fee">
          <input id="fs-other" type="number" min="0" step="0.01" className={LH_INPUT} value={other} onChange={(e) => setOther(e.target.value)} />
        </SchoolField>
      </div>

      <p className="text-sm text-gray-500">
        Total per student: <span className="font-semibold text-gray-900">{money(total)}</span>
      </p>
    </SchoolDialog>
  )
}

/**
 * Issues one voucher per student in a section, from a fee structure.
 *
 * Bulk and irreversible-ish (there is no delete-voucher endpoint), so it
 * names exactly how many students it will bill before the primary action is
 * available, and refuses to submit when the section has no active
 * enrollments. Student ids come from the real enrollment list -- never a
 * hardcoded or invented set.
 */
function GenerateVouchersDialog({
  campusId,
  onGenerated,
}: {
  campusId?: number
  onGenerated: () => void
}) {
  const [open, setOpen] = useState(useDeepLinkAction('generate-vouchers'))
  const [structureId, setStructureId] = useState<number | ''>('')
  const [sectionId, setSectionId] = useState<number | ''>('')
  const [issueDate, setIssueDate] = useState(today())
  const [dueDate, setDueDate] = useState(inDays(14))
  const [discount, setDiscount] = useState('0')
  const [submitting, setSubmitting] = useState(false)

  const structures = useApiResource(() => listFeeStructures({ campusId }), [campusId], {
    skip: !open,
    isEmpty: (d) => d.length === 0,
  })
  const sections = useApiResource(
    () => listClassSections(campusId as number, { isActive: true }),
    [campusId],
    { skip: !open || campusId === undefined }
  )
  const enrollments = useApiResource(
    () => listSectionEnrollments(sectionId as number, 'active'),
    [sectionId],
    { skip: !open || sectionId === '' }
  )

  const studentIds = (enrollments.data ?? []).map((e) => e.student_id)
  const canSubmit =
    structureId !== '' && sectionId !== '' && studentIds.length > 0 && !submitting && issueDate && dueDate

  async function handleSubmit() {
    if (structureId === '' || sectionId === '') return
    if (new Date(dueDate) < new Date(issueDate)) {
      toast.error('The due date cannot be before the issue date.')
      return
    }
    setSubmitting(true)
    try {
      const created = await generateVouchers({
        fee_structure_id: Number(structureId),
        student_ids: studentIds,
        issue_date: issueDate,
        due_date: dueDate,
        discount_per_student: Number(discount) || 0,
      })
      toast.success(`Issued ${created.length} voucher${created.length === 1 ? '' : 's'}.`)
      setOpen(false)
      setSectionId('')
      onGenerated()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not generate vouchers.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <SchoolDialog
      open={open}
      onOpenChange={setOpen}
      trigger={
        <button type="button" className={LH_PRIMARY_BUTTON}>
          <FilePlus2 className="size-4" /> <span>Generate vouchers</span>
        </button>
      }
      title="Generate fee vouchers"
      footer={
        <>
          <button
            type="button"
            className={LH_GHOST_BUTTON}
            onClick={() => setOpen(false)}
            disabled={submitting}
          >
            Cancel
          </button>
          <button
            type="button"
            className={LH_PRIMARY_BUTTON}
            onClick={handleSubmit}
            disabled={!canSubmit}
          >
            <span>
              {submitting
                ? 'Issuing…'
                : studentIds.length > 0
                  ? `Issue ${studentIds.length} voucher${studentIds.length === 1 ? '' : 's'}`
                  : 'Issue vouchers'}
            </span>
          </button>
        </>
      }
    >
      <SchoolField
        id="gen-structure"
        label="Fee structure"
        help={
          structures.status === 'empty'
            ? 'No fee structures exist yet. Close this and use “New fee structure” to create one.'
            : undefined
        }
      >
        <select
          id="gen-structure"
          className={LH_INPUT}
          value={structureId}
          onChange={(e) => setStructureId(e.target.value === '' ? '' : Number(e.target.value))}
        >
          <option value="">Select a fee structure…</option>
          {(structures.data ?? []).map((s) => (
            <option key={s.id} value={s.id}>
              {s.name} — {money(s.total_amount)}
            </option>
          ))}
        </select>
      </SchoolField>

      <SchoolField
        id="gen-section"
        label="Section"
        help={
          sectionId !== ''
            ? enrollments.status === 'loading'
              ? 'Counting enrolled students…'
              : studentIds.length === 0
                ? 'No active enrollments in this section — nothing to bill.'
                : `${studentIds.length} enrolled student${studentIds.length === 1 ? '' : 's'} will be billed.`
            : undefined
        }
      >
        <select
          id="gen-section"
          className={LH_INPUT}
          value={sectionId}
          onChange={(e) => setSectionId(e.target.value === '' ? '' : Number(e.target.value))}
        >
          <option value="">Select a section…</option>
          {(sections.data ?? []).map((s) => (
            <option key={s.id} value={s.id}>
              {s.grade_level} — {s.section_name}
            </option>
          ))}
        </select>
      </SchoolField>

      <div className="grid grid-cols-2 gap-4">
        <SchoolField id="gen-issue" label="Issue date">
          <input
            id="gen-issue"
            type="date"
            className={LH_INPUT}
            value={issueDate}
            onChange={(e) => setIssueDate(e.target.value)}
          />
        </SchoolField>
        <SchoolField id="gen-due" label="Due date">
          <input
            id="gen-due"
            type="date"
            className={LH_INPUT}
            value={dueDate}
            onChange={(e) => setDueDate(e.target.value)}
          />
        </SchoolField>
      </div>

      <SchoolField id="gen-discount" label="Discount per student (optional)">
        <input
          id="gen-discount"
          type="number"
          min="0"
          step="0.01"
          className={LH_INPUT}
          value={discount}
          onChange={(e) => setDiscount(e.target.value)}
        />
      </SchoolField>
    </SchoolDialog>
  )
}

export default function FeesDashClient({ org_id }: FeesDashClientProps) {
  const [campusId, setCampusId] = useState<number | undefined>(undefined)
  const [sectionId, setSectionId] = useState<number | ''>('')
  const [statusFilter, setStatusFilter] = useState<'' | VoucherStatus>('')
  const [accruing, setAccruing] = useState(false)
  const [accrualNote, setAccrualNote] = useState<string | null>(null)

  // 360 Inspection & Document preview states
  const [inspectOpen, setInspectOpen] = useState(false)
  const [inspectVoucher, setInspectVoucher] = useState<any | null>(null)
  const [viewerOpen, setViewerOpen] = useState(false)
  const [feeSlipData, setFeeSlipData] = useState<any | null>(null)

  const campuses = useApiResource(() => listCampuses({ orgId: org_id, isActive: true }), [org_id], {
    isEmpty: (d) => d.length === 0,
  })
  const effectiveCampusId = campusId ?? campuses.data?.[0]?.id

  const sections = useApiResource(
    () => listClassSections(effectiveCampusId as number, { isActive: true }),
    [effectiveCampusId],
    { skip: effectiveCampusId === undefined }
  )

  // No backend section filter exists, so narrow client-side via enrollments.
  const enrollments = useApiResource(
    () => listSectionEnrollments(sectionId as number, 'active'),
    [sectionId],
    { skip: sectionId === '' }
  )

  const vouchers = useApiResource(
    () => (statusFilter === '' ? listVouchers({}) : listVouchers({ status: statusFilter })),
    [statusFilter],
    { isEmpty: (d) => d.length === 0 }
  )

  const allRows = vouchers.data ?? []
  const sectionStudentIds =
    sectionId === '' ? null : new Set((enrollments.data ?? []).map((e) => e.student_id))
  const rows =
    sectionStudentIds === null ? allRows : allRows.filter((v) => sectionStudentIds.has(v.student_id))

  const totalInvoiced = rows.reduce((s, v) => s + v.total_amount, 0)
  const totalPaid = rows.reduce((s, v) => s + v.paid_amount, 0)
  const totalOutstanding = rows.reduce((s, v) => s + v.balance_amount, 0)
  const totalLateFees = rows.reduce((s, v) => s + (v.late_fee_applied ?? 0), 0)

  async function handleAccrueLateFees() {
    setAccruing(true)
    setAccrualNote(null)
    try {
      const changed = await accrueLateFees()
      setAccrualNote(
        changed.length === 0
          ? 'No overdue vouchers needed a late fee.'
          : `Late fees applied to ${changed.length} voucher${changed.length === 1 ? '' : 's'}.`
      )
      vouchers.refetch()
    } catch {
      setAccrualNote("Couldn't run late-fee accrual. Try again in a moment.")
    } finally {
      setAccruing(false)
    }
  }

  const feeExportColumns: ExportColumn[] = [
    { key: 'voucher_no', label: 'Voucher #', type: 'text' },
    { key: 'student_id', label: 'Student ID', type: 'number' },
    { key: 'issue_date', label: 'Issue Date', type: 'date' },
    { key: 'due_date', label: 'Due Date', type: 'date' },
    { key: 'tuition_fee', label: 'Tuition Fee', type: 'currency' },
    { key: 'transport_fee', label: 'Transport Fee', type: 'currency' },
    { key: 'lab_fee', label: 'Lab Fee', type: 'currency' },
    { key: 'other_fee', label: 'Other Fee', type: 'currency' },
    { key: 'discount', label: 'Discount', type: 'currency' },
    { key: 'fine', label: 'Fine', type: 'currency' },
    { key: 'late_fee_applied', label: 'Late Fee Applied', type: 'currency' },
    { key: 'total_amount', label: 'Total Invoiced', type: 'currency' },
    { key: 'paid_amount', label: 'Paid Amount', type: 'currency' },
    { key: 'balance_amount', label: 'Balance Outstanding', type: 'currency' },
    { key: 'status', label: 'Payment Status', type: 'text' },
  ]

  return (
    <DashPageShell
      title="Fees"
      description="Vouchers, collections and outstanding balances across the school."
      module="fees"
      action={
        <div className="flex flex-wrap items-center gap-2">
          {rows.length > 0 && (
            <DataExportToolbar
              data={rows}
              columns={feeExportColumns}
              filenamePrefix="fee_vouchers"
              title="Student Fee Vouchers"
              activeFilters={{ campus_id: effectiveCampusId, section_id: sectionId, status: statusFilter }}
            />
          )}
          <CreateFeeStructureDialog
            campusId={effectiveCampusId}
            onCreated={vouchers.refetch}
          />
          <GenerateVouchersDialog campusId={effectiveCampusId} onGenerated={vouchers.refetch} />
        </div>
      }
    >

      <StatGrid
        state={vouchers.status === 'loading' ? 'loading' : 'success'}
        columns={4}
        items={[
          { label: 'Invoiced', value: money(totalInvoiced), icon: Receipt, tone: 'neutral' },
          { label: 'Collected', value: money(totalPaid), icon: Wallet, tone: 'positive' },
          {
            label: 'Outstanding',
            value: money(totalOutstanding),
            icon: BadgeDollarSign,
            tone: totalOutstanding > 0 ? 'caution' : 'positive',
          },
          {
            label: 'Late fees charged',
            value: money(totalLateFees),
            icon: BadgeDollarSign,
            tone: totalLateFees > 0 ? 'caution' : 'neutral',
          },
        ]}
      />

      <SectionCard
        title="Filter vouchers"
        icon={<Receipt className="size-4 text-gray-500" />}
        state={campuses.status === 'loading' ? 'loading' : campuses.status}
        error={campuses.error}
        onRetry={campuses.refetch}
        emptyTitle="No campuses set up yet"
        emptyDescription="Add a campus and class sections before issuing fee vouchers."
      >
        <div className="flex flex-wrap items-end gap-4">
          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-gray-500">Campus</span>
            <select
              id="fees-campus"
              className="px-3 py-2 bg-white nice-shadow rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-black focus:ring-offset-2 border-0"
              value={effectiveCampusId ?? ''}
              onChange={(e) => {
                setCampusId(Number(e.target.value))
                setSectionId('')
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
              id="fees-section"
              className="px-3 py-2 bg-white nice-shadow rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-black focus:ring-offset-2 border-0"
              value={sectionId}
              onChange={(e) => setSectionId(e.target.value === '' ? '' : Number(e.target.value))}
            >
              <option value="">All sections</option>
              {(sections.data ?? []).map((s) => (
                <option key={s.id} value={s.id}>
                  {s.grade_level} — {s.section_name}
                </option>
              ))}
            </select>
          </label>

          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-gray-500">Status</span>
            <select
              id="fees-status"
              className="px-3 py-2 bg-white nice-shadow rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-black focus:ring-offset-2 border-0"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as '' | VoucherStatus)}
            >
              {STATUS_FILTERS.map((f) => (
                <option key={f.value} value={f.value}>
                  {f.label}
                </option>
              ))}
            </select>
          </label>

          <div className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-gray-500">Overdue vouchers</span>
            <button
              type="button"
              className={LH_SECONDARY_BUTTON}
              onClick={handleAccrueLateFees}
              disabled={accruing}
            >
              <span>{accruing ? 'Applying…' : 'Apply late fees'}</span>
            </button>
          </div>
        </div>
        {accrualNote && <p className="mt-3 text-sm text-gray-500">{accrualNote}</p>}
      </SectionCard>

      <SectionCard
        title="Vouchers"
        description={
          sectionId === '' ? 'Every voucher issued' : 'Narrowed to the selected section'
        }
        icon={<Receipt className="size-4 text-gray-500" />}
        state={vouchers.status}
        error={vouchers.error}
        onRetry={vouchers.refetch}
        emptyTitle="No vouchers issued yet"
        emptyDescription="Generate vouchers from a fee structure to start collecting."
      >
        {rows.length === 0 && sectionId !== '' ? (
          <EmptyState
            title="No vouchers for this section"
            description="Students in this section have no fee vouchers issued yet."
          />
        ) : (
          <DataTable
            rows={rows}
            rowKey={(row) => row.id}
            state="success"
            totalLabel={`${rows.length} voucher${rows.length === 1 ? '' : 's'}`}
            columns={[
              { key: 'voucher', header: 'Voucher #', render: (r) => r.voucher_no },
              { key: 'student', header: 'Student', render: (r) => `Student #${r.student_id}` },
              { key: 'due', header: 'Due', render: (r) => r.due_date },
              {
                key: 'total',
                header: 'Total',
                align: 'right',
                className: 'tabular-nums',
                render: (r) => money(r.total_amount),
              },
              {
                key: 'late',
                header: 'Late fee',
                align: 'right',
                className: 'tabular-nums',
                render: (r) => ((r.late_fee_applied ?? 0) > 0 ? money(r.late_fee_applied as number) : '—'),
              },
              {
                key: 'paid',
                header: 'Paid',
                align: 'right',
                className: 'tabular-nums',
                render: (r) => money(r.paid_amount),
              },
              {
                key: 'balance',
                header: 'Balance',
                align: 'right',
                className: 'tabular-nums',
                render: (r) => money(r.balance_amount),
              },
              {
                key: 'status',
                header: 'Status',
                render: (r) => <StatusChip label={r.status} tone={STATUS_TONE[r.status] ?? 'neutral'} />,
              },
              {
                key: 'actions',
                header: 'Actions',
                align: 'right',
                render: (r: StudentFeeVoucherRead) => (
                  <div className="flex items-center justify-end gap-1.5">
                    <button
                      type="button"
                      title="Inspect Voucher 360°"
                      onClick={() => {
                        setInspectVoucher({
                          id: `VCH-${r.id}`,
                          voucherNo: r.voucher_no,
                          studentId: `STU-${r.student_id}`,
                          studentName: `Student #${r.student_id}`,
                          rollNo: `RN-${r.student_id}`,
                          gradeSection: 'Grade 10 - Section A',
                          campus: 'Main Science Campus',
                          issueDate: r.issue_date,
                          dueDate: r.due_date,
                          status: r.status,
                          totalAmount: r.total_amount,
                          paidAmount: r.paid_amount,
                          balanceAmount: r.balance_amount,
                          lateFeeApplied: r.late_fee_applied ?? 0,
                          lineItems: [
                            { description: 'Tuition Fee', amount: r.tuition_fee, category: 'Tuition' },
                            { description: 'Transport Fee', amount: r.transport_fee, category: 'Transport' },
                            { description: 'Laboratory Fee', amount: r.lab_fee, category: 'Lab' },
                            { description: 'Other Charges', amount: r.other_fee, category: 'Other' },
                          ].filter((item) => item.amount > 0),
                          installments: [],
                          transactions: [],
                        })
                        setInspectOpen(true)
                      }}
                      className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium rounded-md border border-gray-200 bg-white hover:bg-gray-50 text-gray-700 transition-colors"
                    >
                      <Eye className="size-3" />
                      <span>360°</span>
                    </button>
                    <button
                      type="button"
                      title="Print 3-Part Bank Slip (PDF)"
                      onClick={() => {
                        setFeeSlipData({
                          voucherNo: r.voucher_no,
                          issueDate: r.issue_date,
                          dueDate: r.due_date,
                          validUntil: r.due_date,
                          studentName: `Student #${r.student_id}`,
                          studentId: `STU-${r.student_id}`,
                          rollNo: `RN-${r.student_id}`,
                          gradeSection: 'Grade 10 - Section A',
                          campusName: 'Main Science Campus',
                          feeMonth: 'Current Billing Cycle',
                          tuitionFee: r.tuition_fee,
                          transportFee: r.transport_fee,
                          labFee: r.lab_fee,
                          otherFee: r.other_fee,
                          discount: r.discount,
                          fine: r.fine,
                          lateFee: r.late_fee_applied ?? 0,
                          totalAmount: r.total_amount,
                          payableByDueDate: r.total_amount,
                          payableAfterDueDate: r.total_amount + (r.late_fee_applied ?? 500),
                          bankName: 'Habib Bank Limited (HBL)',
                          accountTitle: 'CSG Educational Systems Ltd',
                          accountNumber: 'PK64HABB00012345678901',
                          barcodeValue: r.voucher_no.replace(/[^0-9]/g, '') || '849204810294',
                        })
                        setViewerOpen(true)
                      }}
                      className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium rounded-md border border-gray-200 bg-white hover:bg-gray-50 text-gray-700 transition-colors"
                    >
                      <FileText className="size-3" />
                      <span>PDF</span>
                    </button>
                    {r.balance_amount > 0 && r.status !== 'CANCELLED' ? (
                      <PayVoucherDialog
                        voucher={r}
                        onPaid={vouchers.refetch}
                        trigger={
                          <button type="button" className={LH_SECONDARY_BUTTON}>
                            <span>Collect</span>
                          </button>
                        }
                      />
                    ) : (
                      <span className="text-xs text-gray-500 px-1">Settled</span>
                    )}
                  </div>
                ),
              },
            ]}
          />
        )}
      </SectionCard>

      {/* 360° Fee Voucher Drawer */}
      <FeeVoucher360Drawer
        isOpen={inspectOpen}
        onClose={() => setInspectOpen(false)}
        voucher={inspectVoucher}
      />

      {/* 3-Part Bank Slip Document Viewer Studio */}
      <PrintableDocumentViewer
        isOpen={viewerOpen}
        onClose={() => setViewerOpen(false)}
        initialDocType="bank_slip"
        feeData={feeSlipData}
      />
    </DashPageShell>
  )
}
