'use client'

import React, { useState } from 'react'
import Link from 'next/link'
import {
  GraduationCap,
  CalendarCheck,
  CheckCircle2,
  Clock,
  Users,
  Award,
  AlertTriangle,
  Play,
  Check,
  X,
  Sparkles,
  Sliders,
  FileCheck,
  Layers,
  ChevronRight,
  BookOpen,
  ArrowRight,
  ShieldAlert,
  Save,
  MessageSquare,
  Search,
  Eye,
  BarChart2
} from 'lucide-react'
import { useOrgMembership, useOrg } from '@components/Contexts/OrgContext'
import { PersonaSwitcher } from '@/components/ems/PersonaSwitcher'
import { SpeedGraderStudio } from '@/modules/ems/speedgrader/SpeedGraderStudio'
import { TeacherOversightDesk } from '@/modules/ems/oversight/TeacherOversightDesk'

interface StudentAttendanceRecord {
  id: number
  name: string
  rollNo: string
  avatar: string
  status: 'PRESENT' | 'LATE' | 'ABSENT' | 'EXCUSED'
  pastoralFlag?: string
}

export default function TeacherPortalPage() {
  const { orgslug } = useOrgMembership()
  const org = useOrg() as any

  const [activeTab, setActiveTab] = useState<'schedule' | 'speedgrader' | 'oversight' | 'gradebook'>('schedule')
  const [selectedClass, setSelectedClass] = useState('p1-physics')
  const [isSavedToast, setIsSavedToast] = useState(false)
  const [showSpeedGraderModal, setShowSpeedGraderModal] = useState(false)

  // Live today's schedule
  const todaySchedule = [
    {
      id: 'p1-physics',
      period: 'Period 1 (08:30 - 09:45)',
      subject: 'AP Physics C: Mechanics',
      room: 'Sci-Lab 304',
      section: 'Grade 11-A',
      studentCount: 26,
      status: 'IN_PROGRESS',
      attendanceTaken: false,
    },
    {
      id: 'p2-stem',
      period: 'Period 2 (10:00 - 11:15)',
      subject: 'Robotics & Autonomous Systems',
      room: 'STEM Hub B',
      section: 'Grade 10-B',
      studentCount: 24,
      status: 'UP_NEXT',
      attendanceTaken: false,
    },
    {
      id: 'p4-honors',
      period: 'Period 4 (13:00 - 14:15)',
      subject: 'Honors Calculus & Matrix Theory',
      room: 'Room 210',
      section: 'Grade 12-A',
      studentCount: 28,
      status: 'SCHEDULED',
      attendanceTaken: false,
    },
  ]

  // Attendance Roster State for current class
  const [roster, setRoster] = useState<StudentAttendanceRecord[]>([
    { id: 101, name: 'Liam Vance', rollNo: 'PH-01', avatar: 'LV', status: 'PRESENT' },
    { id: 102, name: 'Sophia Sterling', rollNo: 'PH-02', avatar: 'SS', status: 'PRESENT' },
    { id: 103, name: 'Noah Al-Mansoor', rollNo: 'PH-03', avatar: 'NM', status: 'LATE' },
    { id: 104, name: 'Maya Chen', rollNo: 'PH-04', avatar: 'MC', status: 'PRESENT' },
    { id: 105, name: 'Julian Drake', rollNo: 'PH-05', avatar: 'JD', status: 'ABSENT', pastoralFlag: '3rd consecutive absence' },
    { id: 106, name: 'Elena Rostova', rollNo: 'PH-06', avatar: 'ER', status: 'PRESENT' },
    { id: 107, name: 'Tariq Johnson', rollNo: 'PH-07', avatar: 'TJ', status: 'EXCUSED' },
    { id: 108, name: 'Zoe Zhang', rollNo: 'PH-08', avatar: 'ZZ', status: 'PRESENT' },
  ])

  const setAllStatus = (status: 'PRESENT' | 'ABSENT') => {
    setRoster((prev) => prev.map((s) => ({ ...s, status })))
  }

  const toggleStudentStatus = (id: number) => {
    const cycle: Record<string, 'PRESENT' | 'LATE' | 'ABSENT' | 'EXCUSED'> = {
      PRESENT: 'LATE',
      LATE: 'ABSENT',
      ABSENT: 'EXCUSED',
      EXCUSED: 'PRESENT',
    }
    setRoster((prev) =>
      prev.map((s) => (s.id === id ? { ...s, status: cycle[s.status] } : s))
    )
  }

  const handleSaveAttendance = () => {
    setIsSavedToast(true)
    setTimeout(() => setIsSavedToast(false), 3000)
  }

  const counts = {
    present: roster.filter((r) => r.status === 'PRESENT').length,
    late: roster.filter((r) => r.status === 'LATE').length,
    absent: roster.filter((r) => r.status === 'ABSENT').length,
    excused: roster.filter((r) => r.status === 'EXCUSED').length,
  }

  return (
    <div className="flex flex-col min-h-screen">
      {/* Persona Header Switcher */}
      <PersonaSwitcher
        currentPortal="teacher"
        breadcrumbs={[{ label: 'Teacher Studio' }]}
        actions={
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowSpeedGraderModal(true)}
              className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3.5 py-1.5 text-xs font-semibold text-white shadow-xs hover:bg-emerald-700 transition"
            >
              <FileCheck className="size-3.5" />
              <span>Launch SpeedGrader</span>
            </button>
          </div>
        }
      />

      <main className="mx-auto w-full max-w-7xl px-4 py-8 sm:px-6 lg:px-8 space-y-8">
        {/* Top Teacher Title & Tab Strip */}
        <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-black tracking-tight text-gray-900 sm:text-3xl">
                Teacher Studio & Live Classroom
              </h1>
              <span className="rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-extrabold text-emerald-800 border border-emerald-200">
                Active Term: Fall 2026
              </span>
            </div>
            <p className="mt-1 text-sm text-gray-500">
              One-tap registers, analytical rubric speed-grading, curriculum progression & cognitive oversight desk.
            </p>
          </div>

          {/* Tab Strip */}
          <div className="flex items-center rounded-xl bg-gray-100 p-1 border border-gray-200">
            <button
              onClick={() => setActiveTab('schedule')}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold transition ${
                activeTab === 'schedule'
                  ? 'bg-white text-gray-900 shadow-xs'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              <CalendarCheck className="size-3.5" />
              <span>Today's Classes & Roll</span>
            </button>
            <button
              onClick={() => setActiveTab('speedgrader')}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold transition ${
                activeTab === 'speedgrader'
                  ? 'bg-white text-gray-900 shadow-xs'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              <FileCheck className="size-3.5" />
              <span>SpeedGrader</span>
            </button>
            <button
              onClick={() => setActiveTab('oversight')}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold transition ${
                activeTab === 'oversight'
                  ? 'bg-white text-gray-900 shadow-xs'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              <BarChart2 className="size-3.5" />
              <span>Cognitive Oversight</span>
            </button>
          </div>
        </div>

        {/* Tab 1: Schedule & Quick-Tap Attendance */}
        {activeTab === 'schedule' && (
          <div className="space-y-8">
            {/* Today's Schedule Cards */}
            <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
              {todaySchedule.map((c) => {
                const isSelected = selectedClass === c.id
                return (
                  <div
                    key={c.id}
                    onClick={() => setSelectedClass(c.id)}
                    className={`cursor-pointer rounded-2xl border p-5 transition-all ${
                      isSelected
                        ? 'border-emerald-500 bg-white ring-2 ring-emerald-500/20 shadow-md'
                        : 'border-gray-200 bg-white hover:border-gray-300 hover:shadow-sm'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-[11px] font-bold uppercase tracking-wider text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded">
                        {c.period}
                      </span>
                      {c.status === 'IN_PROGRESS' && (
                        <span className="flex items-center gap-1 text-[11px] font-extrabold text-emerald-600 animate-pulse">
                          <span className="size-2 rounded-full bg-emerald-500" /> Live Now
                        </span>
                      )}
                    </div>
                    <h3 className="mt-2 text-sm font-bold text-gray-900">{c.subject}</h3>
                    <div className="mt-3 flex items-center justify-between text-xs text-gray-500">
                      <span>{c.section} • {c.room}</span>
                      <span className="font-semibold text-gray-700">{c.studentCount} Students</span>
                    </div>
                  </div>
                )
              })}
            </div>

            {/* Quick-Tap Attendance Roster Panel */}
            <div className="rounded-3xl border border-gray-200/90 bg-white p-6 sm:p-8 shadow-xs space-y-6">
              <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center border-b border-gray-100 pb-5">
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="text-lg font-black text-gray-900">
                      Quick-Tap Attendance Register
                    </h2>
                    <span className="rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-semibold text-gray-600">
                      AP Physics C (11-A)
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-gray-500">
                    Tap any badge to cycle status (Present &rarr; Late &rarr; Absent &rarr; Excused).
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setAllStatus('PRESENT')}
                    className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-1.5 text-xs font-bold text-gray-700 hover:bg-gray-100 transition"
                  >
                    Mark All Present
                  </button>
                  <button
                    type="button"
                    onClick={handleSaveAttendance}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-4 py-1.5 text-xs font-bold text-white shadow-xs hover:bg-emerald-700 transition"
                  >
                    <Save className="size-3.5" />
                    <span>Submit Register</span>
                  </button>
                </div>
              </div>

              {/* Roster Vitals Bar */}
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <div className="rounded-xl border border-emerald-100 bg-emerald-50/50 p-3 text-center">
                  <span className="block text-[10px] font-bold uppercase text-emerald-700">Present</span>
                  <span className="text-xl font-black text-emerald-900">{counts.present}</span>
                </div>
                <div className="rounded-xl border border-amber-100 bg-amber-50/50 p-3 text-center">
                  <span className="block text-[10px] font-bold uppercase text-amber-700">Late</span>
                  <span className="text-xl font-black text-amber-900">{counts.late}</span>
                </div>
                <div className="rounded-xl border border-rose-100 bg-rose-50/50 p-3 text-center">
                  <span className="block text-[10px] font-bold uppercase text-rose-700">Absent</span>
                  <span className="text-xl font-black text-rose-900">{counts.absent}</span>
                </div>
                <div className="rounded-xl border border-blue-100 bg-blue-50/50 p-3 text-center">
                  <span className="block text-[10px] font-bold uppercase text-blue-700">Excused</span>
                  <span className="text-xl font-black text-blue-900">{counts.excused}</span>
                </div>
              </div>

              {/* Saved feedback banner */}
              {isSavedToast && (
                <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-xs font-bold text-emerald-800 flex items-center gap-2 animate-in fade-in">
                  <CheckCircle2 className="size-4 text-emerald-600" />
                  <span>Register successfully committed to SIS Attendance records and SMS alerts dispatched.</span>
                </div>
              )}

              {/* Student Roll Table */}
              <div className="overflow-hidden rounded-2xl border border-gray-200">
                <table className="w-full text-left text-xs">
                  <thead className="border-b border-gray-200 bg-gray-50/70 text-gray-500 font-semibold">
                    <tr>
                      <th className="px-4 py-3">Roll #</th>
                      <th className="px-4 py-3">Student Name</th>
                      <th className="px-4 py-3">Attendance Status (Tap to Change)</th>
                      <th className="px-4 py-3 text-right">Pastoral Notes</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 bg-white">
                    {roster.map((student) => (
                      <tr key={student.id} className="hover:bg-gray-50/60 transition">
                        <td className="px-4 py-3 font-mono font-bold text-gray-400">{student.rollNo}</td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2.5">
                            <div className="flex size-7 items-center justify-center rounded-full bg-emerald-100 font-bold text-emerald-800 text-xs">
                              {student.avatar}
                            </div>
                            <span className="font-bold text-gray-900">{student.name}</span>
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <button
                            type="button"
                            onClick={() => toggleStudentStatus(student.id)}
                            className={`inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-bold transition shadow-2xs ${
                              student.status === 'PRESENT'
                                ? 'bg-emerald-100 text-emerald-800 border border-emerald-200'
                                : student.status === 'LATE'
                                ? 'bg-amber-100 text-amber-800 border border-amber-200'
                                : student.status === 'ABSENT'
                                ? 'bg-rose-100 text-rose-800 border border-rose-200'
                                : 'bg-blue-100 text-blue-800 border border-blue-200'
                            }`}
                          >
                            {student.status === 'PRESENT' && <Check className="size-3" />}
                            {student.status === 'LATE' && <Clock className="size-3" />}
                            {student.status === 'ABSENT' && <X className="size-3" />}
                            {student.status}
                          </button>
                        </td>
                        <td className="px-4 py-3 text-right">
                          {student.pastoralFlag ? (
                            <span className="inline-flex items-center gap-1 rounded-full bg-rose-50 px-2.5 py-0.5 text-[11px] font-semibold text-rose-700 border border-rose-200">
                              <ShieldAlert className="size-3" />
                              {student.pastoralFlag}
                            </span>
                          ) : (
                            <span className="text-gray-300">—</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* Tab 2: SpeedGrader Embedded */}
        {activeTab === 'speedgrader' && (
          <div className="space-y-4">
            <div className="rounded-2xl border border-emerald-200 bg-emerald-50/60 p-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="flex size-8 items-center justify-center rounded-lg bg-emerald-600 text-white shadow-xs">
                  <FileCheck className="size-4" />
                </div>
                <div>
                  <h3 className="text-xs font-bold text-emerald-950">SpeedGrader & Rubric Scoring Suite</h3>
                  <p className="text-[11px] text-emerald-700">Analytical grading with automated late penalties and AI critique drafts.</p>
                </div>
              </div>
            </div>
            <SpeedGraderStudio />
          </div>
        )}

        {/* Tab 3: Cognitive Oversight Desk Embedded */}
        {activeTab === 'oversight' && (
          <div className="space-y-4">
            <TeacherOversightDesk />
          </div>
        )}

        {/* Modal SpeedGrader overlay if launched via header */}
        {showSpeedGraderModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-xs">
            <div className="relative max-h-[92vh] w-full max-w-6xl overflow-y-auto rounded-3xl bg-white p-6 shadow-2xl">
              <div className="flex items-center justify-between border-b border-gray-100 pb-4 mb-4">
                <h3 className="text-lg font-bold text-gray-900">SpeedGrader Studio</h3>
                <button
                  onClick={() => setShowSpeedGraderModal(false)}
                  className="rounded-lg p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-700"
                >
                  <X className="size-5" />
                </button>
              </div>
              <SpeedGraderStudio />
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
