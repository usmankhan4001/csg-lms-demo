'use client'

import React, { useState, useEffect } from 'react'
import {
  UserCheck,
  CheckCircle2,
  Sparkles,
  Award,
  Building2,
  Calendar,
  CreditCard,
  FileCheck,
  GraduationCap,
  Mail,
  Phone,
  ShieldCheck,
  Smartphone,
  X,
  Zap,
  ArrowRight,
  Layers,
  AlertCircle,
  Receipt,
  User,
} from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog'
import {
  AdmissionsLeadCard,
  FeePlanType,
  MatriculationPayload,
} from './types'
import { formatPKR } from './mockData'
import toast from 'react-hot-toast'

export interface MatriculationDialogProps {
  isOpen: boolean
  lead: AdmissionsLeadCard | null
  onClose: () => void
  onConfirmMatriculation: (payload: MatriculationPayload) => void
}

const SECTION_OPTIONS = [
  'Section 9-Cambridge Alpha (STEM Honours)',
  'Section 9-Cambridge Beta (Pre-Med / Bio)',
  'Section 10-Cambridge Alpha (Boarding & Day)',
  'Section 11-A Pre-Engineering Syndicate',
  'Section 11-B Pre-Medical Syndicate',
  'Section 12-A Level Honours Syndicate',
  'Section 8-Falcon (Middle Syndicate)',
  'Section 7-Robotics Prime',
  'Section 6-Emerald',
  'Section 3-Sapphire Junior',
]

export const MatriculationDialog: React.FC<MatriculationDialogProps> = ({
  isOpen,
  lead,
  onClose,
  onConfirmMatriculation,
}) => {
  if (!lead) return null

  // State
  const [allocatedSection, setAllocatedSection] = useState<string>(
    lead.proposedSection || 'Section 9-Cambridge Alpha (STEM Honours)'
  )
  const [guardianRelationship, setGuardianRelationship] = useState<'Father' | 'Mother' | 'Legal Guardian'>('Father')
  const [guardianCnic, setGuardianCnic] = useState<string>(
    lead.guardianCnic || '35201-8912763-1'
  )
  const [emergencyPhone, setEmergencyPhone] = useState<string>(
    lead.emergencyPhone || lead.parentPhone || '+92 300 0000000'
  )
  const [billingEmail, setBillingEmail] = useState<string>(
    lead.parentEmail || ''
  )
  const [feePlan, setFeePlan] = useState<FeePlanType>('QUARTERLY_4_PAY')
  const [enableWhatsAppBilling, setEnableWhatsAppBilling] = useState<boolean>(true)
  const [generateLmsPortalAccount, setGenerateLmsPortalAccount] = useState<boolean>(true)
  const [specialInstructions, setSpecialInstructions] = useState<string>('')
  const [isProcessing, setIsProcessing] = useState<boolean>(false)

  // Auto-generate a realistic Roll Number based on year, grade & section code
  const generatedRollNumber = React.useMemo(() => {
    const year = '2026'
    const gradeClean = lead.targetGrade.replace(/[^0-9a-zA-Z]/g, '').slice(0, 3).toUpperCase() || 'G9'
    const idSuffix = lead.id.replace(/\D/g, '').slice(-3) || '101'
    return `${year}-${gradeClean}-${idSuffix}`
  }, [lead])

  const [rollNumber, setRollNumber] = useState<string>(generatedRollNumber)

  useEffect(() => {
    setRollNumber(generatedRollNumber)
  }, [generatedRollNumber])

  // Fee computations
  const grossAnnualTuition = lead.grossTuitionPKR || 650000
  const scholarshipDiscountPercent = lead.scholarshipDiscountPercent || 0
  const discountAmount = (grossAnnualTuition * scholarshipDiscountPercent) / 100
  const netAnnualTuition = Math.max(0, grossAnnualTuition - discountAmount)

  const admissionFee = 65000
  const labTechDeposit = 35000 // refundable security

  // Total payable over year including one-time fees
  let finalPlanMultiplier = 1
  if (feePlan === 'ANNUAL_LUMP_SUM') {
    finalPlanMultiplier = 0.95 // 5% lump sum waiver
  }

  const effectiveNetTuition = Math.round(netAnnualTuition * finalPlanMultiplier)
  const totalFirstYearPayable = effectiveNetTuition + admissionFee + labTechDeposit

  const quarterlyInstallment = Math.round(
    feePlan === 'QUARTERLY_4_PAY'
      ? (effectiveNetTuition + admissionFee + labTechDeposit) / 4
      : feePlan === 'BI_ANNUAL'
      ? (effectiveNetTuition + admissionFee + labTechDeposit) / 2
      : feePlan === 'MONTHLY_10_PAY'
      ? (effectiveNetTuition + admissionFee + labTechDeposit) / 10
      : totalFirstYearPayable
  )

  const handleExecuteHandshake = () => {
    setIsProcessing(true)
    setTimeout(() => {
      setIsProcessing(false)
      const payload: MatriculationPayload = {
        leadId: lead.id,
        studentName: lead.studentName,
        parentName: lead.parentName,
        guardianRelationship,
        guardianCnic,
        emergencyPhone,
        billingEmail,
        targetGrade: lead.targetGrade,
        targetCampus: lead.targetCampus,
        allocatedSection,
        rollNumber,
        feePlan,
        grossAnnualTuition,
        scholarshipDiscountPercent,
        netTuitionPayable: effectiveNetTuition,
        admissionFee,
        labTechDeposit,
        quarterlyInstallment,
        enableWhatsAppBilling,
        generateLmsPortalAccount,
        specialInstructions,
      }
      onConfirmMatriculation(payload)
      toast.success(`1-Click Matriculation complete! ${lead.studentName} is now Closed-Enrolled.`)
      onClose()
    }, 600)
  }

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-3xl max-h-[92vh] overflow-y-auto p-0 border border-slate-200 dark:border-slate-800 rounded-2xl bg-white dark:bg-slate-900 shadow-2xl">
        {/* Header Ribbon */}
        <div className="bg-gradient-to-r from-teal-900 via-emerald-950 to-slate-900 text-white p-6 pb-6 border-b border-emerald-800/30">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3">
              <div className="p-3 bg-emerald-500/20 border border-emerald-400/30 rounded-xl text-emerald-300 shadow-inner">
                <GraduationCap className="w-6 h-6" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-xl font-bold tracking-tight text-white">
                    1-Click Matriculation Handshake
                  </h2>
                  <span className="px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wider bg-emerald-500/30 text-emerald-200 border border-emerald-400/30 rounded-full">
                    Final Handshake
                  </span>
                </div>
                <p className="text-xs text-slate-300 mt-1">
                  Enrolling <span className="text-emerald-300 font-semibold">{lead.studentName}</span> into {lead.targetGrade} &bull; {lead.targetCampus}
                </p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-white/10 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Quick Info Pill */}
          <div className="mt-4 flex flex-wrap items-center gap-2 text-xs">
            <span className="px-2.5 py-1 rounded-md bg-white/10 text-emerald-200 border border-white/10 flex items-center gap-1.5">
              <Award className="w-3.5 h-3.5" />
              Lead Score: {lead.leadScore}/100 ({lead.leadScoreTier})
            </span>
            <span className="px-2.5 py-1 rounded-md bg-white/10 text-emerald-200 border border-white/10 flex items-center gap-1.5">
              <Building2 className="w-3.5 h-3.5" />
              Feeder: {lead.feederSchool}
            </span>
            <span className="px-2.5 py-1 rounded-md bg-emerald-400/20 text-emerald-200 border border-emerald-400/30 font-semibold">
              Merit Grant: {scholarshipDiscountPercent}% OFF
            </span>
          </div>
        </div>

        <div className="p-6 space-y-6">
          {/* Step 1: Academic & Section Allocation */}
          <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/40 space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300 flex items-center gap-2">
                <Layers className="w-4 h-4 text-emerald-600" />
                1. Academic Roster & Section Allocation
              </h3>
              <span className="text-[11px] text-emerald-600 font-semibold flex items-center gap-1">
                <CheckCircle2 className="w-3.5 h-3.5" /> Auto-Provisioned
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1 block">
                  Allocated Section / Syndicate
                </label>
                <select
                  value={allocatedSection}
                  onChange={(e) => setAllocatedSection(e.target.value)}
                  className="w-full px-3 py-2 text-xs font-medium rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-emerald-500"
                >
                  {SECTION_OPTIONS.map((sec) => (
                    <option key={sec} value={sec}>
                      {sec}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1 block">
                  Generated Student Roll Number
                </label>
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    value={rollNumber}
                    onChange={(e) => setRollNumber(e.target.value)}
                    className="w-full px-3 py-2 text-xs font-mono font-bold rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-emerald-600 dark:text-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-500"
                  />
                  <button
                    type="button"
                    onClick={() => setRollNumber(generatedRollNumber)}
                    className="px-2 py-2 text-xs font-medium text-slate-600 border border-slate-300 dark:border-slate-700 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800"
                    title="Reset to generated"
                  >
                    Reset
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* Step 2: Guardian Link & Verification */}
          <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/40 space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300 flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-emerald-600" />
              2. Guardian Link & Verification
            </h3>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1 block">
                  Primary Guardian
                </label>
                <input
                  type="text"
                  defaultValue={lead.parentName}
                  className="w-full px-3 py-2 text-xs font-medium rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100"
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1 block">
                  Relationship
                </label>
                <select
                  value={guardianRelationship}
                  onChange={(e) => setGuardianRelationship(e.target.value as any)}
                  className="w-full px-3 py-2 text-xs font-medium rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100"
                >
                  <option value="Father">Father</option>
                  <option value="Mother">Mother</option>
                  <option value="Legal Guardian">Legal Guardian</option>
                </select>
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1 block">
                  Guardian CNIC / National ID
                </label>
                <input
                  type="text"
                  value={guardianCnic}
                  onChange={(e) => setGuardianCnic(e.target.value)}
                  placeholder="35201-XXXXXXX-X"
                  className="w-full px-3 py-2 text-xs font-mono font-medium rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
              <div>
                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1 block">
                  Emergency / WhatsApp Phone
                </label>
                <div className="relative">
                  <Phone className="w-3.5 h-3.5 absolute inset-y-0 start-3 my-auto text-slate-400" />
                  <input
                    type="text"
                    value={emergencyPhone}
                    onChange={(e) => setEmergencyPhone(e.target.value)}
                    className="w-full ps-9 pe-3 py-2 text-xs font-medium rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100"
                  />
                </div>
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1 block">
                  Billing & Notification Email
                </label>
                <div className="relative">
                  <Mail className="w-3.5 h-3.5 absolute inset-y-0 start-3 my-auto text-slate-400" />
                  <input
                    type="email"
                    value={billingEmail}
                    onChange={(e) => setBillingEmail(e.target.value)}
                    className="w-full ps-9 pe-3 py-2 text-xs font-medium rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100"
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Step 3: Quarterly Fee Plan & Financial Settlement */}
          <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/40 space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300 flex items-center gap-2">
              <CreditCard className="w-4 h-4 text-emerald-600" />
              3. Fee Plan & Institutional Billing Settlement
            </h3>

            {/* Plan Selector Radios */}
            <div className="grid grid-cols-1 sm:grid-cols-4 gap-2.5">
              {[
                {
                  id: 'QUARTERLY_4_PAY',
                  name: 'Quarterly (4 Pay)',
                  badge: 'Standard',
                  desc: '4 equal quarterly installments',
                },
                {
                  id: 'ANNUAL_LUMP_SUM',
                  name: 'Annual Lump Sum',
                  badge: '5% Extra Off',
                  desc: 'Full upfront single challan',
                },
                {
                  id: 'BI_ANNUAL',
                  name: 'Bi-Annual (2 Pay)',
                  badge: 'Semesterly',
                  desc: '2 term-based installments',
                },
                {
                  id: 'MONTHLY_10_PAY',
                  name: 'Monthly (10 Pay)',
                  badge: 'Direct Debit',
                  desc: '10 equal monthly cycles',
                },
              ].map((plan) => {
                const isSelected = feePlan === plan.id
                return (
                  <button
                    key={plan.id}
                    type="button"
                    onClick={() => setFeePlan(plan.id as FeePlanType)}
                    className={`p-3 text-left rounded-xl border text-xs transition-all flex flex-col justify-between ${
                      isSelected
                        ? 'border-emerald-600 bg-emerald-50/70 dark:bg-emerald-950/40 text-emerald-950 dark:text-emerald-200 ring-2 ring-emerald-500/20 shadow-sm'
                        : 'border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-300'
                    }`}
                  >
                    <div>
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-bold truncate">{plan.name}</span>
                        <span
                          className={`text-[9px] px-1.5 py-0.2 rounded font-semibold ${
                            isSelected
                              ? 'bg-emerald-600 text-white'
                              : 'bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-400'
                          }`}
                        >
                          {plan.badge}
                        </span>
                      </div>
                      <p className="text-[10px] text-slate-500 dark:text-slate-400 leading-tight">
                        {plan.desc}
                      </p>
                    </div>
                  </button>
                )
              })}
            </div>

            {/* Financial Breakdown Table */}
            <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-3.5 space-y-2 text-xs">
              <div className="flex justify-between text-slate-600 dark:text-slate-400">
                <span>Gross Annual Tuition:</span>
                <span className="font-medium text-slate-900 dark:text-slate-100">
                  {formatPKR(grossAnnualTuition)}
                </span>
              </div>
              {scholarshipDiscountPercent > 0 && (
                <div className="flex justify-between text-emerald-600 dark:text-emerald-400 font-medium">
                  <span>Merit / Institutional Scholarship ({scholarshipDiscountPercent}%):</span>
                  <span>&minus; {formatPKR(discountAmount)}</span>
                </div>
              )}
              {feePlan === 'ANNUAL_LUMP_SUM' && (
                <div className="flex justify-between text-indigo-600 font-medium">
                  <span>Upfront Annual Settlement Waiver (5%):</span>
                  <span>&minus; {formatPKR(netAnnualTuition * 0.05)}</span>
                </div>
              )}
              <div className="flex justify-between text-slate-600 dark:text-slate-400">
                <span>One-Time Admission & Registration Fee:</span>
                <span className="font-medium text-slate-900 dark:text-slate-100">
                  {formatPKR(admissionFee)}
                </span>
              </div>
              <div className="flex justify-between text-slate-600 dark:text-slate-400">
                <span>Lab & STEM Security Deposit (Refundable):</span>
                <span className="font-medium text-slate-900 dark:text-slate-100">
                  {formatPKR(labTechDeposit)}
                </span>
              </div>
              <div className="pt-2 border-t border-slate-200 dark:border-slate-700 flex justify-between items-baseline font-bold text-sm">
                <span className="text-slate-900 dark:text-slate-100">
                  {feePlan === 'QUARTERLY_4_PAY' ? 'Installment per Quarter (4x):' : 'Total 1st Year Obligation:'}
                </span>
                <span className="text-emerald-600 dark:text-emerald-400 text-base font-extrabold">
                  {formatPKR(quarterlyInstallment)}
                  {feePlan === 'QUARTERLY_4_PAY' && <span className="text-xs font-normal text-slate-500"> / quarter</span>}
                </span>
              </div>
            </div>
          </div>

          {/* Step 4: System Provisioning Toggles */}
          <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/40 space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300 flex items-center gap-2">
              <Zap className="w-4 h-4 text-emerald-600" />
              4. Automated Provisioning & Notification Channels
            </h3>

            <div className="space-y-2">
              <label className="flex items-center gap-3 p-2.5 rounded-lg bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 cursor-pointer">
                <input
                  type="checkbox"
                  checked={generateLmsPortalAccount}
                  onChange={(e) => setGenerateLmsPortalAccount(e.target.checked)}
                  className="w-4 h-4 text-emerald-600 rounded border-slate-300 focus:ring-emerald-500"
                />
                <div className="text-xs">
                  <div className="font-bold text-slate-800 dark:text-slate-200">
                    Generate Learnhouse Student & Parent Portal Credentials
                  </div>
                  <div className="text-slate-500 text-[11px]">
                    Instantly creates auth credentials and dispatches welcome magic link.
                  </div>
                </div>
              </label>

              <label className="flex items-center gap-3 p-2.5 rounded-lg bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 cursor-pointer">
                <input
                  type="checkbox"
                  checked={enableWhatsAppBilling}
                  onChange={(e) => setEnableWhatsAppBilling(e.target.checked)}
                  className="w-4 h-4 text-emerald-600 rounded border-slate-300 focus:ring-emerald-500"
                />
                <div className="text-xs">
                  <div className="font-bold text-slate-800 dark:text-slate-200">
                    Sync Digital Challan to Guardian WhatsApp ({lead.parentPhone})
                  </div>
                  <div className="text-slate-500 text-[11px]">
                    Sends PDF voucher with 1LINK KuickPay and Kuickbill barcode integration.
                  </div>
                </div>
              </label>
            </div>
          </div>
        </div>

        {/* Footer Actions */}
        <div className="p-4 bg-slate-50 dark:bg-slate-900 border-t border-slate-200 dark:border-slate-800 flex items-center justify-between rounded-b-2xl">
          <button
            onClick={onClose}
            disabled={isProcessing}
            className="px-4 py-2 text-xs font-semibold text-slate-700 dark:text-slate-300 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg hover:bg-slate-50 transition-all shadow-sm"
          >
            Cancel
          </button>
          <button
            onClick={handleExecuteHandshake}
            disabled={isProcessing}
            className="px-6 py-2.5 text-xs font-extrabold text-white bg-emerald-600 hover:bg-emerald-700 active:scale-95 disabled:opacity-50 rounded-lg transition-all shadow-lg flex items-center gap-2"
          >
            {isProcessing ? (
              <>
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                Provisioning Roster & LMS Account...
              </>
            ) : (
              <>
                <FileCheck className="w-4 h-4" />
                Execute 1-Click Matriculation Handshake
              </>
            )}
          </button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
