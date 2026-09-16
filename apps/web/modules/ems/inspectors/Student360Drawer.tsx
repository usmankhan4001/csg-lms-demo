'use client'

import React, { useState } from 'react'
import {
  GraduationCap,
  BookOpen,
  CalendarCheck2,
  DollarSign,
  HeartHandshake,
  Bot,
  Users,
  Printer,
  FileCheck,
  CreditCard,
  ShieldAlert,
  Sparkles,
  Award,
  AlertTriangle,
  CheckCircle2,
  Clock,
  MapPin,
  Phone,
  Mail,
  Shield,
  FileText,
  TrendingUp,
  TrendingDown,
  ChevronRight,
  ExternalLink,
  Lock,
  UserCheck,
  Building2,
  QrCode,
  Send,
  X,
  AlertCircle,
  Percent,
} from 'lucide-react'
import { Entity360Drawer, Entity360Tab, Entity360Badge, Entity360QuickAction } from '@/components/ems/Entity360Drawer'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog'
import toast from 'react-hot-toast'
import { clsx, type ClassValue } from 'clsx'

function cn(...inputs: ClassValue[]) {
  return clsx(inputs)
}

export interface StudentCourseGrade {
  code: string
  name: string
  teacher: string
  credits: number
  letterGrade: string
  scorePercent: number
  cogniaStandard: string
  recentAssessment: string
  recentScore: string
  status: 'Mastery' | 'Proficient' | 'Developing' | 'Needs Support'
}

export interface StudentAttendanceDay {
  date: string
  dayOfWeek: string
  status: 'PRESENT' | 'LATE' | 'ABSENT' | 'EXCUSED'
  checkInTime: string
  checkOutTime: string
  gate: string
  notes?: string
}

export interface StudentFeeEntry {
  voucherNo: string
  month: string
  dueDate: string
  amountDue: number
  amountPaid: number
  status: 'PAID' | 'PARTIAL' | 'UNPAID' | 'OVERDUE'
  paymentMethod?: string
  paidDate?: string
  transactionRef?: string
}

export interface StudentPastoralNote {
  id: string
  type: 'MERIT' | 'DEMERIT' | 'COUNSELING' | 'WELLBEING'
  title: string
  description: string
  date: string
  recordedBy: string
  points?: number
  isConfidential?: boolean
  status: 'RESOLVED' | 'FOLLOW_UP_REQUIRED' | 'ACTIVE'
}

export interface StudentSocraticSession {
  id: string
  conceptTitle: string
  subject: string
  struggleRate: number
  hintsConsumed: number
  bloomLevel: 'Remember' | 'Understand' | 'Apply' | 'Analyze' | 'Evaluate'
  outcome: 'Mastered' | 'Assisted' | 'Struggling'
  durationMins: number
  timestamp: string
}

export interface StudentGuardianInfo {
  relationship: string
  name: string
  phone: string
  email: string
  cnic: string
  occupation: string
  employer: string
  isPrimary: boolean
  pickupAuthorized: boolean
}

export interface Student360Profile {
  id: string
  rollNo: string
  name: string
  avatarUrl?: string
  grade: string
  section: string
  campus: string
  house?: string
  academicYear: string
  advisor: string
  dob: string
  gender: string
  bloodGroup: string
  cnicBForm: string
  enrollmentDate: string
  status: 'Active' | 'At Risk' | 'Probation' | 'Graduated'
  gpa: number
  gpaTrend: 'up' | 'down' | 'steady'
  attendanceRate: number
  outstandingBalancePKR: number
  socraticUrgencyScore: number
  aiTutoringBlocked?: boolean
  medicalAlerts?: string[]
  specialAccommodations?: string[]
  courses: StudentCourseGrade[]
  attendanceHistory: StudentAttendanceDay[]
  feeLedger: StudentFeeEntry[]
  pastoralRecords: StudentPastoralNote[]
  socraticSessions: StudentSocraticSession[]
  guardians: StudentGuardianInfo[]
}

export interface Student360DrawerProps {
  isOpen: boolean
  onClose: () => void
  student?: Student360Profile | null
  onRecordPayment?: (studentId: string, amount: number) => void
  onIssuePastoralNote?: (studentId: string, note: Partial<StudentPastoralNote>) => void
}

const DEFAULT_STUDENT_PROFILE: Student360Profile = {
  id: 'STU-2026-1042',
  rollNo: '2026-CS-1042',
  name: 'Aiden Vance',
  grade: 'Grade 11',
  section: 'Section 11-A',
  campus: 'Main Science Campus, Lahore',
  house: 'Newton Blue Phoenix',
  academicYear: '2026-2027',
  advisor: 'Dr. Eleanor Vance (STEM Lead)',
  dob: '2009-04-14',
  gender: 'Male',
  bloodGroup: 'O+ Positive',
  cnicBForm: '35202-9847123-1',
  enrollmentDate: '2022-08-15',
  status: 'At Risk',
  gpa: 3.42,
  gpaTrend: 'down',
  attendanceRate: 88.5,
  outstandingBalancePKR: 45000,
  socraticUrgencyScore: 84,
  aiTutoringBlocked: false,
  medicalAlerts: ['Asthma Inhaler in Bag', 'Mild Peanut Allergy'],
  specialAccommodations: ['Extra 15 mins on timed math tests'],
  courses: [
    {
      code: 'PHY-401',
      name: 'AP Physics C: Mechanics & Dynamics',
      teacher: 'Dr. Eleanor Vance',
      credits: 4,
      letterGrade: 'B+',
      scorePercent: 82.4,
      cogniaStandard: 'STEM.SC.04 (Empirical Inquiry & Modelling)',
      recentAssessment: 'Rotational Torque Exam',
      recentScore: '38/50 (76%)',
      status: 'Developing',
    },
    {
      code: 'MTH-402',
      name: 'Pure Mathematics & Calculus II',
      teacher: 'Prof. Tariq Mahmood',
      credits: 4,
      letterGrade: 'A-',
      scorePercent: 88.0,
      cogniaStandard: 'STEM.MA.02 (Calculus & Analytic Reasoning)',
      recentAssessment: 'Definite Integrals Quiz',
      recentScore: '27/30 (90%)',
      status: 'Proficient',
    },
    {
      code: 'CHM-401',
      name: 'Advanced Organic Chemistry',
      teacher: 'Dr. Sarah Jenkins',
      credits: 4,
      letterGrade: 'A',
      scorePercent: 93.5,
      cogniaStandard: 'STEM.SC.02 (Molecular Synthesis)',
      recentAssessment: 'Stereochemistry Lab Practical',
      recentScore: '98/100 (98%)',
      status: 'Mastery',
    },
    {
      code: 'ENG-301',
      name: 'English Literature & Rhetoric',
      teacher: 'Ms. Ayesha Khan',
      credits: 3,
      letterGrade: 'B',
      scorePercent: 79.5,
      cogniaStandard: 'HUM.LA.03 (Critical Analysis & Thesis)',
      recentAssessment: 'Comparative Essay on Hamlet',
      recentScore: '39/50 (78%)',
      status: 'Developing',
    },
    {
      code: 'CSC-405',
      name: 'Data Structures & Algorithms in Rust',
      teacher: 'Engr. Bilal Farooq',
      credits: 4,
      letterGrade: 'A+',
      scorePercent: 97.0,
      cogniaStandard: 'TECH.CS.05 (Algorithmic Complexity & Systems)',
      recentAssessment: 'Binary Tree Traversal Benchmarking',
      recentScore: '100/100 (100%)',
      status: 'Mastery',
    },
  ],
  attendanceHistory: [
    { date: '2026-09-15', dayOfWeek: 'Tuesday', status: 'PRESENT', checkInTime: '07:48 AM', checkOutTime: '02:35 PM', gate: 'Gate A (Biometric NFC)' },
    { date: '2026-09-14', dayOfWeek: 'Monday', status: 'LATE', checkInTime: '08:14 AM', checkOutTime: '02:30 PM', gate: 'Gate B (Late Desk)', notes: 'Traffic delay reported by parent' },
    { date: '2026-09-11', dayOfWeek: 'Friday', status: 'PRESENT', checkInTime: '07:50 AM', checkOutTime: '01:00 PM', gate: 'Gate A (Biometric NFC)' },
    { date: '2026-09-10', dayOfWeek: 'Thursday', status: 'EXCUSED', checkInTime: '--', checkOutTime: '--', gate: '--', notes: 'Medical leave certificate submitted' },
    { date: '2026-09-09', dayOfWeek: 'Wednesday', status: 'PRESENT', checkInTime: '07:44 AM', checkOutTime: '02:30 PM', gate: 'Gate A (Biometric NFC)' },
    { date: '2026-09-08', dayOfWeek: 'Tuesday', status: 'ABSENT', checkInTime: '--', checkOutTime: '--', gate: '--', notes: 'Unexcused absence - SMS dispatched to guardian' },
  ],
  feeLedger: [
    { voucherNo: 'VOUCH-202609-0842', month: 'September 2026', dueDate: '2026-09-10', amountDue: 45000, amountPaid: 0, status: 'OVERDUE' },
    { voucherNo: 'VOUCH-202608-0842', month: 'August 2026', dueDate: '2026-08-10', amountDue: 45000, amountPaid: 45000, status: 'PAID', paymentMethod: '1Link Digital Portal', paidDate: '2026-08-08', transactionRef: 'TXN-1LINK-94817203' },
    { voucherNo: 'VOUCH-202607-0842', month: 'July 2026', dueDate: '2026-07-10', amountDue: 45000, amountPaid: 45000, status: 'PAID', paymentMethod: 'HBL Bank Deposit Slip', paidDate: '2026-07-09', transactionRef: 'DEP-HBL-330198' },
  ],
  pastoralRecords: [
    { id: 'PAS-01', type: 'MERIT', title: '1st Place in Regional STEM Hackathon', description: 'Engineered an autonomous solar-powered rover firmware.', date: '2026-09-02', recordedBy: 'Engr. Bilal Farooq', points: 15, status: 'RESOLVED' },
    { id: 'PAS-02', type: 'COUNSELING', title: 'Cognitive Load & Homework Anxiety Followup', description: 'Student expressed difficulty managing AP Physics homework pace. Suggested peer tutoring.', date: '2026-08-28', recordedBy: 'Ms. Sarah Malik (Lead Counselor)', isConfidential: true, status: 'FOLLOW_UP_REQUIRED' },
    { id: 'PAS-03', type: 'DEMERIT', title: 'Late Arrival without Slip', description: 'Arrived 25 minutes after homeroom bell without parent sign-in.', date: '2026-08-18', recordedBy: 'Prefect Council', points: -2, status: 'RESOLVED' },
  ],
  socraticSessions: [
    { id: 'SOC-902', conceptTitle: 'Rotational Dynamics & Torque Vectors', subject: 'Physics', struggleRate: 78, hintsConsumed: 4, bloomLevel: 'Analyze', outcome: 'Struggling', durationMins: 32, timestamp: '2026-09-15 11:20' },
    { id: 'SOC-899', conceptTitle: 'Integration by Substitution & Parts', subject: 'Mathematics', struggleRate: 45, hintsConsumed: 2, bloomLevel: 'Apply', outcome: 'Assisted', durationMins: 24, timestamp: '2026-09-14 16:40' },
    { id: 'SOC-882', conceptTitle: 'Markov Chains & State Transitions', subject: 'Computer Science', struggleRate: 15, hintsConsumed: 0, bloomLevel: 'Evaluate', outcome: 'Mastered', durationMins: 18, timestamp: '2026-09-12 14:10' },
  ],
  guardians: [
    {
      relationship: 'Father (Primary Guardian)',
      name: 'Muhammad Vance',
      phone: '+92 300 8472910',
      email: 'm.vance@techventures.pk',
      cnic: '35202-1849201-3',
      occupation: 'Chief Technology Officer',
      employer: 'Cybernetics Labs Pvt Ltd',
      isPrimary: true,
      pickupAuthorized: true,
    },
    {
      relationship: 'Mother',
      name: 'Dr. Zainab Vance',
      phone: '+92 321 9840192',
      email: 'zainab.vance@shaukatkhanum.org.pk',
      cnic: '35202-5401928-2',
      occupation: 'Consultant Radiologist',
      employer: 'SKMCH&RC',
      isPrimary: false,
      pickupAuthorized: true,
    },
  ],
}

export const Student360Drawer: React.FC<Student360DrawerProps> = ({
  isOpen,
  onClose,
  student = DEFAULT_STUDENT_PROFILE,
  onRecordPayment,
  onIssuePastoralNote,
}) => {
  const profile = student || DEFAULT_STUDENT_PROFILE
  const [activeTab, setActiveTab] = useState<string>('overview')

  // Modals state
  const [isIdCardModalOpen, setIsIdCardModalOpen] = useState<boolean>(false)
  const [isTranscriptModalOpen, setIsTranscriptModalOpen] = useState<boolean>(false)
  const [isPaymentModalOpen, setIsPaymentModalOpen] = useState<boolean>(false)
  const [isPastoralModalOpen, setIsPastoralModalOpen] = useState<boolean>(false)

  // Payment form state
  const [payAmount, setPayAmount] = useState<number>(profile.outstandingBalancePKR)
  const [payMethod, setPayMethod] = useState<string>('1Link / Kuickpay')
  const [payNotes, setPayNotes] = useState<string>('')

  // Pastoral form state
  const [pastoralType, setPastoralType] = useState<'MERIT' | 'DEMERIT' | 'COUNSELING' | 'WELLBEING'>('MERIT')
  const [pastoralTitle, setPastoralTitle] = useState<string>('')
  const [pastoralDesc, setPastoralDesc] = useState<string>('')
  const [pastoralPoints, setPastoralPoints] = useState<number>(5)
  const [pastoralConfidential, setPastoralConfidential] = useState<boolean>(false)

  const tabs: Entity360Tab[] = [
    { id: 'overview', label: 'Overview', icon: <Sparkles className="h-3.5 w-3.5" /> },
    { id: 'academics', label: 'Academics & Gradebook', icon: <BookOpen className="h-3.5 w-3.5" />, count: profile.courses.length },
    { id: 'attendance', label: 'Attendance Timeline', icon: <CalendarCheck2 className="h-3.5 w-3.5" />, count: `${profile.attendanceRate}%` },
    { id: 'tuition', label: 'Tuition & Fee Ledger', icon: <DollarSign className="h-3.5 w-3.5" />, count: profile.outstandingBalancePKR > 0 ? 'Due' : 'Clear' },
    { id: 'pastoral', label: 'Pastoral & Counseling', icon: <HeartHandshake className="h-3.5 w-3.5" />, count: profile.pastoralRecords.length },
    { id: 'socratic', label: 'Socratic AI Activity', icon: <Bot className="h-3.5 w-3.5" />, count: profile.socraticSessions.length },
    { id: 'guardians', label: 'Guardians & Emergency', icon: <Users className="h-3.5 w-3.5" />, count: profile.guardians.length },
  ]

  const badges: Entity360Badge[] = [
    {
      label: profile.status,
      variant:
        profile.status === 'Active'
          ? 'success'
          : profile.status === 'At Risk'
          ? 'destructive'
          : 'warning',
    },
    { label: `${profile.grade} • ${profile.section}`, variant: 'purple' },
    { label: `GPA ${profile.gpa.toFixed(2)}`, variant: 'blue' },
  ]

  const quickActions: Entity360QuickAction[] = [
    {
      label: 'Print ID Card',
      icon: <Printer className="h-3.5 w-3.5" />,
      onClick: () => setIsIdCardModalOpen(true),
      variant: 'outline',
    },
    {
      label: 'Generate Transcript',
      icon: <FileCheck className="h-3.5 w-3.5" />,
      onClick: () => setIsTranscriptModalOpen(true),
      variant: 'default',
    },
    {
      label: 'Record Fee Payment',
      icon: <CreditCard className="h-3.5 w-3.5" />,
      onClick: () => {
        setPayAmount(profile.outstandingBalancePKR)
        setIsPaymentModalOpen(true)
      },
      variant: 'primary',
    },
    {
      label: 'Issue Pastoral Note',
      icon: <ShieldAlert className="h-3.5 w-3.5" />,
      onClick: () => setIsPastoralModalOpen(true),
      variant: 'secondary',
    },
  ]

  const handleRecordPaymentSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (payAmount <= 0) {
      toast.error('Payment amount must be greater than 0')
      return
    }
    if (onRecordPayment) {
      onRecordPayment(profile.id, payAmount)
    }
    toast.success(`Fee payment of PKR ${payAmount.toLocaleString()} recorded for ${profile.name}!`)
    setIsPaymentModalOpen(false)
  }

  const handlePastoralSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!pastoralTitle.trim()) {
      toast.error('Title is required')
      return
    }
    if (onIssuePastoralNote) {
      onIssuePastoralNote(profile.id, {
        type: pastoralType,
        title: pastoralTitle,
        description: pastoralDesc,
        points: pastoralPoints,
        isConfidential: pastoralConfidential,
        date: new Date().toISOString().split('T')[0],
      })
    }
    toast.success(`Pastoral note "${pastoralTitle}" logged for ${profile.name}!`)
    setIsPastoralModalOpen(false)
    setPastoralTitle('')
    setPastoralDesc('')
  }

  return (
    <>
      <Entity360Drawer
        isOpen={isOpen}
        onClose={onClose}
        title={profile.name}
        subtitle={`Roll # ${profile.rollNo} • ${profile.campus}`}
        entityTypeBadge="Student 360°"
        avatar={{
          initials: profile.name.slice(0, 2).toUpperCase(),
          statusDot: profile.status === 'Active' ? 'online' : 'busy',
          bgClass: 'bg-gradient-to-br from-indigo-600 to-blue-700 text-white',
        }}
        badges={badges}
        quickActions={quickActions}
        tabs={tabs}
        activeTab={activeTab}
        onTabChange={setActiveTab}
        metaBar={
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
            <div className="flex items-center gap-2 p-2 rounded-lg bg-zinc-100/80 dark:bg-zinc-800/60 border border-zinc-200/50 dark:border-zinc-700/50">
              <GraduationCap className="h-4 w-4 text-indigo-500 shrink-0" />
              <div>
                <p className="text-[10px] text-zinc-400 font-medium">Cumulative GPA</p>
                <p className="font-bold text-zinc-900 dark:text-zinc-100">{profile.gpa.toFixed(2)} / 4.0</p>
              </div>
            </div>
            <div className="flex items-center gap-2 p-2 rounded-lg bg-zinc-100/80 dark:bg-zinc-800/60 border border-zinc-200/50 dark:border-zinc-700/50">
              <CalendarCheck2 className="h-4 w-4 text-emerald-500 shrink-0" />
              <div>
                <p className="text-[10px] text-zinc-400 font-medium">Attendance Rate</p>
                <p className="font-bold text-emerald-600 dark:text-emerald-400">{profile.attendanceRate}%</p>
              </div>
            </div>
            <div className="flex items-center gap-2 p-2 rounded-lg bg-zinc-100/80 dark:bg-zinc-800/60 border border-zinc-200/50 dark:border-zinc-700/50">
              <DollarSign className="h-4 w-4 text-amber-500 shrink-0" />
              <div>
                <p className="text-[10px] text-zinc-400 font-medium">Fee Arrears</p>
                <p className="font-bold text-amber-600 dark:text-amber-400">PKR {profile.outstandingBalancePKR.toLocaleString()}</p>
              </div>
            </div>
            <div className="flex items-center gap-2 p-2 rounded-lg bg-zinc-100/80 dark:bg-zinc-800/60 border border-zinc-200/50 dark:border-zinc-700/50">
              <Bot className="h-4 w-4 text-purple-500 shrink-0" />
              <div>
                <p className="text-[10px] text-zinc-400 font-medium">Socratic Urgency</p>
                <p className="font-bold text-purple-600 dark:text-purple-400">{profile.socraticUrgencyScore} / 100</p>
              </div>
            </div>
          </div>
        }
      >
        {/* TAB 1: OVERVIEW */}
        {activeTab === 'overview' && (
          <div className="space-y-6">
            {/* Medical / Accommodations Alert Banner */}
            {profile.medicalAlerts && profile.medicalAlerts.length > 0 && (
              <div className="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-start gap-3 text-amber-800 dark:text-amber-300">
                <ShieldAlert className="h-5 w-5 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
                <div className="text-xs">
                  <p className="font-bold">Medical Alert & Accommodation Directives</p>
                  <p className="mt-0.5 opacity-90">
                    {profile.medicalAlerts.join(' • ')}
                    {profile.specialAccommodations && ` | Accommodations: ${profile.specialAccommodations.join(' • ')}`}
                  </p>
                </div>
              </div>
            )}

            {/* General Information Grid */}
            <div className="rounded-xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900 shadow-xs">
              <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-400 mb-4 flex items-center gap-2">
                <Users className="h-4 w-4 text-indigo-500" />
                Student Profile & Enrollment Demographics
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
                <div>
                  <span className="text-zinc-400">Full Name</span>
                  <p className="font-semibold text-zinc-900 dark:text-zinc-100 mt-0.5">{profile.name}</p>
                </div>
                <div>
                  <span className="text-zinc-400">Roll & Matriculation ID</span>
                  <p className="font-semibold text-zinc-900 dark:text-zinc-100 mt-0.5 font-mono">{profile.rollNo}</p>
                </div>
                <div>
                  <span className="text-zinc-400">Target Grade & Section</span>
                  <p className="font-semibold text-zinc-900 dark:text-zinc-100 mt-0.5">{profile.grade} - {profile.section}</p>
                </div>
                <div>
                  <span className="text-zinc-400">Campus Allocation</span>
                  <p className="font-semibold text-zinc-900 dark:text-zinc-100 mt-0.5">{profile.campus}</p>
                </div>
                <div>
                  <span className="text-zinc-400">Academic House</span>
                  <p className="font-semibold text-zinc-900 dark:text-zinc-100 mt-0.5">{profile.house || 'N/A'}</p>
                </div>
                <div>
                  <span className="text-zinc-400">Academic Faculty Advisor</span>
                  <p className="font-semibold text-zinc-900 dark:text-zinc-100 mt-0.5">{profile.advisor}</p>
                </div>
                <div>
                  <span className="text-zinc-400">Date of Birth & Age</span>
                  <p className="font-semibold text-zinc-900 dark:text-zinc-100 mt-0.5">{profile.dob} (17 yrs)</p>
                </div>
                <div>
                  <span className="text-zinc-400">Blood Group</span>
                  <p className="font-semibold text-zinc-900 dark:text-zinc-100 mt-0.5">{profile.bloodGroup}</p>
                </div>
                <div>
                  <span className="text-zinc-400">B-Form / CNIC</span>
                  <p className="font-semibold text-zinc-900 dark:text-zinc-100 mt-0.5 font-mono">{profile.cnicBForm}</p>
                </div>
              </div>
            </div>

            {/* Quick Status Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="p-4 rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-semibold text-zinc-600 dark:text-zinc-300">Cognia Accreditation Readiness</span>
                  <span className="text-xs font-bold text-emerald-600 dark:text-emerald-400">92% Compliance</span>
                </div>
                <div className="w-full bg-zinc-100 dark:bg-zinc-800 rounded-full h-2 overflow-hidden">
                  <div className="bg-emerald-500 h-2 rounded-full" style={{ width: '92%' }} />
                </div>
                <p className="text-[11px] text-zinc-400 mt-2">All STEM lab requirements and continuous formative assessments logged.</p>
              </div>

              <div className="p-4 rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-semibold text-zinc-600 dark:text-zinc-300">Socratic AI Mastery Index</span>
                  <span className="text-xs font-bold text-indigo-600 dark:text-indigo-400">76% Concept Health</span>
                </div>
                <div className="w-full bg-zinc-100 dark:bg-zinc-800 rounded-full h-2 overflow-hidden">
                  <div className="bg-indigo-500 h-2 rounded-full" style={{ width: '76%' }} />
                </div>
                <p className="text-[11px] text-zinc-400 mt-2">Identified 1 critical learning bottleneck in Rotational Physics.</p>
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: ACADEMICS & GRADEBOOK */}
        {activeTab === 'academics' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-zinc-900 dark:text-zinc-100">Course Roster & Gradebook Evaluation</h3>
                <p className="text-xs text-zinc-500">Live term performance cross-referenced with Cognia STEM standards</p>
              </div>
              <button
                type="button"
                onClick={() => setIsTranscriptModalOpen(true)}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-indigo-50 text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800 hover:bg-indigo-100 transition-colors"
              >
                <FileCheck className="h-3.5 w-3.5" />
                Export Official Transcript
              </button>
            </div>

            <div className="overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900">
              <table className="w-full text-left text-xs">
                <thead className="border-b border-zinc-200 bg-zinc-50/80 dark:border-zinc-800 dark:bg-zinc-800/50 text-zinc-400 uppercase font-semibold">
                  <tr>
                    <th className="py-3 px-4">Subject / Course</th>
                    <th className="py-3 px-4">Instructor</th>
                    <th className="py-3 px-4">Grade</th>
                    <th className="py-3 px-4">Score %</th>
                    <th className="py-3 px-4">Cognia Alignment</th>
                    <th className="py-3 px-4">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800">
                  {profile.courses.map((c, idx) => (
                    <tr key={idx} className="hover:bg-zinc-50/60 dark:hover:bg-zinc-800/40">
                      <td className="py-3 px-4 font-semibold text-zinc-900 dark:text-zinc-100">
                        <div className="flex items-center gap-1.5">
                          <span className="font-mono text-[10px] text-zinc-400">{c.code}</span>
                          <span>{c.name}</span>
                        </div>
                        <span className="text-[10px] text-zinc-400">Latest: {c.recentAssessment} ({c.recentScore})</span>
                      </td>
                      <td className="py-3 px-4 text-zinc-600 dark:text-zinc-300">{c.teacher}</td>
                      <td className="py-3 px-4 font-bold text-zinc-900 dark:text-zinc-100">{c.letterGrade}</td>
                      <td className="py-3 px-4 font-mono font-medium">{c.scorePercent}%</td>
                      <td className="py-3 px-4 text-[11px] text-zinc-500 max-w-[200px] truncate">{c.cogniaStandard}</td>
                      <td className="py-3 px-4">
                        <span
                          className={cn(
                            'inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold',
                            c.status === 'Mastery' && 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300',
                            c.status === 'Proficient' && 'bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300',
                            c.status === 'Developing' && 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300',
                            c.status === 'Needs Support' && 'bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300'
                          )}
                        >
                          {c.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* TAB 3: ATTENDANCE TIMELINE */}
        {activeTab === 'attendance' && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="p-3 rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900 text-center">
                <p className="text-[11px] text-zinc-400 font-medium">Term Attendance</p>
                <p className="text-xl font-black text-emerald-600 dark:text-emerald-400">{profile.attendanceRate}%</p>
              </div>
              <div className="p-3 rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900 text-center">
                <p className="text-[11px] text-zinc-400 font-medium">Present Days</p>
                <p className="text-xl font-black text-zinc-900 dark:text-zinc-100">82</p>
              </div>
              <div className="p-3 rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900 text-center">
                <p className="text-[11px] text-zinc-400 font-medium">Late Influx</p>
                <p className="text-xl font-black text-amber-600 dark:text-amber-400">4</p>
              </div>
              <div className="p-3 rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900 text-center">
                <p className="text-[11px] text-zinc-400 font-medium">Unexcused Absences</p>
                <p className="text-xl font-black text-rose-600 dark:text-rose-400">2</p>
              </div>
            </div>

            <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-4">
              <h4 className="text-xs font-bold uppercase tracking-wider text-zinc-400 mb-3">Recent Gate & RFID Swipe Log</h4>
              <div className="divide-y divide-zinc-200 dark:divide-zinc-800 text-xs">
                {profile.attendanceHistory.map((day, idx) => (
                  <div key={idx} className="py-2.5 flex items-center justify-between gap-2">
                    <div className="flex items-center gap-3">
                      <span
                        className={cn(
                          'px-2 py-0.5 rounded text-[10px] font-bold uppercase',
                          day.status === 'PRESENT' && 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300',
                          day.status === 'LATE' && 'bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300',
                          day.status === 'ABSENT' && 'bg-rose-100 text-rose-700 dark:bg-rose-950 dark:text-rose-300',
                          day.status === 'EXCUSED' && 'bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300'
                        )}
                      >
                        {day.status}
                      </span>
                      <div>
                        <p className="font-semibold text-zinc-900 dark:text-zinc-100">{day.date} ({day.dayOfWeek})</p>
                        {day.notes && <p className="text-[11px] text-zinc-500 italic">{day.notes}</p>}
                      </div>
                    </div>
                    <div className="text-right text-[11px] text-zinc-500">
                      <p>In: <span className="font-mono font-medium text-zinc-800 dark:text-zinc-200">{day.checkInTime}</span> | Out: <span className="font-mono font-medium text-zinc-800 dark:text-zinc-200">{day.checkOutTime}</span></p>
                      <p className="text-[10px] text-zinc-400">{day.gate}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* TAB 4: TUITION & FEE LEDGER */}
        {activeTab === 'tuition' && (
          <div className="space-y-4">
            <div className="p-4 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 flex items-center justify-between flex-wrap gap-3">
              <div>
                <p className="text-xs text-zinc-400 font-medium">Outstanding Balance Payable</p>
                <p className="text-2xl font-black text-rose-600 dark:text-rose-400">PKR {profile.outstandingBalancePKR.toLocaleString()}</p>
                <p className="text-[11px] text-zinc-500 mt-0.5">Billing Cycle: Monthly Standard Tuition + STEM Lab surcharge</p>
              </div>
              <button
                type="button"
                onClick={() => {
                  setPayAmount(profile.outstandingBalancePKR)
                  setIsPaymentModalOpen(true)
                }}
                className="px-4 py-2 text-xs font-semibold rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white shadow-xs flex items-center gap-1.5 transition-colors cursor-pointer"
              >
                <CreditCard className="h-4 w-4" />
                Record Payment
              </button>
            </div>

            <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 overflow-hidden">
              <div className="p-4 border-b border-zinc-200 dark:border-zinc-800">
                <h4 className="text-xs font-bold uppercase tracking-wider text-zinc-400">Voucher & Ledger History</h4>
              </div>
              <table className="w-full text-left text-xs">
                <thead className="bg-zinc-50/80 dark:bg-zinc-800/50 text-zinc-400 uppercase font-semibold border-b border-zinc-200 dark:border-zinc-800">
                  <tr>
                    <th className="py-2.5 px-4">Voucher No</th>
                    <th className="py-2.5 px-4">Billing Month</th>
                    <th className="py-2.5 px-4">Due Date</th>
                    <th className="py-2.5 px-4">Amount Due</th>
                    <th className="py-2.5 px-4">Paid</th>
                    <th className="py-2.5 px-4">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800">
                  {profile.feeLedger.map((fee, idx) => (
                    <tr key={idx} className="hover:bg-zinc-50/50 dark:hover:bg-zinc-800/30">
                      <td className="py-3 px-4 font-mono font-medium text-zinc-900 dark:text-zinc-100">{fee.voucherNo}</td>
                      <td className="py-3 px-4">{fee.month}</td>
                      <td className="py-3 px-4 text-zinc-500">{fee.dueDate}</td>
                      <td className="py-3 px-4 font-semibold">PKR {fee.amountDue.toLocaleString()}</td>
                      <td className="py-3 px-4 font-semibold text-emerald-600">PKR {fee.amountPaid.toLocaleString()}</td>
                      <td className="py-3 px-4">
                        <span
                          className={cn(
                            'px-2 py-0.5 rounded text-[10px] font-bold uppercase',
                            fee.status === 'PAID' && 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300',
                            fee.status === 'OVERDUE' && 'bg-rose-100 text-rose-700 dark:bg-rose-950 dark:text-rose-300',
                            fee.status === 'PARTIAL' && 'bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300',
                            fee.status === 'UNPAID' && 'bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300'
                          )}
                        >
                          {fee.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* TAB 5: PASTORAL & COUNSELING */}
        {activeTab === 'pastoral' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-zinc-900 dark:text-zinc-100">Pastoral Care, Merits & Counseling Log</h3>
                <p className="text-xs text-zinc-500">Holistic student wellbeing notes and disciplinary audit records</p>
              </div>
              <button
                type="button"
                onClick={() => setIsPastoralModalOpen(true)}
                className="px-3 py-1.5 text-xs font-semibold rounded-lg bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900 hover:opacity-90 flex items-center gap-1.5"
              >
                <HeartHandshake className="h-3.5 w-3.5" />
                Issue Note
              </button>
            </div>

            <div className="space-y-3">
              {profile.pastoralRecords.map((rec) => (
                <div
                  key={rec.id}
                  className="p-4 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900"
                >
                  <div className="flex items-start justify-between gap-2 mb-1.5">
                    <div className="flex items-center gap-2">
                      <span
                        className={cn(
                          'px-2 py-0.5 rounded text-[10px] font-bold uppercase',
                          rec.type === 'MERIT' && 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300',
                          rec.type === 'DEMERIT' && 'bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300',
                          rec.type === 'COUNSELING' && 'bg-purple-100 text-purple-800 dark:bg-purple-950 dark:text-purple-300',
                          rec.type === 'WELLBEING' && 'bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300'
                        )}
                      >
                        {rec.type} {rec.points ? `(${rec.points > 0 ? '+' : ''}${rec.points} pts)` : ''}
                      </span>
                      {rec.isConfidential && (
                        <span className="inline-flex items-center gap-1 text-[10px] font-medium text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/60 px-1.5 py-0.5 rounded border border-amber-200 dark:border-amber-800">
                          <Lock className="h-2.5 w-2.5" />
                          Confidential
                        </span>
                      )}
                      <h4 className="text-xs font-bold text-zinc-900 dark:text-zinc-100">{rec.title}</h4>
                    </div>
                    <span className="text-[10px] text-zinc-400">{rec.date}</span>
                  </div>
                  <p className="text-xs text-zinc-600 dark:text-zinc-300 mt-1">{rec.description}</p>
                  <div className="mt-2.5 pt-2 border-t border-zinc-100 dark:border-zinc-800/80 flex items-center justify-between text-[11px] text-zinc-400">
                    <span>Recorded by: <strong className="text-zinc-600 dark:text-zinc-300">{rec.recordedBy}</strong></span>
                    <span className="font-semibold text-indigo-600 dark:text-indigo-400">{rec.status}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* TAB 6: SOCRATIC AI ACTIVITY */}
        {activeTab === 'socratic' && (
          <div className="space-y-4">
            <div className="p-4 rounded-xl border border-indigo-200 dark:border-indigo-900/60 bg-indigo-50/50 dark:bg-indigo-950/30 flex items-center justify-between flex-wrap gap-3">
              <div className="flex items-center gap-3">
                <div className="h-10 w-10 rounded-xl bg-indigo-600 text-white flex items-center justify-center font-bold shadow-xs">
                  <Bot className="h-5 w-5" />
                </div>
                <div>
                  <h4 className="text-xs font-bold text-zinc-900 dark:text-zinc-100">Autonomous Socratic Tutor Oversight</h4>
                  <p className="text-[11px] text-zinc-500">Live cognitive reasoning sessions with zero hallucination enforcement</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-zinc-500 font-medium">AI Tutoring Access:</span>
                <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
                  ENABLED
                </span>
              </div>
            </div>

            <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 divide-y divide-zinc-200 dark:divide-zinc-800">
              <div className="p-3.5 bg-zinc-50/80 dark:bg-zinc-800/50">
                <h4 className="text-xs font-bold uppercase tracking-wider text-zinc-400">Recent Socratic Reasoning Sessions</h4>
              </div>
              {profile.socraticSessions.map((s) => (
                <div key={s.id} className="p-4 flex items-start justify-between gap-3 text-xs">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-[10px] text-zinc-400 font-bold">{s.subject}</span>
                      <p className="font-bold text-zinc-900 dark:text-zinc-100">{s.conceptTitle}</p>
                    </div>
                    <p className="text-zinc-500 text-[11px]">
                      Bloom’s Cognitive Depth: <strong className="text-zinc-700 dark:text-zinc-300">{s.bloomLevel}</strong> • Hints Consumed: <strong className="text-zinc-700 dark:text-zinc-300">{s.hintsConsumed}</strong> • Session Time: {s.durationMins} mins
                    </p>
                  </div>
                  <div className="text-right">
                    <span
                      className={cn(
                        'px-2 py-0.5 rounded-full text-[10px] font-bold',
                        s.outcome === 'Mastered' && 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300',
                        s.outcome === 'Assisted' && 'bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300',
                        s.outcome === 'Struggling' && 'bg-rose-100 text-rose-700 dark:bg-rose-950 dark:text-rose-300'
                      )}
                    >
                      {s.outcome}
                    </span>
                    <p className="text-[10px] text-zinc-400 mt-1">{s.timestamp}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* TAB 7: GUARDIANS & EMERGENCY */}
        {activeTab === 'guardians' && (
          <div className="space-y-4">
            <h3 className="text-sm font-bold text-zinc-900 dark:text-zinc-100">Guardians, Emergency Contacts & Authorized Pickups</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {profile.guardians.map((g, idx) => (
                <div
                  key={idx}
                  className="p-5 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 space-y-3"
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <span className="text-[10px] font-bold uppercase tracking-wider text-indigo-600 dark:text-indigo-400">
                        {g.relationship}
                      </span>
                      <h4 className="text-sm font-bold text-zinc-900 dark:text-zinc-100 mt-0.5">{g.name}</h4>
                    </div>
                    {g.pickupAuthorized && (
                      <span className="inline-flex items-center gap-1 text-[10px] font-semibold bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 px-2 py-0.5 rounded-full border border-emerald-200 dark:border-emerald-800">
                        <CheckCircle2 className="h-3 w-3" />
                        Authorized Pickup
                      </span>
                    )}
                  </div>

                  <div className="space-y-2 text-xs">
                    <div className="flex items-center gap-2 text-zinc-600 dark:text-zinc-300">
                      <Phone className="h-3.5 w-3.5 text-zinc-400" />
                      <a href={`tel:${g.phone}`} className="hover:underline font-mono">{g.phone}</a>
                    </div>
                    <div className="flex items-center gap-2 text-zinc-600 dark:text-zinc-300">
                      <Mail className="h-3.5 w-3.5 text-zinc-400" />
                      <a href={`mailto:${g.email}`} className="hover:underline">{g.email}</a>
                    </div>
                    <div className="flex items-center gap-2 text-zinc-600 dark:text-zinc-300">
                      <Building2 className="h-3.5 w-3.5 text-zinc-400" />
                      <span>{g.occupation} ({g.employer})</span>
                    </div>
                    <div className="flex items-center gap-2 text-zinc-500 font-mono text-[11px]">
                      <span>CNIC: {g.cnic}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </Entity360Drawer>

      {/* MODAL 1: PRINT ID CARD */}
      <Dialog open={isIdCardModalOpen} onOpenChange={setIsIdCardModalOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Student Smart Identity Card</DialogTitle>
            <DialogDescription>Official NFC / QR enabled campus badge</DialogDescription>
          </DialogHeader>
          <div className="p-4 bg-gradient-to-br from-indigo-900 via-zinc-900 to-black text-white rounded-2xl border border-indigo-500/30 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-white/10 pb-3">
              <div className="flex items-center gap-2">
                <Building2 className="h-5 w-5 text-indigo-400" />
                <div>
                  <p className="text-[11px] font-black uppercase tracking-widest text-indigo-300">CSG FUTURE ACADEMY</p>
                  <p className="text-[9px] text-zinc-400">Cognia Accredited STEM Campus</p>
                </div>
              </div>
              <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">VALID 2026-27</span>
            </div>

            <div className="flex items-center gap-4">
              <div className="h-20 w-20 rounded-xl bg-indigo-600 flex items-center justify-center font-bold text-2xl shadow-inner border border-white/20">
                {profile.name.slice(0, 2).toUpperCase()}
              </div>
              <div className="space-y-1">
                <h3 className="text-base font-bold text-white">{profile.name}</h3>
                <p className="text-xs text-indigo-300 font-mono">{profile.rollNo}</p>
                <p className="text-xs text-zinc-300">{profile.grade} • {profile.section}</p>
                <p className="text-[10px] text-zinc-400">Blood: {profile.bloodGroup}</p>
              </div>
            </div>

            <div className="flex items-center justify-between pt-2 border-t border-white/10 text-[10px] text-zinc-400">
              <div className="flex items-center gap-2">
                <QrCode className="h-8 w-8 text-white p-0.5 bg-white/10 rounded" />
                <span>Scan for Gate Biometrics</span>
              </div>
              <div className="text-right">
                <p className="font-mono text-zinc-300">{profile.cnicBForm}</p>
                <p className="text-[9px] text-zinc-500">Emergency: +92 300 8472910</p>
              </div>
            </div>
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={() => {
                window.print()
                toast.success('Dispatched to Campus Card Printer!')
                setIsIdCardModalOpen(false)
              }}
              className="px-4 py-2 text-xs font-semibold rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white flex items-center gap-1.5"
            >
              <Printer className="h-3.5 w-3.5" />
              Print Smartcard
            </button>
          </div>
        </DialogContent>
      </Dialog>

      {/* MODAL 2: GENERATE COGNIA TRANSCRIPT */}
      <Dialog open={isTranscriptModalOpen} onOpenChange={setIsTranscriptModalOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Official Cognia-Accredited Transcript</DialogTitle>
            <DialogDescription>Verified academic record & high-school course masteries</DialogDescription>
          </DialogHeader>
          <div className="p-4 bg-zinc-50 dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800 space-y-3 text-xs">
            <div className="flex justify-between items-center pb-2 border-b border-zinc-200 dark:border-zinc-800">
              <span className="font-bold text-zinc-900 dark:text-zinc-100">{profile.name} (Roll #{profile.rollNo})</span>
              <span className="font-mono text-indigo-600 dark:text-indigo-400 font-bold">GPA: {profile.gpa.toFixed(2)}</span>
            </div>
            <div className="space-y-1.5 text-zinc-600 dark:text-zinc-300">
              {profile.courses.map((c, i) => (
                <div key={i} className="flex justify-between items-center text-[11px]">
                  <span>{c.code}: {c.name} ({c.credits} Cr)</span>
                  <span className="font-bold text-zinc-900 dark:text-zinc-100">{c.letterGrade} ({c.scorePercent}%)</span>
                </div>
              ))}
            </div>
            <div className="pt-2 border-t border-zinc-200 dark:border-zinc-800 text-[10px] text-zinc-400 flex items-center justify-between">
              <span>Cognia Protocol: STEM-COGNIA-2026</span>
              <span>Cryptographic Seal: SHA256-V29A</span>
            </div>
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={() => {
                toast.success('Cognia Official Transcript PDF generated!')
                setIsTranscriptModalOpen(false)
              }}
              className="px-4 py-2 text-xs font-semibold rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white flex items-center gap-1.5"
            >
              <FileCheck className="h-3.5 w-3.5" />
              Download Verified PDF
            </button>
          </div>
        </DialogContent>
      </Dialog>

      {/* MODAL 3: RECORD FEE PAYMENT */}
      <Dialog open={isPaymentModalOpen} onOpenChange={setIsPaymentModalOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Record Tuition / Fee Payment</DialogTitle>
            <DialogDescription>Credit student account and issue receipt</DialogDescription>
          </DialogHeader>
          <form onSubmit={handleRecordPaymentSubmit} className="space-y-4 text-xs">
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
              <label className="block font-medium text-zinc-700 dark:text-zinc-300 mb-1">Payment Gateway / Method</label>
              <select
                value={payMethod}
                onChange={(e) => setPayMethod(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900"
              >
                <option value="1Link / Kuickpay">1Link / Kuickpay Online</option>
                <option value="Stripe Credit Card">Stripe Credit Card</option>
                <option value="Bank Direct Deposit Slip">Bank Direct Deposit Slip</option>
                <option value="Cash at Bursar Desk">Cash at Bursar Desk</option>
              </select>
            </div>
            <div>
              <label className="block font-medium text-zinc-700 dark:text-zinc-300 mb-1">Receipt / Memo Notes</label>
              <input
                type="text"
                value={payNotes}
                onChange={(e) => setPayNotes(e.target.value)}
                placeholder="e.g. Bank Challan Slip Ref #84729"
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
                className="px-4 py-2 text-xs font-semibold rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white"
              >
                Confirm Payment
              </button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      {/* MODAL 4: ISSUE PASTORAL NOTE */}
      <Dialog open={isPastoralModalOpen} onOpenChange={setIsPastoralModalOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Issue Pastoral / Counseling Note</DialogTitle>
            <DialogDescription>Log behavioral observations, merits, or confidential alerts</DialogDescription>
          </DialogHeader>
          <form onSubmit={handlePastoralSubmit} className="space-y-4 text-xs">
            <div>
              <label className="block font-medium text-zinc-700 dark:text-zinc-300 mb-1">Record Classification</label>
              <select
                value={pastoralType}
                onChange={(e) => setPastoralType(e.target.value as any)}
                className="w-full px-3 py-2 rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 font-semibold"
              >
                <option value="MERIT">Merit Award (+ Points)</option>
                <option value="DEMERIT">Demerit Violation (- Points)</option>
                <option value="COUNSELING">Counseling & Guidance Session</option>
                <option value="WELLBEING">Wellbeing / Health Observation</option>
              </select>
            </div>
            <div>
              <label className="block font-medium text-zinc-700 dark:text-zinc-300 mb-1">Note Title</label>
              <input
                type="text"
                value={pastoralTitle}
                onChange={(e) => setPastoralTitle(e.target.value)}
                placeholder="e.g. Science Fair Leadership Recognition"
                className="w-full px-3 py-2 rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900"
                required
              />
            </div>
            <div>
              <label className="block font-medium text-zinc-700 dark:text-zinc-300 mb-1">Detailed Narrative</label>
              <textarea
                value={pastoralDesc}
                onChange={(e) => setPastoralDesc(e.target.value)}
                rows={3}
                placeholder="Observation details, agreed next steps..."
                className="w-full px-3 py-2 rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900"
              />
            </div>
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="confidential-check"
                checked={pastoralConfidential}
                onChange={(e) => setPastoralConfidential(e.target.checked)}
                className="rounded border-zinc-300"
              />
              <label htmlFor="confidential-check" className="text-zinc-700 dark:text-zinc-300">
                Mark as Confidential (Restricted to Principal & Lead Counselor)
              </label>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setIsPastoralModalOpen(false)}
                className="px-3 py-2 text-xs font-semibold rounded-lg border border-zinc-300 dark:border-zinc-700"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-4 py-2 text-xs font-semibold rounded-lg bg-zinc-900 text-white dark:bg-white dark:text-zinc-900"
              >
                Save Pastoral Entry
              </button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </>
  )
}
