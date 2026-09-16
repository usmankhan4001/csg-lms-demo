'use client'

import React, { useState, useMemo, useCallback } from 'react'
import {
  BookOpen,
  DollarSign,
  TrendingUp,
  TrendingDown,
  Scale,
  CheckCircle2,
  AlertTriangle,
  Plus,
  Trash2,
  RefreshCw,
  Search,
  Filter,
  ArrowRightLeft,
  FileText,
  PieChart,
  ShieldCheck,
  Building2,
  Download,
  Clock,
  Layers,
  HelpCircle,
  ChevronRight,
  AlertCircle,
  Eye,
  Check,
  X,
  Sparkles,
  Zap,
} from 'lucide-react'
import { FeeVoucher360Drawer } from '../inspectors'

export type AccountType = 'ASSET' | 'LIABILITY' | 'EQUITY' | 'REVENUE' | 'EXPENSE'

export interface ChartOfAccountItem {
  id: number
  accountCode: string
  accountName: string
  accountType: AccountType
  campusId?: number
  balance: number
  isActive: boolean
  description?: string
  departmentTag?: string
  budget?: number
}

export interface JournalLineItem {
  id: string
  accountId: number
  accountCode: string
  accountName: string
  debitAmount: number
  creditAmount: number
  description: string
}

export interface JournalVoucherRecord {
  id: number
  referenceNo: string
  entryDate: string
  description: string
  campusId?: number
  totalDebit: number
  totalCredit: number
  reversesEntryId?: number
  lines: JournalLineItem[]
  createdAt: string
  postedBy: string
}

export interface DepartmentBudgetBurn {
  accountId: number
  accountCode: string
  accountName: string
  department: string
  allocatedBudget: number
  actualSpent: number
  burnPercentage: number
  status: 'UNDER_BUDGET' | 'ON_TRACK' | 'WARNING' | 'OVER_BUDGET' | 'CRITICAL'
}

// Initial Mock Chart of Accounts
const INITIAL_ACCOUNTS: ChartOfAccountItem[] = [
  { id: 101, accountCode: '1010', accountName: 'Operating Cash & Bank', accountType: 'ASSET', balance: 145000.0, isActive: true, description: 'Main school treasury bank account' },
  { id: 102, accountCode: '1020', accountName: 'Student Tuition Receivable', accountType: 'ASSET', balance: 42500.0, isActive: true, description: 'Outstanding student fee arrears' },
  { id: 103, accountCode: '1050', accountName: 'Prepaid Educational Resources', accountType: 'ASSET', balance: 12000.0, isActive: true, description: 'Prepaid lab and library supplies' },
  { id: 201, accountCode: '2010', accountName: 'Accounts Payable - Vendors', accountType: 'LIABILITY', balance: 18500.0, isActive: true, description: 'Vendor invoices due within 30 days' },
  { id: 202, accountCode: '2020', accountName: 'Accrued Staff Payroll & Tax', accountType: 'LIABILITY', balance: 35000.0, isActive: true, description: 'Accrued faculty compensation & statutory tax' },
  { id: 301, accountCode: '3010', accountName: 'Institutional General Fund Equity', accountType: 'EQUITY', balance: 100000.0, isActive: true, description: 'Accumulated retained educational capital' },
  { id: 401, accountCode: '4010', accountName: 'Tuition & Academic Fees Revenue', accountType: 'REVENUE', balance: 180000.0, isActive: true, description: 'Term tuition, lab fees, and registration' },
  { id: 402, accountCode: '4020', accountName: 'Grants & Institutional Endowments', accountType: 'REVENUE', balance: 25000.0, isActive: true, description: 'Science and STEM research grants' },
  { id: 501, accountCode: '5010', accountName: 'Faculty & Academic Staff Salaries', accountType: 'EXPENSE', balance: 38000.0, isActive: true, departmentTag: 'Academic Affairs', budget: 50000.0, description: 'Teaching faculty salaries' },
  { id: 502, accountCode: '5020', accountName: 'Campus Utilities & Maintenance', accountType: 'EXPENSE', balance: 11500.0, isActive: true, departmentTag: 'Facilities & Ops', budget: 15000.0, description: 'Electricity, water, lab power, heating' },
  { id: 503, accountCode: '5030', accountName: 'Educational Software & STEM Kits', accountType: 'EXPENSE', balance: 9500.0, isActive: true, departmentTag: 'Technology & IT', budget: 10000.0, description: 'LMS licenses, robotics kits' },
]

export interface GeneralLedgerStudioProps {
  campusName?: string
  currentFiscalYear?: string
}

export function GeneralLedgerStudio({
  campusName = 'Main Academic Campus',
  currentFiscalYear = 'FY 2026-2027',
}: GeneralLedgerStudioProps) {
  const [activeTab, setActiveTab] = useState<'voucher' | 'accounts' | 'trial_balance' | 'budget_burn'>('voucher')
  const [accounts, setAccounts] = useState<ChartOfAccountItem[]>(INITIAL_ACCOUNTS)
  const [searchAccountQuery, setSearchAccountQuery] = useState('')
  const [filterAccountType, setFilterAccountType] = useState<AccountType | 'ALL'>('ALL')

  // Journal Voucher Builder State
  const [voucherDate, setVoucherDate] = useState(() => new Date().toISOString().split('T')[0])
  const [voucherRefNo, setVoucherRefNo] = useState('')
  const [voucherDescription, setVoucherDescription] = useState('')
  const [voucherLines, setVoucherLines] = useState<JournalLineItem[]>([
    { id: '1', accountId: 101, accountCode: '1010', accountName: 'Operating Cash & Bank', debitAmount: 5000, creditAmount: 0, description: 'Tuition collection deposit' },
    { id: '2', accountId: 401, accountCode: '4010', accountName: 'Tuition & Academic Fees Revenue', debitAmount: 0, creditAmount: 5000, description: 'Student fee recognition' },
  ])
  const [postedEntries, setPostedEntries] = useState<JournalVoucherRecord[]>([
    {
      id: 1,
      referenceNo: 'JV-20260901-A81F92',
      entryDate: '2026-09-01',
      description: 'Opening semester tuition receipts and bank deposit',
      totalDebit: 25000.0,
      totalCredit: 25000.0,
      postedBy: 'Senior Financial Controller',
      createdAt: '2026-09-01T09:15:00Z',
      lines: [
        { id: 'l1', accountId: 101, accountCode: '1010', accountName: 'Operating Cash & Bank', debitAmount: 25000.0, creditAmount: 0.0, description: 'Bank wire deposit' },
        { id: 'l2', accountId: 401, accountCode: '4010', accountName: 'Tuition & Academic Fees Revenue', debitAmount: 0.0, creditAmount: 25000.0, description: 'Term 1 tuition revenue' },
      ],
    },
  ])
  const [selectedEntryForReversal, setSelectedEntryForReversal] = useState<JournalVoucherRecord | null>(null)
  const [reversalReason, setReversalReason] = useState('')
  const [feedbackBanner, setFeedbackBanner] = useState<{ type: 'success' | 'error'; message: string } | null>(null)
  const [isFeeVoucherDrawerOpen, setIsFeeVoucherDrawerOpen] = useState(false)

  // Double Entry Invariant Calculations
  const totals = useMemo(() => {
    let debits = 0
    let credits = 0
    for (const line of voucherLines) {
      debits += Number(line.debitAmount) || 0
      credits += Number(line.creditAmount) || 0
    }
    const debitTotal = Math.round(debits * 100) / 100
    const creditTotal = Math.round(credits * 100) / 100
    const delta = Math.round(Math.abs(debitTotal - creditTotal) * 100) / 100
    const isBalanced = delta === 0 && debitTotal > 0 && creditTotal > 0
    return { debitTotal, creditTotal, delta, isBalanced }
  }, [voucherLines])

  // Trial Balance Calculations
  const trialBalance = useMemo(() => {
    let totalDebit = 0
    let totalCredit = 0
    const rows = accounts.map((acc) => {
      let debit = 0
      let credit = 0
      if (acc.accountType === 'ASSET' || acc.accountType === 'EXPENSE') {
        if (acc.balance >= 0) {
          debit = acc.balance
        } else {
          credit = Math.abs(acc.balance)
        }
      } else {
        if (acc.balance >= 0) {
          credit = acc.balance
        } else {
          debit = Math.abs(acc.balance)
        }
      }
      totalDebit += debit
      totalCredit += credit
      return { ...acc, debitBalance: debit, creditBalance: credit }
    })
    const isBalanced = Math.abs(totalDebit - totalCredit) < 0.01
    return { rows, totalDebit, totalCredit, isBalanced }
  }, [accounts])

  // Departmental Budget Burn Calculations
  const budgetBurns: DepartmentBudgetBurn[] = useMemo(() => {
    return accounts
      .filter((a) => a.accountType === 'EXPENSE')
      .map((acc) => {
        const budget = acc.budget || 50000.0
        const spent = acc.balance
        const pct = Math.round((spent / budget) * 1000) / 10
        let status: DepartmentBudgetBurn['status'] = 'UNDER_BUDGET'
        if (pct > 120) status = 'CRITICAL'
        else if (pct > 100) status = 'OVER_BUDGET'
        else if (pct >= 85) status = 'WARNING'
        else if (pct >= 70) status = 'ON_TRACK'

        return {
          accountId: acc.id,
          accountCode: acc.accountCode,
          accountName: acc.accountName,
          department: acc.departmentTag || 'Operations',
          allocatedBudget: budget,
          actualSpent: spent,
          burnPercentage: pct,
          status,
        }
      })
  }, [accounts])

  // Add Line Item
  const handleAddLine = () => {
    const firstAcc = accounts[0]
    setVoucherLines((prev) => [
      ...prev,
      {
        id: Math.random().toString(36).substring(2, 9),
        accountId: firstAcc.id,
        accountCode: firstAcc.accountCode,
        accountName: firstAcc.accountName,
        debitAmount: 0,
        creditAmount: 0,
        description: voucherDescription || 'Split item',
      },
    ])
  }

  // Remove Line Item
  const handleRemoveLine = (id: string) => {
    if (voucherLines.length <= 2) {
      setFeedbackBanner({
        type: 'error',
        message: 'A valid journal entry requires at least 2 lines (debit & credit splits).',
      })
      return
    }
    setVoucherLines((prev) => prev.filter((l) => l.id !== id))
  }

  // Auto-Balance Button
  const handleAutoBalance = () => {
    let debits = 0
    let credits = 0
    voucherLines.forEach((l) => {
      debits += Number(l.debitAmount) || 0
      credits += Number(l.creditAmount) || 0
    })
    const diff = Math.round((debits - credits) * 100) / 100
    if (diff === 0) return

    const selectedAcc = accounts.find((a) => a.accountType === (diff > 0 ? 'REVENUE' : 'EXPENSE')) || accounts[0]
    setVoucherLines((prev) => [
      ...prev,
      {
        id: Math.random().toString(36).substring(2, 9),
        accountId: selectedAcc.id,
        accountCode: selectedAcc.accountCode,
        accountName: selectedAcc.accountName,
        debitAmount: diff < 0 ? Math.abs(diff) : 0,
        creditAmount: diff > 0 ? diff : 0,
        description: 'Auto-balanced offsetting entry',
      },
    ])
  }

  // Post Journal Voucher
  const handlePostVoucher = () => {
    if (!totals.isBalanced) {
      setFeedbackBanner({
        type: 'error',
        message: `Double-entry invariant violated: Total Debits ($${totals.debitTotal.toFixed(2)}) must equal Total Credits ($${totals.creditTotal.toFixed(2)}). Imbalance: $${totals.delta.toFixed(2)}`,
      })
      return
    }

    const ref = voucherRefNo || `JV-${voucherDate.replace(/-/g, '')}-${Math.random().toString(36).substring(2, 8).toUpperCase()}`
    
    // Mutate account balances
    const updatedAccounts = accounts.map((acc) => {
      let balanceChange = 0
      voucherLines.forEach((line) => {
        if (line.accountId === acc.id) {
          if (acc.accountType === 'ASSET' || acc.accountType === 'EXPENSE') {
            balanceChange += (line.debitAmount || 0) - (line.creditAmount || 0)
          } else {
            balanceChange += (line.creditAmount || 0) - (line.debitAmount || 0)
          }
        }
      })
      return { ...acc, balance: Math.round((acc.balance + balanceChange) * 100) / 100 }
    })

    const newEntry: JournalVoucherRecord = {
      id: postedEntries.length + 1,
      referenceNo: ref,
      entryDate: voucherDate,
      description: voucherDescription || 'Posted Journal Voucher',
      totalDebit: totals.debitTotal,
      totalCredit: totals.creditTotal,
      lines: [...voucherLines],
      postedBy: 'Chief Financial Officer',
      createdAt: new Date().toISOString(),
    }

    setAccounts(updatedAccounts)
    setPostedEntries((prev) => [newEntry, ...prev])
    setFeedbackBanner({
      type: 'success',
      message: `Journal Voucher ${ref} posted successfully! Ledgers and Trial Balance updated in real-time.`,
    })

    // Reset lines
    setVoucherRefNo('')
    setVoucherDescription('')
    setVoucherLines([
      { id: '1', accountId: accounts[0].id, accountCode: accounts[0].accountCode, accountName: accounts[0].accountName, debitAmount: 0, creditAmount: 0, description: '' },
      { id: '2', accountId: accounts[3].id, accountCode: accounts[3].accountCode, accountName: accounts[3].accountName, debitAmount: 0, creditAmount: 0, description: '' },
    ])
  }

  // Reverse Journal Entry
  const handleExecuteReversal = () => {
    if (!selectedEntryForReversal) return

    const original = selectedEntryForReversal
    const revRef = `REV-${original.referenceNo}-${Math.random().toString(36).substring(2, 6).toUpperCase()}`

    // Unwind account balances
    const updatedAccounts = accounts.map((acc) => {
      let balanceChange = 0
      original.lines.forEach((line) => {
        if (line.accountId === acc.id) {
          if (acc.accountType === 'ASSET' || acc.accountType === 'EXPENSE') {
            // Reversing: swapped debits and credits
            balanceChange += (line.creditAmount || 0) - (line.debitAmount || 0)
          } else {
            balanceChange += (line.debitAmount || 0) - (line.creditAmount || 0)
          }
        }
      })
      return { ...acc, balance: Math.round((acc.balance + balanceChange) * 100) / 100 }
    })

    const revEntry: JournalVoucherRecord = {
      id: postedEntries.length + 1,
      referenceNo: revRef,
      entryDate: new Date().toISOString().split('T')[0],
      description: `Reversal of ${original.referenceNo}: ${reversalReason || 'Auditing correction'}`,
      reversesEntryId: original.id,
      totalDebit: original.totalCredit,
      totalCredit: original.totalDebit,
      lines: original.lines.map((l, idx) => ({
        ...l,
        id: `rev-${idx}`,
        debitAmount: l.creditAmount,
        creditAmount: l.debitAmount,
        description: `Reversal: ${l.description}`,
      })),
      postedBy: 'Audit & Compliance Officer',
      createdAt: new Date().toISOString(),
    }

    setAccounts(updatedAccounts)
    setPostedEntries((prev) => [revEntry, ...prev])
    setSelectedEntryForReversal(null)
    setReversalReason('')
    setFeedbackBanner({
      type: 'success',
      message: `Reversal entry ${revRef} posted! Original entry #${original.referenceNo} negated with auditable link.`,
    })
  }

  // Filter accounts
  const filteredAccounts = accounts.filter((acc) => {
    const matchType = filterAccountType === 'ALL' || acc.accountType === filterAccountType
    const matchQuery =
      acc.accountCode.toLowerCase().includes(searchAccountQuery.toLowerCase()) ||
      acc.accountName.toLowerCase().includes(searchAccountQuery.toLowerCase()) ||
      (acc.description && acc.description.toLowerCase().includes(searchAccountQuery.toLowerCase()))
    return matchType && matchQuery
  })

  return (
    <div className="flex flex-col w-full h-full min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 p-4 md:p-6 space-y-6">
      {/* Top Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white dark:bg-slate-900 p-5 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-indigo-600/10 dark:bg-indigo-500/20 text-indigo-600 dark:text-indigo-400 flex items-center justify-center font-bold">
            <Scale className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-white">
                General Ledger & Financial Invariant Studio
              </h1>
              <span className="px-2.5 py-0.5 text-xs font-semibold rounded-full bg-emerald-100 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-400 border border-emerald-300 dark:border-emerald-800">
                Double-Entry Enforced
              </span>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              {campusName} • Fiscal Period: <span className="font-semibold text-slate-700 dark:text-slate-300">{currentFiscalYear}</span>
            </p>
          </div>
        </div>

        {/* Global Key Metrics Chips */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700">
            <Scale className="w-4 h-4 text-indigo-500" />
            <span className="text-xs font-medium text-slate-600 dark:text-slate-300">Trial Balance:</span>
            <span className={`text-xs font-bold ${trialBalance.isBalanced ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}`}>
              {trialBalance.isBalanced ? 'Balanced ($' + trialBalance.totalDebit.toLocaleString() + ')' : 'IMBALANCED'}
            </span>
          </div>

          <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700">
            <TrendingUp className="w-4 h-4 text-emerald-500" />
            <span className="text-xs font-medium text-slate-600 dark:text-slate-300">Net Surplus:</span>
            <span className="text-xs font-bold text-slate-800 dark:text-slate-100">
              ${(accounts.filter((a) => a.accountType === 'REVENUE').reduce((sum, a) => sum + a.balance, 0) - accounts.filter((a) => a.accountType === 'EXPENSE').reduce((sum, a) => sum + a.balance, 0)).toLocaleString()}
            </span>
          </div>

          <button
            type="button"
            onClick={() => setIsFeeVoucherDrawerOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold shadow-xs transition-colors cursor-pointer"
          >
            <FileText className="w-4 h-4" />
            Inspect Fee Voucher 360°
          </button>
        </div>
      </div>

      {/* Feedback Banner */}
      {feedbackBanner && (
        <div
          className={`flex items-center justify-between p-4 rounded-xl text-sm font-medium border animate-in fade-in duration-200 ${
            feedbackBanner.type === 'success'
              ? 'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-800 dark:text-emerald-300 border-emerald-300 dark:border-emerald-800'
              : 'bg-rose-50 dark:bg-rose-950/40 text-rose-800 dark:text-rose-300 border-rose-300 dark:border-rose-800'
          }`}
        >
          <div className="flex items-center gap-2">
            {feedbackBanner.type === 'success' ? <CheckCircle2 className="w-5 h-5 shrink-0 text-emerald-500" /> : <AlertTriangle className="w-5 h-5 shrink-0 text-rose-500" />}
            <span>{feedbackBanner.message}</span>
          </div>
          <button onClick={() => setFeedbackBanner(null)} className="p-1 hover:opacity-75">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Tab Navigation */}
      <div className="flex border-b border-slate-200 dark:border-slate-800 gap-2">
        <button
          onClick={() => setActiveTab('voucher')}
          className={`flex items-center gap-2 px-4 py-2.5 text-sm font-semibold border-b-2 transition-all ${
            activeTab === 'voucher'
              ? 'border-indigo-600 text-indigo-600 dark:text-indigo-400 dark:border-indigo-400 bg-indigo-50/50 dark:bg-indigo-950/30 rounded-t-lg'
              : 'border-transparent text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
          }`}
        >
          <FileText className="w-4 h-4" />
          Journal Voucher Builder
        </button>

        <button
          onClick={() => setActiveTab('trial_balance')}
          className={`flex items-center gap-2 px-4 py-2.5 text-sm font-semibold border-b-2 transition-all ${
            activeTab === 'trial_balance'
              ? 'border-indigo-600 text-indigo-600 dark:text-indigo-400 dark:border-indigo-400 bg-indigo-50/50 dark:bg-indigo-950/30 rounded-t-lg'
              : 'border-transparent text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
          }`}
        >
          <Scale className="w-4 h-4" />
          Trial Balance Explorer
        </button>

        <button
          onClick={() => setActiveTab('budget_burn')}
          className={`flex items-center gap-2 px-4 py-2.5 text-sm font-semibold border-b-2 transition-all ${
            activeTab === 'budget_burn'
              ? 'border-indigo-600 text-indigo-600 dark:text-indigo-400 dark:border-indigo-400 bg-indigo-50/50 dark:bg-indigo-950/30 rounded-t-lg'
              : 'border-transparent text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
          }`}
        >
          <PieChart className="w-4 h-4" />
          Departmental Budget Burn
        </button>

        <button
          onClick={() => setActiveTab('accounts')}
          className={`flex items-center gap-2 px-4 py-2.5 text-sm font-semibold border-b-2 transition-all ${
            activeTab === 'accounts'
              ? 'border-indigo-600 text-indigo-600 dark:text-indigo-400 dark:border-indigo-400 bg-indigo-50/50 dark:bg-indigo-950/30 rounded-t-lg'
              : 'border-transparent text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
          }`}
        >
          <BookOpen className="w-4 h-4" />
          Chart of Accounts
        </button>
      </div>

      {/* TAB 1: Journal Voucher Builder */}
      {activeTab === 'voucher' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main Voucher Editor Form */}
          <div className="lg:col-span-2 bg-white dark:bg-slate-900 p-6 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-bold text-slate-900 dark:text-white">Post Journal Entry</h2>
                <p className="text-xs text-slate-500 dark:text-slate-400">Strict invariant: Total Debits must equal Total Credits before posting.</p>
              </div>

              {/* Live Debit = Credit Indicator */}
              <div
                className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-bold border transition-colors ${
                  totals.isBalanced
                    ? 'bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-400 border-emerald-300 dark:border-emerald-700'
                    : 'bg-amber-50 dark:bg-amber-950/60 text-amber-700 dark:text-amber-400 border-amber-300 dark:border-amber-700'
                }`}
              >
                {totals.isBalanced ? <CheckCircle2 className="w-4 h-4 text-emerald-500" /> : <AlertTriangle className="w-4 h-4 text-amber-500" />}
                <span>
                  {totals.isBalanced ? 'Balanced Voucher' : `Imbalance: $${totals.delta.toFixed(2)}`}
                </span>
              </div>
            </div>

            {/* Header Fields */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-600 dark:text-slate-400 mb-1">Entry Date</label>
                <input
                  type="date"
                  value={voucherDate}
                  onChange={(e) => setVoucherDate(e.target.value)}
                  className="w-full text-sm px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-600 dark:text-slate-400 mb-1">Reference No (Auto if empty)</label>
                <input
                  type="text"
                  placeholder="e.g. JV-202609-001"
                  value={voucherRefNo}
                  onChange={(e) => setVoucherRefNo(e.target.value)}
                  className="w-full text-sm px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-600 dark:text-slate-400 mb-1">Narration / Description</label>
                <input
                  type="text"
                  placeholder="Describe academic transaction..."
                  value={voucherDescription}
                  onChange={(e) => setVoucherDescription(e.target.value)}
                  className="w-full text-sm px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>
            </div>

            {/* Split Lines Table */}
            <div className="border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden">
              <table className="w-full text-left text-sm">
                <thead className="bg-slate-100 dark:bg-slate-800/80 text-xs font-bold text-slate-600 dark:text-slate-300">
                  <tr>
                    <th className="p-3">Account</th>
                    <th className="p-3">Line Memo</th>
                    <th className="p-3 w-32 text-right">Debit ($)</th>
                    <th className="p-3 w-32 text-right">Credit ($)</th>
                    <th className="p-3 w-12 text-center"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                  {voucherLines.map((line) => (
                    <tr key={line.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors">
                      <td className="p-2.5">
                        <select
                          value={line.accountId}
                          onChange={(e) => {
                            const accId = Number(e.target.value)
                            const acc = accounts.find((a) => a.id === accId)
                            if (!acc) return
                            setVoucherLines((prev) =>
                              prev.map((l) =>
                                l.id === line.id
                                  ? { ...l, accountId: acc.id, accountCode: acc.accountCode, accountName: acc.accountName }
                                  : l
                              )
                            )
                          }}
                          className="w-full text-xs font-medium px-2.5 py-1.5 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                        >
                          {accounts.map((acc) => (
                            <option key={acc.id} value={acc.id}>
                              {acc.accountCode} - {acc.accountName} ({acc.accountType})
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="p-2.5">
                        <input
                          type="text"
                          placeholder="Line description"
                          value={line.description}
                          onChange={(e) =>
                            setVoucherLines((prev) =>
                              prev.map((l) => (l.id === line.id ? { ...l, description: e.target.value } : l))
                            )
                          }
                          className="w-full text-xs px-2.5 py-1.5 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg focus:outline-none"
                        />
                      </td>
                      <td className="p-2.5 text-right">
                        <input
                          type="number"
                          step="0.01"
                          min="0"
                          value={line.debitAmount || ''}
                          onChange={(e) => {
                            const val = parseFloat(e.target.value) || 0
                            setVoucherLines((prev) =>
                              prev.map((l) =>
                                l.id === line.id
                                  ? { ...l, debitAmount: val, creditAmount: val > 0 ? 0 : l.creditAmount }
                                  : l
                              )
                            )
                          }}
                          className="w-full text-right text-xs font-semibold px-2.5 py-1.5 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                        />
                      </td>
                      <td className="p-2.5 text-right">
                        <input
                          type="number"
                          step="0.01"
                          min="0"
                          value={line.creditAmount || ''}
                          onChange={(e) => {
                            const val = parseFloat(e.target.value) || 0
                            setVoucherLines((prev) =>
                              prev.map((l) =>
                                l.id === line.id
                                  ? { ...l, creditAmount: val, debitAmount: val > 0 ? 0 : l.debitAmount }
                                  : l
                              )
                            )
                          }}
                          className="w-full text-right text-xs font-semibold px-2.5 py-1.5 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                        />
                      </td>
                      <td className="p-2.5 text-center">
                        <button
                          onClick={() => handleRemoveLine(line.id)}
                          className="p-1.5 text-slate-400 hover:text-rose-500 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                          title="Remove line"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot className="bg-slate-50 dark:bg-slate-800/90 font-bold text-xs">
                  <tr>
                    <td colSpan={2} className="p-3 text-slate-700 dark:text-slate-200">
                      Total Ledger Split Invariant:
                    </td>
                    <td className="p-3 text-right text-indigo-600 dark:text-indigo-400 text-sm">
                      ${totals.debitTotal.toFixed(2)}
                    </td>
                    <td className="p-3 text-right text-indigo-600 dark:text-indigo-400 text-sm">
                      ${totals.creditTotal.toFixed(2)}
                    </td>
                    <td></td>
                  </tr>
                </tfoot>
              </table>
            </div>

            {/* Actions Bar */}
            <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
              <div className="flex items-center gap-2">
                <button
                  onClick={handleAddLine}
                  className="flex items-center gap-1.5 px-3 py-2 text-xs font-semibold rounded-xl bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 transition-colors"
                >
                  <Plus className="w-4 h-4" />
                  Add Split Line
                </button>

                <button
                  onClick={handleAutoBalance}
                  className="flex items-center gap-1.5 px-3 py-2 text-xs font-semibold rounded-xl bg-indigo-50 hover:bg-indigo-100 dark:bg-indigo-950/50 dark:hover:bg-indigo-900/50 text-indigo-700 dark:text-indigo-300 transition-colors"
                  title="Auto-calculate balancing row"
                >
                  <Sparkles className="w-4 h-4" />
                  Auto-Balance Difference
                </button>
              </div>

              <button
                onClick={handlePostVoucher}
                disabled={!totals.isBalanced}
                className={`flex items-center gap-2 px-5 py-2.5 text-sm font-bold rounded-xl shadow-sm transition-all ${
                  totals.isBalanced
                    ? 'bg-indigo-600 hover:bg-indigo-700 text-white cursor-pointer active:scale-95'
                    : 'bg-slate-200 dark:bg-slate-800 text-slate-400 cursor-not-allowed'
                }`}
              >
                <Check className="w-4 h-4" />
                Post to General Ledger
              </button>
            </div>
          </div>

          {/* Recent Posted Entries & Audit Reversal Trail */}
          <div className="bg-white dark:bg-slate-900 p-6 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
                <Clock className="w-4 h-4 text-indigo-500" />
                Posted Journal Entries
              </h3>
              <span className="text-xs px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 font-medium">
                {postedEntries.length} entries
              </span>
            </div>

            <div className="space-y-3 max-h-[500px] overflow-y-auto pr-1">
              {postedEntries.map((entry) => (
                <div
                  key={entry.id}
                  className={`p-3.5 rounded-xl border text-xs space-y-2 transition-all ${
                    entry.reversesEntryId
                      ? 'bg-amber-50/50 dark:bg-amber-950/20 border-amber-200 dark:border-amber-800'
                      : 'bg-slate-50 dark:bg-slate-800/60 border-slate-200 dark:border-slate-700'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-slate-900 dark:text-white">{entry.referenceNo}</span>
                    <span className="text-slate-500 dark:text-slate-400">{entry.entryDate}</span>
                  </div>
                  <p className="text-slate-600 dark:text-slate-300 line-clamp-2">{entry.description}</p>
                  
                  <div className="flex items-center justify-between pt-1 border-t border-slate-200 dark:border-slate-700/60">
                    <span className="font-semibold text-indigo-600 dark:text-indigo-400">
                      Amount: ${entry.totalDebit.toLocaleString()}
                    </span>

                    {!entry.reversesEntryId && (
                      <button
                        onClick={() => setSelectedEntryForReversal(entry)}
                        className="flex items-center gap-1 text-[11px] font-semibold text-rose-600 dark:text-rose-400 hover:underline"
                      >
                        <ArrowRightLeft className="w-3 h-3" />
                        Reverse Entry
                      </button>
                    )}

                    {entry.reversesEntryId && (
                      <span className="text-[10px] font-bold text-amber-700 dark:text-amber-400">
                        REVERSAL ENTRY
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: Trial Balance Explorer */}
      {activeTab === 'trial_balance' && (
        <div className="bg-white dark:bg-slate-900 p-6 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-6">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <h2 className="text-lg font-bold text-slate-900 dark:text-white">Real-Time Trial Balance</h2>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Sum of all debits must equal sum of all credits across active accounts for mathematical soundness.
              </p>
            </div>

            <div className="flex items-center gap-3">
              <div
                className={`flex items-center gap-2 px-3 py-1.5 rounded-xl text-xs font-bold border ${
                  trialBalance.isBalanced
                    ? 'bg-emerald-50 dark:bg-emerald-950/50 text-emerald-700 dark:text-emerald-400 border-emerald-300 dark:border-emerald-800'
                    : 'bg-rose-50 dark:bg-rose-950/50 text-rose-700 dark:text-rose-400 border-rose-300 dark:border-rose-800'
                }`}
              >
                {trialBalance.isBalanced ? <ShieldCheck className="w-4 h-4 text-emerald-500" /> : <AlertTriangle className="w-4 h-4 text-rose-500" />}
                <span>{trialBalance.isBalanced ? 'General Ledger Invariant Preserved' : 'Discrepancy Detected'}</span>
              </div>
            </div>
          </div>

          {/* Trial Balance Table */}
          <div className="border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-100 dark:bg-slate-800/80 text-xs font-bold text-slate-600 dark:text-slate-300">
                <tr>
                  <th className="p-3.5">Code</th>
                  <th className="p-3.5">Account Title</th>
                  <th className="p-3.5">Type</th>
                  <th className="p-3.5 text-right w-40">Debit Balance ($)</th>
                  <th className="p-3.5 text-right w-40">Credit Balance ($)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                {trialBalance.rows.map((row) => (
                  <tr key={row.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors text-xs">
                    <td className="p-3.5 font-mono font-bold text-slate-700 dark:text-slate-300">{row.accountCode}</td>
                    <td className="p-3.5 font-medium text-slate-900 dark:text-white">{row.accountName}</td>
                    <td className="p-3.5">
                      <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                        {row.accountType}
                      </span>
                    </td>
                    <td className="p-3.5 text-right font-semibold text-slate-800 dark:text-slate-200">
                      {row.debitBalance > 0 ? `$${row.debitBalance.toLocaleString(undefined, { minimumFractionDigits: 2 })}` : '-'}
                    </td>
                    <td className="p-3.5 text-right font-semibold text-slate-800 dark:text-slate-200">
                      {row.creditBalance > 0 ? `$${row.creditBalance.toLocaleString(undefined, { minimumFractionDigits: 2 })}` : '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot className="bg-slate-100 dark:bg-slate-800 font-bold text-sm">
                <tr>
                  <td colSpan={3} className="p-4 text-slate-800 dark:text-slate-100">
                    Grand Total Trial Balance:
                  </td>
                  <td className="p-4 text-right text-indigo-600 dark:text-indigo-400">
                    ${trialBalance.totalDebit.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                  </td>
                  <td className="p-4 text-right text-indigo-600 dark:text-indigo-400">
                    ${trialBalance.totalCredit.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        </div>
      )}

      {/* TAB 3: Departmental Budget Burn */}
      {activeTab === 'budget_burn' && (
        <div className="bg-white dark:bg-slate-900 p-6 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-6">
          <div>
            <h2 className="text-lg font-bold text-slate-900 dark:text-white">Departmental Budget Burn Telemetry</h2>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Live monitoring of operational expenditure actuals against allocated departmental budgets.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {budgetBurns.map((burn) => (
              <div
                key={burn.accountId}
                className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/50 space-y-3"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-indigo-600 dark:text-indigo-400">{burn.department}</span>
                  <span
                    className={`text-[10px] font-extrabold px-2 py-0.5 rounded-full border ${
                      burn.status === 'UNDER_BUDGET'
                        ? 'bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-400 border-emerald-300'
                        : burn.status === 'ON_TRACK'
                        ? 'bg-blue-50 dark:bg-blue-950/60 text-blue-700 dark:text-blue-400 border-blue-300'
                        : burn.status === 'WARNING'
                        ? 'bg-amber-50 dark:bg-amber-950/60 text-amber-700 dark:text-amber-400 border-amber-300'
                        : 'bg-rose-50 dark:bg-rose-950/60 text-rose-700 dark:text-rose-400 border-rose-300'
                    }`}
                  >
                    {burn.status.replace('_', ' ')}
                  </span>
                </div>

                <div>
                  <h4 className="text-sm font-bold text-slate-900 dark:text-white">{burn.accountName}</h4>
                  <span className="text-xs text-slate-500">Account Code: {burn.accountCode}</span>
                </div>

                {/* Progress Bar */}
                <div className="space-y-1">
                  <div className="flex justify-between text-xs font-semibold">
                    <span className="text-slate-600 dark:text-slate-400">Burn Rate:</span>
                    <span className="text-slate-900 dark:text-white font-bold">{burn.burnPercentage}%</span>
                  </div>
                  <div className="w-full bg-slate-200 dark:bg-slate-700 h-2.5 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all ${
                        burn.burnPercentage > 100
                          ? 'bg-rose-500'
                          : burn.burnPercentage >= 85
                          ? 'bg-amber-500'
                          : 'bg-indigo-600'
                      }`}
                      style={{ width: `${Math.min(100, burn.burnPercentage)}%` }}
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-2 text-xs pt-2 border-t border-slate-200 dark:border-slate-700">
                  <div>
                    <span className="text-slate-500 block">Spent:</span>
                    <span className="font-bold text-slate-800 dark:text-slate-200">${burn.actualSpent.toLocaleString()}</span>
                  </div>
                  <div>
                    <span className="text-slate-500 block">Allocated:</span>
                    <span className="font-bold text-slate-800 dark:text-slate-200">${burn.allocatedBudget.toLocaleString()}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TAB 4: Chart of Accounts */}
      {activeTab === 'accounts' && (
        <div className="bg-white dark:bg-slate-900 p-6 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-6">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <h2 className="text-lg font-bold text-slate-900 dark:text-white">Chart of Accounts Ledger</h2>
              <p className="text-xs text-slate-500 dark:text-slate-400">Active GL classification hierarchy for institutional accounting.</p>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <div className="relative">
                <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
                <input
                  type="text"
                  placeholder="Search code or account..."
                  value={searchAccountQuery}
                  onChange={(e) => setSearchAccountQuery(e.target.value)}
                  className="text-xs pl-9 pr-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <select
                value={filterAccountType}
                onChange={(e) => setFilterAccountType(e.target.value as any)}
                className="text-xs px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 font-medium"
              >
                <option value="ALL">All Account Types</option>
                <option value="ASSET">Assets</option>
                <option value="LIABILITY">Liabilities</option>
                <option value="EQUITY">Equity</option>
                <option value="REVENUE">Revenue</option>
                <option value="EXPENSE">Expense</option>
              </select>
            </div>
          </div>

          <div className="border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-100 dark:bg-slate-800/80 text-xs font-bold text-slate-600 dark:text-slate-300">
                <tr>
                  <th className="p-3.5">Code</th>
                  <th className="p-3.5">Account Name</th>
                  <th className="p-3.5">Type</th>
                  <th className="p-3.5">Description</th>
                  <th className="p-3.5 text-right">Current Balance ($)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                {filteredAccounts.map((acc) => (
                  <tr key={acc.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors text-xs">
                    <td className="p-3.5 font-mono font-bold text-indigo-600 dark:text-indigo-400">{acc.accountCode}</td>
                    <td className="p-3.5 font-medium text-slate-900 dark:text-white">{acc.accountName}</td>
                    <td className="p-3.5">
                      <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                        {acc.accountType}
                      </span>
                    </td>
                    <td className="p-3.5 text-slate-500 max-w-xs truncate">{acc.description || '-'}</td>
                    <td className="p-3.5 text-right font-bold text-slate-900 dark:text-white">
                      ${acc.balance.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Modal: Reversing Journal Entry */}
      {selectedEntryForReversal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white dark:bg-slate-900 max-w-md w-full rounded-2xl border border-slate-200 dark:border-slate-800 p-6 shadow-xl space-y-4 animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-rose-600 dark:text-rose-400">
                <ArrowRightLeft className="w-5 h-5" />
                <h3 className="font-bold text-base">Reverse Journal Voucher</h3>
              </div>
              <button onClick={() => setSelectedEntryForReversal(null)} className="p-1 hover:opacity-75">
                <X className="w-4 h-4" />
              </button>
            </div>

            <p className="text-xs text-slate-600 dark:text-slate-300">
              You are about to post an immutable offsetting reversal for{' '}
              <strong className="text-slate-900 dark:text-white">{selectedEntryForReversal.referenceNo}</strong>. All debits
              and credits will be swapped, safely unwinding ledger mutations while keeping full auditability.
            </p>

            <div>
              <label className="block text-xs font-semibold text-slate-600 dark:text-slate-400 mb-1">
                Reason for Reversal / Audit Memo
              </label>
              <textarea
                rows={3}
                placeholder="e.g. Correcting mistaken account allocation..."
                value={reversalReason}
                onChange={(e) => setReversalReason(e.target.value)}
                className="w-full text-xs p-3 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl focus:outline-none focus:ring-2 focus:ring-rose-500"
              />
            </div>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                onClick={() => setSelectedEntryForReversal(null)}
                className="px-4 py-2 text-xs font-semibold rounded-xl text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800"
              >
                Cancel
              </button>
              <button
                onClick={handleExecuteReversal}
                className="px-4 py-2 text-xs font-bold rounded-xl bg-rose-600 hover:bg-rose-700 text-white shadow-sm"
              >
                Confirm & Post Reversal
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 360 Degree Fee Voucher Slide-Over Inspection Drawer */}
      <FeeVoucher360Drawer
        isOpen={isFeeVoucherDrawerOpen}
        onClose={() => setIsFeeVoucherDrawerOpen(false)}
      />
    </div>
  )
}
