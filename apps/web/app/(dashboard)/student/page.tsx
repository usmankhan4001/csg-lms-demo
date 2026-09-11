'use client'

import React, { useState } from 'react'
import Link from 'next/link'
import {
  Clock,
  BookOpen,
  BrainCircuit,
  CheckCircle2,
  Calendar,
  Sparkles,
  ArrowUpRight,
  Play,
  CheckSquare,
  AlertCircle,
  Video,
  ChevronRight,
  TrendingUp,
  Award,
  Send,
  Bot,
  User,
  X,
  FileText,
} from 'lucide-react'
import { cn } from '@/lib/utils'

interface TimetablePeriod {
  period: number
  time: string
  subject: string
  code: string
  teacher: string
  room: string
  status: 'completed' | 'ongoing' | 'upcoming'
  hasVirtualRoom?: boolean
}

interface CourseItem {
  id: string
  title: string
  code: string
  category: string
  instructor: string
  progress: number
  completedLessons: number
  totalLessons: number
  nextLesson: string
  color: string
}

const TODAY_TIMETABLE: TimetablePeriod[] = [
  {
    period: 1,
    time: '08:30 - 09:20 AM',
    subject: 'Advanced Physics (Mechanics)',
    code: 'PHY-401',
    teacher: 'Dr. Fatima Noor',
    room: 'Science Lab 3',
    status: 'completed',
  },
  {
    period: 2,
    time: '09:25 - 10:15 AM',
    subject: 'Calculus & Analytical Geometry',
    code: 'MTH-302',
    teacher: 'Prof. Tariq Siddiqui',
    room: 'Room 204',
    status: 'ongoing',
    hasVirtualRoom: true,
  },
  {
    period: 3,
    time: '10:35 - 11:25 AM',
    subject: 'Computer Science & Python Algorithmic Logic',
    code: 'CS-205',
    teacher: 'Engr. Bilal Hashmi',
    room: 'Computer Lab 1',
    status: 'upcoming',
    hasVirtualRoom: true,
  },
  {
    period: 4,
    time: '11:30 - 12:20 PM',
    subject: 'Academic English & Rhetoric',
    code: 'ENG-101',
    teacher: 'Ms. Samina Rizvi',
    room: 'Room 108',
    status: 'upcoming',
  },
  {
    period: 5,
    time: '01:00 - 01:50 PM',
    subject: 'Physical Chemistry Practicals',
    code: 'CHM-301',
    teacher: 'Dr. Kamran Qureshi',
    room: 'Chemistry Lab 2',
    status: 'upcoming',
  },
]

const ACTIVE_COURSES: CourseItem[] = [
  {
    id: 'course-1',
    title: 'Advanced Physics: Mechanics & Waves',
    code: 'PHY-401',
    category: 'STEM',
    instructor: 'Dr. Fatima Noor',
    progress: 74,
    completedLessons: 18,
    totalLessons: 24,
    nextLesson: 'Lesson 19: Harmonic Oscillations & Resonance',
    color: 'from-blue-600 to-cyan-600',
  },
  {
    id: 'course-2',
    title: 'Calculus & Analytical Geometry',
    code: 'MTH-302',
    category: 'Mathematics',
    instructor: 'Prof. Tariq Siddiqui',
    progress: 88,
    completedLessons: 22,
    totalLessons: 25,
    nextLesson: 'Lesson 23: Integration by Parts & Definite Integrals',
    color: 'from-purple-600 to-indigo-600',
  },
  {
    id: 'course-3',
    title: 'Data Structures & Algorithms in Python',
    code: 'CS-205',
    category: 'Computer Science',
    instructor: 'Engr. Bilal Hashmi',
    progress: 60,
    completedLessons: 12,
    totalLessons: 20,
    nextLesson: 'Lesson 13: Binary Search Trees and Traversal',
    color: 'from-emerald-600 to-teal-600',
  },
  {
    id: 'course-4',
    title: 'Organic & Physical Chemistry',
    code: 'CHM-301',
    category: 'Sciences',
    instructor: 'Dr. Kamran Qureshi',
    progress: 45,
    completedLessons: 9,
    totalLessons: 20,
    nextLesson: 'Lesson 10: Electrophilic Aromatic Substitution',
    color: 'from-amber-500 to-orange-600',
  },
]

const QUICK_DEADLINES = [
  {
    id: 'dead-1',
    title: 'Calculus Assignment 4: Differentiation Rules',
    course: 'MTH-302',
    dueDate: 'Today at 11:59 PM',
    urgent: true,
  },
  {
    id: 'dead-2',
    title: 'Physics Lab Report: Rotational Dynamics',
    course: 'PHY-401',
    dueDate: 'Tomorrow at 05:00 PM',
    urgent: false,
  },
  {
    id: 'dead-3',
    title: 'Python Binary Tree Implementation',
    course: 'CS-205',
    dueDate: 'Friday at 09:00 AM',
    urgent: false,
  },
]

export default function StudentDashboardPage() {
  const [aiModalOpen, setAiModalOpen] = useState(false)
  const [aiPrompt, setAiPrompt] = useState('')
  const [messages, setMessages] = useState<
    { sender: 'user' | 'ai'; text: string; time: string }[]
  >([
    {
      sender: 'ai',
      text: 'Hello Zaid! I am your CSG Socratic AI Tutor. Rather than just giving answers, I will help you think through problems step-by-step. What topic are you working on today?',
      time: '12:00 PM',
    },
  ])

  const handleSendAiMessage = (e?: React.FormEvent) => {
    if (e) e.preventDefault()
    if (!aiPrompt.trim()) return

    const userText = aiPrompt
    const newMsg = {
      sender: 'user' as const,
      text: userText,
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    }
    setMessages((prev) => [...prev, newMsg])
    setAiPrompt('')

    // Socratic response simulation
    setTimeout(() => {
      let aiResponse = `That's a thoughtful question regarding "${userText}". To explore this deeper, what is the fundamental principle or formula that you recall applying in this scenario?`
      if (userText.toLowerCase().includes('physics') || userText.toLowerCase().includes('newton')) {
        aiResponse = `Great topic! When thinking about Newton's Third Law, if object A exerts a force on object B, what can we deduce about the magnitude and direction of the reaction force?`
      } else if (userText.toLowerCase().includes('calculus') || userText.toLowerCase().includes('derivative')) {
        aiResponse = `Let's break down that derivative. If we treat the inner function as u(x), how would you apply the chain rule here?`
      } else if (userText.toLowerCase().includes('python') || userText.toLowerCase().includes('recursion')) {
        aiResponse = `Recursion is all about finding two things: the base case and the recursive step. What do you think should be the condition where your recursion stops?`
      }

      setMessages((prev) => [
        ...prev,
        {
          sender: 'ai' as const,
          text: aiResponse,
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
      ])
    }, 600)
  }

  const handleLaunchPrompt = (promptText: string) => {
    setAiModalOpen(true)
    setAiPrompt(promptText)
  }

  return (
    <div className="space-y-6">
      {/* Welcome Banner */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-blue-700 via-indigo-700 to-purple-800 text-white p-6 sm:p-8 shadow-lg shadow-blue-900/10">
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/10 backdrop-blur-md border border-white/15 text-xs font-semibold text-blue-100 mb-3">
              <Sparkles className="size-3.5 text-blue-300" />
              <span>Fall Term 2026 • Academic Week 4</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">
              Welcome back, Zaid! 👋
            </h1>
            <p className="text-sm text-blue-100/90 mt-1 max-w-xl leading-relaxed">
              You have 1 ongoing class, 3 upcoming lessons, and 2 assignments due this week. Your attendance is maintaining a top-tier 96.4%.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2.5">
            <button
              onClick={() => setAiModalOpen(true)}
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-white text-blue-900 hover:bg-blue-50 font-semibold text-xs transition-all shadow-md hover:scale-105 active:scale-95"
            >
              <BrainCircuit className="size-4 text-blue-600" />
              <span>Ask Socratic AI</span>
            </button>
            <Link
              href="#timetable"
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-white/15 hover:bg-white/25 border border-white/20 text-white font-medium text-xs transition-colors backdrop-blur-xs"
            >
              <Clock className="size-4" />
              <span>View Timetable</span>
            </Link>
          </div>
        </div>

        {/* Decorative background glow */}
        <div className="absolute -end-12 -bottom-12 size-64 rounded-full bg-white/10 blur-2xl pointer-events-none" />
      </div>

      {/* Top Stat KPI Highlights */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-4 rounded-2xl bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 shadow-2xs">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-neutral-500 dark:text-neutral-400">
              Attendance Rate
            </span>
            <div className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
              <CheckSquare className="size-4" />
            </div>
          </div>
          <div className="text-2xl font-bold text-neutral-900 dark:text-white">96.4%</div>
          <div className="text-[11px] text-emerald-600 dark:text-emerald-400 mt-1 flex items-center gap-1 font-medium">
            <TrendingUp className="size-3" />
            <span>18-day streak intact</span>
          </div>
        </div>

        <div className="p-4 rounded-2xl bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 shadow-2xs">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-neutral-500 dark:text-neutral-400">
              Current GPA / Avg
            </span>
            <div className="p-1.5 rounded-lg bg-blue-500/10 text-blue-600 dark:text-blue-400">
              <Award className="size-4" />
            </div>
          </div>
          <div className="text-2xl font-bold text-neutral-900 dark:text-white">3.88 / 4.0</div>
          <div className="text-[11px] text-blue-600 dark:text-blue-400 mt-1 font-medium">
            Grade A+ Standing
          </div>
        </div>

        <div className="p-4 rounded-2xl bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 shadow-2xs">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-neutral-500 dark:text-neutral-400">
              Enrolled Courses
            </span>
            <div className="p-1.5 rounded-lg bg-purple-500/10 text-purple-600 dark:text-purple-400">
              <BookOpen className="size-4" />
            </div>
          </div>
          <div className="text-2xl font-bold text-neutral-900 dark:text-white">6 Courses</div>
          <div className="text-[11px] text-neutral-500 dark:text-neutral-400 mt-1">
            24 Total Weekly Credit Hours
          </div>
        </div>

        <div className="p-4 rounded-2xl bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 shadow-2xs">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-neutral-500 dark:text-neutral-400">
              Tasks Due
            </span>
            <div className="p-1.5 rounded-lg bg-amber-500/10 text-amber-600 dark:text-amber-400">
              <Calendar className="size-4" />
            </div>
          </div>
          <div className="text-2xl font-bold text-neutral-900 dark:text-white">3 Tasks</div>
          <div className="text-[11px] text-amber-600 dark:text-amber-400 mt-1 font-medium">
            1 due tonight
          </div>
        </div>
      </div>

      {/* Main Grid: Today's Timetable & Socratic AI Launcher */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Today's Timetable & Active Courses */}
        <div className="lg:col-span-2 space-y-6">
          {/* Today's Timetable Card */}
          <div
            id="timetable"
            className="p-5 sm:p-6 rounded-2xl bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 shadow-2xs"
          >
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-xl bg-blue-500/10 text-blue-600 dark:text-blue-400">
                  <Clock className="size-5" />
                </div>
                <div>
                  <h2 className="text-base font-bold text-neutral-900 dark:text-white">
                    Today&apos;s Timetable & Schedule
                  </h2>
                  <p className="text-xs text-neutral-500 dark:text-neutral-400">
                    Live schedule for Friday • 5 Periods Scheduled
                  </p>
                </div>
              </div>
              <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-neutral-100 dark:bg-neutral-800 text-neutral-700 dark:text-neutral-300">
                Period 2 in session
              </span>
            </div>

            {/* Periods Timeline */}
            <div className="space-y-3">
              {TODAY_TIMETABLE.map((t) => {
                const isOngoing = t.status === 'ongoing'
                const isCompleted = t.status === 'completed'

                return (
                  <div
                    key={t.period}
                    className={cn(
                      'p-3.5 sm:p-4 rounded-xl border transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-3',
                      isOngoing
                        ? 'bg-blue-50/70 dark:bg-blue-950/30 border-blue-300 dark:border-blue-700/60 ring-2 ring-blue-500/20'
                        : isCompleted
                        ? 'bg-neutral-50/50 dark:bg-neutral-900/40 border-neutral-200 dark:border-neutral-800 opacity-80'
                        : 'bg-white dark:bg-neutral-800/40 border-neutral-200 dark:border-neutral-800 hover:border-neutral-300 dark:hover:border-neutral-700'
                    )}
                  >
                    <div className="flex items-start gap-3 min-w-0">
                      <div
                        className={cn(
                          'size-8 rounded-lg flex items-center justify-center font-bold text-xs shrink-0',
                          isOngoing
                            ? 'bg-blue-600 text-white animate-pulse'
                            : isCompleted
                            ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
                            : 'bg-neutral-100 dark:bg-neutral-800 text-neutral-500'
                        )}
                      >
                        {isCompleted ? <CheckCircle2 className="size-4" /> : `P${t.period}`}
                      </div>

                      <div className="min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <h4 className="text-xs sm:text-sm font-bold text-neutral-900 dark:text-white truncate">
                            {t.subject}
                          </h4>
                          <span className="px-1.5 py-0.5 rounded text-[10px] font-mono font-medium bg-neutral-100 dark:bg-neutral-800 text-neutral-600 dark:text-neutral-400">
                            {t.code}
                          </span>
                          {isOngoing && (
                            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-blue-600 text-white uppercase tracking-wider animate-pulse">
                              In Session
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-3 text-xs text-neutral-500 dark:text-neutral-400 mt-1">
                          <span>{t.time}</span>
                          <span>•</span>
                          <span>{t.room}</span>
                          <span>•</span>
                          <span>{t.teacher}</span>
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 shrink-0 sm:ms-auto">
                      {isOngoing && t.hasVirtualRoom && (
                        <Link
                          href="/live/phy-401-live"
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold transition-colors shadow-2xs"
                        >
                          <Video className="size-3.5" />
                          <span>Join Classroom</span>
                        </Link>
                      )}
                      {!isOngoing && (
                        <span
                          className={cn(
                            'text-xs font-medium capitalize',
                            isCompleted ? 'text-emerald-600 dark:text-emerald-400' : 'text-neutral-400'
                          )}
                        >
                          {t.status}
                        </span>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Active Courses Card */}
          <div
            id="courses"
            className="p-5 sm:p-6 rounded-2xl bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 shadow-2xs"
          >
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-xl bg-purple-500/10 text-purple-600 dark:text-purple-400">
                  <BookOpen className="size-5" />
                </div>
                <div>
                  <h2 className="text-base font-bold text-neutral-900 dark:text-white">
                    Active Courses
                  </h2>
                  <p className="text-xs text-neutral-500 dark:text-neutral-400">
                    Track your curriculum progression and next lessons
                  </p>
                </div>
              </div>
              <span className="text-xs text-neutral-500 dark:text-neutral-400 font-medium">
                4 Active
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {ACTIVE_COURSES.map((course) => (
                <div
                  key={course.id}
                  className="p-4 rounded-xl border border-neutral-200 dark:border-neutral-800 hover:border-neutral-300 dark:hover:border-neutral-700 bg-neutral-50/50 dark:bg-neutral-800/30 transition-all flex flex-col justify-between"
                >
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-neutral-200 dark:bg-neutral-700 text-neutral-700 dark:text-neutral-300">
                        {course.category}
                      </span>
                      <span className="text-xs font-bold text-neutral-900 dark:text-white">
                        {course.progress}%
                      </span>
                    </div>
                    <h3 className="text-sm font-bold text-neutral-900 dark:text-white line-clamp-1">
                      {course.title}
                    </h3>
                    <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-0.5">
                      {course.instructor}
                    </p>

                    {/* Progress Bar */}
                    <div className="w-full h-2 rounded-full bg-neutral-200 dark:bg-neutral-700 my-3 overflow-hidden">
                      <div
                        className={cn('h-full rounded-full bg-gradient-to-r', course.color)}
                        style={{ width: `${course.progress}%` }}
                      />
                    </div>

                    <div className="text-[11px] text-neutral-600 dark:text-neutral-400 line-clamp-1 mb-3">
                      <span className="font-semibold text-neutral-700 dark:text-neutral-300">Next: </span>
                      {course.nextLesson}
                    </div>
                  </div>

                  <Link
                    href={`/student/courses/${course.code.toLowerCase()}/lesson/les-3`}
                    className="w-full flex items-center justify-center gap-1.5 py-2 rounded-lg bg-white dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-700 text-xs font-semibold text-neutral-800 dark:text-neutral-200 hover:bg-neutral-100 dark:hover:bg-neutral-700 transition-colors shadow-2xs"
                  >
                    <Play className="size-3.5 fill-current text-blue-600" />
                    <span>Resume Course</span>
                  </Link>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right 1 Col: Socratic AI Launcher, Quick Attendance & Deadlines */}
        <div className="space-y-6">
          {/* Socratic AI Tutor Launcher Card */}
          <div
            id="ai-tutor"
            className="p-5 sm:p-6 rounded-2xl bg-gradient-to-br from-indigo-900 via-neutral-900 to-purple-950 border border-indigo-500/30 text-white shadow-xl shadow-indigo-950/20 relative overflow-hidden"
          >
            <div className="flex items-center gap-2.5 mb-3">
              <div className="p-2 rounded-xl bg-indigo-500/20 border border-indigo-400/30 text-indigo-300">
                <BrainCircuit className="size-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-white flex items-center gap-1.5">
                  Socratic AI Tutor
                  <span className="px-1.5 py-0.2 rounded text-[10px] bg-indigo-500/30 text-indigo-200 border border-indigo-400/30 font-semibold">
                    v2.0
                  </span>
                </h3>
                <p className="text-xs text-indigo-200/80">
                  Step-by-step guided problem solving
                </p>
              </div>
            </div>

            <p className="text-xs text-neutral-300 leading-relaxed mb-4">
              Stuck on a concept? Tap a quick prompt or ask any question. The AI tutor guides your logic rather than spoiling the final answer.
            </p>

            {/* Quick Prompt Chips */}
            <div className="space-y-2 mb-4">
              {[
                "Explain Newton's 3rd Law of Motion",
                "Practice Integration by Parts in Calculus",
                "Debug Python Binary Search Tree recursion",
                "Quiz me on Organic Chemistry mechanisms",
              ].map((chip) => (
                <button
                  key={chip}
                  onClick={() => handleLaunchPrompt(chip)}
                  className="w-full text-start p-2 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-xs text-indigo-100 hover:text-white transition-colors flex items-center justify-between group"
                >
                  <span className="truncate">{chip}</span>
                  <ChevronRight className="size-3.5 text-indigo-400 group-hover:translate-x-0.5 transition-transform shrink-0" />
                </button>
              ))}
            </div>

            <button
              onClick={() => setAiModalOpen(true)}
              className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl bg-gradient-to-r from-blue-500 to-indigo-600 hover:from-blue-600 hover:to-indigo-700 text-white font-semibold text-xs shadow-md transition-all active:scale-98"
            >
              <Sparkles className="size-4" />
              <span>Launch Socratic Session</span>
            </button>
          </div>

          {/* Quick Attendance Summary Card */}
          <div
            id="attendance"
            className="p-5 rounded-2xl bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 shadow-2xs"
          >
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-bold text-neutral-900 dark:text-white flex items-center gap-2">
                <CheckSquare className="size-4 text-emerald-500" />
                Attendance Breakdown
              </h3>
              <span className="text-xs font-bold text-emerald-600 dark:text-emerald-400">
                96.4% Overall
              </span>
            </div>

            <div className="space-y-2.5 text-xs">
              <div className="flex items-center justify-between">
                <span className="text-neutral-500">Present Days</span>
                <span className="font-semibold text-neutral-800 dark:text-neutral-200">54 Days</span>
              </div>
              <div className="w-full h-1.5 rounded-full bg-neutral-100 dark:bg-neutral-800 overflow-hidden">
                <div className="h-full bg-emerald-500 rounded-full w-[96.4%]" />
              </div>

              <div className="flex items-center justify-between pt-1">
                <span className="text-neutral-500">Late Arrivals</span>
                <span className="font-semibold text-amber-600">2 Days</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-neutral-500">Excused Leaves</span>
                <span className="font-semibold text-blue-600">1 Day</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-neutral-500">Unexcused Absences</span>
                <span className="font-semibold text-neutral-400">0 Days</span>
              </div>
            </div>
          </div>

          {/* Upcoming Deadlines */}
          <div className="p-5 rounded-2xl bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 shadow-2xs">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-bold text-neutral-900 dark:text-white flex items-center gap-2">
                <Calendar className="size-4 text-amber-500" />
                Upcoming Deadlines
              </h3>
            </div>

            <div className="space-y-2.5">
              {QUICK_DEADLINES.map((d) => (
                <div
                  key={d.id}
                  className="p-2.5 rounded-xl border border-neutral-100 dark:border-neutral-800 bg-neutral-50/60 dark:bg-neutral-800/40 flex items-start justify-between gap-2"
                >
                  <div className="min-w-0">
                    <h5 className="text-xs font-bold text-neutral-900 dark:text-white truncate">
                      {d.title}
                    </h5>
                    <div className="flex items-center gap-2 text-[11px] text-neutral-500 mt-0.5">
                      <span className="font-mono text-neutral-700 dark:text-neutral-300">
                        {d.course}
                      </span>
                      <span>•</span>
                      <span className={cn(d.urgent ? 'text-rose-600 dark:text-rose-400 font-semibold' : '')}>
                        {d.dueDate}
                      </span>
                    </div>
                  </div>
                  <button className="p-1 rounded-md text-neutral-400 hover:text-blue-600 transition-colors">
                    <ArrowUpRight className="size-4" />
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Socratic AI Interactive Dialog Modal */}
      {aiModalOpen && (
        <div
          className="fixed inset-0 z-50 bg-black/70 backdrop-blur-xs flex items-center justify-center p-4 animate-in fade-in"
          role="dialog"
          aria-modal="true"
          aria-label="Socratic AI Tutor Session"
        >
          <div className="w-full max-w-2xl bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 rounded-2xl shadow-2xl flex flex-col h-[600px] overflow-hidden">
            {/* Modal Header */}
            <div className="p-4 border-b border-neutral-200 dark:border-neutral-800 flex items-center justify-between bg-neutral-50 dark:bg-neutral-800/50">
              <div className="flex items-center gap-2.5">
                <div className="size-8 rounded-lg bg-indigo-600 text-white flex items-center justify-center shadow-xs">
                  <BrainCircuit className="size-4.5" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-neutral-900 dark:text-white">
                    Socratic AI Tutor Interactive Session
                  </h3>
                  <p className="text-[11px] text-neutral-500">
                    CSG Neural Learning Engine • Grade 11 STEM
                  </p>
                </div>
              </div>
              <button
                onClick={() => setAiModalOpen(false)}
                className="p-1.5 rounded-lg text-neutral-400 hover:text-neutral-900 dark:hover:text-white hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-colors"
              >
                <X className="size-5" />
              </button>
            </div>

            {/* Chat Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {messages.map((m, idx) => (
                <div
                  key={idx}
                  className={cn(
                    'flex gap-3 max-w-[85%]',
                    m.sender === 'user' ? 'ms-auto flex-row-reverse' : ''
                  )}
                >
                  <div
                    className={cn(
                      'size-7 rounded-full flex items-center justify-center text-xs shrink-0',
                      m.sender === 'user'
                        ? 'bg-blue-600 text-white font-bold'
                        : 'bg-indigo-600 text-white'
                    )}
                  >
                    {m.sender === 'user' ? 'Z' : <Bot className="size-4" />}
                  </div>
                  <div>
                    <div
                      className={cn(
                        'p-3.5 rounded-2xl text-xs leading-relaxed',
                        m.sender === 'user'
                          ? 'bg-blue-600 text-white rounded-te-xs'
                          : 'bg-neutral-100 dark:bg-neutral-800 text-neutral-900 dark:text-neutral-100 rounded-ts-xs border border-neutral-200 dark:border-neutral-700/60'
                      )}
                    >
                      {m.text}
                    </div>
                    <span className="text-[10px] text-neutral-400 mt-1 inline-block px-1">
                      {m.time}
                    </span>
                  </div>
                </div>
              ))}
            </div>

            {/* Chat Input */}
            <form
              onSubmit={handleSendAiMessage}
              className="p-3 border-t border-neutral-200 dark:border-neutral-800 bg-neutral-50/50 dark:bg-neutral-900 flex items-center gap-2"
            >
              <input
                type="text"
                value={aiPrompt}
                onChange={(e) => setAiPrompt(e.target.value)}
                placeholder="Type your question or thought here..."
                className="flex-1 px-3.5 py-2.5 rounded-xl border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-800 text-xs text-neutral-900 dark:text-white placeholder:text-neutral-400 focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
              />
              <button
                type="submit"
                disabled={!aiPrompt.trim()}
                className="p-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white transition-colors flex items-center justify-center shrink-0"
              >
                <Send className="size-4" />
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
