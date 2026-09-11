'use client'

import React, { useState } from 'react'
import {
  Building2,
  Users,
  CreditCard,
  Activity,
  Sparkles,
  TrendingUp,
  ShieldCheck,
  CheckCircle2,
  AlertCircle,
  Plus,
  Search,
  Filter,
  ArrowUpRight,
  Server,
  Zap,
  Globe,
  DollarSign,
  Download,
  Send,
  SlidersHorizontal,
  ChevronRight,
  HardDrive,
  FileText,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { CAMPUSES } from '@/components/navigation/types'

interface AdmissionStage {
  stage: string
  count: number
  conversionRate: string
  statusColor: string
}

const ADMISSION_PIPELINE: AdmissionStage[] = [
  { stage: 'Inquiries & Leads', count: 540, conversionRate: '100%', statusColor: 'bg-blue-500' },
  { stage: 'Applications Submitted', count: 420, conversionRate: '77.7%', statusColor: 'bg-indigo-500' },
  { stage: 'Entrance Exam Cleared', count: 310, conversionRate: '73.8%', statusColor: 'bg-purple-500' },
  { stage: 'Principal Interview', count: 245, conversionRate: '79.0%', statusColor: 'bg-pink-500' },
  { stage: 'Fee Paid & Enrolled', count: 198, conversionRate: '80.8%', statusColor: 'bg-emerald-500' },
]

export default function AdminConsolePage() {
  const [selectedCampusFilter, setSelectedCampusFilter] = useState<string>('all')
  const [smsTriggeredToast, setSmsTriggeredToast] = useState(false)

  const handleSendOverdueReminders = () => {
    setSmsTriggeredToast(true)
    setTimeout(() => setSmsTriggeredToast(false), 3500)
  }

  const filteredCampuses =
    selectedCampusFilter === 'all'
      ? CAMPUSES
      : CAMPUSES.filter((c) => c.id === selectedCampusFilter)

  return (
    <div className="space-y-6">
      {/* Admin Executive Header Ribbon */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-purple-800 via-indigo-800 to-slate-900 text-white p-6 sm:p-8 shadow-lg shadow-purple-950/20">
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/10 backdrop-blur-md border border-white/15 text-xs font-semibold text-purple-200 mb-3">
              <ShieldCheck className="size-3.5 text-purple-300" />
              <span>Multi-Campus Executive Governance Suite</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">
              Admin & Finance Console 🏛️
            </h1>
            <p className="text-sm text-purple-100/90 mt-1 max-w-xl leading-relaxed">
              Real-time multi-campus telemetry across 4 branch locations, 3,920 active students, and PKR 48.4M billing cycle.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2.5">
            <button
              onClick={handleSendOverdueReminders}
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-white text-purple-950 hover:bg-purple-50 font-semibold text-xs transition-all shadow-md hover:scale-105 active:scale-95"
            >
              <Send className="size-4 text-purple-600" />
              <span>Send Fee Reminder SMS</span>
            </button>
            <button
              onClick={() => alert('Exporting full multi-campus compliance audit report...')}
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-white/15 hover:bg-white/25 border border-white/20 text-white font-medium text-xs transition-colors backdrop-blur-xs"
            >
              <Download className="size-4" />
              <span>Audit Export</span>
            </button>
          </div>
        </div>

        {/* Decorative background glow */}
        <div className="absolute -end-12 -bottom-12 size-64 rounded-full bg-purple-500/20 blur-3xl pointer-events-none" />
      </div>

      {/* Overdue SMS Toast */}
      {smsTriggeredToast && (
        <div className="p-3.5 rounded-xl bg-purple-500/15 border border-purple-500/30 text-purple-700 dark:text-purple-300 text-xs font-medium flex items-center justify-between animate-in fade-in">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="size-4 text-purple-600 shrink-0" />
            <span>
              Automated Fee Reminders successfully queued and dispatched to 142 overdue guardian numbers.
            </span>
          </div>
          <button onClick={() => setSmsTriggeredToast(false)}>✕</button>
        </div>
      )}

      {/* Executive KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-4 rounded-2xl bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 shadow-2xs">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-neutral-500">Total Enrolled</span>
            <div className="p-1.5 rounded-lg bg-blue-500/10 text-blue-600">
              <Users className="size-4" />
            </div>
          </div>
          <div className="text-2xl font-bold text-neutral-900 dark:text-white">3,920</div>
          <div className="text-[11px] text-emerald-600 flex items-center gap-1 font-medium mt-1">
            <TrendingUp className="size-3" />
            <span>+14.2% vs prior academic year</span>
          </div>
        </div>

        <div className="p-4 rounded-2xl bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 shadow-2xs">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-neutral-500">Term Fee Collection</span>
            <div className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-600">
              <CreditCard className="size-4" />
            </div>
          </div>
          <div className="text-2xl font-bold text-neutral-900 dark:text-white">88.4%</div>
          <div className="text-[11px] text-neutral-500 mt-1">
            PKR 42.8M of 48.4M Collected
          </div>
        </div>

        <Link
          href="/admin/admissions/crm"
          className="group p-4 rounded-2xl bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 shadow-2xs hover:border-purple-400 dark:hover:border-purple-500 transition-all block"
        >
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-neutral-500 group-hover:text-purple-600 transition-colors">
              Admissions Pipeline & CRM
            </span>
            <div className="p-1.5 rounded-lg bg-purple-500/10 text-purple-600 group-hover:bg-purple-600 group-hover:text-white transition-colors">
              <Sparkles className="size-4" />
            </div>
          </div>
          <div className="text-2xl font-bold text-neutral-900 dark:text-white flex items-center justify-between">
            <span>540 Inquiries</span>
            <ArrowUpRight className="size-4 text-neutral-400 group-hover:text-purple-600 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-all" />
          </div>
          <div className="text-[11px] text-purple-600 font-medium mt-1">
            198 Enrolled (36.6% Funnel Conversion)
          </div>
        </Link>

        <div className="p-4 rounded-2xl bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 shadow-2xs">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-neutral-500">System Health</span>
            <div className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-600">
              <Activity className="size-4" />
            </div>
          </div>
          <div className="text-2xl font-bold text-neutral-900 dark:text-white">99.98%</div>
          <div className="text-[11px] text-emerald-600 font-medium mt-1">All 4 Clusters Healthy</div>
        </div>
      </div>

      {/* Main Grid: Campuses Overview & Admissions Pipeline */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Campuses Manager & Fee Collection KPI */}
        <div className="lg:col-span-2 space-y-6">
          {/* Campuses Manager Card */}
          <div
            id="campuses"
            className="p-5 sm:p-6 rounded-2xl bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 shadow-2xs"
          >
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-xl bg-purple-500/10 text-purple-600 dark:text-purple-400">
                  <Building2 className="size-5" />
                </div>
                <div>
                  <h2 className="text-base font-bold text-neutral-900 dark:text-white">
                    Multi-Campus Governance
                  </h2>
                  <p className="text-xs text-neutral-500">
                    Live branch status, faculty allocation & student capacity
                  </p>
                </div>
              </div>

              {/* Campus Filter */}
              <select
                value={selectedCampusFilter}
                onChange={(e) => setSelectedCampusFilter(e.target.value)}
                className="px-3 py-1.5 rounded-xl border border-neutral-200 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-800 text-xs text-neutral-800 dark:text-neutral-200 self-start sm:self-auto focus:outline-hidden"
              >
                <option value="all">All 4 Campuses</option>
                {CAMPUSES.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {filteredCampuses.map((campus) => (
                <div
                  key={campus.id}
                  className="p-4 rounded-xl border border-neutral-200 dark:border-neutral-800 hover:border-neutral-300 dark:hover:border-neutral-700 bg-neutral-50/50 dark:bg-neutral-800/30 transition-all flex flex-col justify-between"
                >
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-mono text-xs font-bold text-purple-600 dark:text-purple-400 bg-purple-500/10 px-2 py-0.5 rounded border border-purple-500/20">
                        {campus.code}
                      </span>
                      <span className="flex items-center gap-1.5 text-xs text-emerald-600 font-semibold">
                        <span className="size-1.5 rounded-full bg-emerald-500 animate-pulse" />
                        Operational
                      </span>
                    </div>

                    <h3 className="text-sm font-bold text-neutral-900 dark:text-white">
                      {campus.name}
                    </h3>
                    <p className="text-xs text-neutral-500 mt-0.5">{campus.city}</p>

                    <div className="py-3 my-2 border-y border-neutral-200 dark:border-neutral-800/80 grid grid-cols-2 gap-2 text-xs">
                      <div>
                        <span className="text-neutral-500">Students:</span>
                        <div className="font-bold text-neutral-800 dark:text-neutral-200">
                          {campus.studentCount}
                        </div>
                      </div>
                      <div>
                        <span className="text-neutral-500">Faculty:</span>
                        <div className="font-bold text-neutral-800 dark:text-neutral-200">
                          {campus.facultyCount}
                        </div>
                      </div>
                    </div>

                    <div className="text-[11px] text-neutral-500 truncate mb-3">
                      <span className="font-semibold text-neutral-700 dark:text-neutral-300">Director: </span>
                      {campus.director}
                    </div>
                  </div>

                  <button
                    onClick={() => alert(`Drilling down to ${campus.name} deep audit metrics.`)}
                    className="w-full flex items-center justify-center gap-1.5 py-1.5 rounded-lg border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 hover:bg-neutral-100 dark:hover:bg-neutral-700 text-xs font-semibold text-neutral-700 dark:text-neutral-200 transition-colors shadow-2xs"
                  >
                    <span>Manage Campus</span>
                    <ChevronRight className="size-3.5" />
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* Fee Collection & Financial Health Card */}
          <div
            id="finance"
            className="p-5 sm:p-6 rounded-2xl bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 shadow-2xs"
          >
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-xl bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
                  <CreditCard className="size-5" />
                </div>
                <div>
                  <h2 className="text-base font-bold text-neutral-900 dark:text-white">
                    Fee Collection & Recovery KPI
                  </h2>
                  <p className="text-xs text-neutral-500">
                    Term 1 Fall 2026 Collection Cycle
                  </p>
                </div>
              </div>
              <span className="text-xs font-bold text-emerald-600 dark:text-emerald-400">
                88.4% Realized
              </span>
            </div>

            {/* Collection Breakdown Progress */}
            <div className="space-y-4">
              <div>
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="font-semibold text-neutral-700 dark:text-neutral-300">
                    Total Invoiced: PKR 48,400,000
                  </span>
                  <span className="font-bold text-emerald-600 dark:text-emerald-400">
                    Collected: PKR 42,785,600
                  </span>
                </div>
                <div className="w-full h-3 rounded-full bg-neutral-200 dark:bg-neutral-700 overflow-hidden">
                  <div className="h-full bg-gradient-to-r from-emerald-500 to-teal-500 rounded-full w-[88.4%]" />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs pt-2">
                <div className="p-3 rounded-xl bg-neutral-50 dark:bg-neutral-800/40 border border-neutral-200 dark:border-neutral-800">
                  <div className="text-neutral-500">1Bill Online Auto-Sync</div>
                  <div className="text-sm font-bold text-neutral-900 dark:text-white mt-0.5">
                    PKR 34.2M (80%)
                  </div>
                </div>
                <div className="p-3 rounded-xl bg-neutral-50 dark:bg-neutral-800/40 border border-neutral-200 dark:border-neutral-800">
                  <div className="text-neutral-500">Overdue (1 - 30 Days)</div>
                  <div className="text-sm font-bold text-amber-600 mt-0.5">
                    PKR 4.1M (8.5%)
                  </div>
                </div>
                <div className="p-3 rounded-xl bg-neutral-50 dark:bg-neutral-800/40 border border-neutral-200 dark:border-neutral-800">
                  <div className="text-neutral-500">Critical Overdue (&gt;30d)</div>
                  <div className="text-sm font-bold text-rose-600 mt-0.5">
                    PKR 1.5M (3.1%)
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Right 1 Col: Admissions Pipeline & System Health */}
        <div className="space-y-6">
          {/* Admissions Pipeline Funnel */}
          <div
            id="admissions"
            className="p-5 sm:p-6 rounded-2xl bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 shadow-2xs"
          >
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Users className="size-4.5 text-blue-500" />
                <h3 className="text-sm font-bold text-neutral-900 dark:text-white">
                  Admissions Funnel
                </h3>
              </div>
              <span className="text-xs font-semibold text-blue-600">540 Total Leads</span>
            </div>

            <div className="space-y-3">
              {ADMISSION_PIPELINE.map((stage, idx) => (
                <div key={idx} className="space-y-1">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-medium text-neutral-700 dark:text-neutral-300">
                      {stage.stage}
                    </span>
                    <span className="font-bold text-neutral-900 dark:text-white">
                      {stage.count} ({stage.conversionRate})
                    </span>
                  </div>
                  <div className="w-full h-2 rounded-full bg-neutral-100 dark:bg-neutral-800 overflow-hidden">
                    <div
                      className={cn('h-full rounded-full', stage.statusColor)}
                      style={{
                        width: `${(stage.count / ADMISSION_PIPELINE[0].count) * 100}%`,
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>

            <div className="pt-4 mt-4 border-t border-neutral-100 dark:border-neutral-800">
              <Link
                href="/admin/admissions/crm"
                className="w-full flex items-center justify-center gap-2 py-2 px-3 rounded-xl bg-purple-600 hover:bg-purple-700 text-white text-xs font-bold transition-all shadow-md shadow-purple-600/20"
              >
                <Sparkles className="size-3.5" />
                <span>Open CRM Kanban & AI SDR</span>
                <ChevronRight className="size-3.5" />
              </Link>
            </div>
          </div>

          {/* System Health & Infrastructure */}
          <div
            id="health"
            className="p-5 sm:p-6 rounded-2xl bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 shadow-2xs"
          >
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-bold text-neutral-900 dark:text-white flex items-center gap-2">
                <Activity className="size-4 text-emerald-500" />
                Infrastructure & Sync
              </h3>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/10 text-emerald-600 border border-emerald-500/20">
                100% Operational
              </span>
            </div>

            <div className="space-y-3 text-xs">
              <div className="p-2.5 rounded-xl border border-neutral-100 dark:border-neutral-800 bg-neutral-50/50 dark:bg-neutral-800/30 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Server className="size-4 text-neutral-500" />
                  <span>Next.js Web Clusters</span>
                </div>
                <span className="font-semibold text-emerald-600">Healthy (4 Pods)</span>
              </div>

              <div className="p-2.5 rounded-xl border border-neutral-100 dark:border-neutral-800 bg-neutral-50/50 dark:bg-neutral-800/30 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Zap className="size-4 text-amber-500" />
                  <span>Socratic AI Engine</span>
                </div>
                <span className="font-semibold text-emerald-600">182ms avg latency</span>
              </div>

              <div className="p-2.5 rounded-xl border border-neutral-100 dark:border-neutral-800 bg-neutral-50/50 dark:bg-neutral-800/30 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <HardDrive className="size-4 text-blue-500" />
                  <span>Database & Replicas</span>
                </div>
                <span className="font-semibold text-emerald-600">0 Replication Lag</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
