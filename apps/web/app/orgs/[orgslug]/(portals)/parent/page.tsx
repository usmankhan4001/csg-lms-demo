'use client'

import React, { useState } from 'react'
import Link from 'next/link'
import {
  HeartHandshake,
  Users,
  CreditCard,
  FileText,
  Clock,
  ShieldCheck,
  CheckCircle2,
  AlertCircle,
  Calendar,
  DollarSign,
  Download,
  Sliders,
  Send,
  Sparkles,
  ChevronRight,
  User,
  GraduationCap,
  ShieldAlert,
  Moon,
  Lock
} from 'lucide-react'
import { useOrgMembership, useOrg } from '@components/Contexts/OrgContext'
import { PersonaSwitcher } from '@/components/ems/PersonaSwitcher'

interface Ward {
  id: number
  name: string
  grade: string
  section: string
  avatar: string
  attendanceToday: 'PRESENT' | 'LATE' | 'ABSENT'
  gpa: string
  outstandingFee: number
  aiDailyMinutesUsed: number
  aiDailyCapMinutes: number
}

export default function ParentPortalPage() {
  const { orgslug } = useOrgMembership()
  const org = useOrg() as any

  // Multi-child switcher state
  const wards: Ward[] = [
    {
      id: 1,
      name: 'Maya Chen',
      grade: 'Grade 10',
      section: 'Section B',
      avatar: 'MC',
      attendanceToday: 'PRESENT',
      gpa: '3.92',
      outstandingFee: 420.0,
      aiDailyMinutesUsed: 28,
      aiDailyCapMinutes: 45,
    },
    {
      id: 2,
      name: 'Lucas Chen',
      grade: 'Grade 7',
      section: 'Section A',
      avatar: 'LC',
      attendanceToday: 'PRESENT',
      gpa: '3.85',
      outstandingFee: 0.0,
      aiDailyMinutesUsed: 15,
      aiDailyCapMinutes: 30,
    },
  ]

  const [selectedWardId, setSelectedWardId] = useState<number>(1)
  const currentWard = wards.find((w) => w.id === selectedWardId) ?? wards[0]

  // Absence submission form state
  const [absenceReason, setAbsenceReason] = useState('')
  const [absenceDate, setAbsenceDate] = useState('2026-09-18')
  const [absenceCategory, setAbsenceCategory] = useState<'MEDICAL' | 'FAMILY' | 'RELIGIOUS' | 'OTHER'>('MEDICAL')
  const [submittedAbsence, setSubmittedAbsence] = useState(false)

  // AI Screen-Time Caps state
  const [aiCap, setAiCap] = useState(currentWard.aiDailyCapMinutes)
  const [bedtimeCurfew, setBedtimeCurfew] = useState(true)

  // Payment processing state
  const [isPaying, setIsPaying] = useState(false)
  const [paymentSuccess, setPaymentSuccess] = useState(false)

  const handlePay = () => {
    setIsPaying(true)
    setTimeout(() => {
      setIsPaying(false)
      setPaymentSuccess(true)
    }, 1200)
  }

  const handleSubmitAbsence = (e: React.FormEvent) => {
    e.preventDefault()
    setSubmittedAbsence(true)
    setTimeout(() => setSubmittedAbsence(false), 4000)
    setAbsenceReason('')
  }

  return (
    <div className="flex flex-col min-h-screen">
      {/* Persona Header Switcher */}
      <PersonaSwitcher
        currentPortal="parent"
        breadcrumbs={[{ label: 'Parent Gateway' }]}
        actions={
          <div className="flex items-center gap-2">
            <span className="rounded-full bg-rose-50 px-3 py-1 text-xs font-bold text-rose-800 border border-rose-200">
              Verified Guardian
            </span>
          </div>
        }
      />

      <main className="mx-auto w-full max-w-7xl px-4 py-8 sm:px-6 lg:px-8 space-y-8">
        {/* Top Ward Selector Header */}
        <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-black tracking-tight text-gray-900 sm:text-3xl">
                Parent Gateway
              </h1>
              <span className="rounded-full bg-rose-100 px-2.5 py-0.5 text-xs font-extrabold text-rose-800 border border-rose-200">
                {wards.length} Wards Enrolled
              </span>
            </div>
            <p className="mt-1 text-sm text-gray-500">
              Real-time student timelines, frictionless fee payment, absence excuses & safe AI screen-time caps.
            </p>
          </div>

          {/* Child Switcher Pills */}
          <div className="flex items-center gap-2 rounded-2xl bg-white p-1.5 border border-gray-200 shadow-xs">
            {wards.map((ward) => {
              const isSelected = ward.id === selectedWardId
              return (
                <button
                  key={ward.id}
                  onClick={() => {
                    setSelectedWardId(ward.id)
                    setAiCap(ward.aiDailyCapMinutes)
                  }}
                  className={`flex items-center gap-2 rounded-xl px-3.5 py-2 text-xs font-bold transition ${
                    isSelected
                      ? 'bg-rose-600 text-white shadow-xs'
                      : 'text-gray-600 hover:bg-gray-100'
                  }`}
                >
                  <div
                    className={`flex size-5 items-center justify-center rounded-full text-[10px] font-black ${
                      isSelected ? 'bg-white text-rose-700' : 'bg-rose-100 text-rose-800'
                    }`}
                  >
                    {ward.avatar}
                  </div>
                  <span>{ward.name}</span>
                  <span className={`text-[10px] ${isSelected ? 'text-rose-100' : 'text-gray-400'}`}>
                    ({ward.grade})
                  </span>
                </button>
              )
            })}
          </div>
        </div>

        {/* Selected Ward Snapshot Banner */}
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-xs">
            <span className="text-xs font-bold uppercase tracking-wider text-gray-400">Attendance Today</span>
            <div className="mt-2 flex items-center justify-between">
              <span className="text-xl font-black text-gray-900">Present (On Time)</span>
              <div className="flex size-7 items-center justify-center rounded-full bg-emerald-100 text-emerald-700">
                <CheckCircle2 className="size-4" />
              </div>
            </div>
            <p className="mt-1 text-xs text-gray-400">Arrived 08:14 AM • RFID Tap Verified</p>
          </div>

          <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-xs">
            <span className="text-xs font-bold uppercase tracking-wider text-gray-400">Academic Standing</span>
            <div className="mt-2 flex items-center justify-between">
              <span className="text-xl font-black text-gray-900">{currentWard.gpa} GPA</span>
              <div className="flex size-7 items-center justify-center rounded-full bg-indigo-100 text-indigo-700">
                <GraduationCap className="size-4" />
              </div>
            </div>
            <p className="mt-1 text-xs text-emerald-600 font-semibold">Honors Roll Standing</p>
          </div>

          <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-xs">
            <span className="text-xs font-bold uppercase tracking-wider text-gray-400">Term 2 Tuition Balance</span>
            <div className="mt-2 flex items-center justify-between">
              <span className="text-xl font-black text-gray-900">
                {currentWard.outstandingFee > 0 && !paymentSuccess
                  ? `$${currentWard.outstandingFee.toFixed(2)}`
                  : '$0.00'}
              </span>
              <div
                className={`flex size-7 items-center justify-center rounded-full ${
                  currentWard.outstandingFee > 0 && !paymentSuccess
                    ? 'bg-amber-100 text-amber-700'
                    : 'bg-emerald-100 text-emerald-700'
                }`}
              >
                <DollarSign className="size-4" />
              </div>
            </div>
            <p className="mt-1 text-xs text-gray-400">
              {currentWard.outstandingFee > 0 && !paymentSuccess ? 'Due Sep 30' : 'All Dues Cleared'}
            </p>
          </div>

          <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-xs">
            <span className="text-xs font-bold uppercase tracking-wider text-gray-400">AI Tutor Screen-Time</span>
            <div className="mt-2 flex items-center justify-between">
              <span className="text-xl font-black text-gray-900">
                {currentWard.aiDailyMinutesUsed}m / {aiCap}m
              </span>
              <div className="flex size-7 items-center justify-center rounded-full bg-purple-100 text-purple-700">
                <Sparkles className="size-4" />
              </div>
            </div>
            <p className="mt-1 text-xs text-purple-600 font-semibold">Protected Guardian Controls</p>
          </div>
        </div>

        {/* Middle Section: Live Timeline & 1-Click Fee Statement */}
        <div className="grid grid-cols-1 gap-8 lg:grid-cols-12">
          {/* Ward Learning Timeline (7 cols) */}
          <div className="rounded-3xl border border-gray-200/90 bg-white p-6 shadow-xs lg:col-span-7 space-y-6">
            <div className="flex items-center justify-between border-b border-gray-100 pb-4">
              <div>
                <h3 className="text-base font-bold text-gray-900">
                  {currentWard.name}'s Real-Time Timeline
                </h3>
                <p className="text-xs text-gray-400">Daily learning milestones & announcements</p>
              </div>
              <span className="rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-semibold text-gray-600">
                Live Feed
              </span>
            </div>

            <div className="space-y-4">
              {[
                {
                  time: '08:30 AM',
                  title: 'Attended AP Physics C: Harmonic Resonance Lab',
                  desc: 'Completed group oscillator experiment. Teacher marked exemplary engagement.',
                  tag: 'Academics',
                  tone: 'border-blue-500 bg-blue-50/50',
                },
                {
                  time: '11:15 AM',
                  title: 'Grade Published: Calculus Midterm Assessment',
                  desc: 'Score: 96/100 (Grade: A+). Feedback: "Superb analytical derivation in matrix transforms."',
                  tag: 'Grades',
                  tone: 'border-emerald-500 bg-emerald-50/50',
                },
                {
                  time: '14:00 PM',
                  title: 'Library Book Loan: "Quantum Mechanics & Wave Packets"',
                  desc: 'Due date: October 5, 2026. Checked out from Central Campus Library.',
                  tag: 'Library',
                  tone: 'border-purple-500 bg-purple-50/50',
                },
              ].map((item, idx) => (
                <div
                  key={idx}
                  className={`rounded-2xl border-l-4 p-4 ${item.tone} border-gray-200 bg-white shadow-2xs space-y-1`}
                >
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-mono text-gray-400 font-medium">{item.time}</span>
                    <span className="rounded bg-gray-100 px-1.5 py-0.5 text-[10px] font-bold text-gray-700">
                      {item.tag}
                    </span>
                  </div>
                  <h4 className="text-xs font-bold text-gray-900">{item.title}</h4>
                  <p className="text-xs text-gray-600">{item.desc}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Fee Statement & 1-Click Pay (5 cols) */}
          <div className="rounded-3xl border border-gray-200/90 bg-white p-6 shadow-xs lg:col-span-5 space-y-6">
            <div className="flex items-center justify-between border-b border-gray-100 pb-4">
              <div>
                <h3 className="text-base font-bold text-gray-900">Fee Statement & Dues</h3>
                <p className="text-xs text-gray-400">Official statement for {currentWard.name}</p>
              </div>
              <button
                onClick={() => alert('Downloading PDF receipt...')}
                className="text-xs font-bold text-gray-500 hover:text-gray-900 flex items-center gap-1"
              >
                <Download className="size-3.5" />
                <span>PDF</span>
              </button>
            </div>

            {currentWard.outstandingFee > 0 && !paymentSuccess ? (
              <div className="space-y-4">
                <div className="rounded-2xl border border-amber-200 bg-amber-50/50 p-4 space-y-2">
                  <div className="flex justify-between text-xs">
                    <span className="text-gray-600">Term 2 STEM Lab & Technology Fee</span>
                    <span className="font-bold text-gray-900">$220.00</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-gray-600">Co-Curricular Robotics Competition Pass</span>
                    <span className="font-bold text-gray-900">$200.00</span>
                  </div>
                  <div className="border-t border-amber-200/60 pt-2 flex justify-between text-sm font-black text-gray-900">
                    <span>Total Outstanding</span>
                    <span className="text-rose-600">${currentWard.outstandingFee.toFixed(2)}</span>
                  </div>
                </div>

                <button
                  type="button"
                  disabled={isPaying}
                  onClick={handlePay}
                  className="w-full rounded-2xl bg-gray-900 py-3 text-center text-xs font-bold text-white shadow-md hover:bg-gray-800 transition flex items-center justify-center gap-2"
                >
                  <CreditCard className="size-4" />
                  <span>{isPaying ? 'Processing Instant 1-Click Pay...' : `1-Click Pay ($${currentWard.outstandingFee.toFixed(2)})`}</span>
                </button>
              </div>
            ) : (
              <div className="rounded-2xl border border-emerald-200 bg-emerald-50/70 p-6 text-center space-y-2">
                <CheckCircle2 className="size-8 text-emerald-600 mx-auto" />
                <h4 className="text-sm font-bold text-emerald-950">Zero Balance Outstanding</h4>
                <p className="text-xs text-emerald-800">All tuition and lab fees for this academic term have been settled in full.</p>
              </div>
            )}
          </div>
        </div>

        {/* Bottom Section: Digital Absence Excuse & Guardian AI Screen-Time Caps */}
        <div className="grid grid-cols-1 gap-8 lg:grid-cols-12">
          {/* Digital Absence Submission Form (6 cols) */}
          <div className="rounded-3xl border border-gray-200/90 bg-white p-6 sm:p-7 shadow-xs lg:col-span-6 space-y-5">
            <div className="border-b border-gray-100 pb-4">
              <h3 className="text-base font-bold text-gray-900">Submit Absence Excuse Note</h3>
              <p className="text-xs text-gray-400">Digital submission to school attendance registry</p>
            </div>

            {submittedAbsence && (
              <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-xs font-bold text-emerald-800 flex items-center gap-2 animate-in fade-in">
                <CheckCircle2 className="size-4 text-emerald-600" />
                <span>Absence note for {currentWard.name} submitted directly to Head of Section.</span>
              </div>
            )}

            <form onSubmit={handleSubmitAbsence} className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-bold text-gray-700">Absence Date</label>
                  <input
                    type="date"
                    value={absenceDate}
                    onChange={(e) => setAbsenceDate(e.target.value)}
                    className="mt-1 w-full rounded-xl border border-gray-200 bg-white px-3 py-2 text-xs font-medium text-gray-900 focus:border-rose-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-gray-700">Category</label>
                  <select
                    value={absenceCategory}
                    onChange={(e) => setAbsenceCategory(e.target.value as any)}
                    className="mt-1 w-full rounded-xl border border-gray-200 bg-white px-3 py-2 text-xs font-medium text-gray-900 focus:border-rose-500 focus:outline-none"
                  >
                    <option value="MEDICAL">Medical / Doctor Appointment</option>
                    <option value="FAMILY">Family Emergency</option>
                    <option value="RELIGIOUS">Religious Observance</option>
                    <option value="OTHER">Other Excused</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-gray-700">Reason / Explanation</label>
                <textarea
                  rows={2}
                  value={absenceReason}
                  onChange={(e) => setAbsenceReason(e.target.value)}
                  placeholder="Please provide details for the form tutor..."
                  className="mt-1 w-full rounded-xl border border-gray-200 bg-white p-3 text-xs text-gray-900 focus:border-rose-500 focus:outline-none"
                  required
                />
              </div>

              <button
                type="submit"
                className="inline-flex items-center gap-2 rounded-xl bg-rose-600 px-4 py-2 text-xs font-bold text-white shadow-xs hover:bg-rose-700 transition"
              >
                <Send className="size-3.5" />
                <span>Submit Excuse Note</span>
              </button>
            </form>
          </div>

          {/* Minor AI Screen-Time & Safe Controls (6 cols) */}
          <div className="rounded-3xl border border-gray-200/90 bg-white p-6 sm:p-7 shadow-xs lg:col-span-6 space-y-5">
            <div className="border-b border-gray-100 pb-4 flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-gray-900">Guardian AI Screen-Time & Safety Caps</h3>
                <p className="text-xs text-gray-400">Controls for {currentWard.name}'s Socratic AI Tutor</p>
              </div>
              <ShieldCheck className="size-5 text-emerald-600" />
            </div>

            <div className="space-y-4">
              <div>
                <div className="flex justify-between text-xs">
                  <span className="font-bold text-gray-700">Daily Socratic AI Dialogue Budget</span>
                  <span className="font-mono font-black text-rose-600">{aiCap} Minutes</span>
                </div>
                <input
                  type="range"
                  min="15"
                  max="120"
                  step="5"
                  value={aiCap}
                  onChange={(e) => setAiCap(Number(e.target.value))}
                  className="mt-2 w-full accent-rose-600"
                />
                <div className="flex justify-between text-[10px] text-gray-400">
                  <span>15 min (Strict)</span>
                  <span>45 min (Recommended)</span>
                  <span>120 min (Extended)</span>
                </div>
              </div>

              <div className="rounded-2xl bg-gray-50 p-4 border border-gray-200/60 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="flex size-8 items-center justify-center rounded-xl bg-indigo-100 text-indigo-700">
                    <Moon className="size-4" />
                  </div>
                  <div>
                    <h4 className="text-xs font-bold text-gray-900">Bedtime AI Lockout (21:00)</h4>
                    <p className="text-[11px] text-gray-500">Pauses AI tutoring queries during sleep hours.</p>
                  </div>
                </div>
                <input
                  type="checkbox"
                  checked={bedtimeCurfew}
                  onChange={(e) => setBedtimeCurfew(e.target.checked)}
                  className="size-4 accent-rose-600 rounded"
                />
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
