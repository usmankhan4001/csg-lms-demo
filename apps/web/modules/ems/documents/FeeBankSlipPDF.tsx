'use client'

import React from 'react'
import {
  Building2,
  Calendar,
  CreditCard,
  Hash,
  Landmark,
  QrCode,
  Scissors,
  ShieldCheck,
  User,
} from 'lucide-react'
import {
  FeeBankSlipData,
  SchoolBrandingConfig,
  DEFAULT_SCHOOL_BRANDING,
  SAMPLE_FEE_BANK_SLIP_DATA,
  formatCurrency,
  formatDatePretty,
} from '@/lib/sms/document-templates'

interface FeeBankSlipPDFProps {
  data?: FeeBankSlipData
  branding?: SchoolBrandingConfig
  className?: string
}

export function FeeBankSlipPDF({
  data = SAMPLE_FEE_BANK_SLIP_DATA,
  branding = DEFAULT_SCHOOL_BRANDING,
  className = '',
}: FeeBankSlipPDFProps) {
  const copies: Array<{ title: string; subtitle: string; bgTone: string }> = [
    { title: 'BANK COPY', subtitle: 'To be retained by receiving bank branch', bgTone: 'border-l-4 border-l-blue-600' },
    { title: 'INSTITUTION COPY', subtitle: 'To be submitted to School Finance Dept', bgTone: 'border-l-4 border-l-indigo-600' },
    { title: 'STUDENT / PARENT COPY', subtitle: 'To be retained by payer as deposit proof', bgTone: 'border-l-4 border-l-emerald-600' },
  ]

  return (
    <div
      className={`bg-white text-slate-900 font-sans p-4 md:p-6 print:p-2 w-full max-w-[1280px] mx-auto shadow-sm border border-slate-200 print:border-none print:shadow-none ${className}`}
      id="fee-bank-slip-document"
    >
      {/* 3-Part Voucher Container: 3 side-by-side columns on Desktop/Print */}
      <div className="grid grid-cols-1 lg:grid-cols-3 print:grid-cols-3 gap-4 print:gap-3">
        {copies.map((copy, index) => (
          <div key={copy.title} className="relative flex flex-col">
            {/* Tear-off vertical line indicator for index > 0 */}
            {index > 0 && (
              <div className="hidden lg:flex print:flex absolute -left-2 top-0 bottom-0 flex-col items-center justify-between text-slate-400 select-none pointer-events-none -ml-0.5">
                <Scissors className="w-3.5 h-3.5 rotate-90 text-slate-400" />
                <div className="h-full border-l border-dashed border-slate-300 my-1"></div>
                <Scissors className="w-3.5 h-3.5 rotate-90 text-slate-400" />
              </div>
            )}

            {/* Individual Voucher Copy Box */}
            <div
              className={`flex-1 flex flex-col justify-between border border-slate-300 rounded-lg p-3.5 text-xs bg-white ${copy.bgTone}`}
            >
              {/* Header: School & Bank Credentials */}
              <div className="space-y-2 border-b border-slate-200 pb-2">
                <div className="flex items-start justify-between gap-2">
                  <div className="space-y-0.5">
                    <div className="flex items-center gap-1">
                      <Landmark className="w-3.5 h-3.5 text-indigo-700 shrink-0" />
                      <span className="font-extrabold text-[13px] tracking-tight text-slate-900 leading-tight">
                        {branding.schoolName}
                      </span>
                    </div>
                    {branding.campusName && (
                      <p className="text-[10px] text-slate-500 font-medium">
                        {branding.campusName}
                      </p>
                    )}
                  </div>
                  <span className="px-1.5 py-0.5 rounded text-[9px] font-black uppercase tracking-wider bg-slate-900 text-white shrink-0">
                    {copy.title}
                  </span>
                </div>

                {/* Bank Routing Information Box */}
                <div className="bg-slate-50 border border-slate-200 rounded p-2 text-[10px] space-y-0.5 text-slate-700">
                  <div className="flex justify-between font-bold text-slate-900">
                    <span>{branding.bankName || 'Habib Bank Limited'}</span>
                    <span>Br. Code: {branding.bankBranchCode || '0482'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>A/C: {branding.bankAccountNumber || '0482-7901234503'}</span>
                    <span className="font-mono font-semibold text-slate-900">{branding.bankIban || ''}</span>
                  </div>
                  <div className="flex justify-between text-[9px] text-slate-500">
                    <span>Title: {branding.bankAccountTitle || 'CSG Education Ventures'}</span>
                    <span>{branding.taxId}</span>
                  </div>
                </div>

                {/* Voucher Meta & Timestamps */}
                <div className="grid grid-cols-2 gap-1 text-[10px] pt-1">
                  <div className="space-y-0.5">
                    <span className="text-slate-500 block">Voucher No:</span>
                    <span className="font-mono font-bold text-slate-900 text-[11px]">
                      {data.voucherNo}
                    </span>
                  </div>
                  <div className="space-y-0.5 text-right">
                    <span className="text-slate-500 block">Billing Month:</span>
                    <span className="font-bold text-slate-900">{data.billingMonth}</span>
                  </div>
                </div>
              </div>

              {/* Student Demographics Block */}
              <div className="py-2 border-b border-slate-200 space-y-1 text-[10px]">
                <div className="flex justify-between">
                  <span className="text-slate-500">Student Name:</span>
                  <span className="font-bold text-slate-900">{data.studentName}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Roll / Reg No:</span>
                  <span className="font-mono font-semibold text-slate-800">{data.rollNumber}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Class & Section:</span>
                  <span className="font-medium text-slate-800">{data.gradeClass} - {data.section}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Academic Term:</span>
                  <span className="font-medium text-slate-800">{data.academicYear} ({data.termName})</span>
                </div>
              </div>

              {/* Itemized Fee Breakdown Table */}
              <div className="py-2 flex-1">
                <table className="w-full text-left text-[10px] border-collapse">
                  <thead>
                    <tr className="border-b border-slate-300 text-slate-500 uppercase text-[9px] tracking-wider">
                      <th className="py-1">Fee Particulars</th>
                      <th className="py-1 text-right">Amount</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {data.feeItems.map((item) => (
                      <tr key={item.id}>
                        <td className="py-1 text-slate-700 pr-1">
                          {item.title}
                          {item.discount ? (
                            <span className="text-[9px] text-emerald-600 block">
                              (Scholarship / Concession applied)
                            </span>
                          ) : null}
                        </td>
                        <td className="py-1 text-right font-medium text-slate-900 whitespace-nowrap">
                          {item.netAmount.toLocaleString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Totals & Net Payable Block */}
              <div className="border-t border-slate-300 pt-2 space-y-1 bg-slate-50 -mx-3.5 px-3.5 pb-2">
                <div className="flex justify-between text-[10px] text-slate-600">
                  <span>Subtotal Amount:</span>
                  <span>PKR {data.subtotal.toLocaleString()}</span>
                </div>
                {data.totalDiscount > 0 && (
                  <div className="flex justify-between text-[10px] text-emerald-600 font-medium">
                    <span>Total Discount / Waiver:</span>
                    <span>-PKR {data.totalDiscount.toLocaleString()}</span>
                  </div>
                )}
                <div className="flex justify-between text-[11px] font-bold text-slate-900 border-t border-slate-200 pt-1">
                  <span>Payable by Due Date ({formatDatePretty(data.dueDate)}):</span>
                  <span className="text-indigo-700 text-[12px]">
                    PKR {data.netPayableBeforeDueDate.toLocaleString()}
                  </span>
                </div>
                <div className="flex justify-between text-[10px] text-rose-600">
                  <span>Late Fee Surcharge (After Due Date):</span>
                  <span>+PKR {data.lateFeeSurcharge.toLocaleString()}</span>
                </div>
                <div className="flex justify-between text-[11px] font-black text-rose-700 border-t border-slate-200 pt-1">
                  <span>Payable After Due Date:</span>
                  <span>PKR {data.netPayableAfterDueDate.toLocaleString()}</span>
                </div>
              </div>

              {/* Dates & Instructions */}
              <div className="py-2 text-[9px] text-slate-500 space-y-0.5 border-t border-slate-200">
                <div className="flex justify-between">
                  <span>Issue Date: {formatDatePretty(data.issueDate)}</span>
                  <span>Validity: {formatDatePretty(data.validityDate)}</span>
                </div>
                <p className="italic leading-tight text-slate-500">
                  Note: Fee is non-refundable. Paid voucher stamp must be verified.
                </p>
              </div>

              {/* Barcode / Scan Line */}
              <div className="pt-2 border-t border-slate-200 flex items-center justify-between">
                <div className="space-y-0.5">
                  <div className="font-mono tracking-widest text-[10px] font-bold text-slate-800">
                    ||| | |||| || ||||| | ||| ||||
                  </div>
                  <span className="text-[8px] font-mono text-slate-400 block">{data.barcodeValue}</span>
                </div>
                <div className="text-right">
                  <span className="text-[8px] uppercase tracking-wider text-slate-400 block">Bank Officer Seal</span>
                  <div className="h-6 w-20 border-b border-dotted border-slate-400"></div>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Global Bottom Print Footer */}
      <div className="hidden print:block text-center text-[9px] text-slate-400 mt-4 border-t border-slate-200 pt-1">
        Generated by CSG-EMS • Official Academic Document Verification Engine • {branding.websiteUrl}
      </div>
    </div>
  )
}
