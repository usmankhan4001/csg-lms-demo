'use client'

import React, { useState, useRef } from 'react'
import Link from 'next/link'
import {
  CreditCard,
  Download,
  Printer,
  CheckCircle2,
  AlertCircle,
  Clock,
  ArrowUpRight,
  ShieldCheck,
  ChevronLeft,
  ChevronRight,
  DollarSign,
  FileText,
  UploadCloud,
  FileCheck,
  Building,
  QrCode,
  Sparkles,
  User,
  School,
  X,
} from 'lucide-react'
import { cn } from '@/lib/utils'

interface ChildProfile {
  id: string
  name: string
  grade: string
  rollNo: string
  studentId: string
  campus: string
  avatar: string
}

interface FeeVoucher {
  id: string
  voucherNo: string
  consumerId1Bill: string
  month: string
  term: string
  issueDate: string
  dueDate: string
  validityDate: string
  tuitionFee: number
  labFee: number
  transportFee: number
  sportsFund: number
  examFee: number
  concession: number
  lateSurcharge: number
  totalAmount: number
  status: 'paid' | 'unpaid' | 'overdue'
  paidOn?: string
  paymentMethod?: string
  transactionRef?: string
}

const CHILDREN: ChildProfile[] = [
  {
    id: 'ch-1',
    name: 'Zaid Usman Khan',
    grade: 'Grade 11 - Section A (Pre-Engineering)',
    rollNo: '11A-01',
    studentId: 'CSG-2024-ISB-4921',
    campus: 'CSG Islamabad Central Campus (H-8/4)',
    avatar: 'Z',
  },
  {
    id: 'ch-2',
    name: 'Amina Usman Khan',
    grade: 'Grade 8 - Section B (Middle Years)',
    rollNo: '8B-14',
    studentId: 'CSG-2026-ISB-7102',
    campus: 'CSG Islamabad Central Campus (H-8/4)',
    avatar: 'A',
  },
]

const VOUCHER_DATA: Record<string, FeeVoucher[]> = {
  'ch-1': [
    {
      id: 'vch-101',
      voucherNo: 'CSG-2026-09-8839',
      consumerId1Bill: '1004829104821',
      month: 'September 2026',
      term: 'Fall Term 1 - Academic Year 2026-27',
      issueDate: 'Sep 01, 2026',
      dueDate: 'Sep 25, 2026',
      validityDate: 'Oct 05, 2026',
      tuitionFee: 24000,
      labFee: 3500,
      transportFee: 6000,
      sportsFund: 1500,
      examFee: 2000,
      concession: 2000, // 2000 sibling concession
      lateSurcharge: 1500,
      totalAmount: 35000,
      status: 'unpaid',
    },
    {
      id: 'vch-102',
      voucherNo: 'CSG-2026-08-4102',
      consumerId1Bill: '1004829104820',
      month: 'August 2026 (Registration & Term 1)',
      term: 'Fall Term 1 - Academic Year 2026-27',
      issueDate: 'Aug 05, 2026',
      dueDate: 'Aug 20, 2026',
      validityDate: 'Aug 30, 2026',
      tuitionFee: 24000,
      labFee: 3500,
      transportFee: 6000,
      sportsFund: 1500,
      examFee: 0,
      concession: 2000,
      lateSurcharge: 0,
      totalAmount: 33000,
      status: 'paid',
      paidOn: 'Aug 14, 2026',
      paymentMethod: '1Bill KuickPay Online Banking',
      transactionRef: 'KP-99482103',
    },
  ],
  'ch-2': [
    {
      id: 'vch-201',
      voucherNo: 'CSG-2026-09-7712',
      consumerId1Bill: '1004829107712',
      month: 'September 2026',
      term: 'Fall Term 1 - Academic Year 2026-27',
      issueDate: 'Sep 01, 2026',
      dueDate: 'Sep 25, 2026',
      validityDate: 'Oct 05, 2026',
      tuitionFee: 19000,
      labFee: 2500,
      transportFee: 6000,
      sportsFund: 1500,
      examFee: 1500,
      concession: 0,
      lateSurcharge: 0,
      totalAmount: 30500,
      status: 'paid',
      paidOn: 'Sep 08, 2026',
      paymentMethod: 'Visa Debit Card (**** 4892)',
      transactionRef: 'TX-77391024',
    },
  ],
}

export default function ParentFeesPage() {
  const [selectedChildId, setSelectedChildId] = useState(CHILDREN[0].id)
  const [vouchers, setVouchers] = useState(VOUCHER_DATA)
  const [selectedVoucherForPreview, setSelectedVoucherForPreview] = useState<FeeVoucher>(
    VOUCHER_DATA['ch-1'][0]
  )
  const [previewModalOpen, setPreviewModalOpen] = useState(false)
  const [paymentModalOpen, setPaymentModalOpen] = useState(false)
  const [paymentMethodTab, setPaymentMethodTab] = useState<'1bill' | 'card' | 'bank_transfer'>(
    '1bill'
  )

  // Payment Form States
  const [cardNumber, setCardNumber] = useState('')
  const [cardExpiry, setCardExpiry] = useState('')
  const [cardCvc, setCardCvc] = useState('')
  const [uploadedReceiptName, setUploadedReceiptName] = useState<string | null>(null)
  const [bankTxnRef, setBankTxnRef] = useState('')
  const [isProcessingPayment, setIsProcessingPayment] = useState(false)
  const [paymentSuccess, setPaymentSuccess] = useState(false)

  const activeChild = CHILDREN.find((c) => c.id === selectedChildId) || CHILDREN[0]
  const currentChildVouchers = vouchers[selectedChildId] || []

  // Switch Child
  const handleSelectChild = (childId: string) => {
    setSelectedChildId(childId)
    setSelectedVoucherForPreview(vouchers[childId][0])
  }

  // Open Preview
  const handleOpenPreview = (voucher: FeeVoucher) => {
    setSelectedVoucherForPreview(voucher)
    setPreviewModalOpen(true)
  }

  // Open Pay Modal
  const handleOpenPay = (voucher: FeeVoucher) => {
    setSelectedVoucherForPreview(voucher)
    setPaymentModalOpen(true)
    setPaymentSuccess(false)
  }

  // Handle Complete Payment
  const handleExecutePayment = (e: React.FormEvent) => {
    e.preventDefault()
    setIsProcessingPayment(true)

    setTimeout(() => {
      setIsProcessingPayment(false)
      setPaymentSuccess(true)

      // Update state
      setVouchers((prev) => ({
        ...prev,
        [selectedChildId]: prev[selectedChildId].map((v) =>
          v.id === selectedVoucherForPreview.id
            ? {
                ...v,
                status: 'paid',
                paidOn: new Date().toLocaleDateString('en-US', {
                  month: 'short',
                  day: '2-digit',
                  year: 'numeric',
                }),
                paymentMethod:
                  paymentMethodTab === '1bill'
                    ? '1Bill KuickPay Instant'
                    : paymentMethodTab === 'card'
                    ? 'Credit / Debit Card'
                    : 'Bank Deposit Slip Verified',
                transactionRef: bankTxnRef || `PAY-${Math.floor(10000000 + Math.random() * 90000000)}`,
              }
            : v
        ),
      }))

      setTimeout(() => {
        setPaymentModalOpen(false)
      }, 1800)
    }, 1200)
  }

  return (
    <div className="space-y-6">
      {/* Top Header & Child Switcher */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-5 sm:p-6 rounded-2xl bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 shadow-2xs">
        <div>
          <div className="flex items-center gap-2">
            <Link
              href="/parent"
              className="p-1 rounded-lg text-neutral-400 hover:text-neutral-900 dark:hover:text-white"
            >
              <ChevronLeft className="size-5" />
            </Link>
            <span className="text-xs font-bold text-emerald-600 dark:text-emerald-400 uppercase tracking-wider">
              Finance & Billing
            </span>
          </div>
          <h1 className="text-xl sm:text-2xl font-bold text-neutral-900 dark:text-white mt-1">
            Fee Vouchers & Payment Portal
          </h1>
          <p className="text-xs text-neutral-500 mt-0.5">
            Download official 1Bill bank vouchers or complete instant online payment
          </p>
        </div>

        {/* Child Selector */}
        <div className="flex items-center gap-2 p-1.5 rounded-2xl bg-neutral-100 dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-700">
          {CHILDREN.map((child) => {
            const isSelected = child.id === selectedChildId
            return (
              <button
                key={child.id}
                onClick={() => handleSelectChild(child.id)}
                className={cn(
                  'flex items-center gap-2.5 px-3 py-1.5 rounded-xl text-xs font-semibold transition-all',
                  isSelected
                    ? 'bg-white dark:bg-neutral-900 text-neutral-900 dark:text-white shadow-sm ring-1 ring-neutral-300 dark:ring-neutral-700'
                    : 'text-neutral-600 dark:text-neutral-400 hover:text-neutral-900'
                )}
              >
                <div className="size-6 rounded-full bg-emerald-600 text-white flex items-center justify-center text-[10px] font-bold">
                  {child.avatar}
                </div>
                <div className="text-start">
                  <div className="leading-tight">{child.name}</div>
                  <div className="text-[10px] text-neutral-400 font-mono">{child.rollNo}</div>
                </div>
              </button>
            )
          })}
        </div>
      </div>

      {/* Selected Child Summary Banner */}
      <div className="p-5 sm:p-6 rounded-2xl bg-gradient-to-r from-emerald-800 via-teal-800 to-cyan-900 text-white shadow-lg shadow-emerald-950/20">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3.5">
            <div className="size-12 rounded-2xl bg-white/10 backdrop-blur-md border border-white/20 flex items-center justify-center text-white text-lg font-bold">
              {activeChild.avatar}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-bold">{activeChild.name}</h2>
                <span className="px-2 py-0.5 rounded-full text-[10px] bg-white/20 font-mono font-medium">
                  {activeChild.studentId}
                </span>
              </div>
              <p className="text-xs text-emerald-200 mt-0.5">{activeChild.grade}</p>
              <p className="text-[11px] text-emerald-300/80">{activeChild.campus}</p>
            </div>
          </div>

          <div className="flex items-center gap-6">
            <div>
              <div className="text-xs text-emerald-200">1Bill Consumer ID</div>
              <div className="text-lg font-mono font-bold">
                {currentChildVouchers[0]?.consumerId1Bill}
              </div>
            </div>
            <div className="h-8 w-px bg-white/20" />
            <div>
              <div className="text-xs text-emerald-200">Pending Amount</div>
              <div className="text-xl font-bold">
                PKR{' '}
                {currentChildVouchers
                  .filter((v) => v.status === 'unpaid')
                  .reduce((acc, curr) => acc + curr.totalAmount, 0)
                  .toLocaleString()}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Itemized Fee Vouchers List */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-bold text-neutral-900 dark:text-white flex items-center gap-2">
            <FileText className="size-4 text-emerald-600" />
            Billing Vouchers History
          </h2>
          <span className="text-xs text-neutral-500">
            {currentChildVouchers.length} Total Vouchers
          </span>
        </div>

        {currentChildVouchers.map((voucher) => {
          const isPaid = voucher.status === 'paid'

          return (
            <div
              key={voucher.id}
              className={cn(
                'p-5 sm:p-6 rounded-2xl border transition-all bg-white dark:bg-neutral-900 shadow-2xs',
                isPaid
                  ? 'border-neutral-200 dark:border-neutral-800'
                  : 'border-amber-300 dark:border-amber-700/60 ring-2 ring-amber-500/20'
              )}
            >
              {/* Voucher Top Header */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-neutral-100 dark:border-neutral-800">
                <div>
                  <div className="flex items-center gap-2.5">
                    <h3 className="text-sm font-bold text-neutral-900 dark:text-white">
                      {voucher.month}
                    </h3>
                    <span className="font-mono text-xs text-neutral-500">
                      Challan #{voucher.voucherNo}
                    </span>
                    <span
                      className={cn(
                        'px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider',
                        isPaid
                          ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20'
                          : 'bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20'
                      )}
                    >
                      {isPaid ? 'Paid' : 'Due for Payment'}
                    </span>
                  </div>
                  <p className="text-xs text-neutral-500 mt-1">
                    Issue Date: {voucher.issueDate} • Due Date: {voucher.dueDate} • 1Bill ID:{' '}
                    <span className="font-mono text-neutral-700 dark:text-neutral-300 font-bold">
                      {voucher.consumerId1Bill}
                    </span>
                  </p>
                </div>

                <div className="text-end self-start sm:self-auto">
                  <span className="text-xs text-neutral-500">Total Net Payable</span>
                  <div className="text-xl font-extrabold text-blue-600 dark:text-blue-400">
                    PKR {voucher.totalAmount.toLocaleString()}
                  </div>
                </div>
              </div>

              {/* Itemized Fee Breakdown Table */}
              <div className="py-4 grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-3 text-xs border-b border-neutral-100 dark:border-neutral-800">
                <div className="p-2.5 rounded-xl bg-neutral-50 dark:bg-neutral-800/40">
                  <span className="text-neutral-500 block text-[11px]">Tuition Fee</span>
                  <div className="font-bold text-neutral-900 dark:text-white mt-0.5">
                    PKR {voucher.tuitionFee.toLocaleString()}
                  </div>
                </div>

                <div className="p-2.5 rounded-xl bg-neutral-50 dark:bg-neutral-800/40">
                  <span className="text-neutral-500 block text-[11px]">STEM & Lab</span>
                  <div className="font-bold text-neutral-900 dark:text-white mt-0.5">
                    PKR {voucher.labFee.toLocaleString()}
                  </div>
                </div>

                <div className="p-2.5 rounded-xl bg-neutral-50 dark:bg-neutral-800/40">
                  <span className="text-neutral-500 block text-[11px]">Transport</span>
                  <div className="font-bold text-neutral-900 dark:text-white mt-0.5">
                    PKR {voucher.transportFee.toLocaleString()}
                  </div>
                </div>

                <div className="p-2.5 rounded-xl bg-neutral-50 dark:bg-neutral-800/40">
                  <span className="text-neutral-500 block text-[11px]">Sports & Activities</span>
                  <div className="font-bold text-neutral-900 dark:text-white mt-0.5">
                    PKR {voucher.sportsFund.toLocaleString()}
                  </div>
                </div>

                <div className="p-2.5 rounded-xl bg-neutral-50 dark:bg-neutral-800/40">
                  <span className="text-neutral-500 block text-[11px]">Examination Fee</span>
                  <div className="font-bold text-neutral-900 dark:text-white mt-0.5">
                    PKR {voucher.examFee.toLocaleString()}
                  </div>
                </div>

                <div className="p-2.5 rounded-xl bg-emerald-50 dark:bg-emerald-950/20 border border-emerald-500/20">
                  <span className="text-emerald-700 dark:text-emerald-400 block text-[11px]">
                    Scholarship/Concession
                  </span>
                  <div className="font-bold text-emerald-600 dark:text-emerald-400 mt-0.5">
                    - PKR {voucher.concession.toLocaleString()}
                  </div>
                </div>
              </div>

              {/* Footer Actions */}
              <div className="pt-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="text-xs">
                  {isPaid ? (
                    <span className="flex items-center gap-1.5 text-emerald-600 dark:text-emerald-400 font-medium">
                      <CheckCircle2 className="size-4" />
                      Paid on {voucher.paidOn} via {voucher.paymentMethod} (Ref: {voucher.transactionRef})
                    </span>
                  ) : (
                    <span className="text-amber-600 dark:text-amber-400 font-medium flex items-center gap-1.5">
                      <AlertCircle className="size-4" />
                      Pay before {voucher.dueDate} to prevent PKR {voucher.lateSurcharge} late fee surcharge.
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleOpenPreview(voucher)}
                    className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 text-xs font-semibold text-neutral-800 dark:text-neutral-200 hover:bg-neutral-100 dark:hover:bg-neutral-700 transition-colors shadow-2xs"
                  >
                    <Download className="size-3.5" />
                    <span>Print / PDF Voucher</span>
                  </button>

                  {!isPaid && (
                    <button
                      onClick={() => handleOpenPay(voucher)}
                      className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold transition-all shadow-md active:scale-95"
                    >
                      <CreditCard className="size-3.5" />
                      <span>Pay Online Now</span>
                    </button>
                  )}
                </div>
              </div>
            </div>
          )
        })}
      </div>

      {/* 3-Copy Printable Voucher Preview Modal */}
      {previewModalOpen && selectedVoucherForPreview && (
        <div
          className="fixed inset-0 z-50 bg-black/80 backdrop-blur-xs flex items-center justify-center p-4 overflow-y-auto animate-in fade-in"
          role="dialog"
          aria-modal="true"
        >
          <div className="w-full max-w-4xl bg-white text-neutral-900 rounded-2xl shadow-2xl p-6 sm:p-8 my-8 relative flex flex-col max-h-[90vh]">
            {/* Modal Header */}
            <div className="flex items-center justify-between pb-4 border-b border-neutral-200">
              <div>
                <h3 className="text-base font-bold text-neutral-900">
                  Official Bank Fee Voucher Preview
                </h3>
                <p className="text-xs text-neutral-500">
                  Standard 3-Copy Challan (Student Copy, Bank Copy, Institution Copy)
                </p>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => window.print()}
                  className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold transition-colors shadow-xs"
                >
                  <Printer className="size-3.5" />
                  <span>Print Challan</span>
                </button>
                <button
                  onClick={() => setPreviewModalOpen(false)}
                  className="p-1.5 rounded-lg text-neutral-400 hover:text-neutral-900 hover:bg-neutral-100"
                >
                  <X className="size-5" />
                </button>
              </div>
            </div>

            {/* Printable 3-Copy Challan Grid */}
            <div className="flex-1 overflow-y-auto py-6">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 border-2 border-neutral-800 p-4 rounded-xl text-[11px] font-sans">
                {['STUDENT COPY', 'BANK COPY', 'SCHOOL / AUDIT COPY'].map((copyTitle, idx) => (
                  <div
                    key={idx}
                    className={cn(
                      'p-3 space-y-2.5',
                      idx < 2 ? 'md:border-e border-dashed border-neutral-400' : ''
                    )}
                  >
                    {/* Header */}
                    <div className="text-center border-b pb-2">
                      <div className="font-extrabold text-xs uppercase tracking-wider text-blue-900">
                        CSG International School
                      </div>
                      <div className="text-[9px] text-neutral-600">
                        {activeChild.campus}
                      </div>
                      <div className="inline-block mt-1 px-2 py-0.5 rounded bg-neutral-200 text-[10px] font-bold">
                        {copyTitle}
                      </div>
                    </div>

                    {/* Voucher / 1Bill Info */}
                    <div className="space-y-1 bg-neutral-50 p-2 rounded border">
                      <div className="flex justify-between">
                        <span className="text-neutral-600">Challan No:</span>
                        <span className="font-mono font-bold">
                          {selectedVoucherForPreview.voucherNo}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-neutral-600">1Bill ID:</span>
                        <span className="font-mono font-bold text-blue-800">
                          {selectedVoucherForPreview.consumerId1Bill}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-neutral-600">Due Date:</span>
                        <span className="font-bold text-rose-700">
                          {selectedVoucherForPreview.dueDate}
                        </span>
                      </div>
                    </div>

                    {/* Student Info */}
                    <div className="space-y-1 border-b pb-2">
                      <div className="flex justify-between">
                        <span className="text-neutral-600">Student:</span>
                        <span className="font-bold truncate max-w-[130px]">
                          {activeChild.name}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-neutral-600">Roll No / ID:</span>
                        <span className="font-mono">{activeChild.rollNo}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-neutral-600">Grade:</span>
                        <span className="truncate max-w-[130px]">{activeChild.grade}</span>
                      </div>
                    </div>

                    {/* Particulars Table */}
                    <div className="space-y-1 border-b pb-2">
                      <div className="flex justify-between text-neutral-600">
                        <span>Tuition Fee</span>
                        <span>PKR {selectedVoucherForPreview.tuitionFee.toLocaleString()}</span>
                      </div>
                      <div className="flex justify-between text-neutral-600">
                        <span>Lab & STEM</span>
                        <span>PKR {selectedVoucherForPreview.labFee.toLocaleString()}</span>
                      </div>
                      <div className="flex justify-between text-neutral-600">
                        <span>Transport</span>
                        <span>PKR {selectedVoucherForPreview.transportFee.toLocaleString()}</span>
                      </div>
                      <div className="flex justify-between text-neutral-600">
                        <span>Sports / Exam</span>
                        <span>
                          PKR{' '}
                          {(
                            selectedVoucherForPreview.sportsFund + selectedVoucherForPreview.examFee
                          ).toLocaleString()}
                        </span>
                      </div>
                      {selectedVoucherForPreview.concession > 0 && (
                        <div className="flex justify-between text-emerald-700 font-semibold">
                          <span>Concession</span>
                          <span>- PKR {selectedVoucherForPreview.concession.toLocaleString()}</span>
                        </div>
                      )}
                      <div className="flex justify-between font-bold text-xs pt-1 border-t text-neutral-900">
                        <span>Total Payable:</span>
                        <span>PKR {selectedVoucherForPreview.totalAmount.toLocaleString()}</span>
                      </div>
                    </div>

                    {/* Barcode & Bank Stamp */}
                    <div className="text-center pt-2 space-y-1">
                      <div className="font-mono text-center tracking-widest text-[9px] bg-neutral-100 py-1 rounded">
                        ||| | ||||| || |||||| | |||
                      </div>
                      <div className="text-[8px] text-neutral-500">
                        Payable at all 1Bill / KuickPay partner bank branches, ATM & Mobile Apps.
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Online Payment Modal (1Bill / Card / Bank Upload) */}
      {paymentModalOpen && selectedVoucherForPreview && (
        <div
          className="fixed inset-0 z-50 bg-black/75 backdrop-blur-xs flex items-center justify-center p-4 animate-in fade-in"
          role="dialog"
          aria-modal="true"
        >
          <div className="w-full max-w-lg bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 rounded-2xl shadow-2xl p-6">
            <div className="flex items-center justify-between pb-3 border-b border-neutral-100 dark:border-neutral-800">
              <div className="flex items-center gap-2">
                <CreditCard className="size-5 text-emerald-600" />
                <h3 className="text-base font-bold text-neutral-900 dark:text-white">
                  Pay School Fee Online
                </h3>
              </div>
              <button
                onClick={() => setPaymentModalOpen(false)}
                className="text-neutral-400 hover:text-neutral-900 dark:hover:text-white"
              >
                ✕
              </button>
            </div>

            {paymentSuccess ? (
              <div className="py-8 text-center space-y-3 animate-in zoom-in-95">
                <div className="size-16 rounded-full bg-emerald-500/20 text-emerald-500 mx-auto flex items-center justify-center">
                  <CheckCircle2 className="size-10" />
                </div>
                <h3 className="text-lg font-bold text-neutral-900 dark:text-white">
                  Payment Successful!
                </h3>
                <p className="text-xs text-neutral-500 max-w-xs mx-auto">
                  Voucher #{selectedVoucherForPreview.voucherNo} has been marked as PAID. Official digital tax receipt has been generated.
                </p>
              </div>
            ) : (
              <form onSubmit={handleExecutePayment} className="py-4 space-y-4 text-xs">
                {/* Amount Summary */}
                <div className="p-3.5 rounded-xl bg-neutral-50 dark:bg-neutral-800/50 border border-neutral-200 dark:border-neutral-700/60 flex items-center justify-between">
                  <div>
                    <span className="text-neutral-500">Student: {activeChild.name}</span>
                    <div className="font-bold text-neutral-900 dark:text-white text-xs mt-0.5">
                      {selectedVoucherForPreview.month}
                    </div>
                  </div>
                  <div className="text-end">
                    <span className="text-neutral-500 text-[11px]">Total Due</span>
                    <div className="text-base font-extrabold text-emerald-600 dark:text-emerald-400">
                      PKR {selectedVoucherForPreview.totalAmount.toLocaleString()}
                    </div>
                  </div>
                </div>

                {/* Gateway Tabs */}
                <div className="grid grid-cols-3 gap-1.5 p-1 rounded-xl bg-neutral-100 dark:bg-neutral-800">
                  <button
                    type="button"
                    onClick={() => setPaymentMethodTab('1bill')}
                    className={cn(
                      'py-2 rounded-lg font-bold transition-all text-center',
                      paymentMethodTab === '1bill'
                        ? 'bg-white dark:bg-neutral-900 text-emerald-600 dark:text-emerald-400 shadow-xs'
                        : 'text-neutral-600 dark:text-neutral-400'
                    )}
                  >
                    1Bill / KuickPay
                  </button>
                  <button
                    type="button"
                    onClick={() => setPaymentMethodTab('card')}
                    className={cn(
                      'py-2 rounded-lg font-bold transition-all text-center',
                      paymentMethodTab === 'card'
                        ? 'bg-white dark:bg-neutral-900 text-blue-600 dark:text-blue-400 shadow-xs'
                        : 'text-neutral-600 dark:text-neutral-400'
                    )}
                  >
                    Card (Visa/MC)
                  </button>
                  <button
                    type="button"
                    onClick={() => setPaymentMethodTab('bank_transfer')}
                    className={cn(
                      'py-2 rounded-lg font-bold transition-all text-center',
                      paymentMethodTab === 'bank_transfer'
                        ? 'bg-white dark:bg-neutral-900 text-purple-600 dark:text-purple-400 shadow-xs'
                        : 'text-neutral-600 dark:text-neutral-400'
                    )}
                  >
                    Bank Receipt Upload
                  </button>
                </div>

                {/* TAB 1: 1BILL / KUICKPAY */}
                {paymentMethodTab === '1bill' && (
                  <div className="p-4 rounded-xl bg-emerald-50/50 dark:bg-emerald-950/20 border border-emerald-500/20 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-neutral-600 dark:text-neutral-300">
                        1Bill Consumer ID:
                      </span>
                      <span className="font-mono font-bold text-sm text-emerald-700 dark:text-emerald-300">
                        {selectedVoucherForPreview.consumerId1Bill}
                      </span>
                    </div>
                    <p className="text-[11px] text-neutral-500 leading-relaxed">
                      Open your Mobile Banking App (HBL, Meezan, Alfalah, Nayapay, Sadapay), go to <strong>Bill Payments &gt; 1Bill Top-Up / Invoice</strong>, and enter this Consumer ID.
                    </p>
                  </div>
                )}

                {/* TAB 2: CREDIT / DEBIT CARD */}
                {paymentMethodTab === 'card' && (
                  <div className="space-y-3">
                    <div>
                      <label className="block text-neutral-600 dark:text-neutral-300 mb-1 font-medium">
                        Card Number
                      </label>
                      <input
                        type="text"
                        required
                        value={cardNumber}
                        onChange={(e) => setCardNumber(e.target.value)}
                        placeholder="4242 •••• •••• 4242"
                        className="w-full px-3 py-2 rounded-xl border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-800 text-xs text-neutral-900 dark:text-white"
                      />
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="block text-neutral-600 dark:text-neutral-300 mb-1 font-medium">
                          Expiry Date
                        </label>
                        <input
                          type="text"
                          required
                          value={cardExpiry}
                          onChange={(e) => setCardExpiry(e.target.value)}
                          placeholder="MM/YY"
                          className="w-full px-3 py-2 rounded-xl border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-800 text-xs text-neutral-900 dark:text-white"
                        />
                      </div>
                      <div>
                        <label className="block text-neutral-600 dark:text-neutral-300 mb-1 font-medium">
                          CVV
                        </label>
                        <input
                          type="password"
                          required
                          maxLength={4}
                          value={cardCvc}
                          onChange={(e) => setCardCvc(e.target.value)}
                          placeholder="•••"
                          className="w-full px-3 py-2 rounded-xl border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-800 text-xs text-neutral-900 dark:text-white"
                        />
                      </div>
                    </div>
                  </div>
                )}

                {/* TAB 3: BANK RECEIPT UPLOAD */}
                {paymentMethodTab === 'bank_transfer' && (
                  <div className="space-y-3">
                    <div>
                      <label className="block text-neutral-600 dark:text-neutral-300 mb-1 font-medium">
                        Bank Transaction Reference / Deposit Slip ID
                      </label>
                      <input
                        type="text"
                        required
                        value={bankTxnRef}
                        onChange={(e) => setBankTxnRef(e.target.value)}
                        placeholder="e.g. MEZN-TX-8839104"
                        className="w-full px-3 py-2 rounded-xl border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-800 text-xs text-neutral-900 dark:text-white"
                      />
                    </div>

                    <div
                      onClick={() => setUploadedReceiptName('hbl_deposit_slip_signed.pdf')}
                      className="p-4 border-2 border-dashed border-neutral-300 dark:border-neutral-700 rounded-xl text-center cursor-pointer hover:border-emerald-500 transition-colors bg-neutral-50 dark:bg-neutral-800/30"
                    >
                      <UploadCloud className="size-6 text-neutral-400 mx-auto mb-1" />
                      <div className="font-semibold text-neutral-700 dark:text-neutral-300">
                        {uploadedReceiptName || 'Click to Upload Deposit Slip / Screenshot'}
                      </div>
                      <span className="text-[10px] text-neutral-400">
                        Supports PDF, PNG, JPG up to 10MB
                      </span>
                    </div>
                  </div>
                )}

                {/* Submit Actions */}
                <div className="pt-2 flex items-center justify-end gap-2">
                  <button
                    type="button"
                    onClick={() => setPaymentModalOpen(false)}
                    className="px-4 py-2 rounded-xl border border-neutral-200 dark:border-neutral-700 text-xs font-semibold text-neutral-700 dark:text-neutral-300 hover:bg-neutral-100"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={isProcessingPayment}
                    className="px-5 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white text-xs font-bold shadow-md transition-all flex items-center gap-1.5"
                  >
                    {isProcessingPayment && <span className="animate-spin">⏳</span>}
                    <span>
                      Confirm PKR {selectedVoucherForPreview.totalAmount.toLocaleString()}
                    </span>
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
