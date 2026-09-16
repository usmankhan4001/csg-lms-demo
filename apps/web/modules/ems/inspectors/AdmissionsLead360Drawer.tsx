'use client'

import React, { useState } from 'react'
import {
  Users,
  TrendingUp,
  Phone,
  MessageSquare,
  Mail,
  Calendar,
  Sparkles,
  FileCheck,
  FileText,
  DollarSign,
  Award,
  CheckCircle2,
  Clock,
  Send,
  Building2,
  UserCheck,
  Flame,
  Zap,
  Snowflake,
  ShieldCheck,
  Layers,
  MapPin,
  ExternalLink,
  Plus,
  Compass,
} from 'lucide-react'
import { Entity360Drawer, Entity360Tab, Entity360Badge, Entity360QuickAction } from '@/components/ems/Entity360Drawer'
import { AdmissionsLeadCard, PipelineStageId, LeadScoreTier } from '../admissions/types'
import { formatPKR } from '../admissions/mockData'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog'
import toast from 'react-hot-toast'

export interface AdmissionsLead360DrawerProps {
  isOpen: boolean
  onClose: () => void
  lead?: AdmissionsLeadCard | null
  onMatriculate?: (lead: AdmissionsLeadCard) => void
  onScheduleTour?: (leadId: string, tourDate: string) => void
  onSendOffer?: (leadId: string) => void
}

const DEFAULT_LEAD: AdmissionsLeadCard = {
  id: 'LEAD-2026-0901',
  studentName: 'Zayd Al-Mansoor',
  parentName: 'Tariq Al-Mansoor',
  parentPhone: '+92 300 4819201',
  parentEmail: 'tariq.mansoor@alphagroup.pk',
  targetGrade: 'Grade 11',
  targetCampus: 'Main Science Campus, Lahore',
  feederSchool: 'Lahore Grammar School (LGS 55-Main)',
  feederCategory: 'Private Grammar',
  stage: 'assessment',
  leadScore: 88,
  leadScoreTier: 'HOT',
  grossTuitionPKR: 450000,
  scholarshipDiscountPercent: 15,
  netTuitionYieldPKR: 382500,
  assignedOfficer: 'Sarah Ahmed (Senior RevOps)',
  source: 'referral',
  lastContactedDate: '2026-09-15',
  createdAt: '2026-09-01',
  notes: 'High academic profile, interested in AP Physics and Robotics program. Father requested Net Tuition yield simulation.',
  priority: 'URGENT',
  tags: ['AP Physics', 'Robotics Merit', 'Sibling Cohort'],
  guardianCnic: '35201-9281729-1',
  scoreBreakdown: {
    academicFit: 95,
    budgetReadiness: 90,
    parentEngagement: 85,
    decisionUrgency: 82,
  },
  recommendedPitch: 'Highlight state-of-the-art CSG Robotics Lab & MIT/Cognia faculty mentorship for AP Physics C.',
  activities: [
    { id: 'ACT-01', type: 'call', title: 'Admissions Screening Call', description: 'Discussed student academic background and science track goals.', timestamp: '2026-09-15 14:30', officer: 'Sarah Ahmed' },
    { id: 'ACT-02', type: 'tour', title: 'STEM Campus Guided Tour', description: 'Family visited physics lab & met with Dr. Eleanor Vance.', timestamp: '2026-09-12 10:00', officer: 'Hamza Tariq' },
    { id: 'ACT-03', type: 'whatsapp', title: 'Dispatched Prospectus & Fee Structure', description: 'Shared digitized brochure via official WhatsApp bot.', timestamp: '2026-09-02 11:15', officer: 'System Bot' },
  ],
}

export const AdmissionsLead360Drawer: React.FC<AdmissionsLead360DrawerProps> = ({
  isOpen,
  onClose,
  lead = DEFAULT_LEAD,
  onMatriculate,
  onScheduleTour,
  onSendOffer,
}) => {
  const currentLead = lead || DEFAULT_LEAD
  const [activeTab, setActiveTab] = useState<string>('overview')

  // Modals
  const [isTourModalOpen, setIsTourModalOpen] = useState<boolean>(false)
  const [isOfferModalOpen, setIsOfferModalOpen] = useState<boolean>(false)
  const [isAddNoteModalOpen, setIsAddNoteModalOpen] = useState<boolean>(false)

  // Tour Form State
  const [tourDate, setTourDate] = useState<string>('2026-09-22')
  const [tourTime, setTourTime] = useState<string>('10:30 AM')
  const [tourGuide, setTourGuide] = useState<string>('Sarah Ahmed (Senior RevOps)')

  // Quick Note Form
  const [noteText, setNoteText] = useState<string>('')
  const [noteChannel, setNoteChannel] = useState<'call' | 'whatsapp' | 'email' | 'note'>('call')

  // Tuition Yield Dynamic Slider
  const [discountPercent, setDiscountPercent] = useState<number>(currentLead.scholarshipDiscountPercent || 15)
  const simulatedYieldPKR = Math.round(currentLead.grossTuitionPKR * (1 - discountPercent / 100))

  const tabs: Entity360Tab[] = [
    { id: 'overview', label: 'Overview & BANT Radar', icon: <Sparkles className="h-3.5 w-3.5" /> },
    { id: 'timeline', label: 'Interaction Timeline & Calls', icon: <MessageSquare className="h-3.5 w-3.5" />, count: currentLead.activities?.length || 0 },
    { id: 'tours', label: 'Tour Bookings', icon: <Compass className="h-3.5 w-3.5" /> },
    { id: 'documents', label: 'Application Documents', icon: <FileCheck className="h-3.5 w-3.5" />, count: '4/4' },
    { id: 'yield', label: 'Tuition Yield Modeler', icon: <DollarSign className="h-3.5 w-3.5" />, count: formatPKR(simulatedYieldPKR) },
  ]

  const badges: Entity360Badge[] = [
    {
      label: currentLead.leadScoreTier,
      variant: currentLead.leadScoreTier === 'HOT' ? 'destructive' : currentLead.leadScoreTier === 'WARM' ? 'amber' : 'cyan',
      icon: currentLead.leadScoreTier === 'HOT' ? <Flame className="h-3 w-3" /> : currentLead.leadScoreTier === 'WARM' ? <Zap className="h-3 w-3" /> : <Snowflake className="h-3 w-3" />,
    },
    { label: currentLead.stage.replace('_', ' ').toUpperCase(), variant: 'purple' },
    { label: `Score: ${currentLead.leadScore}/100`, variant: 'blue' },
  ]

  const quickActions: Entity360QuickAction[] = [
    {
      label: '1-Click Matriculate',
      icon: <UserCheck className="h-3.5 w-3.5" />,
      onClick: () => {
        if (onMatriculate) onMatriculate(currentLead)
        toast.success(`Matriculation Handshake initiated for ${currentLead.studentName}!`)
      },
      variant: 'primary',
    },
    {
      label: 'Schedule Tour',
      icon: <Calendar className="h-3.5 w-3.5" />,
      onClick: () => setIsTourModalOpen(true),
      variant: 'outline',
    },
    {
      label: 'Send Offer Letter',
      icon: <Send className="h-3.5 w-3.5" />,
      onClick: () => setIsOfferModalOpen(true),
      variant: 'secondary',
    },
  ]

  const handleTourSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (onScheduleTour) {
      onScheduleTour(currentLead.id, `${tourDate} ${tourTime}`)
    }
    toast.success(`Campus tour scheduled for ${currentLead.studentName} on ${tourDate} at ${tourTime}!`)
    setIsTourModalOpen(false)
  }

  const handleAddNoteSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!noteText.trim()) return
    toast.success(`Logged ${noteChannel} record!`)
    setIsAddNoteModalOpen(false)
    setNoteText('')
  }

  return (
    <>
      <Entity360Drawer
        isOpen={isOpen}
        onClose={onClose}
        title={currentLead.studentName}
        subtitle={`Parent: ${currentLead.parentName} • ${currentLead.targetGrade} • ${currentLead.targetCampus}`}
        entityTypeBadge="Admissions Lead 360°"
        avatar={{
          initials: currentLead.studentName.slice(0, 2).toUpperCase(),
          statusDot: currentLead.leadScoreTier === 'HOT' ? 'online' : 'away',
          bgClass: 'bg-gradient-to-br from-amber-500 to-rose-600 text-white',
        }}
        badges={badges}
        quickActions={quickActions}
        tabs={tabs}
        activeTab={activeTab}
        onTabChange={setActiveTab}
        metaBar={
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
            <div className="flex items-center gap-2 p-2 rounded-lg bg-zinc-100/80 dark:bg-zinc-800/60 border border-zinc-200/50 dark:border-zinc-700/50">
              <TrendingUp className="h-4 w-4 text-rose-500 shrink-0" />
              <div>
                <p className="text-[10px] text-zinc-400 font-medium">Lead Propensity</p>
                <p className="font-bold text-zinc-900 dark:text-zinc-100">{currentLead.leadScore} / 100 ({currentLead.leadScoreTier})</p>
              </div>
            </div>
            <div className="flex items-center gap-2 p-2 rounded-lg bg-zinc-100/80 dark:bg-zinc-800/60 border border-zinc-200/50 dark:border-zinc-700/50">
              <DollarSign className="h-4 w-4 text-emerald-500 shrink-0" />
              <div>
                <p className="text-[10px] text-zinc-400 font-medium">Net Tuition Yield</p>
                <p className="font-bold text-emerald-600 dark:text-emerald-400">{formatPKR(currentLead.netTuitionYieldPKR)}</p>
              </div>
            </div>
            <div className="flex items-center gap-2 p-2 rounded-lg bg-zinc-100/80 dark:bg-zinc-800/60 border border-zinc-200/50 dark:border-zinc-700/50">
              <Building2 className="h-4 w-4 text-indigo-500 shrink-0" />
              <div>
                <p className="text-[10px] text-zinc-400 font-medium">Feeder School</p>
                <p className="font-bold text-zinc-900 dark:text-zinc-100 truncate max-w-[120px]">{currentLead.feederSchool}</p>
              </div>
            </div>
            <div className="flex items-center gap-2 p-2 rounded-lg bg-zinc-100/80 dark:bg-zinc-800/60 border border-zinc-200/50 dark:border-zinc-700/50">
              <Users className="h-4 w-4 text-purple-500 shrink-0" />
              <div>
                <p className="text-[10px] text-zinc-400 font-medium">Assigned Officer</p>
                <p className="font-bold text-purple-600 dark:text-purple-400 truncate max-w-[120px]">{currentLead.assignedOfficer}</p>
              </div>
            </div>
          </div>
        }
      >
        {/* TAB 1: OVERVIEW & BANT RADAR */}
        {activeTab === 'overview' && (
          <div className="space-y-6">
            {/* AI Pitch Advisor */}
            {currentLead.recommendedPitch && (
              <div className="p-4 rounded-xl bg-gradient-to-r from-indigo-500/10 via-purple-500/10 to-transparent border border-indigo-500/20 text-xs">
                <div className="flex items-center gap-2 text-indigo-700 dark:text-indigo-300 font-bold mb-1">
                  <Sparkles className="h-4 w-4" />
                  AI Recommended Value Pitch & Conversion Script
                </div>
                <p className="text-zinc-700 dark:text-zinc-300 italic">{currentLead.recommendedPitch}</p>
              </div>
            )}

            {/* BANT Propensity Breakdown */}
            <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-5 space-y-4">
              <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-400 flex items-center gap-2">
                <TrendingUp className="h-4 w-4 text-indigo-500" />
                BANT Lead Score & Multi-Dimensional Fit
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-3">
                  <div>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-zinc-600 dark:text-zinc-300">Academic Alignment (STEM Fit)</span>
                      <span className="font-bold text-indigo-600">{currentLead.scoreBreakdown?.academicFit || 90}%</span>
                    </div>
                    <div className="w-full bg-zinc-100 dark:bg-zinc-800 rounded-full h-2">
                      <div className="bg-indigo-600 h-2 rounded-full" style={{ width: `${currentLead.scoreBreakdown?.academicFit || 90}%` }} />
                    </div>
                  </div>

                  <div>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-zinc-600 dark:text-zinc-300">Budget Readiness & Yield Viability</span>
                      <span className="font-bold text-emerald-600">{currentLead.scoreBreakdown?.budgetReadiness || 85}%</span>
                    </div>
                    <div className="w-full bg-zinc-100 dark:bg-zinc-800 rounded-full h-2">
                      <div className="bg-emerald-600 h-2 rounded-full" style={{ width: `${currentLead.scoreBreakdown?.budgetReadiness || 85}%` }} />
                    </div>
                  </div>
                </div>

                <div className="space-y-3">
                  <div>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-zinc-600 dark:text-zinc-300">Parent Engagement & Speed-to-Reply</span>
                      <span className="font-bold text-purple-600">{currentLead.scoreBreakdown?.parentEngagement || 80}%</span>
                    </div>
                    <div className="w-full bg-zinc-100 dark:bg-zinc-800 rounded-full h-2">
                      <div className="bg-purple-600 h-2 rounded-full" style={{ width: `${currentLead.scoreBreakdown?.parentEngagement || 80}%` }} />
                    </div>
                  </div>

                  <div>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-zinc-600 dark:text-zinc-300">Decision Urgency / Cohort Deadline</span>
                      <span className="font-bold text-amber-600">{currentLead.scoreBreakdown?.decisionUrgency || 75}%</span>
                    </div>
                    <div className="w-full bg-zinc-100 dark:bg-zinc-800 rounded-full h-2">
                      <div className="bg-amber-500 h-2 rounded-full" style={{ width: `${currentLead.scoreBreakdown?.decisionUrgency || 75}%` }} />
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Parent & Contact Information */}
            <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-5 text-xs space-y-3">
              <h3 className="font-bold uppercase tracking-wider text-zinc-400 text-[11px]">Parent & Guardian Direct Line</h3>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div>
                  <span className="text-zinc-400">Parent Full Name</span>
                  <p className="font-semibold text-zinc-900 dark:text-zinc-100 mt-0.5">{currentLead.parentName}</p>
                </div>
                <div>
                  <span className="text-zinc-400">Phone / WhatsApp</span>
                  <p className="font-semibold text-indigo-600 dark:text-indigo-400 mt-0.5 font-mono">
                    <a href={`tel:${currentLead.parentPhone}`} className="hover:underline">{currentLead.parentPhone}</a>
                  </p>
                </div>
                <div>
                  <span className="text-zinc-400">Email Address</span>
                  <p className="font-semibold text-zinc-900 dark:text-zinc-100 mt-0.5">
                    <a href={`mailto:${currentLead.parentEmail}`} className="hover:underline">{currentLead.parentEmail}</a>
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: TIMELINE */}
        {activeTab === 'timeline' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-zinc-900 dark:text-zinc-100">Omnichannel Interaction History</h3>
                <p className="text-xs text-zinc-500">Live call transcripts, WhatsApp exchanges, and tour logs</p>
              </div>
              <button
                type="button"
                onClick={() => setIsAddNoteModalOpen(true)}
                className="px-3 py-1.5 text-xs font-semibold rounded-lg bg-zinc-900 text-white dark:bg-white dark:text-zinc-900 hover:opacity-90 flex items-center gap-1.5 cursor-pointer"
              >
                <Plus className="h-3.5 w-3.5" />
                Log Interaction
              </button>
            </div>

            <div className="space-y-3">
              {currentLead.activities?.map((act) => (
                <div key={act.id} className="p-4 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 space-y-1.5 text-xs">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-indigo-50 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300">
                        {act.type}
                      </span>
                      <h4 className="font-bold text-zinc-900 dark:text-zinc-100">{act.title}</h4>
                    </div>
                    <span className="text-[10px] text-zinc-400">{act.timestamp}</span>
                  </div>
                  <p className="text-zinc-600 dark:text-zinc-300">{act.description}</p>
                  <p className="text-[10px] text-zinc-400 pt-1">Logged by: <strong className="text-zinc-600 dark:text-zinc-300">{act.officer}</strong></p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* TAB 3: TOURS */}
        {activeTab === 'tours' && (
          <div className="space-y-4">
            <div className="p-5 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-bold text-zinc-900 dark:text-zinc-100">STEM Campus Guided Tour</h3>
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-800">COMPLETED</span>
              </div>
              <p className="text-xs text-zinc-600 dark:text-zinc-300">
                Conducted by Senior Admissions Guide Sarah Ahmed. Parent and applicant inspected the Quantum Mechanics Lab, Robotics Fab Studio, and met with the Head of Sciences.
              </p>
              <div className="pt-2 border-t border-zinc-100 dark:border-zinc-800 flex items-center justify-between text-xs text-zinc-500">
                <span>Date: <strong>Sept 12, 2026 at 10:00 AM</strong></span>
                <span>Rating: <strong>5/5 ★ (Parent indicated high satisfaction)</strong></span>
              </div>
            </div>

            <button
              type="button"
              onClick={() => setIsTourModalOpen(true)}
              className="w-full py-3 rounded-xl border-2 border-dashed border-zinc-300 dark:border-zinc-700 text-xs font-semibold text-zinc-600 dark:text-zinc-400 hover:border-indigo-500 hover:text-indigo-600 transition-colors flex items-center justify-center gap-2 cursor-pointer"
            >
              <Calendar className="h-4 w-4" />
              Schedule Follow-Up / Second Campus Tour
            </button>
          </div>
        )}

        {/* TAB 4: DOCUMENTS */}
        {activeTab === 'documents' && (
          <div className="space-y-4">
            <h3 className="text-sm font-bold text-zinc-900 dark:text-zinc-100">Matriculation Document Verification Checklist</h3>
            <div className="space-y-2 text-xs">
              {[
                { name: 'Official Birth Certificate / B-Form', status: 'VERIFIED', date: '2026-09-03' },
                { name: 'Previous 2-Year Official Transcript (LGS)', status: 'VERIFIED', date: '2026-09-04' },
                { name: 'Parent / Guardian CNIC Copy', status: 'VERIFIED', date: '2026-09-03' },
                { name: 'Student Vaccination & Medical Record', status: 'VERIFIED', date: '2026-09-05' },
              ].map((doc, idx) => (
                <div key={idx} className="p-3.5 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <FileCheck className="h-4 w-4 text-emerald-500 shrink-0" />
                    <div>
                      <p className="font-semibold text-zinc-900 dark:text-zinc-100">{doc.name}</p>
                      <p className="text-[10px] text-zinc-400">Verified on {doc.date}</p>
                    </div>
                  </div>
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
                    {doc.status}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* TAB 5: TUITION YIELD */}
        {activeTab === 'yield' && (
          <div className="space-y-5">
            <div className="p-5 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 space-y-4">
              <h3 className="text-sm font-bold text-zinc-900 dark:text-zinc-100">Dynamic Net Tuition Yield Calculator</h3>
              <p className="text-xs text-zinc-500">Model scholarship concessions against annual tuition revenue targets.</p>

              <div className="space-y-2">
                <div className="flex justify-between text-xs">
                  <span className="font-semibold text-zinc-700 dark:text-zinc-300">Scholarship / Merit Discount:</span>
                  <span className="font-bold text-indigo-600">{discountPercent}% Concession</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="50"
                  step="5"
                  value={discountPercent}
                  onChange={(e) => setDiscountPercent(Number(e.target.value))}
                  className="w-full accent-indigo-600 cursor-pointer"
                />
              </div>

              <div className="grid grid-cols-2 gap-4 pt-3 border-t border-zinc-100 dark:border-zinc-800 text-xs">
                <div>
                  <span className="text-zinc-400">Gross Annual Tuition</span>
                  <p className="font-bold text-zinc-900 dark:text-zinc-100 text-base">{formatPKR(currentLead.grossTuitionPKR)}</p>
                </div>
                <div>
                  <span className="text-zinc-400">Simulated Net Annual Yield</span>
                  <p className="font-bold text-emerald-600 dark:text-emerald-400 text-base">{formatPKR(simulatedYieldPKR)}</p>
                </div>
              </div>
            </div>
          </div>
        )}
      </Entity360Drawer>

      {/* SCHEDULE TOUR DIALOG */}
      <Dialog open={isTourModalOpen} onOpenChange={setIsTourModalOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Schedule STEM Campus Tour</DialogTitle>
            <DialogDescription>Assign date, timeslot, and designated admissions officer</DialogDescription>
          </DialogHeader>
          <form onSubmit={handleTourSubmit} className="space-y-4 text-xs">
            <div>
              <label className="block font-medium text-zinc-700 dark:text-zinc-300 mb-1">Tour Date</label>
              <input
                type="date"
                value={tourDate}
                onChange={(e) => setTourDate(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900"
                required
              />
            </div>
            <div>
              <label className="block font-medium text-zinc-700 dark:text-zinc-300 mb-1">Time Slot</label>
              <input
                type="text"
                value={tourTime}
                onChange={(e) => setTourTime(e.target.value)}
                placeholder="e.g. 10:30 AM"
                className="w-full px-3 py-2 rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900"
                required
              />
            </div>
            <div>
              <label className="block font-medium text-zinc-700 dark:text-zinc-300 mb-1">Designated Guide / Officer</label>
              <input
                type="text"
                value={tourGuide}
                onChange={(e) => setTourGuide(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900"
              />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setIsTourModalOpen(false)}
                className="px-3 py-2 text-xs font-semibold rounded-lg border border-zinc-300 dark:border-zinc-700"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-4 py-2 text-xs font-semibold rounded-lg bg-indigo-600 text-white hover:bg-indigo-700"
              >
                Confirm Tour Booking
              </button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      {/* SEND OFFER LETTER DIALOG */}
      <Dialog open={isOfferModalOpen} onOpenChange={setIsOfferModalOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Send Official Admission Offer Letter</DialogTitle>
            <DialogDescription>Generate signed offer letter with net tuition terms</DialogDescription>
          </DialogHeader>
          <div className="p-4 bg-zinc-50 dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800 text-xs space-y-2">
            <p><strong>Candidate:</strong> {currentLead.studentName} ({currentLead.targetGrade})</p>
            <p><strong>Parent:</strong> {currentLead.parentName} ({currentLead.parentEmail})</p>
            <p><strong>Net Annual Tuition:</strong> {formatPKR(simulatedYieldPKR)} ({discountPercent}% Scholarship Applied)</p>
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={() => setIsOfferModalOpen(false)}
              className="px-3 py-2 text-xs font-semibold rounded-lg border border-zinc-300 dark:border-zinc-700"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={() => {
                if (onSendOffer) onSendOffer(currentLead.id)
                toast.success(`Official Offer Letter PDF dispatched to ${currentLead.parentEmail}!`)
                setIsOfferModalOpen(false)
              }}
              className="px-4 py-2 text-xs font-semibold rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 flex items-center gap-1.5"
            >
              <Send className="h-3.5 w-3.5" />
              Dispatch Signed PDF
            </button>
          </div>
        </DialogContent>
      </Dialog>

      {/* LOG NOTE DIALOG */}
      <Dialog open={isAddNoteModalOpen} onOpenChange={setIsAddNoteModalOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Log Interaction / Call Note</DialogTitle>
            <DialogDescription>Record conversation summary and action items</DialogDescription>
          </DialogHeader>
          <form onSubmit={handleAddNoteSubmit} className="space-y-4 text-xs">
            <div>
              <label className="block font-medium text-zinc-700 dark:text-zinc-300 mb-1">Interaction Medium</label>
              <select
                value={noteChannel}
                onChange={(e) => setNoteChannel(e.target.value as any)}
                className="w-full px-3 py-2 rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 font-semibold"
              >
                <option value="call">Phone Call (Inbound/Outbound)</option>
                <option value="whatsapp">WhatsApp Official Chat</option>
                <option value="email">Email Communication</option>
                <option value="note">Internal RevOps Note</option>
              </select>
            </div>
            <div>
              <label className="block font-medium text-zinc-700 dark:text-zinc-300 mb-1">Summary / Discussion Note</label>
              <textarea
                value={noteText}
                onChange={(e) => setNoteText(e.target.value)}
                rows={3}
                placeholder="Parent confirmed attendance for upcoming weekend test..."
                className="w-full px-3 py-2 rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900"
                required
              />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setIsAddNoteModalOpen(false)}
                className="px-3 py-2 text-xs font-semibold rounded-lg border border-zinc-300 dark:border-zinc-700"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-4 py-2 text-xs font-semibold rounded-lg bg-zinc-900 text-white dark:bg-white dark:text-zinc-900"
              >
                Save Interaction
              </button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </>
  )
}
