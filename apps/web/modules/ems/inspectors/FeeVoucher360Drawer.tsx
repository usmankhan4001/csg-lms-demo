'use client'

import React, { useState } from 'react'
import {
  FileText,
  DollarSign,
  Calendar,
  CreditCard,
  Printer,
  Bell,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Sparkles,
  QrCode,
  Building2,
  Users,
  ShieldCheck,
  Send,
  Download,
  Percent,
  Receipt,
  Layers,
  ChevronRight,
} from 'lucide-react'
import { Entity360Drawer, Entity360Tab, Entity360Badge, Entity360QuickAction } from '@/components/ems/Entity360Drawer'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog'
import toast from 'react-hot-toast'

export interface FeeLineItem {
  id: string
  description: string
  category: 'Tuition' | 'Lab & STEM' | 'Activity & Sports' | 'Library & Tech' | 'Concession'
  amountPKR: number
  isDiscount?: boolean
}

export interface FeeInstallmentSchedule {
  installmentNumber: number
  dueDate: string
  amountPKR: number
  lateSurchargePKR: number
  status: 'PAID' | 'DUE' | 'OVERDUE'
  paidDate?: string
}

export interface FeeGatewayTransaction {
  id: string
  gateway: '1Link / Kuickpay' | 'Stripe' | 'HBL Branch Deposit' | 'Bursar Counter Cash'
  referenceNo: string
  amountPKR: number
  timestamp: string
  status: 'SETTLED' | 'PENDING' | 'FAILED'
  receiptUrl?: string
}

export interface FeeVoucher360Profile {
  voucherNo: string
  challanId: string
  consumerId1Link: string
  studentId: string
  studentName: string
  rollNo: string
  grade: string
  section: string
  campus: string
  billingMonth: string
  issueDate: string
  dueDate: string
  validUntilDate: string
  status: 'PAID' | 'PARTIAL' | 'UNPAID' | 'OVERDUE'
  grossTotalPKR: number
  totalDiscountPKR: number
  lateFinePKR: number
  netPayablePKR: number
  amountPaidPKR: number
  guardianName: string
  guardianPhone: string
  guardianEmail: string
  lineItems: FeeLineItem[]
  installments: FeeInstallmentSchedule[]
  transactions: FeeGatewayTransaction[]
}

export interface FeeVoucher360DrawerProps {
  isOpen: boolean
  onClose: () => void
  voucher?: FeeVoucher360Profile | null
  onRecordPayment?: (voucherNo: string, amount: number, method: string) => void
  onSendReminder?: (voucherNo: string) => void
}

const DEFAULT_VOUCHER: FeeVoucher360Profile = {
  voucherNo: 'VOUCH-202609-0842',
  challanId: 'CHL-9940128',
  consumerId1Link: '100481920199',
  studentId: 'STU-2026-1042',
  studentName: 'Aiden Vance',
  rollNo: '2026-CS-1042',
  grade: 'Grade 11',
  section: 'Section 11-A',
  campus: 'Main Science Campus, Lahore',
  billingMonth: 'September 2026',
  issueDate: '2026-09-01',
  dueDate: '2026-09-10',
  validUntilDate: '2026-09-25',
  status: 'OVERDUE',
  grossTotalPKR: 52000,
  totalDiscountPKR: 7000,
  lateFinePKR: 1500,
  netPayablePKR: 46500,
  amountPaidPKR: 0,
  guardianName: 'Muhammad Vance',
  guardianPhone: '+92 300 8472910',
  guardianEmail: 'm.vance@techventures.pk',
  lineItems: [
    { id: 'LI-01', description: 'Tuition Fee (Grade 11 STEM Cohort)', category: 'Tuition', amountPKR: 38000 },
    { id: 'LI-02', description: 'Advanced Physics & Robotics Lab Fee', category: 'Lab & STEM', amountPKR: 8000 },
    { id: 'LI-03', description: 'Digital LMS & Cloud Infrastructure Charge', category: 'Library & Tech', amountPKR: 4000 },
    { id: 'LI-04', description: 'Sports & Student Activity Levy', category: 'Activity & Sports', amountPKR: 2000 },
    { id: 'LI-05', description: 'Merit Scholarship Discount (15%)', category: 'Concession', amountPKR: -7000, isDiscount: true },
  ],
  installments: [
    { installmentNumber: 1, dueDate: '2026-09-10', amountPKR: 23250, lateSurchargePKR: 750, status: 'OVERDUE' },
    { installmentNumber: 2, dueDate: '2026-09-25', amountPKR: 23250, lateSurchargePKR: 750, status: 'DUE' },
  ],
  transactions: [
    {
      id: 'TXN-01',
      gateway: '1Link / Kuickpay',
      referenceNo: '1LINK-BILL-9940128',
      amountPKR: 45000,
      timestamp: '2026-08-08 11:24',
      status: 'SETTLED',
      receiptUrl: '#',
    },
  ],
}

export const FeeVoucher360Drawer: React.FC<FeeVoucher360DrawerProps> = ({
  isOpen,
  onClose,
  voucher = DEFAULT_VOUCHER,
  onRecordPayment,
  onSendReminder,
}) => {
  const currentVoucher = voucher || DEFAULT_VOUCHER
  const [activeTab, setActiveTab] = useState<string>('overview')

  // Modals
  const [isPrintBankSlipOpen, setIsPrintBankSlipOpen] = useState<boolean>(false)
  const [isPaymentModalOpen, setIsPaymentModalOpen] = useState<boolean>(false)

  // Payment form state
  const [payAmount, setPayAmount] = useState<number>(currentVoucher.netPayablePKR)
  const [payMethod, setPayMethod] = useState<string>('1Link / Kuickpay')
  const [payNotes, setPayNotes] = useState<string>('')

  const tabs: Entity360Tab[] = [
    { id: 'overview', label: 'Voucher Overview', icon: <FileText className="h-3.5 w-3.5" /> },
    { id: 'items', label: 'Line Items & Discounts', icon: <DollarSign className="h-3.5 w-3.5" />, count: currentVoucher.lineItems.length },
    { id: 'installments', label: 'Payment Installments', icon: <Calendar className="h-3.5 w-3.5" />, count: currentVoucher.installments.length },
    { id: 'transactions', label: 'Gateway Transactions & Receipts', icon: <Receipt className="h-3.5 w-3.5" /> },
  ]

  const badges: Entity360Badge[] = [
    {
      label: currentVoucher.status,
      variant:
        currentVoucher.status === 'PAID'
          ? 'success'
          : currentVoucher.status === 'OVERDUE'
          ? 'destructive'
          : 'warning',
    },
    { label: currentVoucher.billingMonth, variant: 'purple' },
    { label: `Challan #${currentVoucher.challanId}`, variant: 'blue' },
  ]

  const quickActions: Entity360QuickAction[] = [
    {
      label: 'Print 3-Part Bank Slip',
      icon: <Printer className="h-3.5 w-3.5" />,
      onClick: () => setIsPrintBankSlipOpen(true),
      variant: 'default',
    },
    {
      label: 'Record Manual Payment',
      icon: <CreditCard className="h-3.5 w-3.5" />,
      onClick: () => {
        setPayAmount(currentVoucher.netPayablePKR)
        setIsPaymentModalOpen(true)
      },
      variant: 'primary',
    },
    {
      label: 'Send Reminder',
      icon: <Bell className="h-3.5 w-3.5" />,
      onClick: () => {
        if (onSendReminder) onSendReminder(currentVoucher.voucherNo)
        toast.success(`Payment reminder SMS & WhatsApp dispatched to ${currentVoucher.guardianPhone}!`)
      },
      variant: 'outline',
    },
  ]

  const handlePaymentSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (payAmount <= 0) {
      toast.error('Amount must be greater than zero')
      return
    }
    if (onRecordPayment) {
      onRecordPayment(currentVoucher.voucherNo, payAmount, payMethod)
    }
    toast.success(`Payment of PKR ${payAmount.toLocaleString()} recorded for Voucher #${currentVoucher.voucherNo}!`)
    setIsPaymentModalOpen(false)
  }

  return (
    <>
      <Entity360Drawer
        isOpen={isOpen}
        onClose={onClose}
        title={currentVoucher.voucherNo}
        subtitle={`Student: ${currentVoucher.studentName} (${currentVoucher.rollNo}) • Due: ${currentVoucher.dueDate}`}
        entityTypeBadge="Fee Voucher 360°"
        avatar={{
          icon: <Receipt className="h-6 w-6 text-white" />,
          statusDot: currentVoucher.status === 'PAID' ? 'online' : 'busy',
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
                <p className="text-[10px] text-zinc-400 font-medium">Net Payable</p>
                <p className="font-bold text-zinc-900 dark:text-zinc-100">PKR {currentVoucher.netPayablePKR.toLocaleString()}</p>
              </div>
            </div>
            <div className="flex items-center gap-2 p-2 rounded-lg bg-zinc-100/80 dark:bg-zinc-800/60 border border-zinc-200/50 dark:border-zinc-700/50">
              <Clock className="h-4 w-4 text-rose-500 shrink-0" />
              <div>
                <p className="text-[10px] text-zinc-400 font-medium">Due Date</p>
                <p className="font-bold text-rose-600 dark:text-rose-400">{currentVoucher.dueDate}</p>
              </div>
            </div>
            <div className="flex items-center gap-2 p-2 rounded-lg bg-zinc-100/80 dark:bg-zinc-800/60 border border-zinc-200/50 dark:border-zinc-700/50">
              <QrCode className="h-4 w-4 text-indigo-500 shrink-0" />
              <div>
                <p className="text-[10px] text-zinc-400 font-medium">1Link Consumer ID</p>
                <p className="font-bold text-indigo-600 dark:text-indigo-400 font-mono">{currentVoucher.consumerId1Link}</p>
              </div>
            </div>
            <div className="flex items-center gap-2 p-2 rounded-lg bg-zinc-100/80 dark:bg-zinc-800/60 border border-zinc-200/50 dark:border-zinc-700/50">
              <Building2 className="h-4 w-4 text-purple-500 shrink-0" />
              <div>
                <p className="text-[10px] text-zinc-400 font-medium">Designated Banks</p>
                <p className="font-bold text-zinc-900 dark:text-zinc-100 truncate">HBL / Meezan / 1Link</p>
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
                Voucher & Student Billing Metadata
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
                <div>
                  <span className="text-zinc-400">Student Name</span>
                  <p className="font-semibold text-zinc-900 dark:text-zinc-100 mt-0.5">{currentVoucher.studentName}</p>
                </div>
                <div>
                  <span className="text-zinc-400">Roll No</span>
                  <p className="font-semibold text-zinc-900 dark:text-zinc-100 mt-0.5 font-mono">{currentVoucher.rollNo}</p>
                </div>
                <div>
                  <span className="text-zinc-400">Class & Section</span>
                  <p className="font-semibold text-zinc-900 dark:text-zinc-100 mt-0.5">{currentVoucher.grade} - {currentVoucher.section}</p>
                </div>
                <div>
                  <span className="text-zinc-400">Campus Facility</span>
                  <p className="font-semibold text-zinc-900 dark:text-zinc-100 mt-0.5">{currentVoucher.campus}</p>
                </div>
                <div>
                  <span className="text-zinc-400">Challan Reference No</span>
                  <p className="font-semibold text-zinc-900 dark:text-zinc-100 mt-0.5 font-mono">{currentVoucher.challanId}</p>
                </div>
                <div>
                  <span className="text-zinc-400">Validity Expiration</span>
                  <p className="font-semibold text-zinc-900 dark:text-zinc-100 mt-0.5">{currentVoucher.validUntilDate}</p>
                </div>
              </div>
            </div>

            {/* Online Banking 1Link Card */}
            <div className="p-4 rounded-xl border border-indigo-200 dark:border-indigo-900/60 bg-gradient-to-r from-indigo-500/10 via-purple-500/10 to-transparent flex items-center justify-between flex-wrap gap-4 text-xs">
              <div className="flex items-center gap-3">
                <QrCode className="h-10 w-10 text-indigo-600 dark:text-indigo-400 shrink-0" />
                <div>
                  <h4 className="font-bold text-zinc-900 dark:text-zinc-100">1Link 1Bill Direct Digital Payment</h4>
                  <p className="text-[11px] text-zinc-500">Payable via all major Banking Apps, EasyPaisa, JazzCash, or ATM</p>
                  <p className="font-mono font-bold text-indigo-600 dark:text-indigo-400 text-sm mt-0.5">Consumer No: {currentVoucher.consumerId1Link}</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => {
                  navigator.clipboard.writeText(currentVoucher.consumerId1Link)
                  toast.success('Consumer ID copied to clipboard!')
                }}
                className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-xs transition-colors"
              >
                Copy Consumer No
              </button>
            </div>
          </div>
        )}

        {/* TAB 2: LINE ITEMS & DISCOUNTS */}
        {activeTab === 'items' && (
          <div className="space-y-4">
            <h3 className="text-sm font-bold text-zinc-900 dark:text-zinc-100">Itemized Fee Structure & Applied Concessions</h3>
            <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 overflow-hidden">
              <table className="w-full text-left text-xs">
                <thead className="bg-zinc-50/80 dark:bg-zinc-800/50 text-zinc-400 uppercase font-semibold border-b border-zinc-200 dark:border-zinc-800">
                  <tr>
                    <th className="py-2.5 px-4">Line Item Description</th>
                    <th className="py-2.5 px-4">Category</th>
                    <th className="py-2.5 px-4 text-right">Amount (PKR)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800">
                  {currentVoucher.lineItems.map((item) => (
                    <tr key={item.id} className="hover:bg-zinc-50/50 dark:hover:bg-zinc-800/30">
                      <td className="py-3 px-4 font-semibold text-zinc-900 dark:text-zinc-100">{item.description}</td>
                      <td className="py-3 px-4"><span className="px-2 py-0.5 rounded bg-zinc-100 dark:bg-zinc-800 text-[10px] font-medium">{item.category}</span></td>
                      <td className={`py-3 px-4 text-right font-mono font-bold ${item.isDiscount ? 'text-emerald-600' : 'text-zinc-900 dark:text-zinc-100'}`}>
                        {item.isDiscount ? `- PKR ${Math.abs(item.amountPKR).toLocaleString()}` : `PKR ${item.amountPKR.toLocaleString()}`}
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot className="bg-zinc-50/90 dark:bg-zinc-800/70 border-t border-zinc-200 dark:border-zinc-800 font-bold">
                  <tr>
                    <td colSpan={2} className="py-2.5 px-4 text-right text-zinc-500">Gross Total:</td>
                    <td className="py-2.5 px-4 text-right font-mono">PKR {currentVoucher.grossTotalPKR.toLocaleString()}</td>
                  </tr>
                  <tr>
                    <td colSpan={2} className="py-2.5 px-4 text-right text-emerald-600">Total Scholarship / Concession:</td>
                    <td className="py-2.5 px-4 text-right font-mono text-emerald-600">- PKR {currentVoucher.totalDiscountPKR.toLocaleString()}</td>
                  </tr>
                  {currentVoucher.lateFinePKR > 0 && (
                    <tr>
                      <td colSpan={2} className="py-2.5 px-4 text-right text-rose-600">Late Payment Surcharge:</td>
                      <td className="py-2.5 px-4 text-right font-mono text-rose-600">+ PKR {currentVoucher.lateFinePKR.toLocaleString()}</td>
                    </tr>
                  )}
                  <tr className="border-t border-zinc-300 dark:border-zinc-700 text-sm">
                    <td colSpan={2} className="py-3 px-4 text-right font-black text-zinc-900 dark:text-zinc-100">Net Payable Total:</td>
                    <td className="py-3 px-4 text-right font-mono font-black text-indigo-600 dark:text-indigo-400">PKR {currentVoucher.netPayablePKR.toLocaleString()}</td>
                  </tr>
                </tfoot>
              </table>
            </div>
          </div>
        )}

        {/* TAB 3: INSTALLMENTS */}
        {activeTab === 'installments' && (
          <div className="space-y-4">
            <h3 className="text-sm font-bold text-zinc-900 dark:text-zinc-100">Bi-Monthly Installment Schedule</h3>
            <div className="space-y-3">
              {currentVoucher.installments.map((inst) => (
                <div key={inst.installmentNumber} className="p-4 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 flex items-center justify-between text-xs">
                  <div>
                    <span className="font-bold text-zinc-900 dark:text-zinc-100">Installment #{inst.installmentNumber}</span>
                    <p className="text-[11px] text-zinc-500 mt-0.5">Due Date: {inst.dueDate} • Late Surcharge: PKR {inst.lateSurchargePKR}</p>
                  </div>
                  <div className="text-right">
                    <p className="font-mono font-bold text-sm text-zinc-900 dark:text-zinc-100">PKR {inst.amountPKR.toLocaleString()}</p>
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300">
                      {inst.status}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* TAB 4: TRANSACTIONS & RECEIPTS */}
        {activeTab === 'transactions' && (
          <div className="space-y-4">
            <h3 className="text-sm font-bold text-zinc-900 dark:text-zinc-100">Gateway Transaction & Settlement History</h3>
            <div className="space-y-3">
              {currentVoucher.transactions.map((txn) => (
                <div key={txn.id} className="p-4 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 flex items-center justify-between text-xs">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-800">
                        {txn.gateway}
                      </span>
                      <span className="font-mono text-zinc-500 font-bold">{txn.referenceNo}</span>
                    </div>
                    <p className="text-[10px] text-zinc-400 mt-1">Settled on {txn.timestamp}</p>
                  </div>
                  <div className="text-right flex items-center gap-3">
                    <div>
                      <p className="font-bold font-mono text-emerald-600">PKR {txn.amountPKR.toLocaleString()}</p>
                      <span className="text-[10px] text-emerald-600 font-bold">SETTLED</span>
                    </div>
                    <button
                      type="button"
                      onClick={() => toast.success('Digital receipt downloaded')}
                      className="p-2 rounded-lg bg-zinc-100 hover:bg-zinc-200 dark:bg-zinc-800 dark:hover:bg-zinc-700 text-zinc-700 dark:text-zinc-300"
                    >
                      <Download className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </Entity360Drawer>

      {/* MODAL 1: 3-PART BANK SLIP */}
      <Dialog open={isPrintBankSlipOpen} onOpenChange={setIsPrintBankSlipOpen}>
        <DialogContent className="sm:max-w-xl">
          <DialogHeader>
            <DialogTitle>3-Part Standard Bank Challan Slip</DialogTitle>
            <DialogDescription>Bank Copy • School Accounts Copy • Student Copy</DialogDescription>
          </DialogHeader>
          <div className="grid grid-cols-3 gap-2 p-3 bg-zinc-50 dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800 text-[10px]">
            {['Bank Copy', 'School Copy', 'Student Copy'].map((copy, idx) => (
              <div key={idx} className="p-2.5 border border-dashed border-zinc-300 dark:border-zinc-700 rounded-lg space-y-1.5 bg-white dark:bg-zinc-950">
                <p className="font-black text-center border-b border-zinc-200 dark:border-zinc-800 pb-1 text-indigo-600 dark:text-indigo-400 uppercase tracking-wider">{copy}</p>
                <p className="font-bold">{currentVoucher.studentName}</p>
                <p className="font-mono text-zinc-500">Roll: {currentVoucher.rollNo}</p>
                <p className="font-mono font-bold text-emerald-600">PKR {currentVoucher.netPayablePKR.toLocaleString()}</p>
                <p className="text-[9px] text-zinc-400">Due: {currentVoucher.dueDate}</p>
              </div>
            ))}
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={() => {
                window.print()
                toast.success('Dispatched to Printer!')
                setIsPrintBankSlipOpen(false)
              }}
              className="px-4 py-2 text-xs font-semibold rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white flex items-center gap-1.5"
            >
              <Printer className="h-3.5 w-3.5" />
              Print Challan PDF
            </button>
          </div>
        </DialogContent>
      </Dialog>

      {/* MODAL 2: MANUAL PAYMENT */}
      <Dialog open={isPaymentModalOpen} onOpenChange={setIsPaymentModalOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Record Manual Fee Receipt</DialogTitle>
            <DialogDescription>Record cash or bank branch deposit</DialogDescription>
          </DialogHeader>
          <form onSubmit={handlePaymentSubmit} className="space-y-4 text-xs">
            <div>
              <label className="block font-medium text-zinc-700 dark:text-zinc-300 mb-1">Payment Amount (PKR)</label>
              <input
                type="number"
                value={payAmount}
                onChange={(e) => setPayAmount(Number(e.target.value))}
                className="w-full px-3 py-2 rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 font-bold"
                required
              />
            </div>
            <div>
              <label className="block font-medium text-zinc-700 dark:text-zinc-300 mb-1">Payment Method</label>
              <select
                value={payMethod}
                onChange={(e) => setPayMethod(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 font-semibold"
              >
                <option value="HBL Branch Deposit">HBL Branch Deposit</option>
                <option value="Bursar Counter Cash">Bursar Counter Cash</option>
                <option value="1Link / Kuickpay">1Link / Kuickpay</option>
                <option value="Direct Wire Transfer">Direct Wire Transfer</option>
              </select>
            </div>
            <div>
              <label className="block font-medium text-zinc-700 dark:text-zinc-300 mb-1">Deposit Slip / Ref #</label>
              <input
                type="text"
                value={payNotes}
                onChange={(e) => setPayNotes(e.target.value)}
                placeholder="e.g. HBL Branch Stamp Ref #84920"
                className="w-full px-3 py-2 rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900"
              />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setIsPaymentModalOpen(false)}
                className="px-3 py-2 text-xs font-semibold rounded-lg border border-zinc-300 dark:border-zinc-700"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-4 py-2 text-xs font-semibold rounded-lg bg-emerald-600 text-white hover:bg-emerald-700"
              >
                Confirm Payment Receipt
              </button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </>
  )
}
