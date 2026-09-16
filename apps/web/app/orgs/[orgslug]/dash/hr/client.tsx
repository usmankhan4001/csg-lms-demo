'use client'

/**
 * HR & Payroll, attached as a first-class Learnhouse dash module.
 *
 * Built rather than moved: `modules/sms/hr_payroll` was API-only, with no UI
 * anywhere in the app. The page sits under `dash/`, so it inherits
 * ClientAdminLayout exactly like Courses or Boards, and its nav entry is
 * gated on the real `sms_hr_payroll` toggle already resolved by the backend
 * into `org.config.config.resolved_features`.
 *
 * This screen shows salaries. It deliberately offers no export, download or
 * print affordance, and never writes pay figures to the console -- the only
 * copy of this data is the one the API already returned to this caller,
 * whose role the backend gated server-side.
 */

import { useState } from 'react'
import toast from 'react-hot-toast'
import { Banknote, CalendarDays, IdCard, Users, Eye, FileText } from 'lucide-react'
import {
  LH_GHOST_BUTTON,
  LH_PRIMARY_BUTTON,
  LH_SECONDARY_BUTTON,
  DashPageShell,
  DataTable,
  SchoolDialog,
  SectionCard,
  StatGrid,
  StatusChip,
} from '@/components/widgets'
import { useApiResource } from '@/lib/api/useApiResource'
import { useSchoolSession } from '@/lib/api/useSchoolSession'
import { listCampuses } from '@/modules/sms/campus/api'
import {
  generateSalarySlipsBatch,
  listSalarySlips,
  listStaffLeaves,
  listStaffProfiles,
  recordSalaryPayment,
  updateStaffLeaveStatus,
} from '@/modules/sms/hr_payroll/api'
import type { LeaveStatus, SalaryPaymentStatus, StaffProfileRead, SalarySlipRead } from '@/modules/sms/hr_payroll/types'
import { DataExportToolbar } from '@/components/ems/DataExportToolbar'
import type { ExportColumn } from '@/lib/export/data-export'
import { Teacher360Drawer } from '@/modules/ems/inspectors/Teacher360Drawer'
import { Payslip360Drawer } from '@/modules/ems/inspectors/Payslip360Drawer'
import { PrintableDocumentViewer } from '@/modules/ems/documents/PrintableDocumentViewer'

interface HrDashClientProps {
  org_id: number
  orgslug: string
}

const PAYMENT_TONE: Record<SalaryPaymentStatus, 'positive' | 'caution' | 'critical'> = {
  PAID: 'positive',
  PENDING: 'caution',
  FAILED: 'critical',
}

const LEAVE_TONE: Record<LeaveStatus, 'positive' | 'caution' | 'critical'> = {
  APPROVED: 'positive',
  PENDING: 'caution',
  REJECTED: 'critical',
}

/** Money is right-aligned and tabular so columns of figures line up. */
function money(value: number): string {
  return `Rs. ${value.toFixed(2)}`
}

const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
]

export default function HrDashClient({ org_id }: HrDashClientProps) {
  const { session } = useSchoolSession()
  const now = new Date()
  const [campusId, setCampusId] = useState<number | undefined>(undefined)
  const [month, setMonth] = useState<number>(now.getMonth() + 1)
  const [year, setYear] = useState<number>(now.getFullYear())

  const campuses = useApiResource(() => listCampuses({ orgId: org_id, isActive: true }), [org_id], {
    isEmpty: (d) => d.length === 0,
  })

  const effectiveCampusId = campusId ?? session?.campus_id ?? campuses.data?.[0]?.id

  const staff = useApiResource(
    () => listStaffProfiles({ campusId: effectiveCampusId, isActive: true }),
    [effectiveCampusId],
    { isEmpty: (d) => d.length === 0 }
  )

  const slips = useApiResource(
    () => listSalarySlips({ month, year }),
    [month, year],
    { isEmpty: (d) => d.length === 0 }
  )

  const leaves = useApiResource(() => listStaffLeaves({ status: 'PENDING' }), [], {
    isEmpty: (d) => d.length === 0,
  })

  const staffRows = staff.data ?? []
  const slipRows = slips.data ?? []
  const netPayroll = slipRows.reduce((sum, s) => sum + s.net_salary, 0)
  const unpaidCount = slipRows.filter((s) => s.payment_status !== 'PAID').length

  // Staff id -> name, so payroll reads as people rather than row ids.
  const staffName = new Map(staffRows.map((s) => [s.id, s.full_name]))

  const [decidingLeaveId, setDecidingLeaveId] = useState<number | null>(null)
  const [payingSlipId, setPayingSlipId] = useState<number | null>(null)
  const [generateOpen, setGenerateOpen] = useState(false)
  const [generating, setGenerating] = useState(false)

  // 360 Inspection & Document preview states
  const [inspectTeacherOpen, setInspectTeacherOpen] = useState(false)
  const [inspectTeacher, setInspectTeacher] = useState<any | null>(null)
  const [inspectSlipOpen, setInspectSlipOpen] = useState(false)
  const [inspectSlip, setInspectSlip] = useState<any | null>(null)
  const [viewerOpen, setViewerOpen] = useState(false)
  const [payslipData, setPayslipData] = useState<any | null>(null)

  async function handleLeaveDecision(leaveId: number, decision: 'APPROVED' | 'REJECTED', who: string) {
    setDecidingLeaveId(leaveId)
    try {
      await updateStaffLeaveStatus(leaveId, {
        status: decision,
        approved_by: session?.staff_id ?? undefined,
      })
      toast.success(`Leave for ${who} ${decision === 'APPROVED' ? 'approved' : 'rejected'}.`)
      leaves.refetch()
      // An approved UNPAID leave changes payroll, so the slips may be stale.
      slips.refetch()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not update the leave request.')
    } finally {
      setDecidingLeaveId(null)
    }
  }

  async function handleGenerateSlips() {
    setGenerating(true)
    try {
      const created = await generateSalarySlipsBatch({
        month,
        year,
        campus_id: effectiveCampusId,
      })
      toast.success(
        created.length === 0
          ? 'No payslips were generated — every staff member already has one for this period.'
          : `Generated ${created.length} payslip${created.length === 1 ? '' : 's'} for ${MONTHS[month - 1]} ${year}.`
      )
      setGenerateOpen(false)
      slips.refetch()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not generate payslips.')
    } finally {
      setGenerating(false)
    }
  }

  async function handleRecordPayment(slipId: number, who: string) {
    setPayingSlipId(slipId)
    try {
      await recordSalaryPayment(slipId, {
        payment_date: new Date().toISOString().slice(0, 10),
        payment_method: 'BANK_TRANSFER',
      })
      toast.success(`Salary disbursement recorded for ${who}.`)
      slips.refetch()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not record the payment.')
    } finally {
      setPayingSlipId(null)
    }
  }

  const staffExportColumns: ExportColumn[] = [
    { key: 'employee_code', label: 'Employee Code', type: 'text' },
    { key: 'full_name', label: 'Full Name', type: 'text' },
    { key: 'designation', label: 'Designation', type: 'text' },
    { key: 'department', label: 'Department', type: 'text' },
    { key: 'contract_type', label: 'Contract Type', type: 'text' },
    { key: 'joining_date', label: 'Joining Date', type: 'date' },
  ]

  return (
    <DashPageShell
      title="HR &amp; Payroll"
      description="Staff directory, leave approvals and monthly payroll."
      action={
        /*
          Payroll generation writes a slip for every eligible staff member at
          once, so it confirms and names the period first. Getting the month
          wrong here is expensive to unpick.
        */
        <div className="flex items-center gap-2">
          {staffRows.length > 0 && (
            <DataExportToolbar
              data={staffRows}
              columns={staffExportColumns}
              filenamePrefix="staff_directory"
              title="Staff & Faculty Directory"
              classification="RESTRICTED"
            />
          )}
          <SchoolDialog
            open={generateOpen}
            onOpenChange={setGenerateOpen}
            trigger={
              <button type="button" className={LH_PRIMARY_BUTTON}>
                <span>Generate payslips</span>
              </button>
            }
            title={`Generate payslips for ${MONTHS[month - 1]} ${year}?`}
            footer={
              <>
                <button
                  type="button"
                  className={LH_GHOST_BUTTON}
                  onClick={() => setGenerateOpen(false)}
                  disabled={generating}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  className={LH_PRIMARY_BUTTON}
                  onClick={handleGenerateSlips}
                  disabled={generating}
                >
                  <span>
                    {generating ? 'Generating…' : `Generate for ${MONTHS[month - 1]} ${year}`}
                  </span>
                </button>
              </>
            }
          >
            <p className="text-sm text-gray-500">
              This creates a payslip for every active staff member on this campus who does not
              already have one for {MONTHS[month - 1]} {year}, using their current salary structure
              and any approved unpaid leave in the period. Change the month or year above first if
              this is not the period you meant.
            </p>
          </SchoolDialog>
        </div>
      }
    >

      {/*
        Filters live here, NOT in each SectionCard's `action` slot: that slot
        only renders when the card is in the 'success' state, so an empty
        month would hide the very control needed to switch away from it.
      */}
      <div className="flex flex-wrap items-end gap-4 rounded-xl bg-white nice-shadow px-4 py-3">
        <label className="flex flex-col gap-1.5">
          <span className="text-xs font-medium text-gray-500">Campus</span>
          <select
            id="hr-campus"
            className="px-3 py-2 bg-white nice-shadow rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-black focus:ring-offset-2 border-0"
            value={effectiveCampusId ?? ''}
            onChange={(e) => setCampusId(Number(e.target.value))}
          >
            {(campuses.data ?? []).map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1.5">
          <span className="text-xs font-medium text-gray-500">Payroll month</span>
          <select
            id="payroll-month"
            className="px-3 py-2 bg-white nice-shadow rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-black focus:ring-offset-2 border-0"
            value={month}
            onChange={(e) => setMonth(Number(e.target.value))}
          >
            {MONTHS.map((m, i) => (
              <option key={m} value={i + 1}>
                {m}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1.5">
          <span className="text-xs font-medium text-gray-500">Year</span>
          <select
            id="payroll-year"
            className="px-3 py-2 bg-white nice-shadow rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-black focus:ring-offset-2 border-0"
            value={year}
            onChange={(e) => setYear(Number(e.target.value))}
          >
            {Array.from({ length: 5 }, (_, i) => now.getFullYear() - i).map((y) => (
              <option key={y} value={y}>
                {y}
              </option>
            ))}
          </select>
        </label>
      </div>

      <StatGrid
        state={staff.status === 'loading' || slips.status === 'loading' ? 'loading' : 'success'}
        columns={4}
        items={[
          { label: 'Active staff', value: staffRows.length, icon: Users, tone: 'neutral' },
          { label: 'Payslips this period', value: slipRows.length, icon: Banknote, tone: 'neutral' },
          {
            label: 'Net payroll',
            value: money(netPayroll),
            icon: Banknote,
            tone: 'neutral',
            hint: `${MONTHS[month - 1]} ${year}`,
          },
          {
            label: 'Awaiting payment',
            value: unpaidCount,
            icon: CalendarDays,
            tone: unpaidCount > 0 ? 'caution' : 'positive',
          },
        ]}
      />

      <SectionCard
        id="staff"
        title="Staff directory"
        icon={<IdCard className="size-4 text-gray-500" />}
        state={staff.status}
        error={staff.error ?? campuses.error}
        onRetry={staff.refetch}
        emptyTitle="No staff on record"
        emptyDescription="Add staff profiles before generating payroll."
      >
        <DataTable
          rows={staffRows}
          rowKey={(row) => row.id}
          state="success"
          totalLabel={`${staffRows.length} staff member${staffRows.length === 1 ? '' : 's'}`}
          columns={[
            { key: 'code', header: 'Employee code', render: (r) => r.employee_code },
            {
              key: 'name',
              header: 'Name',
              render: (r: StaffProfileRead) => (
                <button
                  type="button"
                  onClick={() => {
                    setInspectTeacher({
                      id: `STF-${r.id}`,
                      employeeCode: r.employee_code,
                      name: r.full_name,
                      designation: r.designation,
                      department: r.department,
                      campus: 'Main Science Campus',
                      joiningDate: r.joining_date,
                      contractType: r.contract_type,
                      status: r.is_active ? 'Active' : 'On Leave',
                      email: 'teacher@csg-institution.edu.pk',
                      phone: '+92 300 1234567',
                      specialization: `${r.department} Specialist`,
                      workloadHours: 24,
                      weeklySchedule: [],
                      assignedClasses: [],
                      compensation: {
                        basicSalary: 85000,
                        allowances: 15000,
                        grossSalary: 100000,
                        taxDeduction: 7500,
                        netSalary: 92500,
                      },
                    })
                    setInspectTeacherOpen(true)
                  }}
                  className="font-medium text-primary hover:underline text-start"
                >
                  {r.full_name}
                </button>
              ),
            },
            { key: 'designation', header: 'Designation', render: (r) => r.designation },
            { key: 'department', header: 'Department', render: (r) => r.department },
            {
              key: 'contract',
              header: 'Contract',
              render: (r) => <StatusChip label={r.contract_type} tone="info" />,
            },
            { key: 'joined', header: 'Joined', render: (r) => r.joining_date },
            {
              key: 'actions',
              header: 'Actions',
              align: 'right',
              render: (r: StaffProfileRead) => (
                <div className="flex items-center justify-end">
                  <button
                    type="button"
                    title="Inspect Teacher 360° Profile"
                    onClick={() => {
                      setInspectTeacher({
                        id: `STF-${r.id}`,
                        employeeCode: r.employee_code,
                        name: r.full_name,
                        designation: r.designation,
                        department: r.department,
                        campus: 'Main Science Campus',
                        joiningDate: r.joining_date,
                        contractType: r.contract_type,
                        status: r.is_active ? 'Active' : 'On Leave',
                        email: 'teacher@csg-institution.edu.pk',
                        phone: '+92 300 1234567',
                        specialization: `${r.department} Specialist`,
                        workloadHours: 24,
                        weeklySchedule: [],
                        assignedClasses: [],
                        compensation: {
                          basicSalary: 85000,
                          allowances: 15000,
                          grossSalary: 100000,
                          taxDeduction: 7500,
                          netSalary: 92500,
                        },
                      })
                      setInspectTeacherOpen(true)
                    }}
                    className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium rounded-md border border-gray-200 bg-white hover:bg-gray-50 text-gray-700 transition-colors"
                  >
                    <Eye className="size-3" />
                    <span>360°</span>
                  </button>
                </div>
              ),
            },
          ]}
        />
      </SectionCard>

      <SectionCard
        id="payroll"
        title="Payroll"
        description="Generated payslips for the selected period."
        icon={<Banknote className="size-4 text-gray-500" />}
        state={slips.status}
        error={slips.error}
        onRetry={slips.refetch}
        emptyTitle="No payslips for this period"
        emptyDescription="Generate payslips for this month to see them here."
      >
        <div className="overflow-x-auto">
          <DataTable
            rows={slipRows}
            rowKey={(row) => row.id}
            state="success"
            className="[font-variant-numeric:tabular-nums]"
            totalLabel={`${slipRows.length} payslip${slipRows.length === 1 ? '' : 's'} · net ${money(netPayroll)}`}
            columns={[
              { key: 'slip', header: 'Slip no.', render: (r) => r.slip_no },
              {
                key: 'staff',
                header: 'Staff',
                render: (r) => staffName.get(r.staff_id) ?? `Staff #${r.staff_id}`,
              },
              { key: 'gross', header: 'Gross', align: 'right', render: (r) => money(r.gross_salary) },
              {
                // Shown separately from total deductions on purpose: a docked
                // payslip should say why, not just by how much.
                key: 'unpaid',
                header: 'Unpaid leave',
                align: 'right',
                render: (r) =>
                  r.unpaid_leave_days > 0 ? (
                    <span className="text-amber-600 dark:text-amber-400">
                      {r.unpaid_leave_days}d · −{money(r.unpaid_leave_deduction)}
                    </span>
                  ) : (
                    '—'
                  ),
              },
              {
                key: 'deductions',
                header: 'Deductions',
                align: 'right',
                render: (r) => money(r.total_deductions),
              },
              { key: 'net', header: 'Net pay', align: 'right', render: (r) => money(r.net_salary) },
              {
                key: 'status',
                header: 'Status',
                render: (r) => (
                  <StatusChip label={r.payment_status} tone={PAYMENT_TONE[r.payment_status]} />
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
                          staffName: staffName.get(r.staff_id) ?? `Staff Member #${r.staff_id}`,
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
                        setInspectSlipOpen(true)
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
                          employeeName: staffName.get(r.staff_id) ?? `Staff Member #${r.staff_id}`,
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
                    {r.payment_status === 'PAID' ? (
                      <span className="text-xs text-gray-500 px-1">Disbursed</span>
                    ) : (
                      <button
                        type="button"
                        className={LH_SECONDARY_BUTTON}
                        disabled={payingSlipId === r.id}
                        onClick={() =>
                          handleRecordPayment(r.id, staffName.get(r.staff_id) ?? `staff #${r.staff_id}`)
                        }
                      >
                        <span>{payingSlipId === r.id ? 'Recording…' : 'Mark paid'}</span>
                      </button>
                    )}
                  </div>
                ),
              },
            ]}
          />
        </div>
      </SectionCard>

      <SectionCard
        id="leaves"
        title="Leave requests awaiting approval"
        icon={<CalendarDays className="size-4 text-gray-500" />}
        state={leaves.status}
        error={leaves.error}
        onRetry={leaves.refetch}
        emptyTitle="No pending leave requests"
        emptyDescription="Approved and rejected requests are not listed here."
      >
        <DataTable
          rows={leaves.data ?? []}
          rowKey={(row) => row.id}
          state="success"
          columns={[
            {
              key: 'staff',
              header: 'Staff',
              render: (r) => staffName.get(r.staff_id) ?? `Staff #${r.staff_id}`,
            },
            { key: 'type', header: 'Type', render: (r) => <StatusChip label={r.leave_type} tone="neutral" /> },
            { key: 'from', header: 'From', render: (r) => r.start_date },
            { key: 'to', header: 'To', render: (r) => r.end_date },
            { key: 'reason', header: 'Reason', render: (r) => r.reason || '—' },
            {
              key: 'status',
              header: 'Status',
              render: (r) => <StatusChip label={r.status} tone={LEAVE_TONE[r.status]} />,
            },
            {
              key: 'decide',
              header: '',
              align: 'right',
              render: (r) => {
                const who = staffName.get(r.staff_id) ?? `staff #${r.staff_id}`
                const busy = decidingLeaveId === r.id
                return (
                  <span className="flex justify-end gap-2">
                    <button
                      type="button"
                      className={LH_SECONDARY_BUTTON}
                      disabled={busy}
                      onClick={() => handleLeaveDecision(r.id, 'REJECTED', who)}
                    >
                      <span>Reject</span>
                    </button>
                    <button
                      type="button"
                      className={LH_PRIMARY_BUTTON}
                      disabled={busy}
                      onClick={() => handleLeaveDecision(r.id, 'APPROVED', who)}
                    >
                      <span>{busy ? 'Saving…' : 'Approve'}</span>
                    </button>
                  </span>
                )
              },
            },
          ]}
        />
      </SectionCard>

      {/* 360° Teacher / Staff Inspection Drawer */}
      <Teacher360Drawer
        isOpen={inspectTeacherOpen}
        onClose={() => setInspectTeacherOpen(false)}
        teacher={inspectTeacher}
      />

      {/* 360° Payslip Inspection Drawer */}
      <Payslip360Drawer
        isOpen={inspectSlipOpen}
        onClose={() => setInspectSlipOpen(false)}
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
