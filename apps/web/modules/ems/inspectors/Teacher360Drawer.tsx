'use client'

import React, { useState } from 'react'
import {
  Users,
  Calendar,
  BookOpen,
  Award,
  DollarSign,
  TrendingUp,
  Clock,
  Sparkles,
  Download,
  CalendarDays,
  FileCheck,
  Send,
  Building2,
  Mail,
  Phone,
  CheckCircle2,
  AlertTriangle,
  Flame,
  Zap,
  BarChart3,
  GraduationCap,
  Layers,
  ChevronRight,
  ShieldCheck,
  Plus,
} from 'lucide-react'
import { Entity360Drawer, Entity360Tab, Entity360Badge, Entity360QuickAction } from '@/components/ems/Entity360Drawer'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog'
import toast from 'react-hot-toast'

export interface TimetableSlot {
  day: 'Mon' | 'Tue' | 'Wed' | 'Thu' | 'Fri'
  period: number
  time: string
  subject: string
  classSection: string
  room: string
}

export interface AssignedClassItem {
  id: string
  name: string
  section: string
  subject: string
  studentCount: number
  avgGpa: number
  syllabusProgress: number
  upcomingAssessment: string
}

export interface TeacherCompensation {
  basicPKR: number
  housingAllowancePKR: number
  medicalAllowancePKR: number
  specialDutyAllowancePKR: number
  taxDeductionPKR: number
  providentFundPKR: number
  netSalaryPKR: number
  bankIban: string
  bankName: string
  recentPayslips: Array<{
    slipNo: string
    month: string
    netAmount: number
    status: 'PAID' | 'PROCESSING'
  }>
}

export interface Teacher360Profile {
  id: string
  employeeId: string
  name: string
  avatarUrl?: string
  designation: string
  department: string
  campus: string
  qualification: string
  tenureYears: number
  email: string
  phone: string
  status: 'Active' | 'On Leave' | 'Sabbatical'
  performanceRating: number // e.g. 4.85
  teachingHoursPerWeek: number
  cogniaAccreditationCertified: boolean
  speedGraderPending: number
  speedGraderGradedMonth: number
  speedGraderTurnaroundHours: number
  classes: AssignedClassItem[]
  timetable: TimetableSlot[]
  compensation: TeacherCompensation
  kpiRadar: {
    cogniaStandardFidelity: number
    studentGrowthPercentile: number
    peerReviewScore: number
    punctualityScore: number
    lmsEngagement: number
  }
}

export interface Teacher360DrawerProps {
  isOpen: boolean
  onClose: () => void
  teacher?: Teacher360Profile | null
  onAssignCoursework?: (teacherId: string, payload: any) => void
}

const DEFAULT_TEACHER_PROFILE: Teacher360Profile = {
  id: 'TCH-2026-084',
  employeeId: 'EMP-FAC-084',
  name: 'Dr. Eleanor Vance',
  designation: 'Lead STEM Professor & Head of Physics',
  department: 'Sciences & Advanced Robotics',
  campus: 'Main Science Campus, Lahore',
  qualification: 'Ph.D. in Applied Physics (MIT / LUMS Fellow)',
  tenureYears: 6.5,
  email: 'e.vance@csgacademy.edu.pk',
  phone: '+92 300 5551289',
  status: 'Active',
  performanceRating: 4.88,
  teachingHoursPerWeek: 22,
  cogniaAccreditationCertified: true,
  speedGraderPending: 14,
  speedGraderGradedMonth: 128,
  speedGraderTurnaroundHours: 18.4,
  classes: [
    { id: 'CLS-11A-PHY', name: 'AP Physics C: Mechanics', section: 'Grade 11-A', subject: 'Physics', studentCount: 28, avgGpa: 3.54, syllabusProgress: 68, upcomingAssessment: 'Rotational Dynamics Midterm (Sept 24)' },
    { id: 'CLS-12B-PHY', name: 'Quantum & Wave Mechanics', section: 'Grade 12-B', subject: 'Physics', studentCount: 24, avgGpa: 3.72, syllabusProgress: 75, upcomingAssessment: 'Photoelectric Effect Lab Viva (Sept 21)' },
    { id: 'CLS-10A-ROB', name: 'Introduction to Autonomous Robotics', section: 'Grade 10-A', subject: 'Robotics', studentCount: 30, avgGpa: 3.85, syllabusProgress: 80, upcomingAssessment: 'Microcontroller PID Capstone (Sept 30)' },
  ],
  timetable: [
    { day: 'Mon', period: 1, time: '08:00 - 08:50', subject: 'AP Physics C', classSection: '11-A', room: 'Physics Lab 01' },
    { day: 'Mon', period: 3, time: '09:50 - 10:40', subject: 'Quantum Physics', classSection: '12-B', room: 'Lecture Hall B' },
    { day: 'Tue', period: 2, time: '08:55 - 09:45', subject: 'Autonomous Robotics', classSection: '10-A', room: 'Robotics Studio' },
    { day: 'Tue', period: 4, time: '10:45 - 11:35', subject: 'AP Physics C', classSection: '11-A', room: 'Physics Lab 01' },
    { day: 'Wed', period: 1, time: '08:00 - 08:50', subject: 'Quantum Physics', classSection: '12-B', room: 'Lecture Hall B' },
    { day: 'Wed', period: 5, time: '11:40 - 12:30', subject: 'Autonomous Robotics', classSection: '10-A', room: 'Robotics Studio' },
    { day: 'Thu', period: 2, time: '08:55 - 09:45', subject: 'AP Physics C', classSection: '11-A', room: 'Physics Lab 01' },
    { day: 'Fri', period: 1, time: '08:00 - 08:50', subject: 'Faculty Research & Office Hours', classSection: 'All', room: 'Department Office' },
  ],
  compensation: {
    basicPKR: 350000,
    housingAllowancePKR: 70000,
    medicalAllowancePKR: 35000,
    specialDutyAllowancePKR: 45000,
    taxDeductionPKR: 52000,
    providentFundPKR: 29000,
    netSalaryPKR: 419000,
    bankIban: 'PK82HABB0001234567890123',
    bankName: 'Habib Bank Limited (HBL) Executive Account',
    recentPayslips: [
      { slipNo: 'SLIP-202609-084', month: 'September 2026', netAmount: 419000, status: 'PROCESSING' },
      { slipNo: 'SLIP-202608-084', month: 'August 2026', netAmount: 419000, status: 'PAID' },
      { slipNo: 'SLIP-202607-084', month: 'July 2026', netAmount: 419000, status: 'PAID' },
    ],
  },
  kpiRadar: {
    cogniaStandardFidelity: 96,
    studentGrowthPercentile: 92,
    peerReviewScore: 94,
    punctualityScore: 98,
    lmsEngagement: 95,
  },
}

export const Teacher360Drawer: React.FC<Teacher360DrawerProps> = ({
  isOpen,
  onClose,
  teacher = DEFAULT_TEACHER_PROFILE,
  onAssignCoursework,
}) => {
  const profile = teacher || DEFAULT_TEACHER_PROFILE
  const [activeTab, setActiveTab] = useState<string>('overview')

  // Modals
  const [isPayslipModalOpen, setIsPayslipModalOpen] = useState<boolean>(false)
  const [isAssignModalOpen, setIsAssignModalOpen] = useState<boolean>(false)

  // Assign form
  const [assignClass, setAssignClass] = useState<string>(profile.classes[0]?.id || '')
  const [assignTitle, setAssignTitle] = useState<string>('')
  const [assignDueDate, setAssignDueDate] = useState<string>('2026-09-28')
  const [assignMaxScore, setAssignMaxScore] = useState<number>(100)

  const tabs: Entity360Tab[] = [
    { id: 'overview', label: 'Overview', icon: <Sparkles className="h-3.5 w-3.5" /> },
    { id: 'timetable', label: 'Weekly Timetable Schedule', icon: <CalendarDays className="h-3.5 w-3.5" />, count: `${profile.teachingHoursPerWeek} hrs` },
    { id: 'classes', label: 'Assigned Classes & Subjects', icon: <BookOpen className="h-3.5 w-3.5" />, count: profile.classes.length },
    { id: 'speedgrader', label: 'SpeedGrader Workload', icon: <Award className="h-3.5 w-3.5" />, count: `${profile.speedGraderPending} pending` },
    { id: 'payroll', label: 'Payroll & Compensation', icon: <DollarSign className="h-3.5 w-3.5" /> },
    { id: 'performance', label: 'Performance Radar', icon: <TrendingUp className="h-3.5 w-3.5" />, count: `${profile.performanceRating}/5.0` },
  ]

  const badges: Entity360Badge[] = [
    { label: profile.status, variant: profile.status === 'Active' ? 'success' : 'warning' },
    { label: profile.department, variant: 'purple' },
    { label: `Rating: ${profile.performanceRating} ★`, variant: 'amber' },
  ]

  const quickActions: Entity360QuickAction[] = [
    {
      label: 'View Schedule',
      icon: <Calendar className="h-3.5 w-3.5" />,
      onClick: () => setActiveTab('timetable'),
      variant: 'outline',
    },
    {
      label: 'Download Payslip',
      icon: <Download className="h-3.5 w-3.5" />,
      onClick: () => setIsPayslipModalOpen(true),
      variant: 'default',
    },
    {
      label: 'Assign Coursework',
      icon: <Send className="h-3.5 w-3.5" />,
      onClick: () => setIsAssignModalOpen(true),
      variant: 'primary',
    },
  ]

  const handleAssignSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!assignTitle.trim()) {
      toast.error('Assignment title is required')
      return
    }
    if (onAssignCoursework) {
      onAssignCoursework(profile.id, {
        classId: assignClass,
        title: assignTitle,
        dueDate: assignDueDate,
        maxScore: assignMaxScore,
      })
    }
    toast.success(`Coursework "${assignTitle}" dispatched to students!`)
    setIsAssignModalOpen(false)
    setAssignTitle('')
  }

  return (
    <>
      <Entity360Drawer
        isOpen={isOpen}
        onClose={onClose}
        title={profile.name}
        subtitle={`${profile.designation} • ${profile.campus}`}
        entityTypeBadge="Faculty 360°"
        avatar={{
          initials: profile.name.replace('Dr. ', '').replace('Prof. ', '').slice(0, 2).toUpperCase(),
          statusDot: 'online',
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
              <Award className="h-4 w-4 text-amber-500 shrink-0" />
              <div>
                <p className="text-[10px] text-zinc-400 font-medium">Evaluation Score</p>
                <p className="font-bold text-zinc-900 dark:text-zinc-100">{profile.performanceRating} / 5.0</p>
              </div>
            </div>
            <div className="flex items-center gap-2 p-2 rounded-lg bg-zinc-100/80 dark:bg-zinc-800/60 border border-zinc-200/50 dark:border-zinc-700/50">
              <Clock className="h-4 w-4 text-indigo-500 shrink-0" />
              <div>
                <p className="text-[10px] text-zinc-400 font-medium">Teaching Load</p>
                <p className="font-bold text-indigo-600 dark:text-indigo-400">{profile.teachingHoursPerWeek} hrs / week</p>
              </div>
            </div>
            <div className="flex items-center gap-2 p-2 rounded-lg bg-zinc-100/80 dark:bg-zinc-800/60 border border-zinc-200/50 dark:border-zinc-700/50">
              <Sparkles className="h-4 w-4 text-emerald-500 shrink-0" />
              <div>
                <p className="text-[10px] text-zinc-400 font-medium">SpeedGrader SLA</p>
                <p className="font-bold text-emerald-600 dark:text-emerald-400">{profile.speedGraderTurnaroundHours}h avg turnaround</p>
              </div>
            </div>
            <div className="flex items-center gap-2 p-2 rounded-lg bg-zinc-100/80 dark:bg-zinc-800/60 border border-zinc-200/50 dark:border-zinc-700/50">
              <ShieldCheck className="h-4 w-4 text-purple-500 shrink-0" />
              <div>
                <p className="text-[10px] text-zinc-400 font-medium">Cognia STEM Master</p>
                <p className="font-bold text-purple-600 dark:text-purple-400">Certified Lead</p>
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
                <Users className="h-4 w-4 text-emerald-500" />
                Faculty Employment & Academic Credentials
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
                <div>
                  <span className="text-zinc-400">Faculty Member</span>
                  <p className="font-semibold text-zinc-900 dark:text-zinc-100 mt-0.5">{profile.name}</p>
                </div>
                <div>
                  <span className="text-zinc-400">Employee ID</span>
                  <p className="font-semibold text-zinc-900 dark:text-zinc-100 mt-0.5 font-mono">{profile.employeeId}</p>
                </div>
                <div>
                  <span className="text-zinc-400">Department</span>
                  <p className="font-semibold text-zinc-900 dark:text-zinc-100 mt-0.5">{profile.department}</p>
                </div>
                <div>
                  <span className="text-zinc-400">Highest Qualification</span>
                  <p className="font-semibold text-zinc-900 dark:text-zinc-100 mt-0.5">{profile.qualification}</p>
                </div>
                <div>
                  <span className="text-zinc-400">Tenure at CSG</span>
                  <p className="font-semibold text-zinc-900 dark:text-zinc-100 mt-0.5">{profile.tenureYears} Years</p>
                </div>
                <div>
                  <span className="text-zinc-400">Institutional Email</span>
                  <p className="font-semibold text-zinc-900 dark:text-zinc-100 mt-0.5">{profile.email}</p>
                </div>
              </div>
            </div>

            {/* Teaching Load Overview */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="p-4 rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
                <span className="text-xs text-zinc-400">Active Classes</span>
                <p className="text-2xl font-black text-zinc-900 dark:text-zinc-100 mt-1">{profile.classes.length} Cohorts</p>
                <p className="text-[11px] text-zinc-500 mt-0.5">82 Total Enrolled Students</p>
              </div>
              <div className="p-4 rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
                <span className="text-xs text-zinc-400">Submissions Graded This Month</span>
                <p className="text-2xl font-black text-emerald-600 dark:text-emerald-400 mt-1">{profile.speedGraderGradedMonth}</p>
                <p className="text-[11px] text-zinc-500 mt-0.5">99.2% on-time grading rate</p>
              </div>
              <div className="p-4 rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
                <span className="text-xs text-zinc-400">Cognia Rubric Fidelity</span>
                <p className="text-2xl font-black text-indigo-600 dark:text-indigo-400 mt-1">{profile.kpiRadar.cogniaStandardFidelity}%</p>
                <p className="text-[11px] text-zinc-500 mt-0.5">Full standard compliance</p>
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: WEEKLY TIMETABLE SCHEDULE */}
        {activeTab === 'timetable' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-zinc-900 dark:text-zinc-100">Weekly Master Timetable</h3>
                <p className="text-xs text-zinc-500">Period schedule across science laboratories and lecture halls</p>
              </div>
              <button
                type="button"
                onClick={() => toast.success('Timetable exported to iCal / Google Calendar format')}
                className="px-3 py-1.5 text-xs font-semibold rounded-lg bg-zinc-100 hover:bg-zinc-200 dark:bg-zinc-800 dark:hover:bg-zinc-700 text-zinc-800 dark:text-zinc-200 flex items-center gap-1.5 cursor-pointer"
              >
                <Download className="h-3.5 w-3.5" />
                Export iCal Sync
              </button>
            </div>

            <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-zinc-50/80 dark:bg-zinc-800/50 text-zinc-400 uppercase font-semibold border-b border-zinc-200 dark:border-zinc-800">
                  <tr>
                    <th className="py-2.5 px-4">Day</th>
                    <th className="py-2.5 px-4">Time Slot</th>
                    <th className="py-2.5 px-4">Subject</th>
                    <th className="py-2.5 px-4">Class & Section</th>
                    <th className="py-2.5 px-4">Facility / Room</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800">
                  {profile.timetable.map((slot, idx) => (
                    <tr key={idx} className="hover:bg-zinc-50/50 dark:hover:bg-zinc-800/30">
                      <td className="py-3 px-4 font-bold text-indigo-600 dark:text-indigo-400">{slot.day} (P{slot.period})</td>
                      <td className="py-3 px-4 font-mono text-zinc-500">{slot.time}</td>
                      <td className="py-3 px-4 font-semibold text-zinc-900 dark:text-zinc-100">{slot.subject}</td>
                      <td className="py-3 px-4"><span className="px-2 py-0.5 rounded bg-zinc-100 dark:bg-zinc-800 font-medium">{slot.classSection}</span></td>
                      <td className="py-3 px-4 text-zinc-500">{slot.room}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* TAB 3: ASSIGNED CLASSES */}
        {activeTab === 'classes' && (
          <div className="space-y-4">
            <h3 className="text-sm font-bold text-zinc-900 dark:text-zinc-100">Assigned Cohorts & Syllabus Progress</h3>
            <div className="grid grid-cols-1 gap-4">
              {profile.classes.map((c) => (
                <div key={c.id} className="p-4 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 space-y-3">
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-indigo-100 text-indigo-800 dark:bg-indigo-950 dark:text-indigo-300">
                          {c.section}
                        </span>
                        <h4 className="text-sm font-bold text-zinc-900 dark:text-zinc-100">{c.name}</h4>
                      </div>
                      <p className="text-xs text-zinc-500 mt-0.5">{c.studentCount} Active Students • Class Avg GPA: <strong>{c.avgGpa.toFixed(2)}</strong></p>
                    </div>
                    <span className="text-xs font-bold text-emerald-600 dark:text-emerald-400">{c.syllabusProgress}% Complete</span>
                  </div>

                  <div>
                    <div className="w-full bg-zinc-100 dark:bg-zinc-800 rounded-full h-2 overflow-hidden">
                      <div className="bg-indigo-600 h-2 rounded-full" style={{ width: `${c.syllabusProgress}%` }} />
                    </div>
                  </div>

                  <div className="pt-2 border-t border-zinc-100 dark:border-zinc-800 flex items-center justify-between text-xs text-zinc-500">
                    <span>Upcoming: <strong className="text-zinc-800 dark:text-zinc-200">{c.upcomingAssessment}</strong></span>
                    <button
                      type="button"
                      onClick={() => {
                        setAssignClass(c.id)
                        setIsAssignModalOpen(true)
                      }}
                      className="text-indigo-600 dark:text-indigo-400 font-semibold hover:underline"
                    >
                      Assign Task +
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* TAB 4: SPEEDGRADER WORKLOAD */}
        {activeTab === 'speedgrader' && (
          <div className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="p-4 rounded-xl border border-amber-200 dark:border-amber-900/60 bg-amber-50/50 dark:bg-amber-950/30">
                <span className="text-xs text-amber-700 dark:text-amber-400 font-medium">Pending SpeedGrader Queue</span>
                <p className="text-2xl font-black text-amber-700 dark:text-amber-300 mt-1">{profile.speedGraderPending} submissions</p>
                <p className="text-[11px] text-amber-600 dark:text-amber-500 mt-0.5">Across 2 active assignments</p>
              </div>
              <div className="p-4 rounded-xl border border-emerald-200 dark:border-emerald-900/60 bg-emerald-50/50 dark:bg-emerald-950/30">
                <span className="text-xs text-emerald-700 dark:text-emerald-400 font-medium">Graded This Month</span>
                <p className="text-2xl font-black text-emerald-700 dark:text-emerald-300 mt-1">{profile.speedGraderGradedMonth}</p>
                <p className="text-[11px] text-emerald-600 dark:text-emerald-500 mt-0.5">Avg turnaround: {profile.speedGraderTurnaroundHours} hours</p>
              </div>
              <div className="p-4 rounded-xl border border-indigo-200 dark:border-indigo-900/60 bg-indigo-50/50 dark:bg-indigo-950/30">
                <span className="text-xs text-indigo-700 dark:text-indigo-400 font-medium">Rubric Auto-Check</span>
                <p className="text-2xl font-black text-indigo-700 dark:text-indigo-300 mt-1">100%</p>
                <p className="text-[11px] text-indigo-600 dark:text-indigo-500 mt-0.5">Zero unanchored feedback</p>
              </div>
            </div>

            <div className="p-5 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 text-center space-y-3">
              <Award className="h-8 w-8 text-indigo-500 mx-auto" />
              <h4 className="text-sm font-bold text-zinc-900 dark:text-zinc-100">Launch Integrated SpeedGrader Studio</h4>
              <p className="text-xs text-zinc-500 max-w-md mx-auto">
                Evaluate student submissions with split-screen code & PDF review, AI rubric suggestions, and live Cognia criteria scoring.
              </p>
              <button
                type="button"
                onClick={() => toast.success('Transitioning to SpeedGrader Studio...')}
                className="px-4 py-2 text-xs font-semibold rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white shadow-xs inline-flex items-center gap-1.5"
              >
                Open SpeedGrader
              </button>
            </div>
          </div>
        )}

        {/* TAB 5: PAYROLL & COMPENSATION */}
        {activeTab === 'payroll' && (
          <div className="space-y-4">
            <div className="p-4 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 flex items-center justify-between flex-wrap gap-3">
              <div>
                <p className="text-xs text-zinc-400 font-medium">Net Monthly Compensation</p>
                <p className="text-2xl font-black text-emerald-600 dark:text-emerald-400">PKR {profile.compensation.netSalaryPKR.toLocaleString()}</p>
                <p className="text-[11px] text-zinc-500 mt-0.5">{profile.compensation.bankName} • IBAN: {profile.compensation.bankIban}</p>
              </div>
              <button
                type="button"
                onClick={() => setIsPayslipModalOpen(true)}
                className="px-3 py-1.5 text-xs font-semibold rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 flex items-center gap-1.5"
              >
                <Download className="h-3.5 w-3.5" />
                View Official Slip
              </button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
              <div className="p-4 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 space-y-2">
                <h4 className="font-bold text-zinc-900 dark:text-zinc-100 uppercase tracking-wider text-[11px] text-emerald-600">Earnings & Allowances</h4>
                <div className="flex justify-between text-zinc-600 dark:text-zinc-300">
                  <span>Basic Pay</span>
                  <span className="font-semibold">PKR {profile.compensation.basicPKR.toLocaleString()}</span>
                </div>
                <div className="flex justify-between text-zinc-600 dark:text-zinc-300">
                  <span>House Rent Allowance</span>
                  <span className="font-semibold">PKR {profile.compensation.housingAllowancePKR.toLocaleString()}</span>
                </div>
                <div className="flex justify-between text-zinc-600 dark:text-zinc-300">
                  <span>Medical Allowance</span>
                  <span className="font-semibold">PKR {profile.compensation.medicalAllowancePKR.toLocaleString()}</span>
                </div>
                <div className="flex justify-between text-zinc-600 dark:text-zinc-300">
                  <span>Special Duty Allowance</span>
                  <span className="font-semibold">PKR {profile.compensation.specialDutyAllowancePKR.toLocaleString()}</span>
                </div>
              </div>

              <div className="p-4 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 space-y-2">
                <h4 className="font-bold text-zinc-900 dark:text-zinc-100 uppercase tracking-wider text-[11px] text-rose-600">Statutory Deductions</h4>
                <div className="flex justify-between text-zinc-600 dark:text-zinc-300">
                  <span>Income Tax Withholding</span>
                  <span className="font-semibold text-rose-600">- PKR {profile.compensation.taxDeductionPKR.toLocaleString()}</span>
                </div>
                <div className="flex justify-between text-zinc-600 dark:text-zinc-300">
                  <span>Provident Fund (Retirement)</span>
                  <span className="font-semibold text-rose-600">- PKR {profile.compensation.providentFundPKR.toLocaleString()}</span>
                </div>
                <div className="flex justify-between font-bold pt-2 border-t border-zinc-200 dark:border-zinc-800">
                  <span>Total Deductions</span>
                  <span className="text-rose-600">- PKR {(profile.compensation.taxDeductionPKR + profile.compensation.providentFundPKR).toLocaleString()}</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 6: PERFORMANCE RADAR */}
        {activeTab === 'performance' && (
          <div className="space-y-4">
            <h3 className="text-sm font-bold text-zinc-900 dark:text-zinc-100">Cognia & Leadership Evaluation Radar</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="p-4 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 space-y-3">
                <div className="flex justify-between text-xs">
                  <span className="font-medium text-zinc-700 dark:text-zinc-300">Cognia Standard Fidelity</span>
                  <span className="font-bold text-indigo-600">{profile.kpiRadar.cogniaStandardFidelity}%</span>
                </div>
                <div className="w-full bg-zinc-100 dark:bg-zinc-800 rounded-full h-2 overflow-hidden">
                  <div className="bg-indigo-600 h-2 rounded-full" style={{ width: `${profile.kpiRadar.cogniaStandardFidelity}%` }} />
                </div>

                <div className="flex justify-between text-xs pt-1">
                  <span className="font-medium text-zinc-700 dark:text-zinc-300">Student Growth Percentile (SGP)</span>
                  <span className="font-bold text-emerald-600">{profile.kpiRadar.studentGrowthPercentile}%</span>
                </div>
                <div className="w-full bg-zinc-100 dark:bg-zinc-800 rounded-full h-2 overflow-hidden">
                  <div className="bg-emerald-600 h-2 rounded-full" style={{ width: `${profile.kpiRadar.studentGrowthPercentile}%` }} />
                </div>

                <div className="flex justify-between text-xs pt-1">
                  <span className="font-medium text-zinc-700 dark:text-zinc-300">Peer & HOD Review</span>
                  <span className="font-bold text-purple-600">{profile.kpiRadar.peerReviewScore}%</span>
                </div>
                <div className="w-full bg-zinc-100 dark:bg-zinc-800 rounded-full h-2 overflow-hidden">
                  <div className="bg-purple-600 h-2 rounded-full" style={{ width: `${profile.kpiRadar.peerReviewScore}%` }} />
                </div>
              </div>

              <div className="p-4 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 space-y-2 text-xs">
                <h4 className="font-bold text-zinc-900 dark:text-zinc-100">Annual Appraisal Remarks</h4>
                <p className="text-zinc-600 dark:text-zinc-300 italic">
                  "Dr. Vance exhibits stellar instructional mastery in physics and robotics. The AP cohort achieves consistent top-percentile scores in both national Olympiads and Cognia STEM audits."
                </p>
                <p className="text-zinc-400 text-[10px] pt-2">- Academic Director & Head of Faculty Appraisal</p>
              </div>
            </div>
          </div>
        )}
      </Entity360Drawer>

      {/* MODAL 1: PAYSLIP PREVIEW */}
      <Dialog open={isPayslipModalOpen} onOpenChange={setIsPayslipModalOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Official Faculty Salary Slip</DialogTitle>
            <DialogDescription>CSG Educational Foundation - September 2026</DialogDescription>
          </DialogHeader>
          <div className="p-4 bg-zinc-50 dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800 space-y-3 text-xs">
            <div className="flex justify-between items-center pb-2 border-b border-zinc-200 dark:border-zinc-800">
              <div>
                <p className="font-bold text-zinc-900 dark:text-zinc-100">{profile.name}</p>
                <p className="text-[11px] text-zinc-400 font-mono">{profile.employeeId} • {profile.designation}</p>
              </div>
              <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-800">APPROVED</span>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1">
                <p className="font-semibold text-zinc-700 dark:text-zinc-300">Gross Earnings</p>
                <p className="font-bold text-zinc-900 dark:text-zinc-100">
                  PKR {(profile.compensation.basicPKR + profile.compensation.housingAllowancePKR + profile.compensation.medicalAllowancePKR + profile.compensation.specialDutyAllowancePKR).toLocaleString()}
                </p>
              </div>
              <div className="space-y-1">
                <p className="font-semibold text-zinc-700 dark:text-zinc-300">Net Take-Home</p>
                <p className="font-bold text-emerald-600 text-base">
                  PKR {profile.compensation.netSalaryPKR.toLocaleString()}
                </p>
              </div>
            </div>
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={() => {
                toast.success('Payslip PDF downloaded')
                setIsPayslipModalOpen(false)
              }}
              className="px-4 py-2 text-xs font-semibold rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white flex items-center gap-1.5"
            >
              <Download className="h-3.5 w-3.5" />
              Download Official PDF
            </button>
          </div>
        </DialogContent>
      </Dialog>

      {/* MODAL 2: ASSIGN COURSEWORK */}
      <Dialog open={isAssignModalOpen} onOpenChange={setIsAssignModalOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Assign Coursework / Task</DialogTitle>
            <DialogDescription>Dispatch learning assignment to class cohort</DialogDescription>
          </DialogHeader>
          <form onSubmit={handleAssignSubmit} className="space-y-4 text-xs">
            <div>
              <label className="block font-medium text-zinc-700 dark:text-zinc-300 mb-1">Target Class Cohort</label>
              <select
                value={assignClass}
                onChange={(e) => setAssignClass(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 font-semibold"
              >
                {profile.classes.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.section} - {c.name} ({c.studentCount} students)
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block font-medium text-zinc-700 dark:text-zinc-300 mb-1">Assignment Title</label>
              <input
                type="text"
                value={assignTitle}
                onChange={(e) => setAssignTitle(e.target.value)}
                placeholder="e.g. Rotational Kinematics Problem Set 4"
                className="w-full px-3 py-2 rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900"
                required
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block font-medium text-zinc-700 dark:text-zinc-300 mb-1">Due Date</label>
                <input
                  type="date"
                  value={assignDueDate}
                  onChange={(e) => setAssignDueDate(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900"
                />
              </div>
              <div>
                <label className="block font-medium text-zinc-700 dark:text-zinc-300 mb-1">Max Score</label>
                <input
                  type="number"
                  value={assignMaxScore}
                  onChange={(e) => setAssignMaxScore(Number(e.target.value))}
                  className="w-full px-3 py-2 rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900"
                />
              </div>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setIsAssignModalOpen(false)}
                className="px-3 py-2 text-xs font-semibold rounded-lg border border-zinc-300 dark:border-zinc-700"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-4 py-2 text-xs font-semibold rounded-lg bg-indigo-600 text-white hover:bg-indigo-700"
              >
                Dispatch Assignment
              </button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </>
  )
}
