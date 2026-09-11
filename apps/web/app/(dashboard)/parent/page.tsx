'use client'

import React, { useState } from 'react'
import Link from 'next/link'
import {
  Users,
  Calendar,
  CreditCard,
  Sparkles,
  TrendingUp,
  Download,
  CheckCircle2,
  AlertCircle,
  Clock,
  ArrowUpRight,
  ChevronRight,
  ShieldCheck,
  BrainCircuit,
  MessageSquare,
  DollarSign,
  FileText,
  UserCheck,
  Check,
  ChevronLeft,
} from 'lucide-react'
import { cn } from '@/lib/utils'

interface ChildProfile {
  id: string
  name: string
  grade: string
  rollNo: string
  studentId: string
  avatar: string
  attendanceRate: number
  gpa: string
  currentFeeStatus: 'paid' | 'pending' | 'overdue'
}

interface FeeVoucher {
  id: string
  voucherNo: string
  month: string
  term: string
  issueDate: string
  dueDate: string
  tuitionFee: number
  labFee: number
  transportFee: number
  sportsFund: number
  totalAmount: number
  status: 'paid' | 'unpaid'
  paidOn?: string
  paymentMethod?: string
}

const CHILDREN: ChildProfile[] = [
  {
    id: 'ch-1',
    name: 'Zaid Usman Khan',
    grade: 'Grade 11 - Section A (Pre-Engineering)',
    rollNo: '11A-01',
    studentId: 'CSG-2024-ISB-4921',
    avatar: 'Z',
    attendanceRate: 96.4,
    gpa: '3.88 / A+',
    currentFeeStatus: 'pending',
  },
  {
    id: 'ch-2',
    name: 'Amina Usman Khan',
    grade: 'Grade 8 - Section B (Middle Years)',
    rollNo: '8B-14',
    studentId: 'CSG-2026-ISB-7102',
    avatar: 'A',
    attendanceRate: 98.2,
    gpa: '3.95 / A+',
    currentFeeStatus: 'paid',
  },
]

const VOUCHERS: FeeVoucher[] = [
  {
    id: 'vch-1',
    voucherNo: 'CSG-2026-09-8839',
    month: 'September 2026',
    term: 'Fall Term 1',
    issueDate: 'Sep 01, 2026',
    dueDate: 'Sep 25, 2026',
    tuitionFee: 24000,
    labFee: 3500,
    transportFee: 6000,
    sportsFund: 1500,
    totalAmount: 35000,
    status: 'unpaid',
  },
  {
    id: 'vch-2',
    voucherNo: 'CSG-2026-08-4102',
    month: 'August 2026 (Registration & Term 1)',
    term: 'Fall Term 1',
    issueDate: 'Aug 05, 2026',
    dueDate: 'Aug 20, 2026',
    tuitionFee: 24000,
    labFee: 3500,
    transportFee: 6000,
    sportsFund: 1500,
    totalAmount: 35000,
    status: 'paid',
    paidOn: 'Aug 14, 2026',
    paymentMethod: '1Bill Online Banking',
  },
]

// 30-Day Attendance Matrix Mock (P = Present, L = Late, A = Absent, H = Holiday)
const CALENDAR_DAYS = [
  { day: 1, status: 'P' },
  { day: 2, status: 'P' },
  { day: 3, status: 'P' },
  { day: 4, status: 'P' },
  { day: 5, status: 'P' },
  { day: 6, status: 'H' },
  { day: 7, status: 'H' },
  { day: 8, status: 'P' },
  { day: 9, status: 'P' },
  { day: 10, status: 'L' },
  { day: 11, status: 'P' },
  { day: 12, status: 'P' },
  { day: 13, status: 'H' },
  { day: 14, status: 'H' },
  { day: 15, status: 'P' },
  { day: 16, status: 'P' },
  { day: 17, status: 'P' },
  { day: 18, status: 'P' },
  { day: 19, status: 'P' },
  { day: 20, status: 'H' },
  { day: 21, status: 'H' },
  { day: 22, status: 'P' },
  { day: 23, status: 'P' },
  { day: 24, status: 'P' },
  { day: 25, status: 'P' },
  { day: 26, status: 'P' },
  { day: 27, status: 'H' },
  { day: 28, status: 'H' },
  { day: 29, status: 'P' },
  { day: 30, status: 'P' },
]

export default function ParentPortalPage() {
  const [selectedChildId, setSelectedChildId] = useState(CHILDREN[0].id)
  const [payModalOpen, setPayModalOpen] = useState(false)
  const [activeVoucher, setActiveVoucher] = useState<FeeVoucher | null>(null)
  const [vouchersList, setVouchersList] = useState<FeeVoucher[]>(VOUCHERS)

  const activeChild = CHILDREN.find((c) => c.id === selectedChildId) || CHILDREN[0]

  const handleOpenPayModal = (voucher: FeeVoucher) => {
    setActiveVoucher(voucher)
    setPayModalOpen(true)
  }

  const handleConfirmPayment = () => {
    if (!activeVoucher) return
    setVouchersList((prev) =>
      prev.map((v) =>
        v.id === activeVoucher.id
          ? {
              ...v,
              status: 'paid',
              paidOn: new Date().toLocaleDateString(),
              paymentMethod: 'Instant 1Bill / Card Checkout',
            }
          : v
      )
    )
    setPayModalOpen(false)
  }

  return (
    <div className="space-y-6">
      {/* Child Selector & Header Ribbon */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-5 rounded-2xl bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 shadow-2xs">
        <div>
          <span className="text-xs font-semibold text-emerald-600 dark:text-emerald-400 uppercase tracking-wider">
            Parent & Guardian Portal
          </span>
          <h1 className="text-xl sm:text-2xl font-bold text-neutral-900 dark:text-white mt-0.5">
            Student Monitoring & Fees
          </h1>
          <p className="text-xs text-neutral-500 mt-0.5">
            Viewing records for family of Muhammad Usman Khan
          </p>
        </div>

        {/* Child Switcher Pills */}
        <div className="flex items-center gap-2 p-1.5 rounded-2xl bg-neutral-100 dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-700 self-start md:self-auto">
          {CHILDREN.map((child) => {
            const isSelected = child.id === selectedChildId
            return (
              <button
                key={child.id}
                onClick={() => setSelectedChildId(child.id)}
                className={cn(
                  'flex items-center gap-2 px-3 py-1.5 rounded-xl text-xs font-semibold transition-all',
                  isSelected
                    ? 'bg-white dark:bg-neutral-900 text-neutral-900 dark:text-white shadow-sm ring-1 ring-neutral-300 dark:ring-neutral-700'
                    : 'text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-white'
                )}
              >
                <div className="size-6 rounded-full bg-gradient-to-tr from-emerald-600 to-teal-600 text-white flex items-center justify-center text-[10px] font-bold">
                  {child.avatar}
                </div>
                <div className="text-start">
                  <div className="leading-tight truncate max-w-[120px]">{child.name}</div>
                  <div className="text-[10px] text-neutral-400 font-normal leading-tight">
                    {child.rollNo}
                  </div>
                </div>
              </button>
            )
          })}
        </div>
      </div>

      {/* Selected Child KPI Banner */}
      <div className="p-5 sm:p-6 rounded-2xl bg-gradient-to-r from-emerald-700 via-teal-700 to-cyan-800 text-white shadow-lg shadow-emerald-900/10">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3.5">
            <div className="size-12 rounded-2xl bg-white/10 backdrop-blur-md border border-white/20 flex items-center justify-center text-white text-lg font-bold">
              {activeChild.avatar}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg sm:text-xl font-bold">{activeChild.name}</h2>
                <span className="px-2 py-0.5 rounded-full text-[10px] bg-white/20 backdrop-blur-xs font-mono font-medium">
                  {activeChild.studentId}
                </span>
              </div>
              <p className="text-xs text-emerald-100 mt-0.5">{activeChild.grade}</p>
            </div>
          </div>

          <div className="flex items-center gap-6">
            <div>
              <div className="text-xs text-emerald-200">Attendance</div>
              <div className="text-xl font-bold">{activeChild.attendanceRate}%</div>
            </div>
            <div className="h-8 w-px bg-white/20" />
            <div>
              <div className="text-xs text-emerald-200">GPA Standing</div>
              <div className="text-xl font-bold">{activeChild.gpa}</div>
            </div>
            <div className="h-8 w-px bg-white/20" />
            <div>
              <div className="text-xs text-emerald-200">Fee Status</div>
              <div className="text-sm font-bold uppercase tracking-wider">
                {activeChild.currentFeeStatus === 'paid' ? '✅ Paid' : '⏳ Due'}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content Grid: Attendance Calendar & Fee Vouchers */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Attendance Calendar & Fee Vouchers */}
        <div className="lg:col-span-2 space-y-6">
          {/* Attendance Calendar Card */}
          <div
            id="attendance"
            className="p-5 sm:p-6 rounded-2xl bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 shadow-2xs"
          >
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-xl bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
                  <Calendar className="size-5" />
                </div>
                <div>
                  <h2 className="text-base font-bold text-neutral-900 dark:text-white">
                    Attendance Calendar & History
                  </h2>
                  <p className="text-xs text-neutral-500">
                    September 2026 • 96.4% Present Rate
                  </p>
                </div>
              </div>

              {/* Legend */}
              <div className="hidden sm:flex items-center gap-3 text-xs">
                <div className="flex items-center gap-1.5">
                  <span className="size-2.5 rounded-full bg-emerald-500" />
                  <span className="text-neutral-500">Present (23)</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="size-2.5 rounded-full bg-amber-500" />
                  <span className="text-neutral-500">Late (1)</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="size-2.5 rounded-full bg-rose-500" />
                  <span className="text-neutral-500">Absent (0)</span>
                </div>
              </div>
            </div>

            {/* 30-Day Grid */}
            <div className="grid grid-cols-7 gap-2 text-center text-xs">
              {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map((day) => (
                <div
                  key={day}
                  className="py-1 text-[11px] font-bold text-neutral-400 uppercase tracking-wider"
                >
                  {day}
                </div>
              ))}

              {CALENDAR_DAYS.map((d) => {
                let badgeStyle =
                  'bg-emerald-50 dark:bg-emerald-950/30 text-emerald-700 dark:text-emerald-300 border-emerald-500/20'
                if (d.status === 'L') {
                  badgeStyle =
                    'bg-amber-50 dark:bg-amber-950/30 text-amber-700 dark:text-amber-300 border-amber-500/20 font-bold'
                } else if (d.status === 'H') {
                  badgeStyle =
                    'bg-neutral-100 dark:bg-neutral-800 text-neutral-400 border-transparent'
                }

                return (
                  <div
                    key={d.day}
                    className={cn(
                      'p-2 rounded-xl border flex flex-col items-center justify-between min-h-[44px] transition-colors',
                      badgeStyle
                    )}
                  >
                    <span className="text-[11px] font-mono">{d.day}</span>
                    <span className="text-[10px] font-bold">
                      {d.status === 'P' ? '✓' : d.status === 'L' ? 'Late' : 'Off'}
                    </span>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Fee Vouchers & Payments Card */}
          <div
            id="fees"
            className="p-5 sm:p-6 rounded-2xl bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 shadow-2xs"
          >
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-xl bg-amber-500/10 text-amber-600 dark:text-amber-400">
                  <CreditCard className="size-5" />
                </div>
                <div>
                  <h2 className="text-base font-bold text-neutral-900 dark:text-white">
                    Fee Vouchers & Invoices
                  </h2>
                  <p className="text-xs text-neutral-500">
                    Tuition fees, transport & laboratory breakdown
                  </p>
                </div>
              </div>

              <Link
                href="/parent/fees"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 text-xs font-semibold text-neutral-700 dark:text-neutral-200 hover:bg-neutral-100 dark:hover:bg-neutral-700 transition-colors shadow-2xs"
              >
                <span>View Full Billing Portal</span>
                <ArrowUpRight className="size-3.5" />
              </Link>
            </div>

            <div className="space-y-4">
              {vouchersList.map((voucher) => {
                const isPaid = voucher.status === 'paid'
                return (
                  <div
                    key={voucher.id}
                    className={cn(
                      'p-4 sm:p-5 rounded-2xl border transition-all',
                      isPaid
                        ? 'bg-neutral-50/50 dark:bg-neutral-900/40 border-neutral-200 dark:border-neutral-800'
                        : 'bg-amber-50/40 dark:bg-amber-950/20 border-amber-300 dark:border-amber-700/60 ring-2 ring-amber-500/15'
                    )}
                  >
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-neutral-200 dark:border-neutral-800">
                      <div>
                        <div className="flex items-center gap-2">
                          <h3 className="text-sm font-bold text-neutral-900 dark:text-white">
                            {voucher.month}
                          </h3>
                          <span className="font-mono text-xs text-neutral-500">
                            ({voucher.voucherNo})
                          </span>
                        </div>
                        <p className="text-xs text-neutral-500 mt-0.5">
                          Issued: {voucher.issueDate} • Due Date: {voucher.dueDate}
                        </p>
                      </div>

                      <div className="flex items-center gap-2 self-start sm:self-auto">
                        <span
                          className={cn(
                            'px-2.5 py-1 rounded-full text-xs font-bold uppercase tracking-wider',
                            isPaid
                              ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20'
                              : 'bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20'
                          )}
                        >
                          {isPaid ? 'Paid' : 'Unpaid'}
                        </span>
                      </div>
                    </div>

                    {/* Fee Itemized Breakdown */}
                    <div className="py-3 grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs border-b border-neutral-200 dark:border-neutral-800">
                      <div>
                        <span className="text-neutral-500">Tuition Fee</span>
                        <div className="font-bold text-neutral-800 dark:text-neutral-200">
                          PKR {voucher.tuitionFee.toLocaleString()}
                        </div>
                      </div>
                      <div>
                        <span className="text-neutral-500">Lab & STEM</span>
                        <div className="font-bold text-neutral-800 dark:text-neutral-200">
                          PKR {voucher.labFee.toLocaleString()}
                        </div>
                      </div>
                      <div>
                        <span className="text-neutral-500">Transport</span>
                        <div className="font-bold text-neutral-800 dark:text-neutral-200">
                          PKR {voucher.transportFee.toLocaleString()}
                        </div>
                      </div>
                      <div>
                        <span className="text-neutral-500">Total Payable</span>
                        <div className="font-bold text-blue-600 dark:text-blue-400 text-sm">
                          PKR {voucher.totalAmount.toLocaleString()}
                        </div>
                      </div>
                    </div>

                    {/* Action Buttons */}
                    <div className="pt-3 flex flex-wrap items-center justify-between gap-3">
                      <div className="text-xs text-neutral-500">
                        {isPaid ? (
                          <span className="flex items-center gap-1.5 text-emerald-600 dark:text-emerald-400 font-medium">
                            <CheckCircle2 className="size-4" />
                            Paid on {voucher.paidOn} via {voucher.paymentMethod}
                          </span>
                        ) : (
                          <span className="text-amber-600 dark:text-amber-400 font-medium">
                            ⚠️ Pay before {voucher.dueDate} to avoid late surcharge.
                          </span>
                        )}
                      </div>

                      <div className="flex items-center gap-2">
                        <button
                          onClick={() =>
                            alert(
                              `Downloading Official PDF Voucher #${voucher.voucherNo} with 1Bill KuickPay barcode.`
                            )
                          }
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 text-xs font-semibold text-neutral-700 dark:text-neutral-200 hover:bg-neutral-100 dark:hover:bg-neutral-700 transition-colors shadow-2xs"
                        >
                          <Download className="size-3.5" />
                          <span>PDF Voucher</span>
                        </button>

                        {!isPaid && (
                          <button
                            onClick={() => handleOpenPayModal(voucher)}
                            className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold transition-colors shadow-2xs"
                          >
                            <CreditCard className="size-3.5" />
                            <span>Pay Online (1Bill / Card)</span>
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </div>

        {/* Right 1 Col: Weekly AI Report & Teacher Notes */}
        <div className="space-y-6">
          {/* Weekly AI Learning Summary */}
          <div
            id="ai-report"
            className="p-5 sm:p-6 rounded-2xl bg-gradient-to-br from-indigo-900 via-neutral-900 to-purple-950 border border-indigo-500/30 text-white shadow-xl shadow-indigo-950/20 relative overflow-hidden"
          >
            <div className="flex items-center gap-2.5 mb-3">
              <div className="p-2 rounded-xl bg-indigo-500/20 border border-indigo-400/30 text-indigo-300">
                <Sparkles className="size-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-white flex items-center gap-1.5">
                  Weekly AI Learning Summary
                </h3>
                <p className="text-xs text-indigo-200/80">
                  Fall Term • Week 4 AI Intelligence Report
                </p>
              </div>
            </div>

            <div className="space-y-3 text-xs leading-relaxed text-neutral-200">
              <div className="p-3 rounded-xl bg-white/5 border border-white/10">
                <span className="font-bold text-emerald-400 uppercase text-[10px] tracking-wider block mb-1">
                  🌟 Subject Strengths
                </span>
                <p>
                  Zaid demonstrated exceptional mastery in <strong>Calculus BC</strong> and{' '}
                  <strong>Physics Mechanics</strong>. Scored 93% on recent kinematics quizzes.
                </p>
              </div>

              <div className="p-3 rounded-xl bg-white/5 border border-white/10">
                <span className="font-bold text-amber-400 uppercase text-[10px] tracking-wider block mb-1">
                  🎯 Focus Areas
                </span>
                <p>
                  Slight hesitation noted in <strong>Organic Chemistry Reaction Mechanisms</strong>.
                  Socratic AI Tutor recommended 2 interactive guided practice modules.
                </p>
              </div>

              <div className="p-3 rounded-xl bg-white/5 border border-white/10">
                <span className="font-bold text-indigo-300 uppercase text-[10px] tracking-wider block mb-1">
                  🏡 Recommended Home Activity
                </span>
                <p>
                  Encourage 15 minutes of spaced repetition practice on electrophilic substitution
                  before Friday’s lab test.
                </p>
              </div>
            </div>
          </div>

          {/* Teacher Communications / Notes */}
          <div
            id="communications"
            className="p-5 rounded-2xl bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 shadow-2xs"
          >
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-bold text-neutral-900 dark:text-white flex items-center gap-2">
                <MessageSquare className="size-4 text-blue-500" />
                Teacher Communications
              </h3>
              <span className="text-xs font-semibold text-blue-600">2 Notes</span>
            </div>

            <div className="space-y-2.5">
              <div className="p-3 rounded-xl border border-neutral-100 dark:border-neutral-800 bg-neutral-50/60 dark:bg-neutral-800/40">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-bold text-neutral-900 dark:text-white">
                    Dr. Fatima Noor
                  </span>
                  <span className="text-[10px] text-neutral-400">Physics • 2d ago</span>
                </div>
                <p className="text-xs text-neutral-600 dark:text-neutral-400 leading-snug">
                  Zaid did a wonderful job leading the lab experiment on Rotational Dynamics this
                  week.
                </p>
              </div>

              <div className="p-3 rounded-xl border border-neutral-100 dark:border-neutral-800 bg-neutral-50/60 dark:bg-neutral-800/40">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-bold text-neutral-900 dark:text-white">
                    Ms. Samina Rizvi
                  </span>
                  <span className="text-[10px] text-neutral-400">English • 4d ago</span>
                </div>
                <p className="text-xs text-neutral-600 dark:text-neutral-400 leading-snug">
                  Essay on Rhetorical Analysis was submitted on time and well-argued.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Online 1Bill Payment Modal */}
      {payModalOpen && activeVoucher && (
        <div
          className="fixed inset-0 z-50 bg-black/70 backdrop-blur-xs flex items-center justify-center p-4 animate-in fade-in"
          role="dialog"
          aria-modal="true"
        >
          <div className="w-full max-w-md bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 rounded-2xl shadow-2xl p-6">
            <div className="flex items-center justify-between pb-3 border-b border-neutral-100 dark:border-neutral-800">
              <div className="flex items-center gap-2">
                <CreditCard className="size-5 text-emerald-600" />
                <h3 className="text-base font-bold text-neutral-900 dark:text-white">
                  Online Fee Checkout
                </h3>
              </div>
              <button
                onClick={() => setPayModalOpen(false)}
                className="text-neutral-400 hover:text-neutral-900 dark:hover:text-white text-sm"
              >
                ✕
              </button>
            </div>

            <div className="py-4 space-y-3 text-xs">
              <div className="flex justify-between">
                <span className="text-neutral-500">Student Name</span>
                <span className="font-bold text-neutral-900 dark:text-white">
                  {activeChild.name}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-neutral-500">Voucher No</span>
                <span className="font-mono text-neutral-700 dark:text-neutral-300">
                  {activeVoucher.voucherNo}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-neutral-500">Billing Month</span>
                <span className="text-neutral-700 dark:text-neutral-300">
                  {activeVoucher.month}
                </span>
              </div>
              <div className="flex justify-between text-sm font-bold pt-2 border-t border-neutral-100 dark:border-neutral-800">
                <span>Total Payable</span>
                <span className="text-emerald-600 dark:text-emerald-400">
                  PKR {activeVoucher.totalAmount.toLocaleString()}
                </span>
              </div>

              {/* Payment Methods */}
              <div className="pt-2">
                <span className="text-xs font-semibold text-neutral-700 dark:text-neutral-300 mb-2 block">
                  Select Payment Gateway
                </span>
                <div className="grid grid-cols-2 gap-2">
                  <div className="p-2.5 rounded-xl border border-emerald-500 bg-emerald-50/50 dark:bg-emerald-950/30 text-center font-semibold text-emerald-800 dark:text-emerald-200">
                    💳 1Bill / KuickPay
                  </div>
                  <div className="p-2.5 rounded-xl border border-neutral-200 dark:border-neutral-700 text-center text-neutral-600 dark:text-neutral-400 hover:border-neutral-400">
                    💳 Visa / Mastercard
                  </div>
                </div>
              </div>
            </div>

            <div className="pt-2 flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={() => setPayModalOpen(false)}
                className="px-4 py-2 rounded-xl border border-neutral-200 dark:border-neutral-700 text-xs font-medium text-neutral-700 dark:text-neutral-300 hover:bg-neutral-100"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmPayment}
                className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold shadow-xs"
              >
                Confirm PKR {activeVoucher.totalAmount.toLocaleString()}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
