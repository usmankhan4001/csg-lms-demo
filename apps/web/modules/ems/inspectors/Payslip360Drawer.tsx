'use client'

import React, { useState } from 'react'
import {
  FileText,
  DollarSign,
  ShieldCheck,
  ShieldAlert,
  Download,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Printer,
  Users,
  Building2,
  Layers,
  ChevronRight,
  Sparkles,
  Lock,
  UserCheck,
  Send,
  Ban,
  Check,
} from 'lucide-react'
import { Entity360Drawer, Entity360Tab, Entity360Badge, Entity360QuickAction } from '@/components/ems/Entity360Drawer'
import { StaffPayrollRecord, ProgressiveTaxTier } from '../payroll/PayrollProcessingStudio'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog'
import toast from 'react-hot-toast'

export interface Payslip360DrawerProps {
  isOpen: boolean
  onClose: () => void
  record?: StaffPayrollRecord | null
  taxBrackets?: ProgressiveTaxTier[]
  onAuthorize?: (slipId: number) => void
}

const DEFAULT_TAX_TIERS: ProgressiveTaxTier[] = [
  { name: 'Tier 1: Tax-Exempt Base ($0 - $1,000)', lower: 0, upper: 1000, rate: 0.0 },
  { name: 'Tier 2: Standard Base ($1,000 - $3,000)', lower: 1000, upper: 3000, rate: 0.10 },
  { name: 'Tier 3: Mid-Income ($3,000 - $6,000)', lower: 3000, upper: 6000, rate: 0.15 },
  { name: 'Tier 4: Senior Faculty ($6,000 - $10,000)', lower: 6000, upper: 10000, rate: 0.20 },
  { name: 'Tier 5: Executive (> $10,000)', lower: 10000, upper: null, rate: 0.25 },
]

const DEFAULT_RECORD: StaffPayrollRecord = {
  id: 1,
  slipNo: 'SLIP-PROG-202609-101-A48F',
  staffId: 101,
  staffName: 'Dr. Eleanor Vance',
  department: 'STEM & Robotics',
  role: 'Lead Professor',
  month: 9,
  year: 2026,
  basic: 7500,
  housingAllowance: 1500,
  medicalAllowance: 600,
  otherAllowances: 400,
  unpaidLeaveDays: 0,
  unpaidLeaveDeduction: 0,
  providentFund: 450,
  taxDeduction: 1250,
  otherDeductions: 0,
  grossSalary: 10000,
  totalDeductions: 1700,
  netSalary: 8300,
  wasClamped: false,
  status: 'APPROVED',
  preparerUserId: 12,
  preparerName: 'Sarah Ahmed (Finance Officer)',
  approverUserId: 4,
  approverName: 'Usman Khan (Bursar / SuperAdmin)',
  paymentDate: '2026-09-28',
  paymentMethod: 'Direct Bank Wire (HBL Corp)',
  notes: 'Quarterly STEM curriculum revision bonus included in allowances.',
}

export const Payslip360Drawer: React.FC<Payslip360DrawerProps> = ({
  isOpen,
  onClose,
  record = DEFAULT_RECORD,
  taxBrackets = DEFAULT_TAX_TIERS,
  onAuthorize,
}) => {
  const currentRecord = record || DEFAULT_RECORD
  const [activeTab, setActiveTab] = useState<string>('overview')
  const [isPdfModalOpen, setIsPdfModalOpen] = useState<boolean>(false)

  const monthNames = ['', 'January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
  const periodLabel = `${monthNames[currentRecord.month]} ${currentRecord.year}`

  const tabs: Entity360Tab[] = [
    { id: 'overview', label: 'Salary Overview', icon: <DollarSign className="h-3.5 w-3.5" /> },
    { id: 'earnings', label: 'Earnings & Allowances', icon: <Sparkles className="h-3.5 w-3.5" /> },
    { id: 'tax', label: 'Statutory Deductions & Tax', icon: <ShieldCheck className="h-3.5 w-3.5" /> },
    { id: 'audit', label: 'Dual-Authorization Audit', icon: <Lock className="h-3.5 w-3.5" /> },
  ]

  const badges: Entity360Badge[] = [
    {
      label: currentRecord.status,
      variant:
        currentRecord.status === 'PAID'
          ? 'success'
          : currentRecord.status === 'APPROVED'
          ? 'blue'
          : currentRecord.status === 'REJECTED'
          ? 'destructive'
          : 'warning',
    },
    { label: periodLabel, variant: 'purple' },
    { label: currentRecord.department, variant: 'amber' },
  ]

  const quickActions: Entity360QuickAction[] = [
    {
      label: 'Download Payslip PDF',
      icon: <Download className="h-3.5 w-3.5" />,
      onClick: () => setIsPdfModalOpen(true),
      variant: 'default',
    },
    {
      label: currentRecord.status === 'PENDING' ? 'Authorize Run' : 'Authorized',
      icon: <CheckCircle2 className="h-3.5 w-3.5" />,
      onClick: () => {
        if (onAuthorize) onAuthorize(currentRecord.id)
        toast.success(`Payslip #${currentRecord.slipNo} dual-authorization completed!`)
      },
      disabled: currentRecord.status !== 'PENDING',
      variant: 'primary',
    },
  ]

  return (
    <>
      <Entity360Drawer
        isOpen={isOpen}
        onClose={onClose}
        title={currentRecord.staffName}
        subtitle={`Slip #${currentRecord.slipNo} • ${currentRecord.role} • ${periodLabel}`}
        entityTypeBadge="Staff Payslip 360°"
        avatar={{
          initials: currentRecord.staffName.replace('Dr. ', '').slice(0, 2).toUpperCase(),
          statusDot: currentRecord.status === 'PAID' || currentRecord.status === 'APPROVED' ? 'online' : 'away',
          bgClass: 'bg-gradient-to-br from-emerald-600 to-teal-700 text-white',
        }}
        badges={badges}
        quickActions={quickActions}
        tabs={tabs}
        activeTab={activeTab}
        onTabChange={setActiveTab}
        metaBar={
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
            <div className="flex items-center gap-2 p-2 rounded-lg bg-zinc-100/80 dark:bg-zinc-800/60 border border-zinc-200/50 dark:border-zinc-700/50">
              <DollarSign className="h-4 w-4 text-emerald-500 shrink-0" />
              <div>
                <p className="text-[10px] text-zinc-400 font-medium">Net Take-Home</p>
                <p className="font-bold text-emerald-600 dark:text-emerald-400 text-sm">${currentRecord.netSalary.toLocaleString()}</p>
              </div>
            </div>
            <div className="flex items-center gap-2 p-2 rounded-lg bg-zinc-100/80 dark:bg-zinc-800/60 border border-zinc-200/50 dark:border-zinc-700/50">
              <Sparkles className="h-4 w-4 text-indigo-500 shrink-0" />
              <div>
                <p className="text-[10px] text-zinc-400 font-medium">Gross Salary</p>
                <p className="font-bold text-zinc-900 dark:text-zinc-100">${currentRecord.grossSalary.toLocaleString()}</p>
              </div>
            </div>
            <div className="flex items-center gap-2 p-2 rounded-lg bg-zinc-100/80 dark:bg-zinc-800/60 border border-zinc-200/50 dark:border-zinc-700/50">
              <ShieldCheck className="h-4 w-4 text-rose-500 shrink-0" />
              <div>
                <p className="text-[10px] text-zinc-400 font-medium">Tax & Deductions</p>
                <p className="font-bold text-rose-600 dark:text-rose-400">-${currentRecord.totalDeductions.toLocaleString()}</p>
              </div>
            </div>
            <div className="flex items-center gap-2 p-2 rounded-lg bg-zinc-100/80 dark:bg-zinc-800/60 border border-zinc-200/50 dark:border-zinc-700/50">
              <UserCheck className="h-4 w-4 text-purple-500 shrink-0" />
              <div>
                <p className="text-[10px] text-zinc-400 font-medium">Approval Status</p>
                <p className="font-bold text-purple-600 dark:text-purple-400">{currentRecord.status}</p>
              </div>
            </div>
          </div>
        }
      >
        {/* TAB 1: OVERVIEW */}
        {activeTab === 'overview' && (
          <div className="space-y-6">
            <div className="rounded-xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900 shadow-xs">
              <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-400 mb-4 flex items-center gap-2">
                <FileText className="h-4 w-4 text-indigo-500" />
                Staff Employment & Payroll Voucher Specifications
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
                <div>
                  <span className="text-zinc-400">Staff Member</span>
                  <p className="font-semibold text-zinc-900 dark:text-zinc-100 mt-0.5">{currentRecord.staffName}</p>
                </div>
                <div>
                  <span className="text-zinc-400">Department</span>
                  <p className="font-semibold text-zinc-900 dark:text-zinc-100 mt-0.5">{currentRecord.department}</p>
                </div>
                <div>
                  <span className="text-zinc-400">Designation / Role</span>
                  <p className="font-semibold text-zinc-900 dark:text-zinc-100 mt-0.5">{currentRecord.role}</p>
                </div>
                <div>
                  <span className="text-zinc-400">Voucher Reference</span>
                  <p className="font-semibold text-zinc-900 dark:text-zinc-100 mt-0.5 font-mono">{currentRecord.slipNo}</p>
                </div>
                <div>
                  <span className="text-zinc-400">Payment Period</span>
                  <p className="font-semibold text-zinc-900 dark:text-zinc-100 mt-0.5">{periodLabel}</p>
                </div>
                <div>
                  <span className="text-zinc-400">Disbursal Method</span>
                  <p className="font-semibold text-zinc-900 dark:text-zinc-100 mt-0.5">{currentRecord.paymentMethod || 'Wire Transfer'}</p>
                </div>
              </div>
            </div>

            {/* Clamped Notification if applicable */}
            {currentRecord.wasClamped && (
              <div className="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center gap-3 text-amber-800 dark:text-amber-300 text-xs">
                <AlertTriangle className="h-5 w-5 shrink-0" />
                <div>
                  <p className="font-bold">Zero Net Clamping Protection Active</p>
                  <p>Deductions exceeded gross salary. Total deductions were clamped to guarantee non-negative take-home.</p>
                </div>
              </div>
            )}
          </div>
        )}

        {/* TAB 2: EARNINGS & ALLOWANCES */}
        {activeTab === 'earnings' && (
          <div className="space-y-4">
            <h3 className="text-sm font-bold text-zinc-900 dark:text-zinc-100">Itemized Gross Earnings Schedule</h3>
            <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 overflow-hidden text-xs">
              <table className="w-full text-left">
                <thead className="bg-zinc-50/80 dark:bg-zinc-800/50 text-zinc-400 uppercase font-semibold border-b border-zinc-200 dark:border-zinc-800">
                  <tr>
                    <th className="py-2.5 px-4">Component</th>
                    <th className="py-2.5 px-4">Type</th>
                    <th className="py-2.5 px-4 text-right">Amount (USD)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800">
                  <tr className="hover:bg-zinc-50/50">
                    <td className="py-3 px-4 font-semibold text-zinc-900 dark:text-zinc-100">Base Salary</td>
                    <td className="py-3 px-4"><span className="px-2 py-0.5 rounded bg-zinc-100 dark:bg-zinc-800 text-[10px]">Fixed</span></td>
                    <td className="py-3 px-4 text-right font-mono font-bold">${currentRecord.basic.toLocaleString()}</td>
                  </tr>
                  <tr className="hover:bg-zinc-50/50">
                    <td className="py-3 px-4 font-semibold text-zinc-900 dark:text-zinc-100">Housing Allowance</td>
                    <td className="py-3 px-4"><span className="px-2 py-0.5 rounded bg-zinc-100 dark:bg-zinc-800 text-[10px]">Benefit</span></td>
                    <td className="py-3 px-4 text-right font-mono font-bold">${currentRecord.housingAllowance.toLocaleString()}</td>
                  </tr>
                  <tr className="hover:bg-zinc-50/50">
                    <td className="py-3 px-4 font-semibold text-zinc-900 dark:text-zinc-100">Medical Allowance</td>
                    <td className="py-3 px-4"><span className="px-2 py-0.5 rounded bg-zinc-100 dark:bg-zinc-800 text-[10px]">Benefit</span></td>
                    <td className="py-3 px-4 text-right font-mono font-bold">${currentRecord.medicalAllowance.toLocaleString()}</td>
                  </tr>
                  {currentRecord.otherAllowances > 0 && (
                    <tr className="hover:bg-zinc-50/50">
                      <td className="py-3 px-4 font-semibold text-zinc-900 dark:text-zinc-100">Special Duty / Research Stipend</td>
                      <td className="py-3 px-4"><span className="px-2 py-0.5 rounded bg-zinc-100 dark:bg-zinc-800 text-[10px]">Allowance</span></td>
                      <td className="py-3 px-4 text-right font-mono font-bold">${currentRecord.otherAllowances.toLocaleString()}</td>
                    </tr>
                  )}
                </tbody>
                <tfoot className="bg-zinc-50/90 dark:bg-zinc-800/70 border-t border-zinc-200 dark:border-zinc-800 font-bold">
                  <tr>
                    <td colSpan={2} className="py-3 px-4 text-right">Total Gross Earnings:</td>
                    <td className="py-3 px-4 text-right font-mono font-black text-indigo-600 dark:text-indigo-400">${currentRecord.grossSalary.toLocaleString()}</td>
                  </tr>
                </tfoot>
              </table>
            </div>
          </div>
        )}

        {/* TAB 3: DEDUCTIONS & PROGRESSIVE TAX */}
        {activeTab === 'tax' && (
          <div className="space-y-4">
            <h3 className="text-sm font-bold text-zinc-900 dark:text-zinc-100">Progressive Statutory Income Tax & Benefit Deductions</h3>
            <div className="p-4 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 space-y-3 text-xs">
              <h4 className="font-bold text-zinc-900 dark:text-zinc-100 uppercase tracking-wider text-[11px]">Applied Progressive Tax Brackets</h4>
              <div className="space-y-2">
                {taxBrackets.map((tier, idx) => (
                  <div key={idx} className="flex justify-between items-center p-2 rounded-lg bg-zinc-50 dark:bg-zinc-800/50">
                    <span>{tier.name}</span>
                    <span className="font-mono font-bold text-zinc-700 dark:text-zinc-300">{(tier.rate * 100).toFixed(0)}% Marginal</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 overflow-hidden text-xs">
              <table className="w-full text-left">
                <thead className="bg-zinc-50/80 dark:bg-zinc-800/50 text-zinc-400 uppercase font-semibold border-b border-zinc-200 dark:border-zinc-800">
                  <tr>
                    <th className="py-2.5 px-4">Deduction Type</th>
                    <th className="py-2.5 px-4 text-right">Amount (USD)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800">
                  <tr>
                    <td className="py-3 px-4 text-zinc-900 dark:text-zinc-100 font-semibold">Progressive Withholding Income Tax</td>
                    <td className="py-3 px-4 text-right font-mono font-bold text-rose-600">-${currentRecord.taxDeduction.toLocaleString()}</td>
                  </tr>
                  <tr>
                    <td className="py-3 px-4 text-zinc-900 dark:text-zinc-100 font-semibold">Provident Fund (Retirement)</td>
                    <td className="py-3 px-4 text-right font-mono font-bold text-rose-600">-${currentRecord.providentFund.toLocaleString()}</td>
                  </tr>
                  {currentRecord.unpaidLeaveDeduction > 0 && (
                    <tr>
                      <td className="py-3 px-4 text-zinc-900 dark:text-zinc-100 font-semibold">Unpaid Leave Penalty ({currentRecord.unpaidLeaveDays} Days)</td>
                      <td className="py-3 px-4 text-right font-mono font-bold text-rose-600">-${currentRecord.unpaidLeaveDeduction.toLocaleString()}</td>
                    </tr>
                  )}
                </tbody>
                <tfoot className="bg-zinc-50/90 dark:bg-zinc-800/70 border-t border-zinc-200 dark:border-zinc-800 font-bold">
                  <tr>
                    <td className="py-3 px-4 text-right">Total Statutory Deductions:</td>
                    <td className="py-3 px-4 text-right font-mono font-black text-rose-600">-${currentRecord.totalDeductions.toLocaleString()}</td>
                  </tr>
                </tfoot>
              </table>
            </div>
          </div>
        )}

        {/* TAB 4: DUAL-AUTHORIZATION AUDIT */}
        {activeTab === 'audit' && (
          <div className="space-y-4">
            <h3 className="text-sm font-bold text-zinc-900 dark:text-zinc-100">Dual-Signatory Cryptographic Audit Trail</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="p-4 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 space-y-2 text-xs">
                <div className="flex items-center gap-2 text-emerald-600 dark:text-emerald-400 font-bold">
                  <CheckCircle2 className="h-4 w-4" />
                  Signatory 1: Prepared by Finance Officer
                </div>
                <p className="font-semibold text-zinc-900 dark:text-zinc-100">{currentRecord.preparerName}</p>
                <p className="text-[11px] text-zinc-400">User ID: #{currentRecord.preparerUserId} • Timestamp: 2026-09-16 09:15 PKT</p>
                <p className="text-[10px] font-mono text-zinc-400 pt-1">Sig Hash: 8f4a21...91b8</p>
              </div>

              <div className="p-4 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 space-y-2 text-xs">
                <div className="flex items-center gap-2 text-indigo-600 dark:text-indigo-400 font-bold">
                  <CheckCircle2 className="h-4 w-4" />
                  Signatory 2: Authorized by Bursar
                </div>
                <p className="font-semibold text-zinc-900 dark:text-zinc-100">{currentRecord.approverName || 'Pending Bursar Authorization'}</p>
                <p className="text-[11px] text-zinc-400">User ID: #{currentRecord.approverUserId || '--'} • Timestamp: {currentRecord.paymentDate || 'Pending'}</p>
                <p className="text-[10px] font-mono text-zinc-400 pt-1">Sig Hash: e93c12...41a0</p>
              </div>
            </div>
          </div>
        )}
      </Entity360Drawer>

      {/* PAYSLIP PREVIEW MODAL */}
      <Dialog open={isPdfModalOpen} onOpenChange={setIsPdfModalOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Official Staff Salary Voucher</DialogTitle>
            <DialogDescription>CSG Educational Management System</DialogDescription>
          </DialogHeader>
          <div className="p-4 bg-zinc-50 dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800 space-y-3 text-xs">
            <div className="flex justify-between items-center border-b pb-2">
              <span className="font-bold">{currentRecord.staffName} ({currentRecord.department})</span>
              <span className="font-mono text-emerald-600 font-bold">Net: ${currentRecord.netSalary.toLocaleString()}</span>
            </div>
            <p className="text-zinc-500 text-[11px]">Voucher No: {currentRecord.slipNo}</p>
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={() => {
                toast.success('Payslip PDF downloaded')
                setIsPdfModalOpen(false)
              }}
              className="px-4 py-2 text-xs font-semibold rounded-lg bg-indigo-600 text-white flex items-center gap-1.5"
            >
              <Download className="h-3.5 w-3.5" />
              Download Official PDF
            </button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}
