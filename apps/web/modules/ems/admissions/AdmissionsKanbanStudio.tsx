'use client'

import React, { useState, useMemo, useCallback } from 'react'
import {
  Users,
  Search,
  Filter,
  Plus,
  ArrowRight,
  ChevronRight,
  Phone,
  MessageSquare,
  Mail,
  Calendar,
  Sparkles,
  Award,
  DollarSign,
  TrendingUp,
  CheckCircle2,
  XCircle,
  Clock,
  Building2,
  SlidersHorizontal,
  Bot,
  Send,
  Download,
  Copy,
  Check,
  AlertCircle,
  Flame,
  Zap,
  Snowflake,
  FileText,
  FileCheck,
  PhoneCall,
  UserCheck,
  Share2,
  X,
  ExternalLink,
  ChevronDown,
  RefreshCw,
  HelpCircle,
  ShieldCheck,
  GraduationCap,
  Calculator,
  Layers,
  MapPin,
  School,
  Tag,
  MoreVertical,
} from 'lucide-react'
import {
  AdmissionsLeadCard,
  PipelineStageId,
  LeadScoreTier,
  PipelineStageDefinition,
  NetTuitionYieldModelConfig,
  NetTuitionYieldSummary,
  MatriculationPayload,
} from './types'
import {
  PIPELINE_STAGE_DEFINITIONS,
  CAMPUS_OPTIONS,
  FEEDER_SCHOOL_OPTIONS,
  GRADE_OPTIONS,
  INITIAL_LEADS,
  formatPKR,
  formatCompactNumber,
} from './mockData'
import { NetTuitionYieldModal } from './NetTuitionYieldModal'
import { MatriculationDialog } from './MatriculationDialog'
import { AdmissionsLead360Drawer } from '../inspectors'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog'
import toast from 'react-hot-toast'

export interface AdmissionsKanbanStudioProps {
  orgslug?: string
  orgId?: number
  onLeadSelect?: (lead: AdmissionsLeadCard) => void
}

export const AdmissionsKanbanStudio: React.FC<AdmissionsKanbanStudioProps> = ({
  orgslug,
  orgId,
  onLeadSelect,
}) => {
  // Leads Pipeline State
  const [leads, setLeads] = useState<AdmissionsLeadCard[]>(INITIAL_LEADS)

  // Filters State
  const [searchQuery, setSearchQuery] = useState<string>('')
  const [selectedCampus, setSelectedCampus] = useState<string>('All Campuses')
  const [selectedFeederSchool, setSelectedFeederSchool] = useState<string>('All Feeder Schools')
  const [selectedGrade, setSelectedGrade] = useState<string>('All Grades')
  const [selectedScoreTier, setSelectedScoreTier] = useState<'ALL' | LeadScoreTier>('ALL')

  // Drag & Drop State
  const [draggedCardId, setDraggedCardId] = useState<string | null>(null)
  const [dragOverStageId, setDragOverStageId] = useState<PipelineStageId | null>(null)

  // Modals State
  const [isNtyModalOpen, setIsNtyModalOpen] = useState<boolean>(false)
  const [isMatriculationOpen, setIsMatriculationOpen] = useState<boolean>(false)
  const [matriculationTargetLead, setMatriculationTargetLead] = useState<AdmissionsLeadCard | null>(null)
  const [activeDetailLead, setActiveDetailLead] = useState<AdmissionsLeadCard | null>(null)
  const [isNewInquiryOpen, setIsNewInquiryOpen] = useState<boolean>(false)

  // New Inquiry Form State
  const [newStudentName, setNewStudentName] = useState('')
  const [newParentName, setNewParentName] = useState('')
  const [newParentPhone, setNewParentPhone] = useState('')
  const [newParentEmail, setNewParentEmail] = useState('')
  const [newGrade, setNewGrade] = useState('Grade 9 (O-Level)')
  const [newCampus, setNewCampus] = useState('Main Campus (Gulberg)')
  const [newFeeder, setNewFeeder] = useState('Beaconhouse School System')
  const [newTuition, setNewTuition] = useState('650000')

  // Filtered Leads
  const filteredLeads = useMemo(() => {
    return leads.filter((lead) => {
      // Search text filter
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase()
        const matchesName = lead.studentName.toLowerCase().includes(q)
        const matchesParent = lead.parentName.toLowerCase().includes(q)
        const matchesPhone = lead.parentPhone.toLowerCase().includes(q)
        const matchesEmail = lead.parentEmail.toLowerCase().includes(q)
        const matchesFeeder = lead.feederSchool.toLowerCase().includes(q)
        if (!matchesName && !matchesParent && !matchesPhone && !matchesEmail && !matchesFeeder) {
          return false
        }
      }

      // Campus filter
      if (selectedCampus !== 'All Campuses' && lead.targetCampus !== selectedCampus) {
        return false
      }

      // Feeder School filter
      if (
        selectedFeederSchool !== 'All Feeder Schools' &&
        lead.feederSchool !== selectedFeederSchool
      ) {
        return false
      }

      // Grade filter
      if (selectedGrade !== 'All Grades' && lead.targetGrade !== selectedGrade) {
        return false
      }

      // Score Tier filter
      if (selectedScoreTier !== 'ALL' && lead.leadScoreTier !== selectedScoreTier) {
        return false
      }

      return true
    })
  }, [leads, searchQuery, selectedCampus, selectedFeederSchool, selectedGrade, selectedScoreTier])

  // RevOps KPI Aggregates
  const kpiStats = useMemo(() => {
    const totalCount = filteredLeads.length
    const totalGrossRevenue = filteredLeads.reduce((acc, l) => acc + (l.grossTuitionPKR || 0), 0)
    const totalNetYield = filteredLeads.reduce((acc, l) => acc + (l.netTuitionYieldPKR || 0), 0)
    const totalDiscounts = totalGrossRevenue - totalNetYield
    const enrolledCount = filteredLeads.filter((l) => l.stage === 'closed_enrolled').length
    const offersCount = filteredLeads.filter((l) => l.stage === 'offer_issued').length
    const hotCount = filteredLeads.filter((l) => l.leadScoreTier === 'HOT').length

    const conversionRate = totalCount > 0 ? Math.round((enrolledCount / totalCount) * 100) : 0

    return {
      totalCount,
      totalGrossRevenue,
      totalNetYield,
      totalDiscounts,
      enrolledCount,
      offersCount,
      hotCount,
      conversionRate,
    }
  }, [filteredLeads])

  // Stage-grouped Leads
  const leadsByStage = useMemo(() => {
    const map: Record<PipelineStageId, AdmissionsLeadCard[]> = {
      new_inquiry: [],
      tour_scheduled: [],
      application_submitted: [],
      assessment: [],
      offer_issued: [],
      closed_enrolled: [],
    }

    filteredLeads.forEach((lead) => {
      if (map[lead.stage]) {
        map[lead.stage].push(lead)
      } else {
        map['new_inquiry'].push(lead)
      }
    })

    return map
  }, [filteredLeads])

  // Native HTML5 Drag and Drop handlers
  const handleDragStart = (e: React.DragEvent, cardId: string) => {
    e.dataTransfer.setData('text/plain', cardId)
    e.dataTransfer.effectAllowed = 'move'
    setDraggedCardId(cardId)
  }

  const handleDragOver = (e: React.DragEvent, stageId: PipelineStageId) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
    if (dragOverStageId !== stageId) {
      setDragOverStageId(stageId)
    }
  }

  const handleDragLeave = (e: React.DragEvent, stageId: PipelineStageId) => {
    e.preventDefault()
    if (dragOverStageId === stageId) {
      setDragOverStageId(null)
    }
  }

  const handleDrop = (e: React.DragEvent, targetStageId: PipelineStageId) => {
    e.preventDefault()
    setDragOverStageId(null)
    const cardId = e.dataTransfer.getData('text/plain') || draggedCardId
    setDraggedCardId(null)

    if (!cardId) return

    const targetLead = leads.find((l) => l.id === cardId)
    if (!targetLead) return

    if (targetLead.stage === targetStageId) return

    // If dropped to closed_enrolled, prompt 1-Click Matriculation Dialog
    if (targetStageId === 'closed_enrolled') {
      setMatriculationTargetLead(targetLead)
      setIsMatriculationOpen(true)
      return
    }

    // Move stage immediately
    setLeads((prev) =>
      prev.map((l) => (l.id === cardId ? { ...l, stage: targetStageId } : l))
    )

    const stageDef = PIPELINE_STAGE_DEFINITIONS.find((s) => s.id === targetStageId)
    toast.success(`${targetLead.studentName} moved to ${stageDef?.title || targetStageId}`)
  }

  const handleConfirmMatriculation = (payload: MatriculationPayload) => {
    setLeads((prev) =>
      prev.map((l) =>
        l.id === payload.leadId
          ? {
              ...l,
              stage: 'closed_enrolled',
              proposedSection: payload.allocatedSection,
              guardianCnic: payload.guardianCnic,
              emergencyPhone: payload.emergencyPhone,
              tags: Array.from(new Set([...(l.tags || []), 'Matriculated', 'Fee Paid'])),
            }
          : l
      )
    )
  }

  const handleCreateInquiry = (e: React.FormEvent) => {
    e.preventDefault()
    if (!newStudentName || !newParentName || !newParentPhone) {
      toast.error('Please fill in student name, parent name, and phone')
      return
    }

    const tuition = Number(newTuition) || 600000
    const newLead: AdmissionsLeadCard = {
      id: `lead-${Date.now().toString().slice(-4)}`,
      studentName: newStudentName,
      parentName: newParentName,
      parentPhone: newParentPhone,
      parentEmail: newParentEmail || `${newStudentName.toLowerCase().replace(/\s+/g, '')}@example.com`,
      targetGrade: newGrade,
      targetCampus: newCampus,
      feederSchool: newFeeder,
      feederCategory: 'Private Grammar',
      stage: 'new_inquiry',
      leadScore: 85,
      leadScoreTier: 'HOT',
      grossTuitionPKR: tuition,
      scholarshipDiscountPercent: 10,
      netTuitionYieldPKR: Math.round(tuition * 0.9),
      assignedOfficer: 'Sana Malik (Lead SDR)',
      source: 'walk_in',
      lastContactedDate: 'Just now',
      createdAt: new Date().toISOString().split('T')[0],
      notes: 'Captured via Admissions CRM studio quick intake.',
      priority: 'HIGH',
      tags: ['New Walk-In'],
      proposedSection: 'Section Alpha',
      activities: [
        {
          id: `act-${Date.now()}`,
          type: 'call',
          title: 'Direct Walk-in Intake Captured',
          description: 'Inquiry profile recorded at admissions studio desk.',
          timestamp: new Date().toLocaleTimeString(),
          officer: 'Admissions Officer',
        },
      ],
    }

    setLeads([newLead, ...leads])
    setIsNewInquiryOpen(false)
    setNewStudentName('')
    setNewParentName('')
    setNewParentPhone('')
    setNewParentEmail('')
    toast.success(`Inquiry for ${newStudentName} created in New Inquiries pipeline!`)
  }

  return (
    <div className="space-y-5">
      {/* Studio RevOps Header & Executive KPI Bar */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-2xl p-5 shadow-sm space-y-4">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="p-3 bg-indigo-600 text-white rounded-xl shadow-md shadow-indigo-500/20">
              <Layers className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2.5">
                <h1 className="text-2xl font-black text-slate-900 dark:text-slate-100 tracking-tight">
                  Admissions CRM & RevOps Studio
                </h1>
                <span className="px-2.5 py-0.5 text-xs font-bold uppercase tracking-wider bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300 rounded-full border border-emerald-300 dark:border-emerald-800">
                  Phase 3 Live
                </span>
              </div>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                6-Stage Autonomous Enrollment Funnel &bull; Net Tuition Yield (NTY) Modeler &bull; 1-Click Matriculation
              </p>
            </div>
          </div>

          {/* Header Actions */}
          <div className="flex flex-wrap items-center gap-2.5">
            <button
              onClick={() => setIsNtyModalOpen(true)}
              className="px-4 py-2 text-xs font-bold rounded-xl border border-indigo-200 dark:border-indigo-800 bg-indigo-50/80 dark:bg-indigo-950/40 text-indigo-700 dark:text-indigo-300 hover:bg-indigo-100 dark:hover:bg-indigo-900/60 transition-all shadow-sm flex items-center gap-2 active:scale-95"
            >
              <Calculator className="w-4 h-4 text-indigo-600" />
              Net Tuition Yield (NTY) Modeler
            </button>

            <button
              onClick={() => setIsNewInquiryOpen(true)}
              className="px-4 py-2 text-xs font-bold rounded-xl bg-black dark:bg-white text-white dark:text-black hover:opacity-90 transition-all shadow-sm flex items-center gap-2 active:scale-95"
            >
              <Plus className="w-4 h-4" />
              Capture New Inquiry
            </button>
          </div>
        </div>

        {/* RevOps Top KPI Strip */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 pt-3 border-t border-slate-100 dark:border-slate-800/80">
          {/* 1. Total Pipeline Deals */}
          <div className="p-3 bg-slate-50 dark:bg-slate-800/40 rounded-xl border border-slate-100 dark:border-slate-800">
            <div className="text-[11px] font-semibold text-slate-500 flex items-center gap-1">
              <Users className="w-3.5 h-3.5 text-indigo-500" />
              Active Funnel
            </div>
            <div className="text-xl font-extrabold text-slate-900 dark:text-slate-100 mt-0.5">
              {kpiStats.totalCount} <span className="text-xs font-normal text-slate-500">Leads</span>
            </div>
          </div>

          {/* 2. Gross Tuition Pipeline */}
          <div className="p-3 bg-slate-50 dark:bg-slate-800/40 rounded-xl border border-slate-100 dark:border-slate-800">
            <div className="text-[11px] font-semibold text-slate-500 flex items-center gap-1">
              <DollarSign className="w-3.5 h-3.5 text-blue-500" />
              Gross Pipeline
            </div>
            <div className="text-lg font-extrabold text-slate-900 dark:text-slate-100 mt-0.5">
              {formatPKR(kpiStats.totalGrossRevenue)}
            </div>
          </div>

          {/* 3. Net Tuition Yield (NTY) */}
          <div className="p-3 bg-emerald-50/60 dark:bg-emerald-950/20 rounded-xl border border-emerald-200/60 dark:border-emerald-900/40">
            <div className="text-[11px] font-semibold text-emerald-800 dark:text-emerald-300 flex items-center gap-1">
              <TrendingUp className="w-3.5 h-3.5 text-emerald-600" />
              Projected NTY
            </div>
            <div className="text-lg font-extrabold text-emerald-950 dark:text-emerald-100 mt-0.5">
              {formatPKR(kpiStats.totalNetYield)}
            </div>
          </div>

          {/* 4. Scholarship Aid */}
          <div className="p-3 bg-amber-50/60 dark:bg-amber-950/20 rounded-xl border border-amber-200/60 dark:border-amber-900/40">
            <div className="text-[11px] font-semibold text-amber-800 dark:text-amber-300 flex items-center gap-1">
              <Award className="w-3.5 h-3.5 text-amber-600" />
              Scholarship Pool
            </div>
            <div className="text-lg font-extrabold text-amber-950 dark:text-amber-100 mt-0.5">
              {formatPKR(kpiStats.totalDiscounts)}
            </div>
          </div>

          {/* 5. Closed-Enrolled */}
          <div className="p-3 bg-teal-50/60 dark:bg-teal-950/20 rounded-xl border border-teal-200/60 dark:border-teal-900/40">
            <div className="text-[11px] font-semibold text-teal-800 dark:text-teal-300 flex items-center gap-1">
              <CheckCircle2 className="w-3.5 h-3.5 text-teal-600" />
              Matriculated
            </div>
            <div className="text-xl font-extrabold text-teal-950 dark:text-teal-100 mt-0.5">
              {kpiStats.enrolledCount} <span className="text-xs font-normal text-teal-700">({kpiStats.conversionRate}%)</span>
            </div>
          </div>

          {/* 6. HOT Prospects */}
          <div className="p-3 bg-rose-50/60 dark:bg-rose-950/20 rounded-xl border border-rose-200/60 dark:border-rose-900/40">
            <div className="text-[11px] font-semibold text-rose-800 dark:text-rose-300 flex items-center gap-1">
              <Flame className="w-3.5 h-3.5 text-rose-600" />
              High Intent (HOT)
            </div>
            <div className="text-xl font-extrabold text-rose-950 dark:text-rose-100 mt-0.5">
              {kpiStats.hotCount} <span className="text-xs font-normal text-rose-700">Deals</span>
            </div>
          </div>
        </div>
      </div>

      {/* Multi-Dimensional Filter Bar */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-3.5 shadow-sm flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2.5 flex-1 min-w-[280px]">
          {/* Search Box */}
          <div className="relative flex-1 min-w-[200px] max-w-sm">
            <Search className="w-4 h-4 absolute inset-y-0 start-3 my-auto text-slate-400" />
            <input
              type="text"
              placeholder="Search student, parent, feeder, or phone..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full ps-9 pe-3 py-1.5 text-xs rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500 text-slate-900 dark:text-slate-100"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                className="absolute inset-y-0 end-2.5 my-auto text-slate-400 hover:text-slate-600"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>

          {/* Campus Filter */}
          <div className="flex items-center gap-1.5">
            <MapPin className="w-3.5 h-3.5 text-slate-400" />
            <select
              value={selectedCampus}
              onChange={(e) => setSelectedCampus(e.target.value)}
              className="px-2.5 py-1.5 text-xs font-medium rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              {CAMPUS_OPTIONS.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>

          {/* Feeder School Filter */}
          <div className="flex items-center gap-1.5">
            <School className="w-3.5 h-3.5 text-slate-400" />
            <select
              value={selectedFeederSchool}
              onChange={(e) => setSelectedFeederSchool(e.target.value)}
              className="px-2.5 py-1.5 text-xs font-medium rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500 max-w-[190px]"
            >
              {FEEDER_SCHOOL_OPTIONS.map((f) => (
                <option key={f} value={f}>
                  {f}
                </option>
              ))}
            </select>
          </div>

          {/* Grade Filter */}
          <div className="flex items-center gap-1.5">
            <GraduationCap className="w-3.5 h-3.5 text-slate-400" />
            <select
              value={selectedGrade}
              onChange={(e) => setSelectedGrade(e.target.value)}
              className="px-2.5 py-1.5 text-xs font-medium rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              {GRADE_OPTIONS.map((g) => (
                <option key={g} value={g}>
                  {g}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Lead Score Intent Pill Filter */}
        <div className="flex items-center gap-1 bg-slate-100 dark:bg-slate-800 p-1 rounded-lg">
          {(['ALL', 'HOT', 'WARM', 'COLD'] as const).map((tier) => {
            const isSelected = selectedScoreTier === tier
            return (
              <button
                key={tier}
                onClick={() => setSelectedScoreTier(tier)}
                className={`px-2.5 py-1 text-xs font-bold rounded-md transition-all flex items-center gap-1 ${
                  isSelected
                    ? tier === 'HOT'
                      ? 'bg-rose-600 text-white shadow-sm'
                      : tier === 'WARM'
                      ? 'bg-amber-600 text-white shadow-sm'
                      : tier === 'COLD'
                      ? 'bg-blue-600 text-white shadow-sm'
                      : 'bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 shadow-sm'
                    : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
                }`}
              >
                {tier === 'HOT' && <Flame className="w-3 h-3" />}
                {tier === 'WARM' && <Zap className="w-3 h-3" />}
                {tier === 'COLD' && <Snowflake className="w-3 h-3" />}
                {tier}
              </button>
            )
          })}
        </div>
      </div>

      {/* 6-Stage Visual Drag-and-Drop Pipeline Kanban */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-3.5 items-start">
        {PIPELINE_STAGE_DEFINITIONS.map((stageDef) => {
          const stageCards = leadsByStage[stageDef.id] || []
          const stageTotalGross = stageCards.reduce((acc, c) => acc + (c.grossTuitionPKR || 0), 0)
          const stageTotalNet = stageCards.reduce((acc, c) => acc + (c.netTuitionYieldPKR || 0), 0)
          const isDragOver = dragOverStageId === stageDef.id

          return (
            <div
              key={stageDef.id}
              onDragOver={(e) => handleDragOver(e, stageDef.id)}
              onDragLeave={(e) => handleDragLeave(e, stageDef.id)}
              onDrop={(e) => handleDrop(e, stageDef.id)}
              className={`flex flex-col rounded-2xl border transition-all min-h-[580px] bg-slate-50/70 dark:bg-slate-900/50 ${
                isDragOver
                  ? 'border-indigo-500 ring-2 ring-indigo-500/30 bg-indigo-50/40 dark:bg-indigo-950/20'
                  : 'border-slate-200/90 dark:border-slate-800'
              }`}
            >
              {/* Stage Header */}
              <div className={`p-3.5 rounded-t-2xl border-b border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-900 ${stageDef.borderAccent} border-t-4`}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="w-5 h-5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 flex items-center justify-center text-[10px] font-bold">
                      {stageDef.stepNumber}
                    </span>
                    <h3 className="font-bold text-xs text-slate-900 dark:text-slate-100 truncate">
                      {stageDef.title}
                    </h3>
                  </div>
                  <span className={`px-2 py-0.5 text-[11px] font-extrabold rounded-full ${stageDef.badgeClass}`}>
                    {stageCards.length}
                  </span>
                </div>

                {/* Stage Revenue Sum */}
                <div className="mt-2.5 pt-2 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between text-[11px]">
                  <span className="text-slate-500">Yield Value:</span>
                  <span className="font-bold text-slate-800 dark:text-slate-200">
                    {formatCompactNumber(stageTotalNet)} PKR
                  </span>
                </div>
              </div>

              {/* Cards Container */}
              <div className="p-2 space-y-2.5 flex-1 overflow-y-auto max-h-[calc(100vh-340px)]">
                {stageCards.length === 0 ? (
                  <div className="p-6 text-center text-xs text-slate-400 dark:text-slate-500 border border-dashed border-slate-200 dark:border-slate-800 rounded-xl my-3">
                    Drag leads here
                  </div>
                ) : (
                  stageCards.map((lead) => {
                    const isBeingDragged = draggedCardId === lead.id
                    const isHot = lead.leadScoreTier === 'HOT'
                    const isWarm = lead.leadScoreTier === 'WARM'

                    return (
                      <div
                        key={lead.id}
                        draggable
                        onDragStart={(e) => handleDragStart(e, lead.id)}
                        onClick={() => {
                          setActiveDetailLead(lead)
                          if (onLeadSelect) onLeadSelect(lead)
                        }}
                        className={`p-3 bg-white dark:bg-slate-800/90 rounded-xl border border-slate-200/90 dark:border-slate-700/80 shadow-sm hover:shadow-md transition-all cursor-grab active:cursor-grabbing hover:border-indigo-300 dark:hover:border-indigo-600 relative group ${
                          isBeingDragged ? 'opacity-40 scale-95 border-dashed border-indigo-500' : ''
                        }`}
                      >
                        {/* Top Badge Strip: Score & Intent */}
                        <div className="flex items-center justify-between gap-1.5 mb-1.5">
                          <span
                            className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-black uppercase tracking-wider ${
                              isHot
                                ? 'bg-rose-100 text-rose-700 dark:bg-rose-950/60 dark:text-rose-300 border border-rose-300 dark:border-rose-800'
                                : isWarm
                                ? 'bg-amber-100 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300 border border-amber-300 dark:border-amber-800'
                                : 'bg-slate-100 text-slate-700 dark:bg-slate-700 dark:text-slate-300 border border-slate-300 dark:border-slate-600'
                            }`}
                          >
                            {isHot && <Flame className="w-2.5 h-2.5" />}
                            {isWarm && <Zap className="w-2.5 h-2.5" />}
                            {!isHot && !isWarm && <Snowflake className="w-2.5 h-2.5" />}
                            {lead.leadScoreTier} ({lead.leadScore})
                          </span>

                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-700 font-semibold text-slate-600 dark:text-slate-300">
                            {lead.targetGrade.split(' ')[0]}
                          </span>
                        </div>

                        {/* Student & Parent Name */}
                        <div className="mb-2">
                          <h4 className="font-extrabold text-xs text-slate-900 dark:text-slate-100 group-hover:text-indigo-600 dark:group-hover:text-indigo-400 transition-colors">
                            {lead.studentName}
                          </h4>
                          <p className="text-[11px] text-slate-500 dark:text-slate-400 truncate">
                            {lead.parentName}
                          </p>
                        </div>

                        {/* Feeder School & Campus Tag */}
                        <div className="space-y-1 mb-2.5 text-[10px]">
                          <div className="flex items-center gap-1 text-slate-600 dark:text-slate-300 truncate">
                            <School className="w-3 h-3 text-indigo-500 shrink-0" />
                            <span className="truncate font-medium">{lead.feederSchool}</span>
                          </div>
                          <div className="flex items-center gap-1 text-slate-500 truncate">
                            <MapPin className="w-3 h-3 text-slate-400 shrink-0" />
                            <span className="truncate">{lead.targetCampus.replace('Campus', '').replace(/[()]/g, '')}</span>
                          </div>
                        </div>

                        {/* Financial Deal Value Ribbon */}
                        <div className="bg-slate-50 dark:bg-slate-900/60 p-2 rounded-lg border border-slate-100 dark:border-slate-800 flex items-center justify-between text-[11px]">
                          <div>
                            <span className="text-[9px] text-slate-400 block uppercase font-bold">Yield (NTY)</span>
                            <span className="font-extrabold text-emerald-600 dark:text-emerald-400">
                              {formatPKR(lead.netTuitionYieldPKR)}
                            </span>
                          </div>
                          {lead.scholarshipDiscountPercent > 0 && (
                            <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-amber-100 dark:bg-amber-950/60 text-amber-800 dark:text-amber-300 border border-amber-300 dark:border-amber-800">
                              {lead.scholarshipDiscountPercent}% OFF
                            </span>
                          )}
                        </div>

                        {/* Quick Action Footer on Card */}
                        <div className="mt-2.5 pt-2 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between text-[10px] text-slate-500">
                          <span className="truncate">{lead.lastContactedDate}</span>
                          <div className="flex items-center gap-1 opacity-80 group-hover:opacity-100">
                            {lead.stage === 'offer_issued' || lead.stage === 'assessment' ? (
                              <button
                                onClick={(e) => {
                                  e.stopPropagation()
                                  setMatriculationTargetLead(lead)
                                  setIsMatriculationOpen(true)
                                }}
                                className="px-2 py-0.5 text-[10px] font-extrabold text-white bg-emerald-600 hover:bg-emerald-700 rounded-md transition-all flex items-center gap-1 shadow-sm"
                                title="1-Click Matriculation Handshake"
                              >
                                <GraduationCap className="w-3 h-3" />
                                Enrol
                              </button>
                            ) : (
                              <button
                                onClick={(e) => {
                                  e.stopPropagation()
                                  setActiveDetailLead(lead)
                                }}
                                className="p-1 text-slate-400 hover:text-indigo-600 rounded transition-colors"
                              >
                                <ChevronRight className="w-3.5 h-3.5" />
                              </button>
                            )}
                          </div>
                        </div>
                      </div>
                    )
                  })
                )}
              </div>
            </div>
          )
        })}
      </div>

      {/* Net Tuition Yield Modeler Modal */}
      <NetTuitionYieldModal
        isOpen={isNtyModalOpen}
        onClose={() => setIsNtyModalOpen(false)}
        onApplyTarget={(summary, cfg) => {
          toast.success(`Yield target updated: ${formatPKR(summary.totalNetTuitionYieldPKR)}`)
        }}
      />

      {/* 1-Click Matriculation Handshake Dialog */}
      <MatriculationDialog
        isOpen={isMatriculationOpen}
        lead={matriculationTargetLead}
        onClose={() => {
          setIsMatriculationOpen(false)
          setMatriculationTargetLead(null)
        }}
        onConfirmMatriculation={handleConfirmMatriculation}
      />

      {/* 360 Degree Admissions Lead Slide-Over Inspection Drawer */}
      <AdmissionsLead360Drawer
        isOpen={Boolean(activeDetailLead)}
        lead={activeDetailLead}
        onClose={() => setActiveDetailLead(null)}
        onMatriculate={(lead) => {
          setMatriculationTargetLead(lead)
          setActiveDetailLead(null)
          setIsMatriculationOpen(true)
        }}
      />

      {/* Quick Add Inquiry Modal */}
      <Dialog open={isNewInquiryOpen} onOpenChange={(open) => !open && setIsNewInquiryOpen(false)}>
        <DialogContent className="max-w-lg p-0 border border-slate-200 dark:border-slate-800 rounded-2xl bg-white dark:bg-slate-900 shadow-2xl">
          <div className="bg-black text-white p-5 rounded-t-2xl flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="p-2 bg-white/10 rounded-lg">
                <Plus className="w-5 h-5 text-white" />
              </div>
              <h3 className="font-bold text-base text-white">Capture New Inquiry</h3>
            </div>
            <button
              onClick={() => setIsNewInquiryOpen(false)}
              className="p-1 text-slate-400 hover:text-white rounded"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <form onSubmit={handleCreateInquiry} className="p-5 space-y-3.5 text-xs">
            <div>
              <label className="font-semibold text-slate-700 dark:text-slate-300 block mb-1">
                Student Full Name *
              </label>
              <input
                type="text"
                required
                placeholder="e.g. Mahnoor Tariq"
                value={newStudentName}
                onChange={(e) => setNewStudentName(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="font-semibold text-slate-700 dark:text-slate-300 block mb-1">
                  Parent / Guardian Name *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Tariq Javed"
                  value={newParentName}
                  onChange={(e) => setNewParentName(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100"
                />
              </div>

              <div>
                <label className="font-semibold text-slate-700 dark:text-slate-300 block mb-1">
                  Parent Phone / WhatsApp *
                </label>
                <input
                  type="text"
                  required
                  placeholder="+92 300 XXXXXXX"
                  value={newParentPhone}
                  onChange={(e) => setNewParentPhone(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100"
                />
              </div>
            </div>

            <div>
              <label className="font-semibold text-slate-700 dark:text-slate-300 block mb-1">
                Parent Email
              </label>
              <input
                type="email"
                placeholder="parent@example.com"
                value={newParentEmail}
                onChange={(e) => setNewParentEmail(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="font-semibold text-slate-700 dark:text-slate-300 block mb-1">
                  Target Grade
                </label>
                <select
                  value={newGrade}
                  onChange={(e) => setNewGrade(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100"
                >
                  {GRADE_OPTIONS.filter((g) => g !== 'All Grades').map((g) => (
                    <option key={g} value={g}>
                      {g}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="font-semibold text-slate-700 dark:text-slate-300 block mb-1">
                  Target Campus
                </label>
                <select
                  value={newCampus}
                  onChange={(e) => setNewCampus(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100"
                >
                  {CAMPUS_OPTIONS.filter((c) => c !== 'All Campuses').map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div>
              <label className="font-semibold text-slate-700 dark:text-slate-300 block mb-1">
                Previous / Feeder School
              </label>
              <select
                value={newFeeder}
                onChange={(e) => setNewFeeder(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100"
              >
                {FEEDER_SCHOOL_OPTIONS.filter((f) => f !== 'All Feeder Schools').map((f) => (
                  <option key={f} value={f}>
                    {f}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="font-semibold text-slate-700 dark:text-slate-300 block mb-1">
                Gross Annual Tuition (PKR)
              </label>
              <input
                type="number"
                step="10000"
                value={newTuition}
                onChange={(e) => setNewTuition(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100"
              />
            </div>

            <div className="pt-3 flex items-center justify-end gap-2 border-t border-slate-100 dark:border-slate-800">
              <button
                type="button"
                onClick={() => setIsNewInquiryOpen(false)}
                className="px-4 py-2 font-semibold text-slate-700 bg-white border border-slate-300 rounded-lg"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-5 py-2 font-bold text-white bg-black dark:bg-white dark:text-black rounded-lg"
              >
                Create Inquiry
              </button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
