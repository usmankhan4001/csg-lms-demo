'use client'

/**
 * Payroll — salary structures, a payroll run, and the approval queue.
 *
 * Payroll had no screen of its own: it was folded into the HR page as a slip
 * list. That mattered more than it sounds, because the three payroll endpoints
 * compose into a self-dealing path — one person could set a salary structure,
 * generate the slip, and mark it paid with no second party. The backend now
 * refuses self-approval; this screen is where the second party actually does
 * the reviewing.
 *
 * The `self_approval_refused` outcome is rendered as its own visible state
 * rather than an error, because it is not a failure — it is the control
 * working, and the reviewer needs to see which slips still need someone else.
 */

import { useCallback, useMemo, useState } from 'react'
import { BadgeCheck, CircleDollarSign, Clock, ShieldCheck, Eye, FileText } from 'lucide-react'
import {
  DataTable,
  EmptyState,
  LH_INPUT,
  LH_PRIMARY_BUTTON,
  LH_SECONDARY_BUTTON,
  SchoolDialog,
  SchoolField,
  SectionCard,
  StatGrid,
  StatusChip,
  DashPageShell,
} from '@/components/widgets'
import { ApiError } from '@/lib/api/api-client'
import { useApiResource } from '@/lib/api/useApiResource'
import {
  approveSalarySlips,
  generateSalarySlipsBatch,
  listSalarySlips,
  listSlipActions,
  recordSalaryPayment,
  rejectSalarySlips,
} from '@/modules/sms/hr_payroll/api'
import type {
  PayrollApprovalOutcome,
  PayrollActionRead,
  SalarySlipRead,
} from '@/modules/sms/hr_payroll/types'
import { DataExportToolbar } from '@/components/ems/DataExportToolbar'
import type { ExportColumn } from '@/lib/export/data-export'
import { Payslip360Drawer } from '@/modules/ems/inspectors/Payslip360Drawer'
import { PrintableDocumentViewer } from '@/modules/ems/documents/PrintableDocumentViewer'

interface PayrollClientProps {
  org_id: number
  orgslug: string
}

const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
]

/** Money is never invented. A slip with no net figure shows that it has none. */
function formatMoney(value: number | null | undefined): string {
  if (value === null || value === undefined) return 'Not recorded'
  return value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function statusTone(status: string): 'positive' | 'caution' | 'critical' | 'neutral' {
  if (status === 'PAID') return 'positive'
  if (status === 'PENDING') return 'caution'
  if (status === 'FAILED') return 'critical'
  return 'neutral'
}

export default function PayrollClient({ org_id }: PayrollClientProps) {
  const now = new Date()
  const [month, setMonth] = useState<number>(now.getMonth() + 1)
  const [year, setYear] = useState<number>(now.getFullYear())
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [outcomes, setOutcomes] = useState<PayrollApprovalOutcome[] | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const [trailSlipId, setTrailSlipId] = useState<number | null>(null)
  const [trail, setTrail] = useState<PayrollActionRead[] | null>(null)
  const [trailError, setTrailError] = useState<string | null>(null)

  // 360 Inspection & Document preview states
  const [inspectOpen, setInspectOpen] = useState(false)
  const [inspectSlip, setInspectSlip] = useState<any | null>(null)
  const [viewerOpen, setViewerOpen] = useState(false)
  const [payslipData, setPayslipData] = useState<any | null>(null)

  const slips = useApiResource(
    () => listSalarySlips({ month, year }),
    [month, year],
    { isEmpty: (d) => d.length === 0 }
  )

  const rows = useMemo(() => slips.data ?? [], [slips.data])

  const pending = rows.filter((s) => s.payment_status === 'PENDING')
  const paid = rows.filter((s) => s.payment_status === 'PAID')

  const toggle = useCallback((id: number) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }, [])

  const describe = (err: unknown): string => {
    if (err instanceof ApiError) {
      if (err.kind === 'permission_denied') {
        return 'You need payroll-administrator access to do this.'
      }
      return err.message
    }
    return 'Something went wrong. Try again.'
  }

  async function runApproval(reject: boolean) {
    const ids = [...selected]
    if (ids.length === 0) return
    setBusy(true)
    setActionError(null)
    setOutcomes(null)
    try {
      const fn = reject ? rejectSalarySlips : approveSalarySlips
      const res = await fn({ slip_ids: ids })
      setOutcomes(res.results)
      setSelected(new Set())
      slips.refetch()
    } catch (err) {
      setActionError(describe(err))
    } finally {
      setBusy(false)
    }
  }

  async function openTrail(slipId: number) {
    setTrailSlipId(slipId)
    setTrail(null)
    setTrailError(null)
    try {
      setTrail(await listSlipActions(slipId))
    } catch (err) {
      setTrailError(describe(err))
    }
  }

  const refused = (outcomes ?? []).filter((o) => o.outcome === 'self_approval_refused')
  const approved = (outcomes ?? []).filter((o) => o.outcome === 'approved' || o.outcome === 'rejected')
  const notFound = (outcomes ?? []).filter((o) => o.outcome === 'not_found')
  const alreadyPaid = (outcomes ?? []).filter((o) => o.outcome === 'already_paid')

  const payrollExportColumns: ExportColumn<SalarySlipRead>[] = useMemo(
    () => [
      { key: 'slip_no', label: 'Slip #', type: 'text' },
      { key: 'staff_id', label: 'Staff ID', type: 'number' },
      { key: 'month', label: 'Month', type: 'text', accessor: (s) => MONTHS[s.month - 1] ?? s.month },
      { key: 'year', label: 'Year', type: 'number' },
      { key: 'basic', label: 'Basic Salary', type: 'currency' },
      { key: 'housing_allowance', label: 'Housing Allowance', type: 'currency' },
      { key: 'medical_allowance', label: 'Medical Allowance', type: 'currency' },
      { key: 'other_allowances', label: 'Other Allowances', type: 'currency' },
      { key: 'gross_salary', label: 'Gross Salary', type: 'currency' },
      { key: 'tax_deduction', label: 'Tax Deduction', type: 'currency' },
      { key: 'provident_fund', label: 'Provident Fund', type: 'currency' },
      { key: 'other_deductions', label: 'Other Deductions', type: 'currency' },
      { key: 'unpaid_leave_deduction', label: 'Unpaid Leave Deduction', type: 'currency' },
      { key: 'total_deductions', label: 'Total Deductions', type: 'currency' },
      { key: 'net_salary', label: 'Net Salary', type: 'currency' },
      { key: 'payment_status', label: 'Payment Status', type: 'text' },
      { key: 'payment_date', label: 'Payment Date', type: 'date' },
    ],
    []
  )

  return (
    <DashPageShell
      title="Payroll"
      description="Salary slips, approval and disbursement for this pay period."
    >
      <SectionCard
        id="payroll-period"
        title="Pay period"
        icon={<Clock className="size-4 text-gray-500" />}
      >
        <div className="flex flex-wrap items-end gap-4">
          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-gray-500">Month</span>
            <select
              id="payroll-month"
              className={LH_INPUT}
              value={month}
              onChange={(e) => setMonth(Number(e.target.value))}
            >
              {MONTHS.map((m, i) => (
                <option key={m} value={i + 1}>{m}</option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-gray-500">Year</span>
            <input
              id="payroll-year"
              type="number"
              className={LH_INPUT}
              value={year}
              onChange={(e) => setYear(Number(e.target.value))}
            />
          </label>
        </div>
      </SectionCard>

      <StatGrid
        state={slips.status === 'loading' ? 'loading' : 'success'}
        columns={3}
        items={[
          { label: 'Slips this period', value: rows.length, icon: CircleDollarSign, tone: 'neutral' },
          { label: 'Awaiting approval or payment', value: pending.length, icon: Clock, tone: pending.length ? 'caution' : 'neutral' },
          { label: 'Paid', value: paid.length, icon: BadgeCheck, tone: 'positive' },
        ]}
      />

      {outcomes && (
        <SectionCard
          id="payroll-outcomes"
          title="Result of the last review"
          icon={<ShieldCheck className="size-4 text-gray-500" />}
        >
          <div className="flex flex-col gap-3">
            {approved.length > 0 && (
              <p className="text-sm text-gray-700">
                {approved.length} slip{approved.length === 1 ? '' : 's'} actioned.
              </p>
            )}
            {refused.length > 0 && (
              <div className="rounded-lg border border-amber-300 bg-amber-50 p-3">
                <p className="text-sm font-medium text-amber-900">
                  {refused.length} slip{refused.length === 1 ? '' : 's'} could not be approved by you
                </p>
                <p className="mt-1 text-sm text-amber-800">
                  You prepared {refused.length === 1 ? 'it' : 'them'}. Payroll must be approved by a
                  second person — this is a control, not an error. Ask a colleague with payroll
                  access to review {refused.length === 1 ? 'this slip' : 'these slips'}.
                </p>
                <p className="mt-1 text-xs text-amber-700">
                  Slip {refused.map((o) => o.slip_id).join(', ')}
                </p>
              </div>
            )}
            {alreadyPaid.length > 0 && (
              <p className="text-sm text-gray-600">
                {alreadyPaid.length} already disbursed; approval no longer applies.
              </p>
            )}
            {notFound.length > 0 && (
              <p className="text-sm text-rose-600">
                {notFound.length} slip{notFound.length === 1 ? '' : 's'} no longer exist.
              </p>
            )}
          </div>
        </SectionCard>
      )}

      <SectionCard
        id="payroll-slips"
        title="Salary slips"
        icon={<CircleDollarSign className="size-4 text-gray-500" />}
        state={slips.status}
        error={slips.error}
        onRetry={slips.refetch}
        emptyTitle="No salary slips for this period"
        emptyDescription="Generate slips for the selected month and year to begin a payroll run."
        action={
          <div className="flex flex-wrap items-center gap-2">
            {rows.length > 0 && (
              <DataExportToolbar
                data={rows}
                columns={payrollExportColumns}
                filenamePrefix={`payroll_slips_${year}_${month}`}
                title={`Payroll Register - ${MONTHS[month - 1]} ${year}`}
                selectedIds={selected}
                activeFilters={{ month, year }}
                classification="RESTRICTED"
              />
            )}
            <button
              type="button"
              id="payroll-approve"
              className={LH_PRIMARY_BUTTON}
              disabled={busy || selected.size === 0}
              onClick={() => runApproval(false)}
            >
              <span>{busy ? 'Working…' : `Approve${selected.size ? ` (${selected.size})` : ''}`}</span>
            </button>
            <button
              type="button"
              id="payroll-reject"
              className={LH_SECONDARY_BUTTON}
              disabled={busy || selected.size === 0}
              onClick={() => runApproval(true)}
            >
              <span>Reject</span>
            </button>
          </div>
        }
      >
        {actionError && <p className="mb-3 text-sm text-rose-600">{actionError}</p>}
        <DataTable
          rows={rows}
          rowKey={(r) => r.id}
          state="success"
          totalLabel={`${rows.length} slip${rows.length === 1 ? '' : 's'}`}
          columns={[
            {
              key: 'select',
              header: '',
              render: (r: SalarySlipRead) =>
                r.payment_status === 'PAID' ? (
                  <span className="text-xs text-gray-400">—</span>
                ) : (
                  <input
                    type="checkbox"
                    id={`payroll-select-${r.id}`}
                    aria-label={`Select slip ${r.slip_no}`}
                    checked={selected.has(r.id)}
                    onChange={() => toggle(r.id)}
                  />
                ),
            },
            { key: 'slip_no', header: 'Slip', render: (r: SalarySlipRead) => r.slip_no },
            { key: 'staff', header: 'Staff ID', render: (r: SalarySlipRead) => r.staff_id },
            {
              key: 'net',
              header: 'Net',
              align: 'right',
              render: (r: SalarySlipRead) => formatMoney(r.net_salary),
            },
            {
              key: 'status',
              header: 'Status',
              render: (r: SalarySlipRead) => (
                <StatusChip label={r.payment_status} tone={statusTone(r.payment_status)} />
              ),
            },
            {
              key: 'actions',
              header: 'Actions',
              align: 'right',
              render: (r: SalarySlipRead) => (
                <div className="flex items-center justify-end gap-1.5">
                  <button
                    type="button"
                    title="Inspect Payslip 360°"
                    onClick={() => {
                      setInspectSlip({
                        id: r.id,
                        slipNo: r.slip_no,
                        staffId: r.staff_id,
                        staffName: `Staff Member #${r.staff_id}`,
                        department: 'Academic Faculty',
                        role: 'Faculty Member',
                        month: r.month,
                        year: r.year,
                        basic: r.basic,
                        housingAllowance: r.housing_allowance,
                        medicalAllowance: r.medical_allowance,
                        otherAllowances: r.other_allowances,
                        unpaidLeaveDays: r.unpaid_leave_days,
                        unpaidLeaveDeduction: r.unpaid_leave_deduction,
                        providentFund: r.provident_fund,
                        taxDeduction: r.tax_deduction,
                        otherDeductions: r.other_deductions,
                        grossSalary: r.gross_salary,
                        totalDeductions: r.total_deductions,
                        netSalary: r.net_salary,
                        status: r.payment_status,
                        preparerUserId: null,
                        preparerName: 'Payroll Officer',
                        wasClamped: false,
                        auditTrail: [],
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
                    title="Print Payslip (PDF)"
                    onClick={() => {
                      const totalAllowances = (r.housing_allowance ?? 0) + (r.medical_allowance ?? 0) + (r.other_allowances ?? 0)
                      setPayslipData({
                        payslipNumber: r.slip_no,
                        payPeriod: `${MONTHS[month - 1]} ${year}`,
                        paymentDate: new Date().toISOString().slice(0, 10),
                        employeeName: `Staff Member #${r.staff_id}`,
                        employeeId: `STF-${r.staff_id}`,
                        department: 'Academic Faculty',
                        designation: 'Faculty Member',
                        campusName: 'Main Science Campus',
                        bankName: 'Habib Bank Limited (HBL)',
                        bankAccount: 'PK64HABB000987654321',
                        taxNumber: 'NTN-7492019-3',
                        earnings: [
                          { description: 'Basic Salary', amount: r.basic },
                          { description: 'Allowances', amount: totalAllowances },
                        ].filter((e) => e.amount > 0),
                        deductions: [
                          { description: 'Income Tax & Statutory', amount: r.total_deductions },
                        ].filter((d) => d.amount > 0),
                        grossPay: r.gross_salary,
                        totalDeductions: r.total_deductions,
                        netPay: r.net_salary,
                        preparedBy: 'Payroll Accountant',
                        approvedBy: 'Financial Controller',
                        disbursementStatus: r.payment_status === 'PAID' ? 'Disbursed' : 'Approved / Pending',
                      })
                      setViewerOpen(true)
                    }}
                    className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium rounded-md border border-gray-200 bg-white hover:bg-gray-50 text-gray-700 transition-colors"
                  >
                    <FileText className="size-3" />
                    <span>PDF</span>
                  </button>
                  <button
                    type="button"
                    id={`payroll-trail-${r.id}`}
                    className="text-xs text-gray-600 underline hover:text-gray-900 px-1"
                    onClick={() => openTrail(r.id)}
                  >
                    Trail
                  </button>
                </div>
              ),
            },
          ]}
        />
      </SectionCard>

      <SchoolDialog
        open={trailSlipId !== null}
        onOpenChange={(open) => {
          if (!open) {
            setTrailSlipId(null)
            setTrail(null)
            setTrailError(null)
          }
        }}
        title="Approval trail"
        description="Who prepared, approved and paid this slip. Append-only — a payroll decision cannot be edited after the fact."
      >
        {trailError && <p className="text-sm text-rose-600">{trailError}</p>}
        {!trailError && trail === null && <p className="text-sm text-gray-400">Loading…</p>}
        {trail !== null && trail.length === 0 && (
          <EmptyState
            title="No actions recorded"
            description="Nothing has been done to this slip yet — that is different from it having been rejected."
          />
        )}
        {trail !== null && trail.length > 0 && (
          <ul className="flex flex-col gap-2">
            {trail.map((a) => (
              <li key={a.id} className="rounded-lg bg-gray-50 p-3">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-medium text-gray-900">{a.action}</span>
                  <span className="text-xs text-gray-500">
                    {new Date(a.created_at).toLocaleString()}
                  </span>
                </div>
                <p className="mt-1 text-xs text-gray-600">
                  {a.actor_label ?? (a.actor_user_id !== null ? `User #${a.actor_user_id}` : 'Actor not recorded')}
                  {a.net_salary_at_action !== null && ` · net ${formatMoney(a.net_salary_at_action)}`}
                </p>
                {a.note && <p className="mt-1 text-xs text-gray-600">{a.note}</p>}
              </li>
            ))}
          </ul>
        )}
      </SchoolDialog>

      {/* 360° Payslip Inspection Drawer */}
      <Payslip360Drawer
        isOpen={inspectOpen}
        onClose={() => setInspectOpen(false)}
        record={inspectSlip}
      />

      {/* Printable Payslip PDF Document Viewer Studio */}
      <PrintableDocumentViewer
        isOpen={viewerOpen}
        onClose={() => setViewerOpen(false)}
        initialDocType="payslip"
        payslipData={payslipData}
      />
    </DashPageShell>
  )
}
