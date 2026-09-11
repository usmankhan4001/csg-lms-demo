'use client'

import React, { useState } from 'react'
import Link from 'next/link'
import {
  Users,
  CheckSquare,
  Award,
  BookOpen,
  Calendar,
  Clock,
  Plus,
  CheckCircle2,
  XCircle,
  AlertCircle,
  MessageSquare,
  Send,
  Sparkles,
  TrendingUp,
  ChevronRight,
  FileCheck,
  Edit3,
  Search,
  Check,
  X,
  UploadCloud,
  FileText,
} from 'lucide-react'
import { cn } from '@/lib/utils'

interface ClassScheduleItem {
  id: string
  period: number
  time: string
  grade: string
  subject: string
  room: string
  studentCount: number
  attendanceStatus: 'marked' | 'pending' | 'in_progress'
}

interface StudentRosterItem {
  id: string
  rollNo: string
  name: string
  status: 'present' | 'absent' | 'late' | 'excused'
}

interface PendingSubmission {
  id: string
  studentName: string
  rollNo: string
  assignmentTitle: string
  course: string
  submittedAt: string
  score?: number
  maxScore: number
}

interface LessonPlanItem {
  id: string
  title: string
  course: string
  week: number
  status: 'published' | 'draft' | 'scheduled'
  updatedAt: string
  resourcesCount: number
}

const TEACHER_CLASSES: ClassScheduleItem[] = [
  {
    id: 'cls-1',
    period: 1,
    time: '08:30 - 09:20 AM',
    grade: 'Grade 11 - Section A',
    subject: 'Advanced Physics (Mechanics)',
    room: 'Science Lab 3',
    studentCount: 32,
    attendanceStatus: 'marked',
  },
  {
    id: 'cls-2',
    period: 2,
    time: '09:25 - 10:15 AM',
    grade: 'Grade 12 - Section B',
    subject: 'Electromagnetism & Wave Optics',
    room: 'Physics Lab 1',
    studentCount: 28,
    attendanceStatus: 'in_progress',
  },
  {
    id: 'cls-3',
    period: 4,
    time: '11:30 - 12:20 PM',
    grade: 'Grade 10 - Section C',
    subject: 'General Physics & Energy Systems',
    room: 'Room 205',
    studentCount: 35,
    attendanceStatus: 'pending',
  },
  {
    id: 'cls-4',
    period: 6,
    time: '02:00 - 02:50 PM',
    grade: 'Grade 11 - STEM Honors',
    subject: 'STEM Robotics & Applied Kinematics',
    room: 'Innovation Center',
    studentCount: 24,
    attendanceStatus: 'pending',
  },
]

const INITIAL_ROSTER: StudentRosterItem[] = [
  { id: 'std-1', rollNo: '11A-01', name: 'Zaid Usman Khan', status: 'present' },
  { id: 'std-2', rollNo: '11A-02', name: 'Ahmad Bilal Malik', status: 'present' },
  { id: 'std-3', rollNo: '11A-03', name: 'Fatima Zahra', status: 'present' },
  { id: 'std-4', rollNo: '11A-04', name: 'Hamza Farooq', status: 'late' },
  { id: 'std-5', rollNo: '11A-05', name: 'Maryam Sajid', status: 'present' },
  { id: 'std-6', rollNo: '11A-06', name: 'Mustafa Ali', status: 'absent' },
  { id: 'std-7', rollNo: '11A-07', name: 'Sara Noor', status: 'present' },
  { id: 'std-8', rollNo: '11A-08', name: 'Usman Tariq', status: 'excused' },
]

const INITIAL_SUBMISSIONS: PendingSubmission[] = [
  {
    id: 'sub-1',
    studentName: 'Zaid Usman Khan',
    rollNo: '11A-01',
    assignmentTitle: 'Lab Report: Rotational Dynamics & Moment of Inertia',
    course: 'PHY-401',
    submittedAt: 'Today at 08:45 AM',
    maxScore: 30,
  },
  {
    id: 'sub-2',
    studentName: 'Ahmad Bilal Malik',
    rollNo: '11A-02',
    assignmentTitle: 'Calculus BC: Differential Equations Problem Set',
    course: 'MTH-302',
    submittedAt: 'Yesterday at 11:20 PM',
    maxScore: 50,
  },
  {
    id: 'sub-3',
    studentName: 'Fatima Zahra',
    rollNo: '11A-03',
    assignmentTitle: 'Optics Simulation & Waveform Analysis',
    course: 'PHY-401',
    submittedAt: 'Yesterday at 06:15 PM',
    maxScore: 25,
  },
]

const LESSON_PLANS: LessonPlanItem[] = [
  {
    id: 'lp-1',
    title: 'Unit 4.2: Work, Energy & Conservation of Momentum',
    course: 'Grade 11 Physics (PHY-401)',
    week: 4,
    status: 'published',
    updatedAt: '2 days ago',
    resourcesCount: 4,
  },
  {
    id: 'lp-2',
    title: 'Unit 4.3: Simple Harmonic Motion & Spring Oscillators',
    course: 'Grade 11 Physics (PHY-401)',
    week: 5,
    status: 'scheduled',
    updatedAt: 'Yesterday',
    resourcesCount: 6,
  },
  {
    id: 'lp-3',
    title: 'Unit 5.1: Wave Mechanics & Doppler Shift in Acoustics',
    course: 'Grade 12 Physics (PHY-501)',
    week: 5,
    status: 'draft',
    updatedAt: 'Just now',
    resourcesCount: 2,
  },
]

export default function TeacherClassroomHubPage() {
  const [roster, setRoster] = useState<StudentRosterItem[]>(INITIAL_ROSTER)
  const [selectedClassId, setSelectedClassId] = useState('cls-2')
  const [attendanceSavedToast, setAttendanceSavedToast] = useState(false)
  const [submissions, setSubmissions] = useState<PendingSubmission[]>(INITIAL_SUBMISSIONS)
  const [gradeModalOpen, setGradeModalOpen] = useState(false)
  const [activeSubmission, setActiveSubmission] = useState<PendingSubmission | null>(null)
  const [gradeScore, setGradeScore] = useState<number | string>('')
  const [gradeFeedback, setGradeFeedback] = useState('')

  // Roll-Call Helpers
  const handleMarkAllPresent = () => {
    setRoster((prev) => prev.map((s) => ({ ...s, status: 'present' })))
  }

  const handleToggleStudentStatus = (id: string, newStatus: StudentRosterItem['status']) => {
    setRoster((prev) =>
      prev.map((s) => (s.id === id ? { ...s, status: newStatus } : s))
    )
  }

  const handleSaveAttendance = () => {
    setAttendanceSavedToast(true)
    setTimeout(() => setAttendanceSavedToast(false), 3000)
  }

  // Quick Grading
  const handleOpenGradeModal = (sub: PendingSubmission) => {
    setActiveSubmission(sub)
    setGradeScore(sub.maxScore ? Math.round(sub.maxScore * 0.9) : 25)
    setGradeFeedback('Excellent analysis of experimental errors and thorough derivation.')
    setGradeModalOpen(true)
  }

  const handleSaveGrade = (e: React.FormEvent) => {
    e.preventDefault()
    if (!activeSubmission) return

    setSubmissions((prev) => prev.filter((s) => s.id !== activeSubmission.id))
    setGradeModalOpen(false)
  }

  const presentCount = roster.filter((s) => s.status === 'present').length
  const absentCount = roster.filter((s) => s.status === 'absent').length
  const lateCount = roster.filter((s) => s.status === 'late').length
  const excusedCount = roster.filter((s) => s.status === 'excused').length

  return (
    <div className="space-y-6">
      {/* Teacher Hero Hub Banner */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-amber-600 via-orange-600 to-rose-700 text-white p-6 sm:p-8 shadow-lg shadow-amber-900/10">
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/10 backdrop-blur-md border border-white/15 text-xs font-semibold text-amber-100 mb-3">
              <Sparkles className="size-3.5 text-amber-300" />
              <span>Faculty Portal • Dept. of Physical Sciences</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">
              Teacher Classroom Hub 👩‍🏫
            </h1>
            <p className="text-sm text-amber-100/90 mt-1 max-w-xl leading-relaxed">
              Dr. Fatima Noor • You have 4 classes scheduled today across 119 enrolled students. Period 2 roll-call is ready to be finalized.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2.5">
            <Link
              href="#rollcall"
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-white text-neutral-900 hover:bg-amber-50 font-semibold text-xs transition-all shadow-md hover:scale-105 active:scale-95"
            >
              <CheckSquare className="size-4 text-amber-600" />
              <span>1-Click Roll-Call</span>
            </Link>
            <Link
              href="#gradebook"
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-white/15 hover:bg-white/25 border border-white/20 text-white font-medium text-xs transition-colors backdrop-blur-xs"
            >
              <Award className="size-4" />
              <span>Review Submissions ({submissions.length})</span>
            </Link>
          </div>
        </div>

        {/* Decorative background circle */}
        <div className="absolute -end-12 -bottom-12 size-64 rounded-full bg-white/10 blur-2xl pointer-events-none" />
      </div>

      {/* Top Stat Highlights */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-4 rounded-2xl bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 shadow-2xs">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-neutral-500">Classes Today</span>
            <div className="p-1.5 rounded-lg bg-amber-500/10 text-amber-600">
              <Clock className="size-4" />
            </div>
          </div>
          <div className="text-2xl font-bold text-neutral-900 dark:text-white">4 Periods</div>
          <div className="text-[11px] text-neutral-500 mt-1">119 Total Enrolled Students</div>
        </div>

        <div className="p-4 rounded-2xl bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 shadow-2xs">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-neutral-500">Roll-Call Status</span>
            <div className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-600">
              <CheckSquare className="size-4" />
            </div>
          </div>
          <div className="text-2xl font-bold text-neutral-900 dark:text-white">1 of 4 Done</div>
          <div className="text-[11px] text-amber-600 font-medium mt-1">Period 2 in progress</div>
        </div>

        <div className="p-4 rounded-2xl bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 shadow-2xs">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-neutral-500">Pending Grading</span>
            <div className="p-1.5 rounded-lg bg-rose-500/10 text-rose-600">
              <FileCheck className="size-4" />
            </div>
          </div>
          <div className="text-2xl font-bold text-neutral-900 dark:text-white">
            {submissions.length} Items
          </div>
          <div className="text-[11px] text-rose-600 font-medium mt-1">3 assignments pending</div>
        </div>

        <div className="p-4 rounded-2xl bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 shadow-2xs">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-neutral-500">Class Average</span>
            <div className="p-1.5 rounded-lg bg-blue-500/10 text-blue-600">
              <TrendingUp className="size-4" />
            </div>
          </div>
          <div className="text-2xl font-bold text-neutral-900 dark:text-white">86.2%</div>
          <div className="text-[11px] text-blue-600 font-medium mt-1">+3.4% vs last term</div>
        </div>
      </div>

      {/* Main Grid: 1-Click Roll-Call Hub & My Classes */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: 1-Click Roll Call & Gradebook Submissions */}
        <div className="lg:col-span-2 space-y-6">
          {/* 1-Click Roll-Call Card */}
          <div
            id="rollcall"
            className="p-5 sm:p-6 rounded-2xl bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 shadow-2xs"
          >
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-xl bg-amber-500/10 text-amber-600 dark:text-amber-400">
                  <CheckSquare className="size-5" />
                </div>
                <div>
                  <h2 className="text-base font-bold text-neutral-900 dark:text-white">
                    1-Click Roll-Call Quick Action
                  </h2>
                  <p className="text-xs text-neutral-500">
                    Active Class: <span className="font-semibold text-neutral-800 dark:text-neutral-200">Grade 12-B • Period 2</span>
                  </p>
                </div>
              </div>

              {/* Quick Batch Actions */}
              <div className="flex items-center gap-2">
                <button
                  onClick={handleMarkAllPresent}
                  className="px-3 py-1.5 rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 border border-emerald-500/20 text-xs font-semibold transition-colors"
                >
                  Mark All Present
                </button>
                <button
                  onClick={handleSaveAttendance}
                  className="px-4 py-1.5 rounded-lg bg-amber-600 hover:bg-amber-700 text-white text-xs font-semibold transition-colors shadow-2xs"
                >
                  Save & Finalize
                </button>
              </div>
            </div>

            {/* Attendance Toast Notification */}
            {attendanceSavedToast && (
              <div className="p-3 mb-4 rounded-xl bg-emerald-500/15 border border-emerald-500/30 text-emerald-700 dark:text-emerald-300 text-xs font-medium flex items-center justify-between animate-in fade-in">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="size-4 text-emerald-600 shrink-0" />
                  <span>
                    Roll-call successfully recorded and synced with Parent Portal & SMS Gateway.
                  </span>
                </div>
                <button onClick={() => setAttendanceSavedToast(false)}>
                  <X className="size-4" />
                </button>
              </div>
            )}

            {/* Quick Summary Pill Row */}
            <div className="grid grid-cols-4 gap-2 mb-4">
              <div className="p-2 rounded-xl bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-500/20 text-center">
                <div className="text-base font-bold text-emerald-700 dark:text-emerald-300">
                  {presentCount}
                </div>
                <div className="text-[10px] text-emerald-600 dark:text-emerald-400 uppercase font-semibold">
                  Present
                </div>
              </div>
              <div className="p-2 rounded-xl bg-rose-50 dark:bg-rose-950/30 border border-rose-500/20 text-center">
                <div className="text-base font-bold text-rose-700 dark:text-rose-300">
                  {absentCount}
                </div>
                <div className="text-[10px] text-rose-600 dark:text-rose-400 uppercase font-semibold">
                  Absent
                </div>
              </div>
              <div className="p-2 rounded-xl bg-amber-50 dark:bg-amber-950/30 border border-amber-500/20 text-center">
                <div className="text-base font-bold text-amber-700 dark:text-amber-300">
                  {lateCount}
                </div>
                <div className="text-[10px] text-amber-600 dark:text-amber-400 uppercase font-semibold">
                  Late
                </div>
              </div>
              <div className="p-2 rounded-xl bg-blue-50 dark:bg-blue-950/30 border border-blue-500/20 text-center">
                <div className="text-base font-bold text-blue-700 dark:text-blue-300">
                  {excusedCount}
                </div>
                <div className="text-[10px] text-blue-600 dark:text-blue-400 uppercase font-semibold">
                  Excused
                </div>
              </div>
            </div>

            {/* Roster Table */}
            <div className="border border-neutral-200 dark:border-neutral-800 rounded-xl overflow-hidden divide-y divide-neutral-100 dark:divide-neutral-800">
              {roster.map((student) => (
                <div
                  key={student.id}
                  className="p-3 hover:bg-neutral-50 dark:hover:bg-neutral-800/40 transition-colors flex flex-col sm:flex-row sm:items-center justify-between gap-2"
                >
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-xs font-semibold text-neutral-400 w-12">
                      {student.rollNo}
                    </span>
                    <span className="text-xs sm:text-sm font-semibold text-neutral-900 dark:text-neutral-100">
                      {student.name}
                    </span>
                  </div>

                  {/* 4-State Toggle Pills */}
                  <div className="flex items-center gap-1 sm:ms-auto">
                    <button
                      onClick={() => handleToggleStudentStatus(student.id, 'present')}
                      className={cn(
                        'px-2.5 py-1 rounded-md text-xs font-medium transition-colors',
                        student.status === 'present'
                          ? 'bg-emerald-600 text-white shadow-2xs font-semibold'
                          : 'bg-neutral-100 dark:bg-neutral-800 text-neutral-600 dark:text-neutral-400 hover:bg-neutral-200'
                      )}
                    >
                      P
                    </button>
                    <button
                      onClick={() => handleToggleStudentStatus(student.id, 'absent')}
                      className={cn(
                        'px-2.5 py-1 rounded-md text-xs font-medium transition-colors',
                        student.status === 'absent'
                          ? 'bg-rose-600 text-white shadow-2xs font-semibold'
                          : 'bg-neutral-100 dark:bg-neutral-800 text-neutral-600 dark:text-neutral-400 hover:bg-neutral-200'
                      )}
                    >
                      A
                    </button>
                    <button
                      onClick={() => handleToggleStudentStatus(student.id, 'late')}
                      className={cn(
                        'px-2.5 py-1 rounded-md text-xs font-medium transition-colors',
                        student.status === 'late'
                          ? 'bg-amber-600 text-white shadow-2xs font-semibold'
                          : 'bg-neutral-100 dark:bg-neutral-800 text-neutral-600 dark:text-neutral-400 hover:bg-neutral-200'
                      )}
                    >
                      L
                    </button>
                    <button
                      onClick={() => handleToggleStudentStatus(student.id, 'excused')}
                      className={cn(
                        'px-2.5 py-1 rounded-md text-xs font-medium transition-colors',
                        student.status === 'excused'
                          ? 'bg-blue-600 text-white shadow-2xs font-semibold'
                          : 'bg-neutral-100 dark:bg-neutral-800 text-neutral-600 dark:text-neutral-400 hover:bg-neutral-200'
                      )}
                    >
                      E
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Gradebook Quick Submissions Card */}
          <div
            id="gradebook"
            className="p-5 sm:p-6 rounded-2xl bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 shadow-2xs"
          >
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-xl bg-rose-500/10 text-rose-600 dark:text-rose-400">
                  <Award className="size-5" />
                </div>
                <div>
                  <h2 className="text-base font-bold text-neutral-900 dark:text-white">
                    Gradebook & Marking Queue
                  </h2>
                  <p className="text-xs text-neutral-500">
                    {submissions.length} Student submissions waiting for evaluation
                  </p>
                </div>
              </div>
            </div>

            <div className="space-y-3">
              {submissions.length === 0 ? (
                <div className="p-8 text-center text-xs text-neutral-400">
                  🎉 All submissions have been evaluated and graded!
                </div>
              ) : (
                submissions.map((sub) => (
                  <div
                    key={sub.id}
                    className="p-3.5 sm:p-4 rounded-xl border border-neutral-200 dark:border-neutral-800 hover:border-neutral-300 dark:hover:border-neutral-700 bg-neutral-50/50 dark:bg-neutral-800/30 flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                  >
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-mono text-xs font-bold text-neutral-600 dark:text-neutral-300">
                          {sub.rollNo}
                        </span>
                        <h4 className="text-xs sm:text-sm font-bold text-neutral-900 dark:text-white">
                          {sub.studentName}
                        </h4>
                        <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-neutral-200 dark:bg-neutral-700 text-neutral-700 dark:text-neutral-300">
                          {sub.course}
                        </span>
                      </div>
                      <p className="text-xs text-neutral-600 dark:text-neutral-400 mt-1 truncate">
                        {sub.assignmentTitle}
                      </p>
                      <span className="text-[11px] text-neutral-400 mt-0.5 inline-block">
                        Submitted: {sub.submittedAt} • Max Score: {sub.maxScore}
                      </span>
                    </div>

                    <button
                      onClick={() => handleOpenGradeModal(sub)}
                      className="px-3.5 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold transition-colors flex items-center justify-center gap-1.5 shrink-0 shadow-2xs"
                    >
                      <Edit3 className="size-3.5" />
                      <span>Grade Submission</span>
                    </button>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Right 1 Col: My Classes Today & Lesson Plans / Announcements */}
        <div className="space-y-6">
          {/* My Classes Today */}
          <div
            id="classes"
            className="p-5 rounded-2xl bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 shadow-2xs"
          >
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-bold text-neutral-900 dark:text-white flex items-center gap-2">
                <Users className="size-4 text-amber-500" />
                My Classes Today
              </h3>
              <span className="text-xs font-bold text-neutral-500">4 Classes</span>
            </div>

            <div className="space-y-2.5">
              {TEACHER_CLASSES.map((cls) => {
                const isSelected = selectedClassId === cls.id
                return (
                  <div
                    key={cls.id}
                    onClick={() => setSelectedClassId(cls.id)}
                    className={cn(
                      'p-3 rounded-xl border transition-all cursor-pointer',
                      isSelected
                        ? 'bg-amber-500/10 border-amber-500/40 shadow-xs'
                        : 'bg-neutral-50/50 dark:bg-neutral-800/40 border-neutral-200 dark:border-neutral-800 hover:border-neutral-300'
                    )}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[11px] font-bold font-mono text-amber-600 dark:text-amber-400">
                        Period {cls.period} • {cls.time}
                      </span>
                      <span
                        className={cn(
                          'px-1.5 py-0.2 rounded text-[10px] font-semibold capitalize',
                          cls.attendanceStatus === 'marked'
                            ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/50 dark:text-emerald-300'
                            : cls.attendanceStatus === 'in_progress'
                            ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/50 dark:text-amber-300'
                            : 'bg-neutral-200 text-neutral-600 dark:bg-neutral-700 dark:text-neutral-300'
                        )}
                      >
                        {cls.attendanceStatus.replace('_', ' ')}
                      </span>
                    </div>

                    <h4 className="text-xs font-bold text-neutral-900 dark:text-white">
                      {cls.grade}
                    </h4>
                    <p className="text-[11px] text-neutral-500 mt-0.5">
                      {cls.subject} • {cls.room} ({cls.studentCount} students)
                    </p>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Course Editor & Curriculum Manager */}
          <div
            id="editor"
            className="p-5 rounded-2xl bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 shadow-2xs"
          >
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-bold text-neutral-900 dark:text-white flex items-center gap-2">
                <BookOpen className="size-4 text-blue-500" />
                Lesson Planner & Editor
              </h3>
              <button className="p-1 rounded-md text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-950/40 transition-colors">
                <Plus className="size-4" />
              </button>
            </div>

            <div className="space-y-2.5">
              {LESSON_PLANS.map((lp) => (
                <div
                  key={lp.id}
                  className="p-2.5 rounded-xl border border-neutral-100 dark:border-neutral-800 bg-neutral-50/60 dark:bg-neutral-800/40"
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-neutral-400">
                      Week {lp.week}
                    </span>
                    <span
                      className={cn(
                        'px-1.5 py-0.2 rounded text-[10px] font-semibold capitalize',
                        lp.status === 'published'
                          ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/50 dark:text-emerald-300'
                          : lp.status === 'scheduled'
                          ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/50 dark:text-blue-300'
                          : 'bg-neutral-200 text-neutral-600 dark:bg-neutral-700 dark:text-neutral-300'
                      )}
                    >
                      {lp.status}
                    </span>
                  </div>
                  <h5 className="text-xs font-bold text-neutral-900 dark:text-white truncate">
                    {lp.title}
                  </h5>
                  <div className="flex items-center justify-between text-[11px] text-neutral-500 mt-1">
                    <span>{lp.course}</span>
                    <span>{lp.resourcesCount} Files</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Quick SMS & Notification Dispatcher */}
          <div
            id="announcements"
            className="p-5 rounded-2xl bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 shadow-2xs"
          >
            <h3 className="text-sm font-bold text-neutral-900 dark:text-white flex items-center gap-2 mb-3">
              <MessageSquare className="size-4 text-purple-500" />
              Quick Parent/Class SMS Alert
            </h3>

            <form
              onSubmit={(e) => {
                e.preventDefault()
                alert('Broadcast SMS & in-app announcement sent to 32 parents.')
              }}
              className="space-y-2.5"
            >
              <select className="w-full px-3 py-2 rounded-xl border border-neutral-200 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-800 text-xs text-neutral-800 dark:text-neutral-200 focus:outline-hidden">
                <option>Send to Grade 11-A Parents (32)</option>
                <option>Send to Grade 12-B Parents (28)</option>
                <option>Send to All My Students (119)</option>
              </select>
              <textarea
                rows={2}
                placeholder="Type short alert message (e.g. Bring lab coat tomorrow)..."
                className="w-full p-2.5 rounded-xl border border-neutral-200 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-800 text-xs text-neutral-800 dark:text-neutral-200 placeholder:text-neutral-400 focus:outline-hidden focus:ring-2 focus:ring-purple-500"
              />
              <button
                type="submit"
                className="w-full py-2 rounded-xl bg-purple-600 hover:bg-purple-700 text-white text-xs font-semibold transition-colors flex items-center justify-center gap-1.5 shadow-2xs"
              >
                <Send className="size-3.5" />
                <span>Broadcast Alert</span>
              </button>
            </form>
          </div>
        </div>
      </div>

      {/* Grade Submission Modal Dialog */}
      {gradeModalOpen && activeSubmission && (
        <div
          className="fixed inset-0 z-50 bg-black/70 backdrop-blur-xs flex items-center justify-center p-4 animate-in fade-in"
          role="dialog"
          aria-modal="true"
        >
          <div className="w-full max-w-lg bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 rounded-2xl shadow-2xl p-6">
            <div className="flex items-center justify-between pb-3 border-b border-neutral-100 dark:border-neutral-800">
              <div className="flex items-center gap-2.5">
                <div className="size-8 rounded-lg bg-blue-600 text-white flex items-center justify-center">
                  <Award className="size-4.5" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-neutral-900 dark:text-white">
                    Evaluate Submission
                  </h3>
                  <p className="text-xs text-neutral-500">
                    {activeSubmission.studentName} ({activeSubmission.rollNo})
                  </p>
                </div>
              </div>
              <button
                onClick={() => setGradeModalOpen(false)}
                className="p-1.5 rounded-lg text-neutral-400 hover:text-neutral-900 dark:hover:text-white"
              >
                <X className="size-5" />
              </button>
            </div>

            <form onSubmit={handleSaveGrade} className="space-y-4 pt-4">
              <div>
                <label className="text-xs font-semibold text-neutral-700 dark:text-neutral-300 mb-1 block">
                  Assignment Title
                </label>
                <input
                  type="text"
                  readOnly
                  value={activeSubmission.assignmentTitle}
                  className="w-full px-3 py-2 rounded-xl bg-neutral-100 dark:bg-neutral-800 text-xs text-neutral-700 dark:text-neutral-300 border border-neutral-200 dark:border-neutral-700"
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-neutral-700 dark:text-neutral-300 mb-1 block">
                  Score (Out of {activeSubmission.maxScore})
                </label>
                <input
                  type="number"
                  required
                  min="0"
                  max={activeSubmission.maxScore}
                  value={gradeScore}
                  onChange={(e) => setGradeScore(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-800 text-xs font-bold text-neutral-900 dark:text-white focus:outline-hidden focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-neutral-700 dark:text-neutral-300 mb-1 block">
                  Feedback to Student & Parent
                </label>
                <textarea
                  rows={3}
                  value={gradeFeedback}
                  onChange={(e) => setGradeFeedback(e.target.value)}
                  className="w-full p-2.5 rounded-xl border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-800 text-xs text-neutral-900 dark:text-white placeholder:text-neutral-400 focus:outline-hidden focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setGradeModalOpen(false)}
                  className="px-4 py-2 rounded-xl border border-neutral-200 dark:border-neutral-700 text-xs font-medium text-neutral-700 dark:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-800"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold shadow-xs"
                >
                  Save & Publish Grade
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
