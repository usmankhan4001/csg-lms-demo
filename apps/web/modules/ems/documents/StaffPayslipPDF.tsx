'use client'

import React from 'react'
import {
  Building2,
  Calendar,
  CheckCircle2,
  CreditCard,
  FileCheck2,
  Landmark,
  QrCode,
  ShieldCheck,
  UserCheck,
} from 'lucide-react'
import {
  StaffPayslipData,
  SchoolBrandingConfig,
  DEFAULT_SCHOOL_BRANDING,
  SAMPLE_STAFF_PAYSLIP_DATA,
  formatCurrency,
  formatDatePretty,
} from '@/lib/sms/document-templates'

interface StaffPayslipPDFProps {
  data?: StaffPayslipData
  branding?: SchoolBrandingConfig
  className?: string
}

export function StaffPayslipPDF({
  data = SAMPLE_STAFF_PAYSLIP_DATA,
  branding = DEFAULT_SCHOOL_BRANDING,
  className = '',
}: StaffPayslipPDFProps) {
  return (
    <div
      className={`bg-white text-slate-900 font-sans p-6 md:p-10 print:p-6 w-full max-w-[900px] mx-auto shadow-md border border-slate-200 print:border-none print:shadow-none space-y-6 ${className}`}
      id="staff-payslip-document"
    >
      {/* 1. Official School Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b-2 border-slate-900 pb-4">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <div className="w-9 h-9 rounded-lg bg-indigo-700 flex items-center justify-center text-white font-black text-base shadow-sm">
              CSG
            </div>
            <div>
              <h1 className="text-xl md:text-2xl font-black text-slate-900 tracking-tight leading-tight">
                {branding.schoolName}
              </h1>
              <p className="text-xs text-indigo-700 font-bold uppercase tracking-wider">
                Office of Finance & Human Resource Directorate
              </p>
            </div>
          </div>
          <p className="text-[11px] text-slate-500 max-w-lg">
            {branding.physicalAddress} • Reg: {branding.registrationNumber} • {branding.taxId}
          </p>
        </div>

        <div className="text-right sm:text-right shrink-0 bg-slate-50 p-3 rounded-lg border border-slate-200">
          <span className="text-[10px] font-black uppercase tracking-widest text-slate-500 block">
            Official Payslip
          </span>
          <span className="font-mono text-sm font-bold text-slate-900 block">
            {data.slipNo}
          </span>
          <span className="text-xs font-semibold text-indigo-600 block mt-0.5">
            {data.payPeriodMonth} {data.payPeriodYear}
          </span>
        </div>
      </div>

      {/* 2. Employee Identity & Pay Period Details */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 bg-slate-50 border border-slate-200 rounded-xl p-4 text-xs">
        <div className="space-y-1.5">
          <div className="flex justify-between">
            <span className="text-slate-500">Employee Name:</span>
            <span className="font-bold text-slate-900">{data.staffName}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-500">Employee ID / Code:</span>
            <span className="font-mono font-semibold text-slate-900">{data.employeeCode}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-500">Department:</span>
            <span className="font-medium text-slate-800">{data.department}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-500">Designation / Role:</span>
            <span className="font-medium text-slate-800">{data.designation}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-500">Salary Band / Grade:</span>
            <span className="font-medium text-slate-800">{data.gradeBand}</span>
          </div>
        </div>

        <div className="space-y-1.5 border-t md:border-t-0 md:border-l border-slate-200 pt-2 md:pt-0 md:pl-4">
          <div className="flex justify-between">
            <span className="text-slate-500">National Tax No (NTN):</span>
            <span className="font-mono font-semibold text-slate-900">{data.nationalTaxNumber}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-500">Bank Account No:</span>
            <span className="font-mono font-semibold text-slate-900">{data.bankAccountNumber}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-500">Bank IBAN:</span>
            <span className="font-mono text-[11px] text-slate-800">{data.bankIban}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-500">Attendance / Working Days:</span>
            <span className="font-medium text-slate-800">
              {data.daysPresent} / {data.workingDays} Days ({data.unpaidLeaveDays} Unpaid)
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-500">Disbursement Channel:</span>
            <span className="font-medium text-emerald-700">{data.paymentMethod}</span>
          </div>
        </div>
      </div>

      {/* 3. Side-by-Side Itemized Earnings & Deductions Table */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Earnings Column */}
        <div className="border border-slate-200 rounded-xl overflow-hidden flex flex-col justify-between">
          <div>
            <div className="bg-indigo-50 border-b border-indigo-100 px-4 py-2 flex justify-between items-center">
              <span className="text-xs font-black text-indigo-900 uppercase tracking-wider">
                Itemized Earnings
              </span>
              <span className="text-[11px] font-semibold text-indigo-600">Credit (PKR)</span>
            </div>
            <div className="p-4 space-y-2 text-xs divide-y divide-slate-100">
              <div className="flex justify-between pt-1">
                <span className="text-slate-600">Basic Academic Salary</span>
                <span className="font-semibold text-slate-900">{data.basicSalary.toLocaleString()}</span>
              </div>
              <div className="flex justify-between pt-1.5">
                <span className="text-slate-600">Housing Allowance</span>
                <span className="font-semibold text-slate-900">{data.housingAllowance.toLocaleString()}</span>
              </div>
              <div className="flex justify-between pt-1.5">
                <span className="text-slate-600">Medical Allowance</span>
                <span className="font-semibold text-slate-900">{data.medicalAllowance.toLocaleString()}</span>
              </div>
              <div className="flex justify-between pt-1.5">
                <span className="text-slate-600">Conveyance Allowance</span>
                <span className="font-semibold text-slate-900">{data.conveyanceAllowance.toLocaleString()}</span>
              </div>
              {data.specialDutyAllowance > 0 && (
                <div className="flex justify-between pt-1.5">
                  <span className="text-slate-600">Examiner / Special Duty</span>
                  <span className="font-semibold text-slate-900">{data.specialDutyAllowance.toLocaleString()}</span>
                </div>
              )}
            </div>
          </div>
          <div className="bg-slate-50 border-t border-slate-200 px-4 py-2.5 flex justify-between items-center text-xs font-black text-slate-900">
            <span>Total Gross Earnings:</span>
            <span className="text-indigo-700 text-sm">PKR {data.grossSalary.toLocaleString()}</span>
          </div>
        </div>

        {/* Deductions Column */}
        <div className="border border-slate-200 rounded-xl overflow-hidden flex flex-col justify-between">
          <div>
            <div className="bg-rose-50 border-b border-rose-100 px-4 py-2 flex justify-between items-center">
              <span className="text-xs font-black text-rose-900 uppercase tracking-wider">
                Statutory & Policy Deductions
              </span>
              <span className="text-[11px] font-semibold text-rose-600">Debit (PKR)</span>
            </div>
            <div className="p-4 space-y-2 text-xs divide-y divide-slate-100">
              <div className="flex justify-between pt-1">
                <span className="text-slate-600">Provident Fund (5% Retirement Scheme)</span>
                <span className="font-semibold text-rose-600">-{data.providentFundPensionDeduction.toLocaleString()}</span>
              </div>
              <div className="flex justify-between pt-1.5">
                <span className="text-slate-600">Progressive Income Tax (FBR Withholding)</span>
                <span className="font-semibold text-rose-600">-{data.progressiveIncomeTaxDeduction.toLocaleString()}</span>
              </div>
              {data.unpaidLeaveDeduction > 0 && (
                <div className="flex justify-between pt-1.5">
                  <span className="text-slate-600">Unpaid Absence ({data.unpaidLeaveDays} days)</span>
                  <span className="font-semibold text-rose-600">-{data.unpaidLeaveDeduction.toLocaleString()}</span>
                </div>
              )}
              {data.healthInsuranceDeduction > 0 && (
                <div className="flex justify-between pt-1.5">
                  <span className="text-slate-600">Health & Group Life Insurance</span>
                  <span className="font-semibold text-rose-600">-{data.healthInsuranceDeduction.toLocaleString()}</span>
                </div>
              )}
              {data.otherDeductions > 0 && (
                <div className="flex justify-between pt-1.5">
                  <span className="text-slate-600">Other Adjustments</span>
                  <span className="font-semibold text-rose-600">-{data.otherDeductions.toLocaleString()}</span>
                </div>
              )}
            </div>
          </div>
          <div className="bg-slate-50 border-t border-slate-200 px-4 py-2.5 flex justify-between items-center text-xs font-black text-slate-900">
            <span>Total Deductions:</span>
            <span className="text-rose-700 text-sm">-PKR {data.totalDeductions.toLocaleString()}</span>
          </div>
        </div>
      </div>

      {/* 4. Progressive Tax Bracket Calculation Breakdown */}
      <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 text-[11px] space-y-2">
        <div className="flex items-center gap-1.5 font-bold text-slate-800">
          <ShieldCheck className="w-4 h-4 text-indigo-600" />
          <span>Progressive Income Tax Schedule Breakdown (Itemized Audit Proof)</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-[10px] border-collapse">
            <thead>
              <tr className="border-b border-slate-300 text-slate-500 uppercase tracking-wider">
                <th className="py-1">Tax Bracket Tier</th>
                <th className="py-1 text-center">Applicable Rate</th>
                <th className="py-1 text-right">Taxable Base (PKR)</th>
                <th className="py-1 text-right">Tax Charged (PKR)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 font-mono">
              {data.taxSchedule.map((tier, idx) => (
                <tr key={idx}>
                  <td className="py-1 font-sans text-slate-700">{tier.tierName}</td>
                  <td className="py-1 text-center">{tier.ratePercent}%</td>
                  <td className="py-1 text-right">{tier.taxableAmount.toLocaleString()}</td>
                  <td className="py-1 text-right font-semibold text-slate-900">{tier.taxCharged.toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 5. Net Clamped Compensation Banner */}
      <div className="bg-indigo-900 text-white rounded-2xl p-5 shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="space-y-1">
          <span className="text-[11px] font-bold text-indigo-200 uppercase tracking-wider block">
            Net Clamped Disbursed Salary
          </span>
          <p className="text-xs text-indigo-100 italic">
            Amount in Words: <span className="font-semibold text-white">{data.netSalaryInWords}</span>
          </p>
        </div>
        <div className="text-left sm:text-right">
          <span className="text-3xl font-black text-white tracking-tight block">
            PKR {data.netSalary.toLocaleString()}
          </span>
          <span className="text-[10px] text-emerald-300 font-semibold flex items-center sm:justify-end gap-1 mt-0.5">
            <CheckCircle2 className="w-3.5 h-3.5" /> Disbursed via 1Link RTGS
          </span>
        </div>
      </div>

      {/* 6. Dual-Approver Authorization & Tamper Verification */}
      <div className="pt-4 border-t border-slate-200 grid grid-cols-1 md:grid-cols-3 gap-6 items-end text-xs">
        {/* Preparer Seal */}
        <div className="space-y-2 text-center md:text-left">
          <div className="h-10 border-b border-slate-300 flex items-end justify-center md:justify-start pb-1">
            <span className="font-serif italic text-sm text-indigo-800 font-bold">{data.preparerName}</span>
          </div>
          <div>
            <span className="font-bold text-slate-900 block">{data.preparerName}</span>
            <span className="text-[10px] text-slate-500 block">{data.preparerTitle}</span>
          </div>
        </div>

        {/* Approver Seal */}
        <div className="space-y-2 text-center">
          <div className="h-10 border-b border-slate-300 flex items-end justify-center pb-1">
            <span className="font-serif italic text-sm text-indigo-800 font-bold">{data.approverName}</span>
          </div>
          <div>
            <span className="font-bold text-slate-900 block">{data.approverName}</span>
            <span className="text-[10px] text-slate-500 block">{data.approverTitle}</span>
          </div>
        </div>

        {/* Anti-Tamper Cryptographic Signature Box */}
        <div className="bg-slate-50 border border-slate-200 rounded-lg p-3 text-[9px] space-y-1">
          <div className="flex items-center justify-between font-bold text-slate-700">
            <span>Cryptographic Verification</span>
            <FileCheck2 className="w-3.5 h-3.5 text-emerald-600" />
          </div>
          <p className="font-mono text-[8px] text-slate-500 break-all leading-tight">
            HASH: {data.verificationHash}
          </p>
          <span className="text-[8px] text-slate-400 block">
            Generated on {formatDatePretty(data.paymentDate || '2026-03-31')} • ISO 27001 Protected
          </span>
        </div>
      </div>
    </div>
  )
}
