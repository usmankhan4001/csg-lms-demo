'use client'

import React, { useState } from 'react'
import Link from 'next/link'
import {
  Sparkles,
  BookOpen,
  Calendar,
  Clock,
  Award,
  Flame,
  CheckCircle2,
  ChevronRight,
  BrainCircuit,
  Lightbulb,
  ArrowUpRight,
  TrendingUp,
  HelpCircle,
  Play,
  ShieldCheck,
  Star,
  Zap,
  Target
} from 'lucide-react'
import { useOrgMembership, useOrg } from '@components/Contexts/OrgContext'
import { PersonaSwitcher } from '@/components/ems/PersonaSwitcher'
import { SocraticLearnerStudio } from '@/modules/ems/tutor/SocraticLearnerStudio'

export default function LearnerPortalPage() {
  const { orgslug } = useOrgMembership()
  const org = useOrg() as any

  const [activeTab, setActiveTab] = useState<'flightplan' | 'aitutor' | 'mastery'>('flightplan')
  const [selectedTaskTier, setSelectedTaskTier] = useState<1 | 2 | 3>(1)

  // Enrolled courses
  const enrolledCourses = [
    {
      id: 'c1',
      title: 'AP Physics C: Mechanics & Waves',
      instructor: 'Dr. Evelyn Cross',
      progress: 78,
      nextAssignment: 'Harmonic Oscillators Lab',
      due: 'Today, 23:59',
      grade: '94.5%',
      color: 'from-blue-500 to-indigo-600',
    },
    {
      id: 'c2',
      title: 'Multivariable Calculus & Linear Algebra',
      instructor: 'Prof. Marcus Bell',
      progress: 84,
      nextAssignment: 'Eigenvector Problem Set #4',
      due: 'Tomorrow, 16:00',
      grade: '91.0%',
      color: 'from-amber-500 to-orange-600',
    },
    {
      id: 'c3',
      title: 'Autonomous Robotics & Python Control',
      instructor: 'Sarah Jenkins, M.Sc.',
      progress: 65,
      nextAssignment: 'PID Controller Simulation',
      due: 'Friday',
      grade: '98.0%',
      color: 'from-emerald-500 to-teal-600',
    },
  ]

  // Competency mastery nodes
  const masteryNodes = [
    { subject: 'Quantum Theory & Waves', level: 'Mastered', score: 96, xp: 450, icon: '⚛️' },
    { subject: 'Vector Calculus', level: 'Proficient', score: 88, xp: 320, icon: '📐' },
    { subject: 'Robotics Kinematics', level: 'Mastered', score: 95, xp: 500, icon: '🤖' },
    { subject: 'Organic Synthesis Reactions', level: 'In Progress', score: 74, xp: 180, icon: '🧪' },
  ]

  return (
    <div className="flex flex-col min-h-screen">
      {/* Persona Header Switcher */}
      <PersonaSwitcher
        currentPortal="learner"
        breadcrumbs={[{ label: 'Learner Hub' }]}
        actions={
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1.5 rounded-full bg-amber-50 px-3 py-1 text-xs font-bold text-amber-800 border border-amber-200">
              <Flame className="size-4 text-orange-500 animate-bounce" />
              <span>14-Day Streak</span>
            </div>
            <div className="flex items-center gap-1 rounded-full bg-indigo-50 px-3 py-1 text-xs font-bold text-indigo-800 border border-indigo-200">
              <Zap className="size-3.5 text-indigo-600" />
              <span>1,850 XP</span>
            </div>
          </div>
        }
      />

      <main className="mx-auto w-full max-w-7xl px-4 py-8 sm:px-6 lg:px-8 space-y-8">
        {/* Top Header & Tab Navigation */}
        <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-black tracking-tight text-gray-900 sm:text-3xl">
                Learner Hub & Daily Flight Plan
              </h1>
              <span className="rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-extrabold text-amber-800 border border-amber-200">
                Grade 11 Scholar
              </span>
            </div>
            <p className="mt-1 text-sm text-gray-500">
              My schedule, course deadlines, 3-tier Socratic tutor & competency mastery tree.
            </p>
          </div>

          <div className="flex items-center rounded-xl bg-gray-100 p-1 border border-gray-200">
            <button
              onClick={() => setActiveTab('flightplan')}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold transition ${
                activeTab === 'flightplan'
                  ? 'bg-white text-gray-900 shadow-xs'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              <Calendar className="size-3.5" />
              <span>Flight Plan & Courses</span>
            </button>
            <button
              onClick={() => setActiveTab('aitutor')}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold transition ${
                activeTab === 'aitutor'
                  ? 'bg-white text-gray-900 shadow-xs'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              <Sparkles className="size-3.5 text-amber-500" />
              <span>Socratic AI Companion</span>
            </button>
            <button
              onClick={() => setActiveTab('mastery')}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold transition ${
                activeTab === 'mastery'
                  ? 'bg-white text-gray-900 shadow-xs'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              <Target className="size-3.5" />
              <span>Mastery Graph</span>
            </button>
          </div>
        </div>

        {/* Tab 1: Flight Plan & Courses */}
        {activeTab === 'flightplan' && (
          <div className="space-y-8">
            {/* Daily Schedule Banner */}
            <div className="rounded-3xl border border-amber-200 bg-gradient-to-r from-amber-500/10 via-orange-500/5 to-transparent p-6 sm:p-7 space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div className="flex size-10 items-center justify-center rounded-2xl bg-amber-500 text-white shadow-sm font-bold">
                    <Clock className="size-5" />
                  </div>
                  <div>
                    <h2 className="text-base font-black text-gray-900">Today's Flight Plan</h2>
                    <p className="text-xs text-gray-600">Tuesday, Sep 15 • Period 2 starts in 25 minutes</p>
                  </div>
                </div>
                <span className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-bold text-emerald-800 border border-emerald-200 self-start sm:self-auto">
                  Roll-Call: Present (On-Time)
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2">
                <div className="rounded-2xl bg-white p-4 border border-gray-200 shadow-2xs">
                  <span className="text-[10px] font-bold text-gray-400 uppercase">Period 1 (Completed)</span>
                  <p className="font-bold text-sm text-gray-800 mt-1">AP Physics C</p>
                  <span className="text-xs text-emerald-600 font-semibold">Attendance Logged</span>
                </div>
                <div className="rounded-2xl bg-white p-4 border-2 border-amber-400 shadow-xs ring-2 ring-amber-400/20">
                  <span className="text-[10px] font-bold text-amber-600 uppercase">Period 2 (10:00 - 11:15)</span>
                  <p className="font-bold text-sm text-gray-900 mt-1">Robotics Lab B</p>
                  <span className="text-xs text-amber-700 font-semibold">Bring Project Breadboard</span>
                </div>
                <div className="rounded-2xl bg-white p-4 border border-gray-200 shadow-2xs">
                  <span className="text-[10px] font-bold text-gray-400 uppercase">Period 4 (13:00 - 14:15)</span>
                  <p className="font-bold text-sm text-gray-800 mt-1">Honors Calculus</p>
                  <span className="text-xs text-gray-500 font-semibold">Room 210</span>
                </div>
              </div>
            </div>

            {/* Active Courses Grid */}
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-black text-gray-900">My Active Courses & Quests</h3>
                <span className="text-xs text-gray-500">Term 2 Progress</span>
              </div>

              <div className="grid grid-cols-1 gap-5 md:grid-cols-3">
                {enrolledCourses.map((course) => (
                  <div
                    key={course.id}
                    className="flex flex-col justify-between rounded-3xl border border-gray-200 bg-white p-6 shadow-xs transition hover:shadow-md hover:border-gray-300"
                  >
                    <div>
                      <div className="flex items-center justify-between">
                        <span className="rounded-full bg-gray-100 px-2.5 py-0.5 text-[11px] font-bold text-gray-700">
                          {course.grade} Grade
                        </span>
                        <span className="font-mono text-xs font-bold text-indigo-600">
                          {course.progress}%
                        </span>
                      </div>

                      <h4 className="mt-3 text-base font-bold text-gray-900 leading-snug">
                        {course.title}
                      </h4>
                      <p className="mt-1 text-xs text-gray-400">{course.instructor}</p>

                      <div className="mt-4 h-2 w-full overflow-hidden rounded-full bg-gray-100">
                        <div
                          className="h-full rounded-full bg-gradient-to-r from-amber-500 to-indigo-600"
                          style={{ width: `${course.progress}%` }}
                        />
                      </div>
                    </div>

                    <div className="mt-6 border-t border-gray-100 pt-4">
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-gray-500">Next Due:</span>
                        <span className="font-bold text-rose-600">{course.due}</span>
                      </div>
                      <p className="text-xs font-semibold text-gray-800 truncate mt-0.5">
                        {course.nextAssignment}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* 3-Tier Homework Assistant Interactive Feature */}
            <div className="rounded-3xl border border-indigo-200/80 bg-white p-6 sm:p-8 shadow-xs space-y-6">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-gray-100 pb-4">
                <div>
                  <div className="flex items-center gap-2">
                    <BrainCircuit className="size-5 text-indigo-600" />
                    <h3 className="text-base font-black text-gray-900">
                      3-Tier Adaptive Homework Scaffold
                    </h3>
                  </div>
                  <p className="text-xs text-gray-500 mt-0.5">
                    Safe cognitive assistance that fosters genuine mastery without spoon-feeding answers.
                  </p>
                </div>

                {/* Tier Selector */}
                <div className="flex items-center rounded-xl bg-indigo-50 p-1 border border-indigo-100">
                  <button
                    onClick={() => setSelectedTaskTier(1)}
                    className={`rounded-lg px-2.5 py-1 text-xs font-bold transition ${
                      selectedTaskTier === 1
                        ? 'bg-indigo-600 text-white shadow-2xs'
                        : 'text-indigo-800 hover:bg-indigo-100'
                    }`}
                  >
                    Tier 1: Socratic Hint
                  </button>
                  <button
                    onClick={() => setSelectedTaskTier(2)}
                    className={`rounded-lg px-2.5 py-1 text-xs font-bold transition ${
                      selectedTaskTier === 2
                        ? 'bg-indigo-600 text-white shadow-2xs'
                        : 'text-indigo-800 hover:bg-indigo-100'
                    }`}
                  >
                    Tier 2: Step Scaffold
                  </button>
                  <button
                    onClick={() => setSelectedTaskTier(3)}
                    className={`rounded-lg px-2.5 py-1 text-xs font-bold transition ${
                      selectedTaskTier === 3
                        ? 'bg-indigo-600 text-white shadow-2xs'
                        : 'text-indigo-800 hover:bg-indigo-100'
                    }`}
                  >
                    Tier 3: Verify Solution
                  </button>
                </div>
              </div>

              {/* Tier Content Display */}
              <div className="rounded-2xl bg-gray-50 p-5 border border-gray-200/70 space-y-3">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-bold text-gray-700">Problem: Harmonic Resonance of Damped Springs</span>
                  <span className="text-gray-400 font-mono">Physics C #8.2</span>
                </div>

                {selectedTaskTier === 1 && (
                  <div className="space-y-2 text-xs text-gray-700">
                    <p className="font-semibold text-indigo-900">💡 Conceptual Socratic Question:</p>
                    <p className="bg-white p-3 rounded-xl border border-indigo-100 italic">
                      "What happens to the total mechanical energy in a damped harmonic oscillator over time, and how does the damping coefficient b affect the exponential envelope?"
                    </p>
                  </div>
                )}

                {selectedTaskTier === 2 && (
                  <div className="space-y-2 text-xs text-gray-700">
                    <p className="font-semibold text-indigo-900">🧩 Structural Step-by-Step Breakdown:</p>
                    <ol className="list-decimal list-inside space-y-1 bg-white p-3 rounded-xl border border-indigo-100">
                      <li>Set up Newton's second law: <code className="font-mono bg-gray-100 px-1">m(d²x/dt²) + b(dx/dt) + kx = 0</code></li>
                      <li>Find the characteristic roots of the differential equation.</li>
                      <li>Classify whether the system is underdamped (<code className="font-mono bg-gray-100 px-1">b² &lt; 4mk</code>) or overdamped.</li>
                    </ol>
                  </div>
                )}

                {selectedTaskTier === 3 && (
                  <div className="space-y-2 text-xs text-gray-700">
                    <p className="font-semibold text-indigo-900">✅ Solution Verification & Error Check:</p>
                    <p className="bg-white p-3 rounded-xl border border-indigo-100">
                      Enter your calculated angular frequency <code className="font-mono bg-gray-100 px-1">ω'</code> to check for dimensional consistency and sign errors before final submission.
                    </p>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Tab 2: Socratic AI Companion Studio */}
        {activeTab === 'aitutor' && (
          <div className="space-y-4">
            <SocraticLearnerStudio
              studentId="stu-104"
              subjectTitle="AP Physics C & Advanced Mechanics"
              dailyMinutesBudget={60}
              initialMinutesUsed={18}
            />
          </div>
        )}

        {/* Tab 3: Mastery Graph & Badges */}
        {activeTab === 'mastery' && (
          <div className="space-y-8">
            <div className="rounded-3xl border border-gray-200 bg-white p-6 sm:p-8 shadow-xs space-y-6">
              <div className="flex items-center justify-between border-b border-gray-100 pb-4">
                <div>
                  <h3 className="text-lg font-black text-gray-900">Competency Skill Graph</h3>
                  <p className="text-xs text-gray-400">Autonomous concept mastery measured across all coursework</p>
                </div>
                <span className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-bold text-emerald-800">
                  Overall Mastery: 92.4%
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {masteryNodes.map((node) => (
                  <div
                    key={node.subject}
                    className="rounded-2xl border border-gray-200 bg-gray-50/50 p-4 transition hover:bg-white hover:shadow-xs"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2.5">
                        <span className="text-xl">{node.icon}</span>
                        <div>
                          <h4 className="text-xs font-bold text-gray-900">{node.subject}</h4>
                          <span className="text-[10px] text-gray-500 font-semibold">{node.level}</span>
                        </div>
                      </div>
                      <span className="text-xs font-mono font-black text-indigo-600">
                        {node.score}%
                      </span>
                    </div>

                    <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-gray-200">
                      <div
                        className="h-full rounded-full bg-indigo-600"
                        style={{ width: `${node.score}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
