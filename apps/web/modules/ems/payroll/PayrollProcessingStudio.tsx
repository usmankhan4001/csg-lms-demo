'use client'

import React, { useState, useMemo } from 'react'
import {
  DollarSign,
  Users,
  ShieldCheck,
  ShieldAlert,
  FileText,
  Calculator,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Send,
  Eye,
  Download,
  Printer,
  X,
  Check,
  Ban,
  Building2,
  Calendar,
  Layers,
  ArrowRight,
  TrendingDown,
  Info,
  Sparkles,
  Search,
  Filter,
} from 'lucide-react'
import { Payslip360Drawer } from '../inspectors'

export interface ProgressiveTaxTier {
  name: string
  lower: number
  upper: number | null
  rate: number
}

export interface StaffPayrollRecord {
  id: number
  slipNo: string
  staffId: number
  staffName: string
  department: string
  role: string
  month: number
  year: number
  basic: number
  housingAllowance: number
  medicalAllowance: number
  otherAllowances: number
  unpaidLeaveDays: number
  unpaidLeaveDeduction: number
  providentFund: number
  taxDeduction: number
  otherDeductions: number
  grossSalary: number
  totalDeductions: number
  netSalary: number
  wasClamped: boolean
  status: 'PENDING' | 'APPROVED' | 'REJECTED' | 'PAID'
  preparerUserId: number
  preparerName: string
  approverUserId?: number
  approverName?: string
  paymentDate?: string
  paymentMethod?: string
  notes?: string
}

export interface PayrollAuditAction {
  id: number
  slipId: number
  action: 'PREPARED' | 'APPROVED' | 'REJECTED' | 'PAID'
  actorUserId: number
  actorName: string
  timestamp: string
  netSalaryAtAction: number
  note?: string
}

const DEFAULT_TAX_BRACKETS: ProgressiveTaxTier[] = [
  { name: 'Tax-Exempt Allowance Tier (0%)', lower: 0, upper: 1000, rate: 0.0 },
  { name: 'Standard Base Tier (10%)', lower: 1000, upper: 3000, rate: 0.10 },
  { name: 'Mid-Income Bracket (15%)', lower: 3000, upper: 6000, rate: 0.15 },
  { name: 'Upper-Mid Bracket (20%)', lower: 6000, upper: 10000, rate: 0.20 },
  { name: 'Executive / Top Tier (25%)', lower: 10000, upper: null, rate: 0.25 },
]

const INITIAL_STAFF_PAYROLL: StaffPayrollRecord[] = [
  {
    id: 1,
    slipNo: 'SLIP-PROG-202609-101-A48F',
    staffId: 101,
    staffName: 'Dr. Eleanor Vance',
    department: 'STEM & Robotics',
    role: 'Lead Professor',
    month: 9,
    year: 2026,
    basic: 7500,
    housingAllowance: 1200,
    medicalAllowance: 500,
    otherAllowances: 300,
    unpaidLeaveDays: 1,
    unpaidLeaveDeduction: 250,
    providentFund: 362.5,
    taxDeduction: 1125.0,
    otherDeductions: 0,
    grossSalary: 9500,
    totalDeductions: 1737.5,
    netSalary: 7762.5,
    wasClamped: false,
    status: 'PENDING',
    preparerUserId: 1,
    preparerName: 'Sarah Jenkins (Payroll Clerk)',
  },
  {
    id: 2,
    slipNo: 'SLIP-PROG-202609-102-B72D',
    staffId: 102,
    staffName: 'Marcus Thorne',
    department: 'Humanities & Arts',
    role: 'Senior Lecturer',
    month: 9,
    year: 2026,
    basic: 4500,
    housingAllowance: 800,
    medicalAllowance: 350,
    otherAllowances: 150,
    unpaidLeaveDays: 0,
    unpaidLeaveDeduction: 0,
    providentFund: 225.0,
    taxDeduction: 495.0,
    otherDeductions: 100,
    grossSalary: 5800,
    totalDeductions: 820.0,
    netSalary: 4980.0,
    wasClamped: false,
    status: 'PENDING',
    preparerUserId: 1,
    preparerName: 'Sarah Jenkins (Payroll Clerk)',
  },
  {
    id: 3,
    slipNo: 'SLIP-PROG-202609-103-C99E',
    staffId: 103,
    staffName: 'Amina Al-Mansoor',
    department: 'Campus Administration',
    role: 'Operations Coordinator',
    month: 9,
    year: 2026,
    basic: 2800,
    housingAllowance: 400,
    medicalAllowance: 200,
    otherAllowances: 100,
    unpaidLeaveDays: 0,
    unpaidLeaveDeduction: 0,
    providentFund: 140.0,
    taxDeduction: 200.0,
    otherDeductions: 0,
    grossSalary: 3500,
    totalDeductions: 340.0,
    netSalary: 3160.0,
    wasClamped: false,
    status: 'APPROVED',
    preparerUserId: 2,
    preparerName: 'Tariq Mehmood (Finance Officer)',
    approverUserId: 99,
    approverName: 'Dean of Administration',
  },
]

export interface PayrollProcessingStudioProps {
  currentUserId?: number
  currentUserName?: string
  currentUserRole?: string
  campusName?: string
}

export function PayrollProcessingStudio({
  currentUserId = 99, // Current User is Dean / Approver (different from Preparer #1 Sarah)
  currentUserName = 'Dr. Robert Sterling (Dean of Operations)',
  currentUserRole = 'SCHOOL_ADMIN',
  campusName = 'Main Academic Campus',
}: PayrollProcessingStudioProps) {
  const [activeTab, setActiveTab] = useState<'roster' | 'tax_matrix' | 'approvals'>('roster')
  const [selectedMonth, setSelectedMonth] = useState<number>(9)
  const [selectedYear, setSelectedYear] = useState<number>(2026)
  const [staffPayroll, setStaffPayroll] = useState<StaffPayrollRecord[]>(INITIAL_STAFF_PAYROLL)
  const [selectedPayslip, setSelectedPayslip] = useState<StaffPayrollRecord | null>(null)
  const [interactiveTaxSalary, setInteractiveTaxSalary] = useState<number>(6500)
  const [searchQuery, setSearchQuery] = useState('')
  const [feedbackBanner, setFeedbackBanner] = useState<{ type: 'success' | 'error' | 'warning'; message: string } | null>(null)

  // Interactive Tax Bracket Calculation
  const interactiveTaxCalculation = useMemo(() => {
    let totalTax = 0
    const income = Math.max(0, interactiveTaxSalary)
    const breakdown = DEFAULT_TAX_BRACKETS.map((tier) => {
      if (income <= tier.lower) {
        return { ...tier, taxableInTier: 0, taxInTier: 0 }
      }
      const cap = tier.upper !== null ? Math.min(income, tier.upper) : income
      const taxableInTier = cap - tier.lower
      const taxInTier = taxableInTier * tier.rate
      totalTax += taxInTier
      return { ...tier, taxableInTier, taxInTier }
    })
    const effectiveRate = income > 0 ? (totalTax / income) * 100 : 0
    return { income, totalTax, effectiveRate, breakdown }
  }, [interactiveTaxSalary])

  // Roster Aggregates
  const stats = useMemo(() => {
    let totalGross = 0
    let totalTax = 0
    let totalPension = 0
    let totalNet = 0
    let pendingCount = 0
    let approvedCount = 0
    let paidCount = 0

    staffPayroll.forEach((s) => {
      totalGross += s.grossSalary
      totalTax += s.taxDeduction
      totalPension += s.providentFund
      totalNet += s.netSalary
      if (s.status === 'PENDING') pendingCount++
      else if (s.status === 'APPROVED') approvedCount++
      else if (s.status === 'PAID') paidCount++
    })

    return { totalGross, totalTax, totalPension, totalNet, pendingCount, approvedCount, paidCount }
  }, [staffPayroll])

  // Dual Authorization Actions
  const handleApproveSlip = (slip: StaffPayrollRecord) => {
    // Strict Segregation of Duties Check
    if (slip.preparerUserId === currentUserId) {
      setFeedbackBanner({
        type: 'error',
        message: `Segregation of Duties Violation: You (${currentUserName}) prepared this slip. Approval requires a distinct reviewer.`,
      })
      return
    }

    setStaffPayroll((prev) =>
      prev.map((s) =>
        s.id === slip.id
          ? {
              ...s,
              status: 'APPROVED',
              approverUserId: currentUserId,
              approverName: currentUserName,
            }
          : s
      )
    )
    setFeedbackBanner({
      type: 'success',
      message: `Salary Slip ${slip.slipNo} for ${slip.staffName} approved for disbursement!`,
    })
  }

  const handleRejectSlip = (slip: StaffPayrollRecord) => {
    setStaffPayroll((prev) =>
      prev.map((s) =>
        s.id === slip.id
          ? {
              ...s,
              status: 'REJECTED',
              approverUserId: currentUserId,
              approverName: currentUserName,
            }
          : s
      )
    )
    setFeedbackBanner({
      type: 'warning',
      message: `Salary Slip ${slip.slipNo} rejected and sent back to preparer for revision.`,
    })
  }

  const handleDisburseSlip = (slip: StaffPayrollRecord) => {
    if (slip.status !== 'APPROVED') {
      setFeedbackBanner({
        type: 'error',
        message: 'Slip must be approved by a designated reviewer before disbursement can occur.',
      })
      return
    }

    setStaffPayroll((prev) =>
      prev.map((s) =>
        s.id === slip.id
          ? {
              ...s,
              status: 'PAID',
              paymentDate: new Date().toISOString().split('T')[0],
              paymentMethod: 'DIRECT_DEPOSIT_BANK_TRANSFER',
            }
          : s
      )
    )
    setFeedbackBanner({
      type: 'success',
      message: `Disbursed $${slip.netSalary.toLocaleString()} to ${slip.staffName} via Direct Bank Transfer!`,
    })
  }

  // Filtered staff
  const filteredRoster = staffPayroll.filter(
    (s) =>
      s.staffName.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.department.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.slipNo.toLowerCase().includes(searchQuery.toLowerCase())
  )

  return (
    <div className="flex flex-col w-full h-full min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 p-4 md:p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white dark:bg-slate-900 p-5 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-indigo-600/10 dark:bg-indigo-500/20 text-indigo-600 dark:text-indigo-400 flex items-center justify-center font-bold">
            <DollarSign className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-white">
                Progressive Payroll & Dual-Authorization Studio
              </h1>
              <span className="px-2.5 py-0.5 text-xs font-semibold rounded-full bg-indigo-100 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-400 border border-indigo-300 dark:border-indigo-800">
                Segregation of Duties
              </span>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              {campusName} • Actor: <span className="font-semibold text-slate-700 dark:text-slate-300">{currentUserName}</span> ({currentUserRole})
            </p>
          </div>
        </div>

        {/* Global Key Metrics */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700">
            <Users className="w-4 h-4 text-indigo-500" />
            <span className="text-xs font-medium text-slate-600 dark:text-slate-300">Net Payroll:</span>
            <span className="text-xs font-bold text-slate-900 dark:text-white">
              ${stats.totalNet.toLocaleString(undefined, { minimumFractionDigits: 2 })}
            </span>
          </div>

          <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700">
            <ShieldCheck className="w-4 h-4 text-emerald-500" />
            <span className="text-xs font-medium text-slate-600 dark:text-slate-300">Approval Queue:</span>
            <span className="text-xs font-bold text-amber-600 dark:text-amber-400">
              {stats.pendingCount} Pending
            </span>
          </div>
        </div>
      </div>

      {/* Feedback Banner */}
      {feedbackBanner && (
        <div
          className={`flex items-center justify-between p-4 rounded-xl text-sm font-medium border animate-in fade-in duration-200 ${
            feedbackBanner.type === 'success'
              ? 'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-800 dark:text-emerald-300 border-emerald-300 dark:border-emerald-800'
              : feedbackBanner.type === 'warning'
              ? 'bg-amber-50 dark:bg-amber-950/40 text-amber-800 dark:text-amber-300 border-amber-300 dark:border-amber-800'
              : 'bg-rose-50 dark:bg-rose-950/40 text-rose-800 dark:text-rose-300 border-rose-300 dark:border-rose-800'
          }`}
        >
          <div className="flex items-center gap-2">
            {feedbackBanner.type === 'success' ? (
              <CheckCircle2 className="w-5 h-5 shrink-0 text-emerald-500" />
            ) : feedbackBanner.type === 'warning' ? (
              <AlertTriangle className="w-5 h-5 shrink-0 text-amber-500" />
            ) : (
              <ShieldAlert className="w-5 h-5 shrink-0 text-rose-500" />
            )}
            <span>{feedbackBanner.message}</span>
          </div>
          <button onClick={() => setFeedbackBanner(null)} className="p-1 hover:opacity-75">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Tabs */}
      <div className="flex border-b border-slate-200 dark:border-slate-800 gap-2">
        <button
          onClick={() => setActiveTab('roster')}
          className={`flex items-center gap-2 px-4 py-2.5 text-sm font-semibold border-b-2 transition-all ${
            activeTab === 'roster'
              ? 'border-indigo-600 text-indigo-600 dark:text-indigo-400 dark:border-indigo-400 bg-indigo-50/50 dark:bg-indigo-950/30 rounded-t-lg'
              : 'border-transparent text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
          }`}
        >
          <Users className="w-4 h-4" />
          Monthly Payroll Run
        </button>

        <button
          onClick={() => setActiveTab('tax_matrix')}
          className={`flex items-center gap-2 px-4 py-2.5 text-sm font-semibold border-b-2 transition-all ${
            activeTab === 'tax_matrix'
              ? 'border-indigo-600 text-indigo-600 dark:text-indigo-400 dark:border-indigo-400 bg-indigo-50/50 dark:bg-indigo-950/30 rounded-t-lg'
              : 'border-transparent text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
          }`}
        >
          <Calculator className="w-4 h-4" />
          Progressive Tax Matrix
        </button>

        <button
          onClick={() => setActiveTab('approvals')}
          className={`flex items-center gap-2 px-4 py-2.5 text-sm font-semibold border-b-2 transition-all ${
            activeTab === 'approvals'
              ? 'border-indigo-600 text-indigo-600 dark:text-indigo-400 dark:border-indigo-400 bg-indigo-50/50 dark:bg-indigo-950/30 rounded-t-lg'
              : 'border-transparent text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
          }`}
        >
          <ShieldCheck className="w-4 h-4" />
          Dual-Authorization Queue
        </button>
      </div>

      {/* TAB 1: Monthly Payroll Run */}
      {activeTab === 'roster' && (
        <div className="bg-white dark:bg-slate-900 p-6 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-6">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <h2 className="text-lg font-bold text-slate-900 dark:text-white">Academic Faculty & Staff Roster</h2>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Progressive taxation, pension fund contributions (5%), and non-negative clamping evaluated.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <div className="relative">
                <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
                <input
                  type="text"
                  placeholder="Search staff, slip or dept..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="text-xs pl-9 pr-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <button className="flex items-center gap-1.5 px-4 py-2 text-xs font-bold rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white shadow-sm">
                <Sparkles className="w-4 h-4" />
                Generate New Batch Run
              </button>
            </div>
          </div>

          {/* Roster Table */}
          <div className="border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-100 dark:bg-slate-800/80 text-xs font-bold text-slate-600 dark:text-slate-300">
                <tr>
                  <th className="p-3.5">Staff & Designation</th>
                  <th className="p-3.5">Slip #</th>
                  <th className="p-3.5 text-right">Basic</th>
                  <th className="p-3.5 text-right">Gross</th>
                  <th className="p-3.5 text-right">Tax (Tiered)</th>
                  <th className="p-3.5 text-right">Pension (5%)</th>
                  <th className="p-3.5 text-right">Net Salary</th>
                  <th className="p-3.5 text-center">Status</th>
                  <th className="p-3.5 text-center w-28">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                {filteredRoster.map((slip) => (
                  <tr key={slip.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors text-xs">
                    <td className="p-3.5">
                      <div className="font-bold text-slate-900 dark:text-white">{slip.staffName}</div>
                      <div className="text-[11px] text-slate-500">{slip.role} • {slip.department}</div>
                    </td>
                    <td className="p-3.5 font-mono text-slate-600 dark:text-slate-400">{slip.slipNo}</td>
                    <td className="p-3.5 text-right font-medium text-slate-700 dark:text-slate-300">
                      ${slip.basic.toLocaleString()}
                    </td>
                    <td className="p-3.5 text-right font-semibold text-slate-800 dark:text-slate-200">
                      ${slip.grossSalary.toLocaleString()}
                    </td>
                    <td className="p-3.5 text-right font-medium text-rose-600 dark:text-rose-400">
                      -${slip.taxDeduction.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </td>
                    <td className="p-3.5 text-right font-medium text-indigo-600 dark:text-indigo-400">
                      -${slip.providentFund.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </td>
                    <td className="p-3.5 text-right font-bold text-slate-900 dark:text-white">
                      ${slip.netSalary.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </td>
                    <td className="p-3.5 text-center">
                      <span
                        className={`px-2.5 py-1 text-[10px] font-extrabold rounded-full border ${
                          slip.status === 'PAID'
                            ? 'bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-400 border-emerald-300'
                            : slip.status === 'APPROVED'
                            ? 'bg-blue-50 dark:bg-blue-950/60 text-blue-700 dark:text-blue-400 border-blue-300'
                            : slip.status === 'REJECTED'
                            ? 'bg-rose-50 dark:bg-rose-950/60 text-rose-700 dark:text-rose-400 border-rose-300'
                            : 'bg-amber-50 dark:bg-amber-950/60 text-amber-700 dark:text-amber-400 border-amber-300'
                        }`}
                      >
                        {slip.status}
                      </span>
                    </td>
                    <td className="p-3.5 text-center">
                      <button
                        onClick={() => setSelectedPayslip(slip)}
                        className="flex items-center gap-1 mx-auto px-2.5 py-1 text-xs font-semibold rounded-lg bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 transition-colors"
                      >
                        <Eye className="w-3.5 h-3.5" />
                        Payslip
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 2: Progressive Tax Matrix */}
      {activeTab === 'tax_matrix' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Interactive Calculator */}
          <div className="bg-white dark:bg-slate-900 p-6 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-6">
            <div className="flex items-center gap-2">
              <Calculator className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
              <h2 className="text-base font-bold text-slate-900 dark:text-white">Live Progressive Tax Simulator</h2>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-600 dark:text-slate-400 mb-2">
                Monthly Taxable Base ($)
              </label>
              <input
                type="number"
                step="100"
                min="0"
                value={interactiveTaxSalary}
                onChange={(e) => setInteractiveTaxSalary(parseFloat(e.target.value) || 0)}
                className="w-full text-base font-bold px-3.5 py-2.5 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 space-y-3">
              <div className="flex justify-between text-xs font-medium">
                <span className="text-slate-500">Effective Tax Rate:</span>
                <span className="font-bold text-indigo-600 dark:text-indigo-400">
                  {interactiveTaxCalculation.effectiveRate.toFixed(2)}%
                </span>
              </div>
              <div className="flex justify-between text-xs font-medium">
                <span className="text-slate-500">Total Tax Deduction:</span>
                <span className="font-bold text-rose-600 dark:text-rose-400">
                  ${interactiveTaxCalculation.totalTax.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                </span>
              </div>
              <div className="flex justify-between text-xs font-medium pt-2 border-t border-slate-200 dark:border-slate-700">
                <span className="text-slate-700 dark:text-slate-200 font-bold">Post-Tax Income:</span>
                <span className="font-bold text-slate-900 dark:text-white">
                  ${(interactiveTaxSalary - interactiveTaxCalculation.totalTax).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                </span>
              </div>
            </div>
          </div>

          {/* Tiered Bracket Matrix Explorer */}
          <div className="lg:col-span-2 bg-white dark:bg-slate-900 p-6 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-6">
            <div>
              <h2 className="text-base font-bold text-slate-900 dark:text-white">Marginal Progressive Bracket Schedule</h2>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Income is split across brackets. Only the slice within each threshold band is taxed at that rate.
              </p>
            </div>

            <div className="border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden">
              <table className="w-full text-left text-sm">
                <thead className="bg-slate-100 dark:bg-slate-800/80 text-xs font-bold text-slate-600 dark:text-slate-300">
                  <tr>
                    <th className="p-3">Bracket Tier</th>
                    <th className="p-3">Income Range</th>
                    <th className="p-3 text-center">Marginal Rate</th>
                    <th className="p-3 text-right">Taxable in Tier</th>
                    <th className="p-3 text-right">Tax Due ($)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                  {interactiveTaxCalculation.breakdown.map((tier, idx) => (
                    <tr key={idx} className="hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors text-xs">
                      <td className="p-3 font-semibold text-slate-900 dark:text-white">{tier.name}</td>
                      <td className="p-3 font-mono text-slate-600 dark:text-slate-400">
                        ${tier.lower.toLocaleString()} - {tier.upper ? `$${tier.upper.toLocaleString()}` : '∞'}
                      </td>
                      <td className="p-3 text-center font-bold text-indigo-600 dark:text-indigo-400">
                        {(tier.rate * 100).toFixed(0)}%
                      </td>
                      <td className="p-3 text-right font-medium text-slate-700 dark:text-slate-300">
                        ${tier.taxableInTier.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                      </td>
                      <td className="p-3 text-right font-bold text-slate-900 dark:text-white">
                        ${tier.taxInTier.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* TAB 3: Dual Authorization Queue (Segregation of Duties) */}
      {activeTab === 'approvals' && (
        <div className="bg-white dark:bg-slate-900 p-6 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-bold text-slate-900 dark:text-white">Dual-Authorization & Segregation of Duties</h2>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                A staff member who prepares a payroll run cannot approve it. Two distinct authorized officers are strictly enforced.
              </p>
            </div>
          </div>

          <div className="space-y-4">
            {staffPayroll.map((slip) => {
              const isPreparer = slip.preparerUserId === currentUserId
              return (
                <div
                  key={slip.id}
                  className="p-5 rounded-2xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/40 flex flex-col md:flex-row md:items-center justify-between gap-4"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-slate-900 dark:text-white text-base">{slip.staffName}</span>
                      <span className="text-xs font-mono text-slate-500">({slip.slipNo})</span>
                      <span
                        className={`px-2 py-0.5 text-[10px] font-extrabold rounded-full ${
                          slip.status === 'APPROVED'
                            ? 'bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300'
                            : slip.status === 'PAID'
                            ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300'
                            : 'bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300'
                        }`}
                      >
                        {slip.status}
                      </span>
                    </div>

                    <div className="text-xs text-slate-500 flex flex-wrap items-center gap-3">
                      <span>Prepared by: <strong className="text-slate-700 dark:text-slate-300">{slip.preparerName}</strong></span>
                      {slip.approverName && (
                        <span>Approved by: <strong className="text-slate-700 dark:text-slate-300">{slip.approverName}</strong></span>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-4">
                    <div className="text-right">
                      <span className="text-xs text-slate-500 block">Net Payable:</span>
                      <span className="text-base font-bold text-slate-900 dark:text-white">
                        ${slip.netSalary.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                      </span>
                    </div>

                    {/* Segregation of Duties Action Buttons */}
                    <div className="flex items-center gap-2">
                      {slip.status === 'PENDING' && (
                        <>
                          <button
                            onClick={() => handleApproveSlip(slip)}
                            disabled={isPreparer}
                            className={`flex items-center gap-1.5 px-3 py-2 text-xs font-bold rounded-xl shadow-sm transition-all ${
                              isPreparer
                                ? 'bg-slate-200 dark:bg-slate-800 text-slate-400 cursor-not-allowed'
                                : 'bg-emerald-600 hover:bg-emerald-700 text-white cursor-pointer active:scale-95'
                            }`}
                            title={isPreparer ? 'Self-approval prohibited (Segregation of Duties)' : 'Approve payroll slip'}
                          >
                            {isPreparer ? <Ban className="w-4 h-4" /> : <Check className="w-4 h-4" />}
                            {isPreparer ? 'Self-Approval Prohibited' : 'Authorize & Approve'}
                          </button>

                          <button
                            onClick={() => handleRejectSlip(slip)}
                            className="flex items-center gap-1.5 px-3 py-2 text-xs font-semibold rounded-xl bg-slate-200 hover:bg-slate-300 dark:bg-slate-700 dark:hover:bg-slate-600 text-slate-700 dark:text-slate-200"
                          >
                            <X className="w-4 h-4" />
                            Reject
                          </button>
                        </>
                      )}

                      {slip.status === 'APPROVED' && (
                        <button
                          onClick={() => handleDisburseSlip(slip)}
                          className="flex items-center gap-1.5 px-4 py-2 text-xs font-bold rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white shadow-sm"
                        >
                          <Send className="w-4 h-4" />
                          Disburse Payment
                        </button>
                      )}

                      {slip.status === 'PAID' && (
                        <span className="text-xs font-semibold text-emerald-600 dark:text-emerald-400 flex items-center gap-1">
                          <CheckCircle2 className="w-4 h-4" /> Disbursed
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* 360 Degree Payslip Inspection Slide-Over Drawer */}
      <Payslip360Drawer
        isOpen={Boolean(selectedPayslip)}
        onClose={() => setSelectedPayslip(null)}
        record={selectedPayslip}
        taxBrackets={DEFAULT_TAX_BRACKETS}
        onAuthorize={(id) => {
          if (selectedPayslip) {
            handleApproveSlip(selectedPayslip)
          }
        }}
      />
    </div>
  )
}
