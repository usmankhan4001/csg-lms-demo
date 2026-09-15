'use client'

import React, { useState, useMemo, useEffect } from 'react'
import Link from 'next/link'
import toast from 'react-hot-toast'
import { useApiResource } from '@/lib/api/useApiResource'
import {
  getLeadPipeline,
  updateLeadStage,
  createLead,
  logLeadActivity,
  aiQualifyLead,
  enrollLead,
} from '@/modules/sms/revops/api'
import { COLUMN_TO_STAGE, adaptLead, leadIdFromCardId } from '@/modules/sms/revops/adapt'
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
} from 'lucide-react'
import { cn } from '@/lib/utils'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog'
import type {
  ActivityLog,
  Lead,
  BoardLeadScoreBreakdown,
  PipelineStage,
  StageId,
} from '../types'

// -----------------------------------------------------------------------------
// Types & Data Structures
// -----------------------------------------------------------------------------

// Pipeline Stages Configuration
export const PIPELINE_STAGES: PipelineStage[] = [
  {
    id: 'inquiry',
    title: 'New Inquiries',
    color: 'text-blue-600 dark:text-blue-400',
    borderAccent: 'border-t-blue-500',
    bgLight: 'bg-blue-500/10 text-blue-700 dark:text-blue-300',
    badgeColor: 'bg-blue-500',
    icon: MessageSquare,
    description: 'Fresh inbound inquiries from web, ads & WhatsApp',
  },
  {
    id: 'contacted',
    title: 'Contacted',
    color: 'text-indigo-600 dark:text-indigo-400',
    borderAccent: 'border-t-indigo-500',
    bgLight: 'bg-indigo-500/10 text-indigo-700 dark:text-indigo-300',
    badgeColor: 'bg-indigo-500',
    icon: PhoneCall,
    description: 'SDR initial discovery call completed',
  },
  {
    id: 'tour_booked',
    title: 'Tour Booked',
    color: 'text-purple-600 dark:text-purple-400',
    borderAccent: 'border-t-purple-500',
    bgLight: 'bg-purple-500/10 text-purple-700 dark:text-purple-300',
    badgeColor: 'bg-purple-500',
    icon: Calendar,
    description: 'Campus visit & facility tour scheduled',
  },
  {
    id: 'assessment',
    title: 'Assessment',
    color: 'text-amber-600 dark:text-amber-400',
    borderAccent: 'border-t-amber-500',
    bgLight: 'bg-amber-500/10 text-amber-700 dark:text-amber-300',
    badgeColor: 'bg-amber-500',
    icon: FileCheck,
    description: 'Entrance diagnostic & academic test in progress',
  },
  {
    id: 'offer_sent',
    title: 'Offer Sent',
    color: 'text-cyan-600 dark:text-cyan-400',
    borderAccent: 'border-t-cyan-500',
    bgLight: 'bg-cyan-500/10 text-cyan-700 dark:text-cyan-300',
    badgeColor: 'bg-cyan-500',
    icon: Send,
    description: 'Formal letter & scholarship voucher dispatched',
  },
  {
    id: 'enrolled',
    title: 'Enrolled',
    color: 'text-emerald-600 dark:text-emerald-400',
    borderAccent: 'border-t-emerald-500',
    bgLight: 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-300',
    badgeColor: 'bg-emerald-500',
    icon: CheckCircle2,
    description: 'Registration fee verified & student ID generated',
  },
  {
    id: 'lost',
    title: 'Lost',
    color: 'text-rose-600 dark:text-rose-400',
    borderAccent: 'border-t-rose-500',
    bgLight: 'bg-rose-500/10 text-rose-700 dark:text-rose-300',
    badgeColor: 'bg-rose-500',
    icon: XCircle,
    description: 'Unresponsive, relocated, or chose competitor',
  },
]


// -----------------------------------------------------------------------------
// Component: Admissions CRM Main Page
// -----------------------------------------------------------------------------

export default function AdmissionsCRMBoard() {
  // Real pipeline from `GET /sms/revops/leads/pipeline`, replacing the former
  // hardcoded INITIAL_LEADS mock. Kept in local state because the board does
  // optimistic stage moves; `pipeline` is the server source of truth and
  // re-seeds this whenever it refetches.
  const pipeline = useApiResource(() => getLeadPipeline(), [])
  const [leads, setLeads] = useState<Lead[]>([])

  useEffect(() => {
    if (!pipeline.data) return
    setLeads(pipeline.data.stages.flatMap((group) => group.leads.map(adaptLead)))
  }, [pipeline.data])
  const [searchQuery, setSearchQuery] = useState('')
  const [campusFilter, setCampusFilter] = useState('all')
  const [scoreFilter, setScoreFilter] = useState<'all' | 'hot' | 'warm' | 'cool'>('all')
  const [sourceFilter, setSourceFilter] = useState('all')

  // Selected Lead for Drawer
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null)
  const [drawerTab, setDrawerTab] = useState<'overview' | 'timeline' | 'ai'>('overview')

  // Scholarship Modal State
  const [scholarshipModalLead, setScholarshipModalLead] = useState<Lead | null>(null)
  const [scholarshipDiscount, setScholarshipDiscount] = useState<number>(20)
  const [letterCopied, setLetterCopied] = useState(false)
  const [letterDispatchedToast, setLetterDispatchedToast] = useState(false)

  // Drag and Drop State
  const [draggedLeadId, setDraggedLeadId] = useState<string | null>(null)
  const [dragOverStage, setDragOverStage] = useState<StageId | null>(null)

  // New Lead Modal State
  const [isNewLeadModalOpen, setIsNewLeadModalOpen] = useState(false)
  const [newLeadForm, setNewLeadForm] = useState({
    studentName: '',
    parentName: '',
    parentPhone: '',
    parentEmail: '',
    targetGrade: 'Grade 11 (Pre-Engineering)',
    targetCampus: 'Islamabad Main Campus',
    source: 'whatsapp' as Lead['source'],
    notes: '',
  })

  // SDR Chat Simulator Floating Widget State
  const [isSdrSimulatorOpen, setIsSdrSimulatorOpen] = useState(false)
  const [sdrMessages, setSdrMessages] = useState<
    { sender: 'user' | 'bot'; text: string; time: string; qualificationDelta?: number }[]
  >([
    {
      sender: 'bot',
      text: 'Salam! Welcome to CSG Admissions AI. How can I assist you with your child’s enrollment for Academic Year 2026-2027?',
      time: '12:00 PM',
    },
  ])
  const [sdrInput, setSdrInput] = useState('')
  const [sdrLiveScore, setSdrLiveScore] = useState(72)
  const [sdrIsTyping, setSdrIsTyping] = useState(false)

  // Quick activity log addition state inside Drawer
  const [newActivityNote, setNewActivityNote] = useState('')
  const [newActivityType, setNewActivityType] = useState<ActivityLog['type']>('call')

  // Filtered Leads
  const filteredLeads = useMemo(() => {
    return leads.filter((lead) => {
      // Search
      const matchesSearch =
        searchQuery.trim() === '' ||
        lead.studentName.toLowerCase().includes(searchQuery.toLowerCase()) ||
        lead.parentName.toLowerCase().includes(searchQuery.toLowerCase()) ||
        lead.parentPhone.includes(searchQuery) ||
        lead.targetGrade.toLowerCase().includes(searchQuery.toLowerCase())

      // Campus
      const matchesCampus =
        campusFilter === 'all' ||
        lead.targetCampus.toLowerCase().includes(campusFilter.toLowerCase())

      // Score
      let matchesScore = true
      if (scoreFilter === 'hot') matchesScore = lead.score >= 80
      else if (scoreFilter === 'warm') matchesScore = lead.score >= 50 && lead.score < 80
      else if (scoreFilter === 'cool') matchesScore = lead.score < 50

      // Source
      const matchesSource = sourceFilter === 'all' || lead.source === sourceFilter

      return matchesSearch && matchesCampus && matchesScore && matchesSource
    })
  }, [leads, searchQuery, campusFilter, scoreFilter, sourceFilter])

  // Drag & Drop Handlers
  const handleDragStart = (e: React.DragEvent, leadId: string) => {
    e.dataTransfer.setData('text/plain', leadId)
    setDraggedLeadId(leadId)
  }

  const handleDragOver = (e: React.DragEvent, stageId: StageId) => {
    e.preventDefault()
    if (dragOverStage !== stageId) {
      setDragOverStage(stageId)
    }
  }

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault()
  }

  const handleDrop = (e: React.DragEvent, targetStage: StageId) => {
    e.preventDefault()
    const leadId = e.dataTransfer.getData('text/plain') || draggedLeadId
    if (leadId) {
      moveLeadToStage(leadId, targetStage)
    }
    setDraggedLeadId(null)
    setDragOverStage(null)
  }

  const moveLeadToStage = (leadId: string, targetStage: StageId) => {
    setLeads((prev) =>
      prev.map((l) => {
        if (l.id === leadId) {
          const updatedTimeline: ActivityLog[] = [
            {
              id: `act-${Date.now()}`,
              type: 'note',
              title: `Pipeline Stage Updated`,
              description: `Moved from ${l.stage.replace('_', ' ').toUpperCase()} to ${targetStage.replace('_', ' ').toUpperCase()} by Admin.`,
              timestamp: 'Just now',
              agent: 'Admin RevOps',
            },
            ...l.activityTimeline,
          ]
          return {
            ...l,
            stage: targetStage,
            lastContact: 'Just now',
            activityTimeline: updatedTimeline,
          }
        }
        return l
      })
    )
    if (selectedLead && selectedLead.id === leadId) {
      setSelectedLead((prev) => (prev ? { ...prev, stage: targetStage } : null))
    }

    // Persist for real. The optimistic move above is rolled back by refetching
    // the authoritative pipeline if the server rejects the transition.
    const numericId = leadIdFromCardId(leadId)
    const backendStage = COLUMN_TO_STAGE[targetStage]
    if (numericId === null || !backendStage) return

    updateLeadStage(numericId, { stage: backendStage })
      .then(() => toast.success(`Moved to ${backendStage.replace(/_/g, ' ').toLowerCase()}.`))
      .catch((err: unknown) => {
        toast.error(err instanceof Error ? err.message : 'Could not update the lead stage.')
        pipeline.refetch()
      })
  }

  // Quick Action: WhatsApp Trigger
  const handleTriggerWhatsApp = (lead: Lead) => {
    const text = encodeURIComponent(
      `Assalam o Alaikum Mr. ${lead.parentName}, this is CSG Admissions Office regarding ${lead.studentName}'s application for ${lead.targetGrade}. We have reviewed the academic profile and would love to invite you for a campus tour.`
    )
    const cleanPhone = lead.parentPhone.replace(/[^0-9]/g, '')
    window.open(`https://wa.me/${cleanPhone}?text=${text}`, '_blank')
  }

  // Quick Action: Add Activity to Selected Lead
  const handleAddActivity = async () => {
    if (!selectedLead || !newActivityNote.trim()) return
    const numericId = leadIdFromCardId(selectedLead.id)
    const noteText = newActivityNote.trim()
    const logType = newActivityType

    const newLog: ActivityLog = {
      id: `act-${Date.now()}`,
      type: logType,
      title: `${logType.toUpperCase()} Logged`,
      description: noteText,
      timestamp: 'Just now',
      agent: 'Admissions Officer',
    }
    const updatedLead: Lead = {
      ...selectedLead,
      lastContact: 'Just now',
      activityTimeline: [newLog, ...selectedLead.activityTimeline],
    }
    setLeads((prev) => prev.map((l) => (l.id === selectedLead.id ? updatedLead : l)))
    setSelectedLead(updatedLead)
    setNewActivityNote('')

    if (numericId !== null) {
      try {
        const mappedType = logType.toUpperCase() as any
        await logLeadActivity(numericId, {
          activity_type: mappedType,
          summary: noteText,
        })
        toast.success('Touchpoint logged to server.')
      } catch (err) {
        console.warn('Could not persist activity log remotely:', err)
      }
    }
  }

  // Add New Lead Form Submission (Live Backend API)
  const handleCreateNewLead = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newLeadForm.studentName || !newLeadForm.parentName) return

    const sourceMap: Record<string, any> = {
      whatsapp: 'WHATSAPP',
      walk_in: 'WALK_IN',
      meta: 'META_ADS',
      google: 'GOOGLE_ADS',
      referral: 'REFERRAL',
      web: 'WEBSITE_FORM',
    }

    try {
      const created = await createLead({
        parent_name: newLeadForm.parentName,
        student_name: newLeadForm.studentName,
        phone: newLeadForm.parentPhone || '+92 300 0000000',
        email: newLeadForm.parentEmail || `${newLeadForm.parentName.toLowerCase().replace(/\s+/g, '')}@admissions.local`,
        grade_applying_for: newLeadForm.targetGrade,
        source: sourceMap[newLeadForm.source] || 'WALK_IN',
        notes: newLeadForm.notes || 'Created via Admissions CRM Quick Entry.',
      })

      toast.success(`Prospect "${created.student_name || created.parent_name}" registered successfully!`)
      setIsNewLeadModalOpen(false)
      setNewLeadForm({
        studentName: '',
        parentName: '',
        parentPhone: '',
        parentEmail: '',
        targetGrade: 'Grade 11 (Pre-Engineering)',
        targetCampus: 'Islamabad Main Campus',
        source: 'whatsapp',
        notes: '',
      })
      pipeline.refetch()
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Could not register lead on server.')
    }
  }

  // SDR Chat Simulator Handler
  const handleSendSdrMessage = (customText?: string) => {
    const textToSend = customText || sdrInput
    if (!textToSend.trim()) return

    const userMsg = {
      sender: 'user' as const,
      text: textToSend,
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    }
    setSdrMessages((prev) => [...prev, userMsg])
    if (!customText) setSdrInput('')
    setSdrIsTyping(true)

    // Simulate AI response with intelligent revops scoring
    setTimeout(() => {
      let botResponse = ''
      let scoreBump = 4

      const lower = textToSend.toLowerCase()
      if (lower.includes('fee') || lower.includes('tuition') || lower.includes('cost') || lower.includes('scholarship')) {
        botResponse =
          'Our standard tuition is PKR 45,000/month. However, based on your student’s high academic standing, they qualify for our CSG STEM Merit Scholarship (up to 30% reduction). Would you like me to generate a personalized scholarship voucher?'
        scoreBump = 6
      } else if (lower.includes('lab') || lower.includes('stem') || lower.includes('facility') || lower.includes('science')) {
        botResponse =
          'CSG Islamabad Main features world-class Cambridge-certified STEM & Robotics laboratories with 3D printers and AI compute clusters. We have dedicated faculty mentors from NUST and KEMU.'
        scoreBump = 5
      } else if (lower.includes('tour') || lower.includes('visit') || lower.includes('appointment')) {
        botResponse =
          'I’d be delighted to book your campus tour! We have open slots this Saturday at 11:00 AM and Monday at 10:00 AM. Which day works best for you and your family?'
        scoreBump = 8
      } else if (lower.includes('transport') || lower.includes('bus') || lower.includes('route')) {
        botResponse =
          'Yes, we provide air-conditioned coaster shuttles with live GPS tracking and female attendants covering all major sectors in Islamabad & Rawalpindi.'
        scoreBump = 4
      } else {
        botResponse =
          'Thank you for sharing! Our Admissions Directorate ensures every student gets individualized academic counseling. Would you like to schedule an entrance diagnostic test or speak with Principal Dr. Tariq?'
        scoreBump = 3
      }

      setSdrMessages((prev) => [
        ...prev,
        {
          sender: 'bot',
          text: botResponse,
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          qualificationDelta: scoreBump,
        },
      ])
      setSdrLiveScore((prev) => Math.min(99, prev + scoreBump))
      setSdrIsTyping(false)
    }, 600)
  }

  // Convert Chat Simulator to Lead in CRM
  const handleConvertSimulatorToLead = () => {
    const newLead: Lead = {
      id: `lead-sim-${Date.now()}`,
      studentName: 'Prospective Student (AI SDR)',
      parentName: 'WhatsApp Inquiry Lead',
      parentPhone: '+92 300 1234567',
      parentEmail: 'sdr.lead@csg.edu.pk',
      targetGrade: 'Grade 11 (Pre-Engineering)',
      targetCampus: 'Islamabad Main Campus',
      previousSchool: 'Inquiry in Progress',
      stage: 'inquiry',
      source: 'whatsapp',
      score: sdrLiveScore,
      estimatedTuitionPKR: 45000,
      discountOffered: 15,
      assignedSDR: 'AI SDR Autonomous',
      lastContact: 'Just now',
      createdAt: new Date().toISOString().split('T')[0],
      notes: `Captured live via SDR Chat Simulator. AI qualification score: ${sdrLiveScore}/100.`,
      tags: ['AI SDR Qualified', 'High Interest'],
      aiScoreBreakdown: {
        academicFit: 92,
        budgetMatch: 88,
        parentEngagement: 95,
        decisionUrgency: 89,
      },
      aiRecommendedPitch: 'Engage immediately with 15% Early Decision Scholarship offer.',
      aiSdrSummary: `Prospective parent engaged in ${sdrMessages.length} chat exchanges. High interest in STEM and scholarship options.`,
      activityTimeline: [
        {
          id: `act-${Date.now()}`,
          type: 'whatsapp',
          title: 'AI SDR Chat Completed',
          description: `Conversation simulated with qualification score ${sdrLiveScore}.`,
          timestamp: 'Just now',
          agent: 'AI Admissions Bot',
        },
      ],
    }

    setLeads((prev) => [newLead, ...prev])
    setIsSdrSimulatorOpen(false)
    alert(`Lead successfully imported into "New Inquiries" pipeline with AI Score ${sdrLiveScore}! 🔥`)
  }

  // Computed Metrics
  const totalLeadsCount = leads.length
  const hotLeadsCount = leads.filter((l) => l.score >= 80).length
  const totalPipelineValuePKR = leads.reduce((acc, l) => acc + l.estimatedTuitionPKR * 12, 0)
  const enrolledCount = leads.filter((l) => l.stage === 'enrolled').length
  // null, not '0': with no leads there is no conversion rate to report. It
  // previously rendered "0% Enrolled Conversion Rate", so a school that had
  // just been set up was told its admissions funnel had converted nobody
  // before it had entered a single enquiry.
  const conversionRate =
    totalLeadsCount > 0 ? ((enrolledCount / totalLeadsCount) * 100).toFixed(1) : null

  return (
    <div className="space-y-6 pb-20">
      {/* 1. Header Ribbon & RevOps Telemetry */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-slate-900 via-purple-950 to-indigo-950 text-white p-6 sm:p-8 shadow-xl border border-purple-900/30">
        <div className="relative z-10 flex flex-col lg:flex-row lg:items-center justify-between gap-6">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <Link
                href="/admin"
                className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg bg-white/10 hover:bg-white/15 text-xs font-semibold text-purple-200 transition-colors"
              >
                <ShieldCheck className="size-3.5 text-purple-300" />
                <span>Admin Console</span>
              </Link>
              <ChevronRight className="size-3.5 text-purple-400" />
              <span className="text-xs font-medium text-purple-300">Admissions Directorate</span>
            </div>

            <div className="flex items-center gap-3">
              <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight">
                Admissions CRM & AI RevOps 🎯
              </h1>
              <span className="hidden sm:inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                <span className="size-2 rounded-full bg-emerald-400 animate-pulse" />
                AI SDR Online
              </span>
            </div>

            <p className="text-sm text-purple-100/80 max-w-2xl leading-relaxed">
              Multi-stage prospective enrollment pipeline with AI lead scoring, automated WhatsApp triggers, 1-click scholarship generator, and live SDR objection playbooks.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2.5">
            <button
              onClick={() => setIsSdrSimulatorOpen(true)}
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white font-semibold text-xs transition-all shadow-lg hover:shadow-blue-500/25 active:scale-95"
            >
              <Bot className="size-4 text-blue-200" />
              <span>Launch SDR Simulator</span>
            </button>

            <button
              onClick={() => setIsNewLeadModalOpen(true)}
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-white text-purple-950 hover:bg-purple-50 font-bold text-xs transition-all shadow-md active:scale-95"
            >
              <Plus className="size-4 text-purple-600" />
              <span>Add Prospective Lead</span>
            </button>
          </div>
        </div>

        {/* Decorative background glow */}
        <div className="absolute -end-16 -bottom-16 size-80 rounded-full bg-purple-500/15 blur-3xl pointer-events-none" />
      </div>

      {/* 2. RevOps Key Telemetry Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-4 rounded-2xl bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 shadow-2xs">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs font-medium text-neutral-500 dark:text-neutral-400">
              Active CRM Leads
            </span>
            <div className="p-1.5 rounded-lg bg-blue-500/10 text-blue-600">
              <Users className="size-4" />
            </div>
          </div>
          <div className="text-2xl font-bold text-neutral-900 dark:text-white">
            {totalLeadsCount} Leads
          </div>
          <div className="text-[11px] text-emerald-600 flex items-center gap-1 font-medium mt-1">
            <TrendingUp className="size-3" />
            <span>+18.4% weekly velocity</span>
          </div>
        </div>

        <div className="p-4 rounded-2xl bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 shadow-2xs">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs font-medium text-neutral-500 dark:text-neutral-400">
              Hot High-Intent Leads
            </span>
            <div className="p-1.5 rounded-lg bg-rose-500/10 text-rose-600">
              <Flame className="size-4" />
            </div>
          </div>
          <div className="text-2xl font-bold text-neutral-900 dark:text-white">
            {hotLeadsCount} Leads <span className="text-sm font-semibold text-rose-600">(&gt;80 Score)</span>
          </div>
          <div className="text-[11px] text-neutral-500 mt-1">
            Immediate SDR Outreach Priority
          </div>
        </div>

        <div className="p-4 rounded-2xl bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 shadow-2xs">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs font-medium text-neutral-500 dark:text-neutral-400">
              Annual Pipeline Value
            </span>
            <div className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-600">
              <DollarSign className="size-4" />
            </div>
          </div>
          <div className="text-2xl font-bold text-neutral-900 dark:text-white">
            PKR {(totalPipelineValuePKR / 1000000).toFixed(1)}M
          </div>
          <div className="text-[11px] text-emerald-600 font-medium mt-1">
            {conversionRate !== null
              ? `${conversionRate}% Enrolled Conversion Rate`
              : 'No leads yet — conversion rate not available'}
          </div>
        </div>

        <div className="p-4 rounded-2xl bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 shadow-2xs">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs font-medium text-neutral-500 dark:text-neutral-400">
              AI Qualification Accuracy
            </span>
            <div className="p-1.5 rounded-lg bg-purple-500/10 text-purple-600">
              <Sparkles className="size-4" />
            </div>
          </div>
          <div className="text-2xl font-bold text-neutral-900 dark:text-white">
            94.8%
          </div>
          <div className="text-[11px] text-purple-600 font-medium mt-1">
            Avg 4.2d SDR cycle to Offer
          </div>
        </div>
      </div>

      {/* 3. Search, Filters & View Bar */}
      <div className="p-4 rounded-2xl bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 shadow-2xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        {/* Search */}
        <div className="relative flex-1 max-w-md">
          <Search className="absolute start-3.5 top-1/2 -translate-y-1/2 size-4 text-neutral-400" />
          <input
            type="text"
            placeholder="Search student, parent, phone or grade..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full ps-10 pe-4 py-2 text-xs rounded-xl border border-neutral-200 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-800 text-neutral-900 dark:text-white focus:outline-hidden focus:ring-2 focus:ring-purple-500"
          />
        </div>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-2.5">
          {/* Campus Filter */}
          <select
            value={campusFilter}
            onChange={(e) => setCampusFilter(e.target.value)}
            className="px-3 py-2 rounded-xl text-xs border border-neutral-200 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-800 text-neutral-800 dark:text-neutral-200 focus:outline-hidden"
          >
            <option value="all">All Campuses</option>
            <option value="Islamabad">Islamabad Main</option>
            <option value="Lahore">Lahore Gulberg</option>
            <option value="Rawalpindi">Rawalpindi North</option>
            <option value="Karachi">Karachi DHA</option>
          </select>

          {/* Score Tier Filter */}
          <div className="inline-flex rounded-xl border border-neutral-200 dark:border-neutral-700 p-0.5 bg-neutral-50 dark:bg-neutral-800 text-xs">
            <button
              onClick={() => setScoreFilter('all')}
              className={cn(
                'px-2.5 py-1.5 rounded-lg font-medium transition-all',
                scoreFilter === 'all'
                  ? 'bg-white dark:bg-neutral-700 text-neutral-900 dark:text-white shadow-2xs'
                  : 'text-neutral-500 hover:text-neutral-800 dark:hover:text-neutral-200'
              )}
            >
              All Scores
            </button>
            <button
              onClick={() => setScoreFilter('hot')}
              className={cn(
                'px-2.5 py-1.5 rounded-lg font-medium transition-all flex items-center gap-1',
                scoreFilter === 'hot'
                  ? 'bg-rose-500 text-white shadow-2xs'
                  : 'text-neutral-500 hover:text-neutral-800 dark:hover:text-neutral-200'
              )}
            >
              <Flame className="size-3" />
              <span>Hot 🔥</span>
            </button>
            <button
              onClick={() => setScoreFilter('warm')}
              className={cn(
                'px-2.5 py-1.5 rounded-lg font-medium transition-all flex items-center gap-1',
                scoreFilter === 'warm'
                  ? 'bg-amber-500 text-white shadow-2xs'
                  : 'text-neutral-500 hover:text-neutral-800 dark:hover:text-neutral-200'
              )}
            >
              <Zap className="size-3" />
              <span>Warm ⚡</span>
            </button>
            <button
              onClick={() => setScoreFilter('cool')}
              className={cn(
                'px-2.5 py-1.5 rounded-lg font-medium transition-all flex items-center gap-1',
                scoreFilter === 'cool'
                  ? 'bg-slate-500 text-white shadow-2xs'
                  : 'text-neutral-500 hover:text-neutral-800 dark:hover:text-neutral-200'
              )}
            >
              <Snowflake className="size-3" />
              <span>Cool ❄️</span>
            </button>
          </div>

          {/* Lead Source Filter */}
          <select
            value={sourceFilter}
            onChange={(e) => setSourceFilter(e.target.value)}
            className="px-3 py-2 rounded-xl text-xs border border-neutral-200 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-800 text-neutral-800 dark:text-neutral-200 focus:outline-hidden"
          >
            <option value="all">All Sources</option>
            <option value="whatsapp">WhatsApp Inbound</option>
            <option value="ads">Meta / Google Ads</option>
            <option value="web">Web Portal</option>
            <option value="referral">Parent Referral</option>
            <option value="walkin">Campus Walk-in</option>
          </select>
        </div>
      </div>

      {/* 4. Kanban Pipeline Grid (7 Columns) */}
      {pipeline.status === 'loading' && (
        <div className="mb-3 rounded-xl border border-neutral-200 bg-neutral-50 px-4 py-2.5 text-xs text-neutral-600 dark:border-neutral-800 dark:bg-neutral-900 dark:text-neutral-400">
          Loading admissions pipeline…
        </div>
      )}
      {pipeline.status === 'error' && (
        <div className="mb-3 flex items-center justify-between gap-3 rounded-xl border border-rose-300 bg-rose-50 px-4 py-2.5 text-xs text-rose-700 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-300">
          <span>
            {pipeline.error?.kind === 'permission_denied'
              ? "You don't have access to the admissions pipeline."
              : "Couldn't load the admissions pipeline — the board below may be incomplete."}
          </span>
          <button
            type="button"
            onClick={() => pipeline.refetch()}
            className="rounded-lg border border-rose-400 px-2.5 py-1 font-semibold hover:bg-rose-100 dark:border-rose-800 dark:hover:bg-rose-900/40"
          >
            Retry
          </button>
        </div>
      )}

      <div className="overflow-x-auto pb-4 pt-1">
        <div className="flex gap-4 min-w-[1540px]">
          {PIPELINE_STAGES.map((stage) => {
            const stageLeads = filteredLeads.filter((l) => l.stage === stage.id)
            const stageValue = stageLeads.reduce((sum, l) => sum + l.estimatedTuitionPKR * 12, 0)
            const isTarget = dragOverStage === stage.id

            return (
              <div
                key={stage.id}
                onDragOver={(e) => handleDragOver(e, stage.id)}
                onDragLeave={handleDragLeave}
                onDrop={(e) => handleDrop(e, stage.id)}
                className={cn(
                  'flex-1 min-w-[240px] max-w-[270px] rounded-2xl flex flex-col bg-neutral-100/70 dark:bg-neutral-900/60 border transition-all duration-200',
                  stage.borderAccent,
                  'border-t-4',
                  isTarget
                    ? 'border-purple-500 bg-purple-500/10 shadow-lg scale-[1.01]'
                    : 'border-neutral-200/80 dark:border-neutral-800/80'
                )}
              >
                {/* Stage Header */}
                <div className="p-3.5 border-b border-neutral-200/60 dark:border-neutral-800 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <stage.icon className={cn('size-4', stage.color)} />
                    <span className="text-xs font-bold text-neutral-900 dark:text-white">
                      {stage.title}
                    </span>
                    <span
                      className={cn(
                        'px-2 py-0.5 rounded-full text-[11px] font-bold text-white',
                        stage.badgeColor
                      )}
                    >
                      {stageLeads.length}
                    </span>
                  </div>

                  <span className="text-[10px] font-semibold text-neutral-500">
                    PKR {(stageValue / 1000).toFixed(0)}k/yr
                  </span>
                </div>

                {/* Stage Cards List */}
                <div className="p-2.5 flex-1 space-y-2.5 min-h-[450px]">
                  {stageLeads.length === 0 ? (
                    <div className="h-40 rounded-xl border border-dashed border-neutral-300 dark:border-neutral-700/60 flex flex-col items-center justify-center p-3 text-center text-xs text-neutral-400">
                      <p className="font-medium">No leads in this stage</p>
                      <p className="text-[10px] text-neutral-400 mt-0.5">
                        Drag cards here or add new
                      </p>
                    </div>
                  ) : (
                    stageLeads.map((lead) => {
                      const isHot = lead.score >= 80
                      const isWarm = lead.score >= 50 && lead.score < 80

                      return (
                        <div
                          key={lead.id}
                          draggable
                          onDragStart={(e) => handleDragStart(e, lead.id)}
                          className={cn(
                            'group relative p-3.5 rounded-xl bg-white dark:bg-neutral-800/90 border border-neutral-200/80 dark:border-neutral-700/60 shadow-2xs hover:shadow-md hover:border-purple-400 dark:hover:border-purple-500 transition-all cursor-grab active:cursor-grabbing flex flex-col justify-between gap-2.5',
                            draggedLeadId === lead.id ? 'opacity-40 scale-95' : 'opacity-100'
                          )}
                        >
                          {/* Card Header: Score Ring Badge & Source */}
                          <div className="flex items-center justify-between">
                            {/* Score Ring Badge */}
                            <div
                              className={cn(
                                'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-extrabold tracking-tight border',
                                isHot
                                  ? 'bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/30'
                                  : isWarm
                                  ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/30'
                                  : 'bg-slate-500/10 text-slate-600 dark:text-slate-400 border-slate-500/30'
                              )}
                            >
                              {isHot ? (
                                <>
                                  <Flame className="size-3 text-rose-500 fill-rose-500" />
                                  <span>{lead.score} HOT 🔥</span>
                                </>
                              ) : isWarm ? (
                                <>
                                  <Zap className="size-3 text-amber-500 fill-amber-500" />
                                  <span>{lead.score} WARM ⚡</span>
                                </>
                              ) : (
                                <>
                                  <Snowflake className="size-3 text-slate-500" />
                                  <span>{lead.score} COOL ❄️</span>
                                </>
                              )}
                            </div>

                            {/* Source Tag */}
                            <span className="text-[10px] font-semibold text-neutral-500 uppercase tracking-wider">
                              {lead.source}
                            </span>
                          </div>

                          {/* Student & Parent Info */}
                          <div>
                            <h4 className="text-xs font-bold text-neutral-900 dark:text-white group-hover:text-purple-600 dark:group-hover:text-purple-400 transition-colors">
                              {lead.studentName}
                            </h4>
                            <p className="text-[11px] text-neutral-500 truncate">
                              Guardian: <span className="text-neutral-700 dark:text-neutral-300 font-medium">{lead.parentName}</span>
                            </p>
                            <p className="text-[10px] text-purple-600 dark:text-purple-400 font-medium mt-0.5">
                              {lead.targetGrade}
                            </p>
                          </div>

                          {/* Campus & Estimated Fee */}
                          <div className="pt-2 border-t border-neutral-100 dark:border-neutral-700/60 flex items-center justify-between text-[10px] text-neutral-500">
                            <span className="truncate max-w-[120px]">{lead.targetCampus.replace(' Campus', '')}</span>
                            <span className="font-bold text-neutral-800 dark:text-neutral-200">
                              PKR {(lead.estimatedTuitionPKR / 1000).toFixed(0)}k/m
                            </span>
                          </div>

                          {/* Action Bar */}
                          <div className="flex items-center justify-between pt-1 gap-1">
                            <div className="flex items-center gap-1">
                              <button
                                onClick={(e) => {
                                  e.stopPropagation()
                                  handleTriggerWhatsApp(lead)
                                }}
                                title="Chat on WhatsApp"
                                className="p-1.5 rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-600 transition-colors"
                              >
                                <MessageSquare className="size-3.5" />
                              </button>
                              <button
                                onClick={(e) => {
                                  e.stopPropagation()
                                  setScholarshipModalLead(lead)
                                  setScholarshipDiscount(lead.discountOffered || 20)
                                }}
                                title="Generate Scholarship Offer"
                                className="p-1.5 rounded-lg bg-purple-500/10 hover:bg-purple-500/20 text-purple-600 transition-colors"
                              >
                                <Award className="size-3.5" />
                              </button>
                            </div>

                            <button
                              onClick={() => {
                                setSelectedLead(lead)
                                setDrawerTab('overview')
                              }}
                              className="inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-neutral-100 dark:bg-neutral-700 hover:bg-purple-100 dark:hover:bg-purple-900/40 text-[10px] font-bold text-neutral-700 dark:text-neutral-200 hover:text-purple-700 dark:hover:text-purple-300 transition-colors"
                            >
                              <span>Details</span>
                              <ChevronRight className="size-3" />
                            </button>
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
      </div>

      {/* 5. Lead Details Slide-over Drawer */}
      {selectedLead && (
        <div className="fixed inset-0 z-50 overflow-hidden">
          {/* Backdrop */}
          <div
            onClick={() => setSelectedLead(null)}
            className="absolute inset-0 bg-black/50 backdrop-blur-xs transition-opacity animate-in fade-in"
          />

          <div className="fixed inset-y-0 end-0 max-w-full flex pl-10">
            <div className="w-screen max-w-xl bg-white dark:bg-neutral-900 shadow-2xl border-s border-neutral-200 dark:border-neutral-800 flex flex-col animate-in slide-in-from-right duration-300">
              {/* Drawer Header */}
              <div className="p-5 border-b border-neutral-200 dark:border-neutral-800 bg-neutral-50/50 dark:bg-neutral-800/40 flex items-start justify-between">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-purple-500/10 text-purple-600 dark:text-purple-400 border border-purple-500/20">
                      LEAD #{selectedLead.id.toUpperCase()}
                    </span>
                    <span className="text-xs text-neutral-400">• Last contact: {selectedLead.lastContact}</span>
                  </div>

                  <h2 className="text-lg font-bold text-neutral-900 dark:text-white flex items-center gap-2">
                    {selectedLead.studentName}
                  </h2>
                  <p className="text-xs text-neutral-500">
                    Guardian: <span className="font-semibold text-neutral-800 dark:text-neutral-200">{selectedLead.parentName}</span> ({selectedLead.parentPhone})
                  </p>
                </div>

                <button
                  onClick={() => setSelectedLead(null)}
                  className="p-1.5 rounded-lg text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-200 hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-colors"
                >
                  <X className="size-5" />
                </button>
              </div>

              {/* Stage Mover Ribbon */}
              <div className="px-5 py-3 border-b border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 flex items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-semibold text-neutral-500">Pipeline Stage:</span>
                  <select
                    value={selectedLead.stage}
                    onChange={(e) => moveLeadToStage(selectedLead.id, e.target.value as StageId)}
                    className="px-2.5 py-1 text-xs font-bold rounded-lg border border-neutral-300 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-800 text-purple-600 dark:text-purple-400 focus:outline-hidden"
                  >
                    {PIPELINE_STAGES.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.title}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleTriggerWhatsApp(selectedLead)}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold transition-colors shadow-2xs"
                  >
                    <MessageSquare className="size-3.5" />
                    <span>WhatsApp</span>
                  </button>
                  <button
                    onClick={() => {
                      setScholarshipModalLead(selectedLead)
                      setScholarshipDiscount(selectedLead.discountOffered || 20)
                    }}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-purple-600 hover:bg-purple-700 text-white text-xs font-semibold transition-colors shadow-2xs"
                  >
                    <Award className="size-3.5" />
                    <span>Scholarship</span>
                  </button>
                </div>
              </div>

              {/* Drawer Navigation Tabs */}
              <div className="flex border-b border-neutral-200 dark:border-neutral-800 px-5 bg-neutral-50/70 dark:bg-neutral-900 text-xs">
                <button
                  onClick={() => setDrawerTab('overview')}
                  className={cn(
                    'py-3 px-4 font-bold border-b-2 transition-colors',
                    drawerTab === 'overview'
                      ? 'border-purple-600 text-purple-600 dark:text-purple-400'
                      : 'border-transparent text-neutral-500 hover:text-neutral-800 dark:hover:text-neutral-200'
                  )}
                >
                  Overview & Profile
                </button>
                <button
                  onClick={() => setDrawerTab('timeline')}
                  className={cn(
                    'py-3 px-4 font-bold border-b-2 transition-colors flex items-center gap-1.5',
                    drawerTab === 'timeline'
                      ? 'border-purple-600 text-purple-600 dark:text-purple-400'
                      : 'border-transparent text-neutral-500 hover:text-neutral-800 dark:hover:text-neutral-200'
                  )}
                >
                  <span>Activity History</span>
                  <span className="px-1.5 py-0.2 rounded-full bg-neutral-200 dark:bg-neutral-800 text-[10px]">
                    {selectedLead.activityTimeline.length}
                  </span>
                </button>
                <button
                  onClick={() => setDrawerTab('ai')}
                  className={cn(
                    'py-3 px-4 font-bold border-b-2 transition-colors flex items-center gap-1.5',
                    drawerTab === 'ai'
                      ? 'border-purple-600 text-purple-600 dark:text-purple-400'
                      : 'border-transparent text-neutral-500 hover:text-neutral-800 dark:hover:text-neutral-200'
                  )}
                >
                  <Sparkles className="size-3.5 text-purple-500" />
                  <span>AI SDR Intelligence</span>
                </button>
              </div>

              {/* Drawer Content */}
              <div className="flex-1 overflow-y-auto p-5 space-y-6">
                {drawerTab === 'overview' && (
                  <div className="space-y-5">
                    {/* Key Attributes Grid */}
                    <div className="grid grid-cols-2 gap-3 text-xs">
                      <div className="p-3 rounded-xl bg-neutral-50 dark:bg-neutral-800/50 border border-neutral-200 dark:border-neutral-800">
                        <span className="text-neutral-400">Target Grade</span>
                        <div className="font-bold text-neutral-900 dark:text-white mt-0.5">
                          {selectedLead.targetGrade}
                        </div>
                      </div>
                      <div className="p-3 rounded-xl bg-neutral-50 dark:bg-neutral-800/50 border border-neutral-200 dark:border-neutral-800">
                        <span className="text-neutral-400">Campus Branch</span>
                        <div className="font-bold text-neutral-900 dark:text-white mt-0.5">
                          {selectedLead.targetCampus}
                        </div>
                      </div>
                      <div className="p-3 rounded-xl bg-neutral-50 dark:bg-neutral-800/50 border border-neutral-200 dark:border-neutral-800">
                        <span className="text-neutral-400">Previous School</span>
                        <div className="font-bold text-neutral-900 dark:text-white mt-0.5">
                          {selectedLead.previousSchool}
                        </div>
                      </div>
                      <div className="p-3 rounded-xl bg-neutral-50 dark:bg-neutral-800/50 border border-neutral-200 dark:border-neutral-800">
                        <span className="text-neutral-400">Base Monthly Tuition</span>
                        <div className="font-bold text-emerald-600 dark:text-emerald-400 mt-0.5">
                          PKR {selectedLead.estimatedTuitionPKR.toLocaleString()} / mo
                        </div>
                      </div>
                    </div>

                    {/* Contact & SDR Desk */}
                    <div className="p-4 rounded-xl border border-neutral-200 dark:border-neutral-800 space-y-3">
                      <h4 className="text-xs font-bold text-neutral-900 dark:text-white uppercase tracking-wider">
                        Contact & SDR Assignment
                      </h4>
                      <div className="space-y-2 text-xs">
                        <div className="flex items-center justify-between">
                          <span className="text-neutral-500">Parent Phone:</span>
                          <span className="font-mono font-bold text-neutral-900 dark:text-white">
                            {selectedLead.parentPhone}
                          </span>
                        </div>
                        <div className="flex items-center justify-between">
                          <span className="text-neutral-500">Parent Email:</span>
                          <span className="font-medium text-neutral-900 dark:text-white">
                            {selectedLead.parentEmail}
                          </span>
                        </div>
                        <div className="flex items-center justify-between">
                          <span className="text-neutral-500">Assigned SDR Officer:</span>
                          <span className="font-bold text-purple-600 dark:text-purple-400">
                            {selectedLead.assignedSDR}
                          </span>
                        </div>
                        <div className="flex items-center justify-between">
                          <span className="text-neutral-500">Acquisition Source:</span>
                          <span className="font-semibold text-neutral-700 dark:text-neutral-300 uppercase">
                            {selectedLead.source}
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* Tags */}
                    <div>
                      <h4 className="text-xs font-bold text-neutral-500 uppercase tracking-wider mb-2">
                        Tags & Classifications
                      </h4>
                      <div className="flex flex-wrap gap-1.5">
                        {selectedLead.tags.map((tag, idx) => (
                          <span
                            key={idx}
                            className="px-2.5 py-1 rounded-lg text-xs font-semibold bg-neutral-100 dark:bg-neutral-800 text-neutral-700 dark:text-neutral-300 border border-neutral-200 dark:border-neutral-700"
                          >
                            {tag}
                          </span>
                        ))}
                      </div>
                    </div>

                    {/* Notes */}
                    <div className="p-4 rounded-xl bg-purple-50/50 dark:bg-purple-950/20 border border-purple-200/60 dark:border-purple-900/30">
                      <h4 className="text-xs font-bold text-purple-900 dark:text-purple-300 mb-1">
                        SDR Notes
                      </h4>
                      <p className="text-xs text-neutral-700 dark:text-neutral-300 leading-relaxed">
                        {selectedLead.notes}
                      </p>
                    </div>
                  </div>
                )}

                {drawerTab === 'timeline' && (
                  <div className="space-y-5">
                    {/* Add Activity Box */}
                    <div className="p-3.5 rounded-xl bg-neutral-50 dark:bg-neutral-800/50 border border-neutral-200 dark:border-neutral-800 space-y-2.5">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-neutral-800 dark:text-neutral-200">
                          Log New Interaction
                        </span>
                        <select
                          value={newActivityType}
                          onChange={(e) => setNewActivityType(e.target.value as ActivityLog['type'])}
                          className="text-xs px-2 py-1 rounded-lg border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-800"
                        >
                          <option value="call">Phone Call</option>
                          <option value="whatsapp">WhatsApp Message</option>
                          <option value="tour">Campus Tour</option>
                          <option value="assessment">Assessment Result</option>
                          <option value="note">Internal Note</option>
                        </select>
                      </div>
                      <textarea
                        rows={2}
                        placeholder="Type interaction summary, parent feedback or agreed next step..."
                        value={newActivityNote}
                        onChange={(e) => setNewActivityNote(e.target.value)}
                        className="w-full p-2.5 text-xs rounded-lg border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 text-neutral-900 dark:text-white focus:outline-hidden focus:ring-2 focus:ring-purple-500"
                      />
                      <div className="flex justify-end">
                        <button
                          onClick={handleAddActivity}
                          disabled={!newActivityNote.trim()}
                          className="px-3 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-700 disabled:opacity-50 text-white text-xs font-bold transition-colors shadow-2xs"
                        >
                          Log Activity
                        </button>
                      </div>
                    </div>

                    {/* Timeline Stream */}
                    <div className="relative border-s-2 border-purple-200 dark:border-purple-900/60 ms-3 space-y-4">
                      {selectedLead.activityTimeline.map((item) => (
                        <div key={item.id} className="relative ps-6">
                          {/* Dot */}
                          <div className="absolute -start-[9px] top-1 size-4 rounded-full bg-purple-600 border-2 border-white dark:border-neutral-900" />

                          <div className="p-3 rounded-xl bg-white dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-700/60 shadow-2xs">
                            <div className="flex items-center justify-between text-xs mb-1">
                              <span className="font-bold text-neutral-900 dark:text-white">
                                {item.title}
                              </span>
                              <span className="text-[10px] text-neutral-400">{item.timestamp}</span>
                            </div>
                            <p className="text-xs text-neutral-600 dark:text-neutral-300">
                              {item.description}
                            </p>
                            <div className="text-[10px] text-purple-600 dark:text-purple-400 font-medium mt-1">
                              By {item.agent}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {drawerTab === 'ai' && (
                  <div className="space-y-5">
                    {/* Score Radar / Breakdown */}
                    <div className="p-4 rounded-xl bg-purple-500/10 border border-purple-500/20 space-y-3">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <Sparkles className="size-4 text-purple-600 dark:text-purple-400" />
                          <h4 className="text-xs font-bold text-purple-950 dark:text-purple-200">
                            AI Qualification Score: {selectedLead.score}/100
                          </h4>
                        </div>
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-extrabold bg-purple-600 text-white">
                          HOT INTENT 🔥
                        </span>
                      </div>

                      {/* Attribute Bars */}
                      <div className="space-y-2 text-xs pt-1">
                        <div>
                          <div className="flex justify-between text-[11px] mb-1">
                            <span className="text-neutral-600 dark:text-neutral-400">Academic & Grade Fit</span>
                            <span className="font-bold">{selectedLead.aiScoreBreakdown.academicFit}%</span>
                          </div>
                          <div className="h-1.5 rounded-full bg-purple-200 dark:bg-purple-950 overflow-hidden">
                            <div
                              className="h-full bg-purple-600 rounded-full"
                              style={{ width: `${selectedLead.aiScoreBreakdown.academicFit}%` }}
                            />
                          </div>
                        </div>

                        <div>
                          <div className="flex justify-between text-[11px] mb-1">
                            <span className="text-neutral-600 dark:text-neutral-400">Budget & Financial Match</span>
                            <span className="font-bold">{selectedLead.aiScoreBreakdown.budgetMatch}%</span>
                          </div>
                          <div className="h-1.5 rounded-full bg-purple-200 dark:bg-purple-950 overflow-hidden">
                            <div
                              className="h-full bg-indigo-600 rounded-full"
                              style={{ width: `${selectedLead.aiScoreBreakdown.budgetMatch}%` }}
                            />
                          </div>
                        </div>

                        <div>
                          <div className="flex justify-between text-[11px] mb-1">
                            <span className="text-neutral-600 dark:text-neutral-400">Parent Responsiveness</span>
                            <span className="font-bold">{selectedLead.aiScoreBreakdown.parentEngagement}%</span>
                          </div>
                          <div className="h-1.5 rounded-full bg-purple-200 dark:bg-purple-950 overflow-hidden">
                            <div
                              className="h-full bg-emerald-600 rounded-full"
                              style={{ width: `${selectedLead.aiScoreBreakdown.parentEngagement}%` }}
                            />
                          </div>
                        </div>

                        <div>
                          <div className="flex justify-between text-[11px] mb-1">
                            <span className="text-neutral-600 dark:text-neutral-400">Decision Urgency Index</span>
                            <span className="font-bold">{selectedLead.aiScoreBreakdown.decisionUrgency}%</span>
                          </div>
                          <div className="h-1.5 rounded-full bg-purple-200 dark:bg-purple-950 overflow-hidden">
                            <div
                              className="h-full bg-rose-600 rounded-full"
                              style={{ width: `${selectedLead.aiScoreBreakdown.decisionUrgency}%` }}
                            />
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* AI Recommended Pitch */}
                    <div className="p-4 rounded-xl bg-blue-50 dark:bg-blue-950/20 border border-blue-200 dark:border-blue-900/40 space-y-2">
                      <div className="flex items-center gap-2 text-blue-900 dark:text-blue-300">
                        <Zap className="size-4 text-blue-600" />
                        <h4 className="text-xs font-bold uppercase tracking-wider">
                          Recommended SDR Pitch Strategy
                        </h4>
                      </div>
                      <p className="text-xs text-neutral-800 dark:text-neutral-200 leading-relaxed font-medium">
                        {selectedLead.aiRecommendedPitch}
                      </p>
                    </div>

                    {/* Autonomous SDR Summary */}
                    <div className="p-4 rounded-xl border border-neutral-200 dark:border-neutral-800 space-y-2">
                      <h4 className="text-xs font-bold text-neutral-900 dark:text-white uppercase tracking-wider">
                        RevOps Objection & Sentiment Notes
                      </h4>
                      <p className="text-xs text-neutral-600 dark:text-neutral-400 leading-relaxed">
                        {selectedLead.aiSdrSummary}
                      </p>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 6. 1-Click Scholarship Offer Generator Modal (Radix UI Dialog) */}
      {scholarshipModalLead && (
        <Dialog
          open={!!scholarshipModalLead}
          onOpenChange={(open) => {
            if (!open) {
              setScholarshipModalLead(null)
              setLetterCopied(false)
              setLetterDispatchedToast(false)
            }
          }}
        >
          <DialogContent className="max-w-2xl">
            <DialogHeader>
              <div className="flex items-center gap-2 text-purple-600 mb-1">
                <Award className="size-5" />
                <span className="text-xs font-bold uppercase tracking-wider">
                  Official Directorate Scholarship Suite
                </span>
              </div>
              <DialogTitle className="text-lg font-bold">
                1-Click Scholarship & Admission Offer Generator
              </DialogTitle>
              <DialogDescription className="text-xs">
                Calculate real-time fee concessions, waive enrollment charges, and generate official offer letters.
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-5 py-3">
              {/* Candidate Quick Header */}
              <div className="p-3.5 rounded-xl bg-purple-500/10 border border-purple-500/20 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
                <div>
                  <span className="text-neutral-500">Student Name:</span>
                  <div className="font-bold text-neutral-900 dark:text-white">
                    {scholarshipModalLead.studentName} ({scholarshipModalLead.targetGrade})
                  </div>
                </div>
                <div>
                  <span className="text-neutral-500">Target Campus:</span>
                  <div className="font-semibold text-purple-600 dark:text-purple-400">
                    {scholarshipModalLead.targetCampus}
                  </div>
                </div>
                <div>
                  <span className="text-neutral-500">AI Qualification:</span>
                  <div className="font-extrabold text-rose-600">
                    {scholarshipModalLead.score}/100 HOT
                  </div>
                </div>
              </div>

              {/* Slider for Discount Concession */}
              <div className="space-y-3 p-4 rounded-xl border border-neutral-200 dark:border-neutral-800">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-bold text-neutral-800 dark:text-neutral-200">
                    Scholarship Concession Discount (%):
                  </label>
                  <span className="text-sm font-extrabold text-purple-600 dark:text-purple-400 px-3 py-1 rounded-lg bg-purple-500/10">
                    {scholarshipDiscount}% Discount
                  </span>
                </div>

                <input
                  type="range"
                  min={0}
                  max={50}
                  step={5}
                  value={scholarshipDiscount}
                  onChange={(e) => setScholarshipDiscount(Number(e.target.value))}
                  className="w-full accent-purple-600 cursor-pointer"
                />

                {/* Quick Preset Buttons */}
                <div className="flex flex-wrap gap-2 pt-1">
                  {[0, 15, 20, 25, 35, 50].map((val) => (
                    <button
                      key={val}
                      onClick={() => setScholarshipDiscount(val)}
                      className={cn(
                        'px-2.5 py-1 rounded-lg text-xs font-semibold transition-colors',
                        scholarshipDiscount === val
                          ? 'bg-purple-600 text-white shadow-2xs'
                          : 'bg-neutral-100 dark:bg-neutral-800 text-neutral-600 dark:text-neutral-300 hover:bg-neutral-200'
                      )}
                    >
                      {val === 0 ? 'Standard 0%' : `${val}% ${val >= 35 ? 'Merit' : 'Early Bird'}`}
                    </button>
                  ))}
                </div>
              </div>

              {/* Real-time Tuition Math Breakdown */}
              {(() => {
                const base = scholarshipModalLead.estimatedTuitionPKR
                const discountAmt = (base * scholarshipDiscount) / 100
                const netFee = base - discountAmt
                const annualSavings = discountAmt * 12

                return (
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 text-xs">
                    <div className="p-3 rounded-xl bg-neutral-50 dark:bg-neutral-800/50 border border-neutral-200 dark:border-neutral-800">
                      <span className="text-neutral-400 text-[11px]">Base Tuition</span>
                      <div className="font-bold text-neutral-800 dark:text-neutral-200 mt-0.5">
                        PKR {base.toLocaleString()}
                      </div>
                    </div>
                    <div className="p-3 rounded-xl bg-rose-50 dark:bg-rose-950/20 border border-rose-200 dark:border-rose-900/30">
                      <span className="text-rose-500 text-[11px]">Concession ({scholarshipDiscount}%)</span>
                      <div className="font-bold text-rose-600 mt-0.5">
                        -PKR {discountAmt.toLocaleString()}
                      </div>
                    </div>
                    <div className="p-3 rounded-xl bg-emerald-50 dark:bg-emerald-950/20 border border-emerald-200 dark:border-emerald-900/30">
                      <span className="text-emerald-600 text-[11px]">Net Monthly Fee</span>
                      <div className="font-extrabold text-emerald-700 dark:text-emerald-400 mt-0.5">
                        PKR {netFee.toLocaleString()}
                      </div>
                    </div>
                    <div className="p-3 rounded-xl bg-purple-50 dark:bg-purple-950/20 border border-purple-200 dark:border-purple-900/30">
                      <span className="text-purple-600 text-[11px]">Annual Family Savings</span>
                      <div className="font-extrabold text-purple-700 dark:text-purple-400 mt-0.5">
                        PKR {annualSavings.toLocaleString()}
                      </div>
                    </div>
                  </div>
                )
              })()}

              {/* Formal Letter Preview */}
              <div className="p-4 rounded-xl bg-slate-50 dark:bg-neutral-900 border border-neutral-300 dark:border-neutral-700 font-mono text-[11px] text-neutral-800 dark:text-neutral-200 space-y-2 select-text">
                <div className="flex items-center justify-between border-b pb-2 border-neutral-200 dark:border-neutral-800 text-[10px] text-purple-600 dark:text-purple-400 font-bold uppercase">
                  <span>CSG Directorate of Admissions</span>
                  <span>Ref: CSG-SCH-2026-{(scholarshipModalLead.id).replace('lead-', '')}</span>
                </div>
                <p>Dear Mr./Mrs. {scholarshipModalLead.parentName},</p>
                <p>
                  We are delighted to confirm that following the academic diagnostic review, <strong>{scholarshipModalLead.studentName}</strong> has been granted a <strong>{scholarshipDiscount}% Merit & Early Decision Scholarship Concession</strong> for admission into <strong>{scholarshipModalLead.targetGrade}</strong> at our {scholarshipModalLead.targetCampus}.
                </p>
                <p>
                  Revised Monthly Fee: <strong>PKR {((scholarshipModalLead.estimatedTuitionPKR * (100 - scholarshipDiscount)) / 100).toLocaleString()}</strong> (Standard PKR {scholarshipModalLead.estimatedTuitionPKR.toLocaleString()}).
                </p>
                <p className="text-[10px] text-neutral-500">
                  *This concession offer is valid for 7 business days from date of issuance.
                </p>
              </div>

              {letterDispatchedToast && (
                <div className="p-3 rounded-xl bg-emerald-500/15 border border-emerald-500/30 text-emerald-700 dark:text-emerald-300 text-xs font-semibold flex items-center gap-2">
                  <CheckCircle2 className="size-4 text-emerald-600" />
                  <span>
                    Scholarship Offer & revised voucher successfully dispatched via WhatsApp & Email!
                  </span>
                </div>
              )}
            </div>

            <DialogFooter className="flex flex-col sm:flex-row gap-2">
              <button
                onClick={() => {
                  const letterText = `CSG Admissions Directorate: Dear Mr. ${scholarshipModalLead.parentName}, we are pleased to offer ${scholarshipModalLead.studentName} a ${scholarshipDiscount}% Merit Scholarship for ${scholarshipModalLead.targetGrade}. Revised fee: PKR ${((scholarshipModalLead.estimatedTuitionPKR * (100 - scholarshipDiscount)) / 100).toLocaleString()}/month.`
                  navigator.clipboard.writeText(letterText)
                  setLetterCopied(true)
                  setTimeout(() => setLetterCopied(false), 2500)
                }}
                className="px-3 py-2 rounded-xl border border-neutral-200 dark:border-neutral-700 hover:bg-neutral-100 dark:hover:bg-neutral-800 text-xs font-semibold text-neutral-700 dark:text-neutral-200 flex items-center justify-center gap-1.5"
              >
                {letterCopied ? <Check className="size-3.5 text-emerald-600" /> : <Copy className="size-3.5" />}
                <span>{letterCopied ? 'Copied to Clipboard' : 'Copy Letter Text'}</span>
              </button>

              <button
                onClick={() => {
                  setLetterDispatchedToast(true)
                  // Update lead discount and move stage to offer_sent
                  setLeads((prev) =>
                    prev.map((l) =>
                      l.id === scholarshipModalLead.id
                        ? {
                            ...l,
                            discountOffered: scholarshipDiscount,
                            stage: 'offer_sent',
                            activityTimeline: [
                              {
                                id: `act-${Date.now()}`,
                                type: 'email',
                                title: `Scholarship Offer Issued (${scholarshipDiscount}%)`,
                                description: `Generated and dispatched formal admission letter with ${scholarshipDiscount}% concession.`,
                                timestamp: 'Just now',
                                agent: 'Scholarship Directorate',
                              },
                              ...l.activityTimeline,
                            ],
                          }
                        : l
                    )
                  )
                  setTimeout(() => {
                    setScholarshipModalLead(null)
                    setLetterDispatchedToast(false)
                  }, 1800)
                }}
                className="px-4 py-2 rounded-xl bg-purple-600 hover:bg-purple-700 text-white text-xs font-bold flex items-center justify-center gap-1.5 shadow-md"
              >
                <Send className="size-3.5" />
                <span>Apply Concession & Dispatch Offer</span>
              </button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}

      {/* 7. Add Prospective Lead Modal */}
      <Dialog open={isNewLeadModalOpen} onOpenChange={setIsNewLeadModalOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <div className="flex items-center gap-2 text-purple-600 mb-1">
              <Users className="size-5" />
              <span className="text-xs font-bold uppercase tracking-wider">
                Admissions Intake Desk
              </span>
            </div>
            <DialogTitle className="text-lg font-bold">Add Prospective Student Lead</DialogTitle>
            <DialogDescription className="text-xs">
              Quickly create a prospective lead record to initiate autonomous AI nurture drips.
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={handleCreateNewLead} className="space-y-4 py-2">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold text-neutral-700 dark:text-neutral-300 mb-1">
                  Student Full Name *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Zaid Khan"
                  value={newLeadForm.studentName}
                  onChange={(e) =>
                    setNewLeadForm({ ...newLeadForm, studentName: e.target.value })
                  }
                  className="w-full p-2 text-xs rounded-xl border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 text-neutral-900 dark:text-white focus:outline-hidden focus:ring-2 focus:ring-purple-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-neutral-700 dark:text-neutral-300 mb-1">
                  Parent / Guardian Name *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Usman Khan"
                  value={newLeadForm.parentName}
                  onChange={(e) =>
                    setNewLeadForm({ ...newLeadForm, parentName: e.target.value })
                  }
                  className="w-full p-2 text-xs rounded-xl border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 text-neutral-900 dark:text-white focus:outline-hidden focus:ring-2 focus:ring-purple-500"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold text-neutral-700 dark:text-neutral-300 mb-1">
                  Parent WhatsApp / Phone *
                </label>
                <input
                  type="text"
                  required
                  placeholder="+92 300 1234567"
                  value={newLeadForm.parentPhone}
                  onChange={(e) =>
                    setNewLeadForm({ ...newLeadForm, parentPhone: e.target.value })
                  }
                  className="w-full p-2 text-xs rounded-xl border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 text-neutral-900 dark:text-white focus:outline-hidden focus:ring-2 focus:ring-purple-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-neutral-700 dark:text-neutral-300 mb-1">
                  Parent Email
                </label>
                <input
                  type="email"
                  placeholder="parent@gmail.com"
                  value={newLeadForm.parentEmail}
                  onChange={(e) =>
                    setNewLeadForm({ ...newLeadForm, parentEmail: e.target.value })
                  }
                  className="w-full p-2 text-xs rounded-xl border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 text-neutral-900 dark:text-white focus:outline-hidden focus:ring-2 focus:ring-purple-500"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold text-neutral-700 dark:text-neutral-300 mb-1">
                  Target Grade
                </label>
                <select
                  value={newLeadForm.targetGrade}
                  onChange={(e) =>
                    setNewLeadForm({ ...newLeadForm, targetGrade: e.target.value })
                  }
                  className="w-full p-2 text-xs rounded-xl border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 text-neutral-900 dark:text-white focus:outline-hidden"
                >
                  <option value="Grade 11 (Pre-Engineering)">Grade 11 (Pre-Engineering)</option>
                  <option value="Grade 11 (Pre-Medical)">Grade 11 (Pre-Medical)</option>
                  <option value="Grade 11 (Computer Science)">Grade 11 (Computer Science)</option>
                  <option value="Grade 9 (O-Levels)">Grade 9 (O-Levels)</option>
                  <option value="Grade 12 (A-Levels)">Grade 12 (A-Levels)</option>
                  <option value="Grade 8 (Middle School)">Grade 8 (Middle School)</option>
                  <option value="Primary School (Grade 1-5)">Primary School (Grade 1-5)</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-neutral-700 dark:text-neutral-300 mb-1">
                  Target Campus
                </label>
                <select
                  value={newLeadForm.targetCampus}
                  onChange={(e) =>
                    setNewLeadForm({ ...newLeadForm, targetCampus: e.target.value })
                  }
                  className="w-full p-2 text-xs rounded-xl border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 text-neutral-900 dark:text-white focus:outline-hidden"
                >
                  <option value="Islamabad Main Campus">Islamabad Main Campus</option>
                  <option value="Lahore Gulberg Campus">Lahore Gulberg Campus</option>
                  <option value="Rawalpindi North Campus">Rawalpindi North Campus</option>
                  <option value="Karachi DHA Campus">Karachi DHA Campus</option>
                </select>
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-neutral-700 dark:text-neutral-300 mb-1">
                Acquisition Channel Source
              </label>
              <select
                value={newLeadForm.source}
                onChange={(e) =>
                  setNewLeadForm({ ...newLeadForm, source: e.target.value as Lead['source'] })
                }
                className="w-full p-2 text-xs rounded-xl border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 text-neutral-900 dark:text-white focus:outline-hidden"
              >
                <option value="whatsapp">WhatsApp Direct Inbound</option>
                <option value="ads">Social Media Ads (Meta / Google)</option>
                <option value="web">Web Portal Lead Form</option>
                <option value="referral">Parent / Faculty Referral</option>
                <option value="walkin">Campus Walk-in Visit</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-neutral-700 dark:text-neutral-300 mb-1">
                Initial Discussion Notes
              </label>
              <textarea
                rows={2}
                placeholder="Specific parent requirements, discount requests, previous school..."
                value={newLeadForm.notes}
                onChange={(e) => setNewLeadForm({ ...newLeadForm, notes: e.target.value })}
                className="w-full p-2 text-xs rounded-xl border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 text-neutral-900 dark:text-white focus:outline-hidden"
              />
            </div>

            <DialogFooter>
              <button
                type="button"
                onClick={() => setIsNewLeadModalOpen(false)}
                className="px-3 py-2 rounded-xl border border-neutral-200 dark:border-neutral-700 text-xs font-semibold"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-4 py-2 rounded-xl bg-purple-600 hover:bg-purple-700 text-white text-xs font-bold shadow-md"
              >
                Create Lead & Queue AI SDR
              </button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* 8. Interactive SDR Chat Simulator Widget (Floating Dock) */}
      {isSdrSimulatorOpen && (
        <div className="fixed bottom-5 end-5 z-50 w-96 max-w-[calc(100vw-2rem)] rounded-2xl bg-white dark:bg-neutral-900 border border-purple-500/30 shadow-2xl shadow-purple-950/30 flex flex-col overflow-hidden animate-in slide-in-from-bottom-5">
          {/* Simulator Top Header */}
          <div className="p-3.5 bg-gradient-to-r from-purple-800 to-indigo-800 text-white flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="size-7 rounded-lg bg-white/20 flex items-center justify-center">
                <Bot className="size-4 text-white" />
              </div>
              <div>
                <h3 className="text-xs font-bold leading-tight flex items-center gap-1.5">
                  AI SDR Admissions Simulator
                  <span className="size-1.5 rounded-full bg-emerald-400 animate-pulse" />
                </h3>
                <span className="text-[10px] text-purple-200">
                  Live Qualification Score: {sdrLiveScore}/100
                </span>
              </div>
            </div>

            <button
              onClick={() => setIsSdrSimulatorOpen(false)}
              className="p-1 rounded-md text-white/80 hover:text-white hover:bg-white/10 transition-colors"
            >
              <X className="size-4" />
            </button>
          </div>

          {/* Quick Scenario Buttons */}
          <div className="p-2 border-b border-neutral-200 dark:border-neutral-800 bg-neutral-50/70 dark:bg-neutral-800/40 flex items-center gap-1 overflow-x-auto text-[10px]">
            <span className="text-neutral-400 px-1 font-semibold">Test Prompt:</span>
            <button
              onClick={() => handleSendSdrMessage('What are your fee structure and STEM scholarship options?')}
              className="px-2 py-1 rounded-md bg-white dark:bg-neutral-700 border border-neutral-200 dark:border-neutral-600 hover:border-purple-400 text-neutral-700 dark:text-neutral-200 shrink-0 font-medium"
            >
              💰 Fees & Concession
            </button>
            <button
              onClick={() => handleSendSdrMessage('Can we schedule a campus visit for Saturday?')}
              className="px-2 py-1 rounded-md bg-white dark:bg-neutral-700 border border-neutral-200 dark:border-neutral-600 hover:border-purple-400 text-neutral-700 dark:text-neutral-200 shrink-0 font-medium"
            >
              🏫 Saturday Tour
            </button>
            <button
              onClick={() => handleSendSdrMessage('Do you have transport for Bahria Town?')}
              className="px-2 py-1 rounded-md bg-white dark:bg-neutral-700 border border-neutral-200 dark:border-neutral-600 hover:border-purple-400 text-neutral-700 dark:text-neutral-200 shrink-0 font-medium"
            >
              🚌 Transport
            </button>
          </div>

          {/* Chat Messages */}
          <div className="p-3 space-y-2.5 h-64 overflow-y-auto text-xs bg-neutral-50/30 dark:bg-neutral-900/50">
            {sdrMessages.map((msg, idx) => (
              <div
                key={idx}
                className={cn(
                  'flex flex-col',
                  msg.sender === 'user' ? 'items-end' : 'items-start'
                )}
              >
                <div
                  className={cn(
                    'p-2.5 rounded-xl max-w-[85%] leading-relaxed',
                    msg.sender === 'user'
                      ? 'bg-purple-600 text-white rounded-br-none'
                      : 'bg-white dark:bg-neutral-800 text-neutral-800 dark:text-neutral-200 border border-neutral-200 dark:border-neutral-700 rounded-bl-none shadow-2xs'
                  )}
                >
                  {msg.text}
                </div>
                <div className="flex items-center gap-1.5 mt-0.5 text-[9px] text-neutral-400 px-1">
                  <span>{msg.time}</span>
                  {msg.qualificationDelta && (
                    <span className="text-emerald-600 font-bold">
                      +{msg.qualificationDelta} Score
                    </span>
                  )}
                </div>
              </div>
            ))}
            {sdrIsTyping && (
              <div className="flex items-center gap-1 text-[11px] text-neutral-400 p-2">
                <span className="size-1.5 rounded-full bg-purple-500 animate-bounce" />
                <span className="size-1.5 rounded-full bg-purple-500 animate-bounce delay-150" />
                <span className="size-1.5 rounded-full bg-purple-500 animate-bounce delay-300" />
                <span className="ms-1">AI SDR analyzing intent...</span>
              </div>
            )}
          </div>

          {/* Simulator Input Box */}
          <div className="p-2.5 border-t border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 flex items-center gap-1.5">
            <input
              type="text"
              placeholder="Ask SDR Bot anything (fees, tour, faculty)..."
              value={sdrInput}
              onChange={(e) => setSdrInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleSendSdrMessage()
              }}
              className="flex-1 p-2 text-xs rounded-xl border border-neutral-300 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-800 text-neutral-900 dark:text-white focus:outline-hidden focus:ring-2 focus:ring-purple-500"
            />
            <button
              onClick={() => handleSendSdrMessage()}
              className="p-2 rounded-xl bg-purple-600 hover:bg-purple-700 text-white transition-colors"
            >
              <Send className="size-3.5" />
            </button>
          </div>

          {/* Footer: Convert to CRM Lead */}
          <div className="p-2 bg-purple-50 dark:bg-neutral-800/80 border-t border-purple-100 dark:border-neutral-700 flex items-center justify-between text-[11px]">
            <span className="text-neutral-500 font-medium">Ready to save prospect?</span>
            <button
              onClick={handleConvertSimulatorToLead}
              className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-purple-600 hover:bg-purple-700 text-white font-bold transition-colors shadow-2xs"
            >
              <Plus className="size-3" />
              <span>Save as Lead</span>
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
