'use client'

import React, { useState } from 'react'
import Link from 'next/link'
import {
  Compass,
  TrendingUp,
  DollarSign,
  Users,
  ShieldCheck,
  AlertTriangle,
  Award,
  Sparkles,
  Download,
  RefreshCw,
  Layers,
  ArrowUpRight,
  ArrowDownRight,
  ChevronRight,
  BarChart3,
  Calendar,
  Building2,
  CheckCircle2,
  PieChart,
  BrainCircuit,
  Activity,
  UserCheck,
  Clock,
  Briefcase
} from 'lucide-react'
import { useOrgMembership, useOrg } from '@components/Contexts/OrgContext'
import { PersonaSwitcher } from '@/components/ems/PersonaSwitcher'
import { useSchoolSession } from '@/lib/api/useSchoolSession'

export default function ExecutivePortalPage() {
  const { orgslug } = useOrgMembership()
  const org = useOrg() as any
  const { session: schoolSession } = useSchoolSession()
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [selectedDept, setSelectedDept] = useState<'all' | 'stem' | 'humanities' | 'arts' | 'languages'>('all')

  const handleRefresh = () => {
    setIsRefreshing(true)
    setTimeout(() => setIsRefreshing(false), 600)
  }

  // AMI Pillars
  const amiPillars = [
    { title: 'Curriculum Mastery', score: 96.2, change: '+2.4%', tone: 'emerald', benchmark: 'Top 2% Globally' },
    { title: 'Self-Directed Autonomy', score: 92.4, change: '+4.1%', tone: 'indigo', benchmark: 'Exceeds Goal' },
    { title: 'Operational Friction Delta', score: 98.1, change: '+1.2%', tone: 'teal', benchmark: 'Zero Bottlenecks' },
    { title: 'Net Tuition Realization', score: 94.8, change: '+3.0%', tone: 'blue', benchmark: '$18,450/seat' },
    { title: 'Faculty Workload Health', score: 91.5, change: '+5.5%', tone: 'purple', benchmark: 'Low Burnout' },
  ]

  // Faculty Department Radar Data
  const facultyWorkloads = [
    { dept: 'STEM & Robotics', facultyCount: 24, avgHours: 26.5, gradingLoad: 'Moderate', healthScore: 92, risk: 'Low' },
    { dept: 'Humanities & Social Sciences', facultyCount: 18, avgHours: 24.0, gradingLoad: 'High', healthScore: 89, risk: 'Moderate' },
    { dept: 'Languages & Literature', facultyCount: 16, avgHours: 25.5, gradingLoad: 'High', healthScore: 88, risk: 'Moderate' },
    { dept: 'Fine Arts & Music', facultyCount: 10, avgHours: 21.0, gradingLoad: 'Low', healthScore: 96, risk: 'Optimal' },
    { dept: 'Physical & Health Education', facultyCount: 8, avgHours: 22.0, gradingLoad: 'Low', healthScore: 97, risk: 'Optimal' },
  ]

  return (
    <div className="flex flex-col min-h-screen">
      {/* Persona Header Switcher */}
      <PersonaSwitcher
        currentPortal="executive"
        breadcrumbs={[{ label: 'Executive Leadership Console' }]}
        actions={
          <div className="flex items-center gap-2">
            <button
              onClick={handleRefresh}
              disabled={isRefreshing}
              className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-xs font-semibold text-gray-700 shadow-2xs hover:bg-gray-50 transition"
            >
              <RefreshCw className={`size-3.5 ${isRefreshing ? 'animate-spin text-indigo-600' : ''}`} />
              <span className="hidden sm:inline">Refresh Data</span>
            </button>
            <button
              onClick={() => alert('Exporting Executive Board Briefing PDF (ISO 27001 Certified)...')}
              className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3.5 py-1.5 text-xs font-semibold text-white shadow-xs hover:bg-indigo-700 transition"
            >
              <Download className="size-3.5" />
              <span>Board Pack</span>
            </button>
          </div>
        }
      />

      {/* Main Content Area */}
      <main className="mx-auto w-full max-w-7xl px-4 py-8 sm:px-6 lg:px-8 space-y-8">
        {/* Top Executive Summary Header */}
        <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-black tracking-tight text-gray-900 sm:text-3xl">
                Executive Leadership Console
              </h1>
              <span className="rounded-full bg-indigo-100 px-2.5 py-0.5 text-xs font-extrabold text-indigo-800 border border-indigo-200">
                AMI Tier: AAA
              </span>
            </div>
            <p className="mt-1 text-sm text-gray-500">
              Autonomous Mastery Index, institutional solvency, enrollment yield & faculty workload telemetry for {org?.name || 'School System'}.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <Link
              href={`/orgs/${orgslug}/admissions`}
              className="inline-flex items-center gap-1.5 text-xs font-semibold text-indigo-600 hover:text-indigo-800 transition"
            >
              <span>Admissions CRM</span>
              <ArrowUpRight className="size-3.5" />
            </Link>
            <span className="text-gray-300">|</span>
            <Link
              href={`/orgs/${orgslug}/operations`}
              className="inline-flex items-center gap-1.5 text-xs font-semibold text-indigo-600 hover:text-indigo-800 transition"
            >
              <span>Operations Desk</span>
              <ArrowUpRight className="size-3.5" />
            </Link>
          </div>
        </div>

        {/* Hero AMI Index Card */}
        <div className="relative overflow-hidden rounded-3xl border border-indigo-100 bg-gradient-to-br from-indigo-900 via-indigo-950 to-slate-900 p-6 sm:p-8 text-white shadow-xl">
          <div className="absolute right-0 top-0 -mt-12 -mr-12 size-96 rounded-full bg-indigo-500/10 blur-3xl pointer-events-none" />
          
          <div className="grid grid-cols-1 gap-8 lg:grid-cols-12 lg:items-center">
            {/* Left Score Block */}
            <div className="space-y-4 lg:col-span-4">
              <div className="inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1 text-xs font-semibold text-indigo-200 backdrop-blur-md border border-white/10">
                <BrainCircuit className="size-3.5 text-indigo-300 animate-pulse" />
                <span>Autonomous Mastery Index (AMI)</span>
              </div>
              <div className="flex items-baseline gap-3">
                <span className="text-5xl font-black tracking-tight text-white sm:text-6xl">94.6</span>
                <span className="text-xl font-bold text-indigo-300">/ 100</span>
                <span className="inline-flex items-center text-xs font-bold text-emerald-400 bg-emerald-500/20 px-2 py-0.5 rounded-full">
                  <ArrowUpRight className="size-3.5 mr-0.5" /> +3.8% YoY
                </span>
              </div>
              <p className="text-xs text-indigo-200/80 leading-relaxed">
                Institutional telemetry calculated in real time across 12 cognitive, operational, financial, and pedagogical sensors.
              </p>
            </div>

            {/* Right Pillars Breakdown */}
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:col-span-8">
              {amiPillars.map((p) => (
                <div
                  key={p.title}
                  className="rounded-2xl border border-white/10 bg-white/5 p-3.5 backdrop-blur-md transition hover:bg-white/10"
                >
                  <div className="flex items-center justify-between text-[11px] font-medium text-indigo-200">
                    <span className="truncate pr-1">{p.title}</span>
                    <span className="font-mono text-emerald-400 font-bold">{p.change}</span>
                  </div>
                  <div className="mt-2 flex items-baseline gap-1.5">
                    <span className="text-2xl font-extrabold text-white">{p.score}</span>
                    <span className="text-[10px] text-indigo-300 font-medium">/ 100</span>
                  </div>
                  <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-white/10">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-indigo-400 to-teal-400"
                      style={{ width: `${p.score}%` }}
                    />
                  </div>
                  <span className="mt-2 block text-[10px] text-gray-400 truncate">{p.benchmark}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* 4 Financial & Operational Vitals */}
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-xs transition hover:shadow-md">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-gray-400">Total Net Revenue</span>
              <div className="flex size-8 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600">
                <DollarSign className="size-4" />
              </div>
            </div>
            <div className="mt-3">
              <span className="text-2xl font-black text-gray-900">$14,842,000</span>
              <div className="mt-1 flex items-center gap-1.5 text-xs">
                <span className="font-bold text-emerald-600 flex items-center">
                  <ArrowUpRight className="size-3.5" /> +6.4%
                </span>
                <span className="text-gray-400">vs Annual Budget</span>
              </div>
            </div>
          </div>

          <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-xs transition hover:shadow-md">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-gray-400">Tuition Realization</span>
              <div className="flex size-8 items-center justify-center rounded-xl bg-blue-50 text-blue-600">
                <PieChart className="size-4" />
              </div>
            </div>
            <div className="mt-3">
              <span className="text-2xl font-black text-gray-900">97.4%</span>
              <div className="mt-1 flex items-center gap-1.5 text-xs">
                <span className="font-bold text-emerald-600 flex items-center">
                  <ArrowUpRight className="size-3.5" /> +1.8%
                </span>
                <span className="text-gray-400">Arrears: $142.5k</span>
              </div>
            </div>
          </div>

          <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-xs transition hover:shadow-md">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-gray-400">Enrollment Fill Rate</span>
              <div className="flex size-8 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600">
                <Users className="size-4" />
              </div>
            </div>
            <div className="mt-3">
              <span className="text-2xl font-black text-gray-900">1,215 / 1,250</span>
              <div className="mt-1 flex items-center gap-1.5 text-xs">
                <span className="font-bold text-indigo-600">97.2% Capacity</span>
                <span className="text-gray-400">• +85 Waitlisted</span>
              </div>
            </div>
          </div>

          <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-xs transition hover:shadow-md">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-gray-400">Faculty Retention</span>
              <div className="flex size-8 items-center justify-center rounded-xl bg-purple-50 text-purple-600">
                <UserCheck className="size-4" />
              </div>
            </div>
            <div className="mt-3">
              <span className="text-2xl font-black text-gray-900">96.8%</span>
              <div className="mt-1 flex items-center gap-1.5 text-xs">
                <span className="font-bold text-purple-600">76 Total Staff</span>
                <span className="text-gray-400">• Burnout: Low</span>
              </div>
            </div>
          </div>
        </div>

        {/* Middle Section: Enrollment Pipeline & Faculty Workload Radar */}
        <div className="grid grid-cols-1 gap-8 lg:grid-cols-12">
          {/* Enrollment Pipeline (7 cols) */}
          <div className="rounded-3xl border border-gray-200/90 bg-white p-6 shadow-xs lg:col-span-7 space-y-6">
            <div className="flex items-center justify-between border-b border-gray-100 pb-4">
              <div>
                <h3 className="text-base font-bold text-gray-900">Enrollment & Net Yield Pipeline</h3>
                <p className="text-xs text-gray-400">Fall 2026 Cohort Conversion & Yield Performance</p>
              </div>
              <Link
                href={`/orgs/${orgslug}/admissions`}
                className="inline-flex items-center gap-1 text-xs font-bold text-indigo-600 hover:text-indigo-800"
              >
                <span>Full CRM</span>
                <ChevronRight className="size-3.5" />
              </Link>
            </div>

            {/* Funnel Progress Bars */}
            <div className="space-y-4">
              {[
                { stage: '1. Inquiries & Campus Tours', count: 480, target: 500, percent: 96, color: 'bg-gray-200 text-gray-700' },
                { stage: '2. Formal Applications', count: 290, target: 300, percent: 96.6, color: 'bg-blue-100 text-blue-700' },
                { stage: '3. Cognitive & Academic Assessment', count: 180, target: 175, percent: 102.8, color: 'bg-indigo-100 text-indigo-700' },
                { stage: '4. Executive Interviews & Offers', count: 140, target: 135, percent: 103.7, color: 'bg-purple-100 text-purple-700' },
                { stage: '5. Matriculated & Deposit Paid', count: 125, target: 120, percent: 104.1, color: 'bg-emerald-100 text-emerald-800 font-bold' },
              ].map((f) => (
                <div key={f.stage} className="space-y-1.5">
                  <div className="flex justify-between text-xs">
                    <span className="font-semibold text-gray-700">{f.stage}</span>
                    <span className="font-mono text-gray-900 font-bold">
                      {f.count} <span className="text-gray-400 font-normal">/ target {f.target}</span>
                    </span>
                  </div>
                  <div className="h-2.5 w-full overflow-hidden rounded-full bg-gray-100">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${
                        f.percent >= 100 ? 'bg-emerald-500' : 'bg-indigo-500'
                      }`}
                      style={{ width: `${Math.min(f.percent, 100)}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>

            <div className="rounded-2xl bg-indigo-50/70 p-4 border border-indigo-100 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="flex size-9 items-center justify-center rounded-xl bg-indigo-600 text-white shadow-xs">
                  <Sparkles className="size-4" />
                </div>
                <div>
                  <h4 className="text-xs font-bold text-indigo-950">Net Tuition Yield Optimization</h4>
                  <p className="text-[11px] text-indigo-700">Projected yield at $18,450/seat with 8.2% financial aid margin.</p>
                </div>
              </div>
              <span className="rounded-full bg-indigo-200/80 px-2.5 py-1 text-xs font-black text-indigo-900">
                +4.2% Above Target
              </span>
            </div>
          </div>

          {/* Faculty Workload Radar (5 cols) */}
          <div className="rounded-3xl border border-gray-200/90 bg-white p-6 shadow-xs lg:col-span-5 space-y-6">
            <div className="flex items-center justify-between border-b border-gray-100 pb-4">
              <div>
                <h3 className="text-base font-bold text-gray-900">Faculty Workload Radar</h3>
                <p className="text-xs text-gray-400">Teaching hours, grading pressure & burnout index</p>
              </div>
              <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-bold text-emerald-700 border border-emerald-200">
                Balanced
              </span>
            </div>

            <div className="space-y-3.5">
              {facultyWorkloads.map((item) => (
                <div
                  key={item.dept}
                  className="rounded-2xl border border-gray-100 bg-gray-50/50 p-3.5 transition hover:bg-gray-50"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-gray-900">{item.dept}</span>
                    <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${
                      item.risk === 'Low' || item.risk === 'Optimal'
                        ? 'bg-emerald-100 text-emerald-800'
                        : 'bg-amber-100 text-amber-800'
                    }`}>
                      {item.risk} Risk
                    </span>
                  </div>
                  <div className="mt-2 grid grid-cols-3 gap-2 text-center text-[11px]">
                    <div className="rounded-lg bg-white p-1.5 border border-gray-100">
                      <span className="block text-gray-400 text-[9px] uppercase">Staff</span>
                      <span className="font-bold text-gray-800">{item.facultyCount}</span>
                    </div>
                    <div className="rounded-lg bg-white p-1.5 border border-gray-100">
                      <span className="block text-gray-400 text-[9px] uppercase">Weekly Hrs</span>
                      <span className="font-bold text-gray-800">{item.avgHours}h</span>
                    </div>
                    <div className="rounded-lg bg-white p-1.5 border border-gray-100">
                      <span className="block text-gray-400 text-[9px] uppercase">Health</span>
                      <span className="font-bold text-emerald-600">{item.healthScore}%</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* AI Autonomous Briefing & Risk Alerts */}
        <div className="rounded-3xl border border-indigo-200/80 bg-white p-6 sm:p-8 shadow-sm">
          <div className="flex items-center gap-3 border-b border-gray-100 pb-4">
            <div className="flex size-9 items-center justify-center rounded-xl bg-gradient-to-tr from-indigo-600 to-teal-500 text-white shadow-sm">
              <BrainCircuit className="size-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-gray-900">Autonomous Strategic Intelligence Briefing</h3>
              <p className="text-xs text-gray-400">Generated automatically by CSG-EMS Cognitive Engine</p>
            </div>
          </div>

          <div className="mt-5 grid grid-cols-1 gap-4 md:grid-cols-3">
            <div className="rounded-2xl border border-emerald-100 bg-emerald-50/40 p-4 space-y-2">
              <div className="flex items-center gap-2 text-xs font-bold text-emerald-800">
                <CheckCircle2 className="size-4 text-emerald-600" />
                <span>Accreditation & Curriculum Mastery</span>
              </div>
              <p className="text-xs text-emerald-950/80 leading-relaxed">
                Grade 11 & 12 AP mastery indicators are 4.2% ahead of state target. IB Diploma candidate progress reaches 98.6% completion velocity.
              </p>
            </div>

            <div className="rounded-2xl border border-amber-100 bg-amber-50/40 p-4 space-y-2">
              <div className="flex items-center gap-2 text-xs font-bold text-amber-800">
                <AlertTriangle className="size-4 text-amber-600" />
                <span>Language Faculty Overload Watch</span>
              </div>
              <p className="text-xs text-amber-950/80 leading-relaxed">
                Grading load in Humanities & Modern Languages peaked at 25.5 hrs/wk due to mid-term essays. SpeedGrader AI copilot draft adoption is recommended.
              </p>
            </div>

            <div className="rounded-2xl border border-indigo-100 bg-indigo-50/40 p-4 space-y-2">
              <div className="flex items-center gap-2 text-xs font-bold text-indigo-800">
                <Sparkles className="size-4 text-indigo-600" />
                <span>Net Tuition Opportunity</span>
              </div>
              <p className="text-xs text-indigo-950/80 leading-relaxed">
                Waitlist demand in Middle School STEM Section B supports unlocking 1 additional 25-seat cohort for $460k incremental net revenue.
              </p>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
