'use client'

import React from 'react'
import Link from 'next/link'
import {
  GraduationCap,
  Layers,
  Users,
  ShieldCheck,
  ArrowRight,
  Sparkles,
  BookOpen,
  Calendar,
  CheckSquare,
  CreditCard,
  Building2,
} from 'lucide-react'

const PORTALS = [
  {
    role: 'STUDENT',
    title: 'Student Dashboard',
    description: 'View today’s timetable, active courses, attendance rate, and launch the Socratic AI Tutor.',
    icon: GraduationCap,
    href: '/student',
    gradient: 'from-blue-600 to-indigo-600',
    border: 'hover:border-blue-500/50',
    badge: 'Active Student',
    features: ['Today’s Schedule', 'Active Courses', 'Socratic AI Tutor', 'Attendance Summary'],
  },
  {
    role: 'TEACHER',
    title: 'Teacher Classroom Hub',
    description: '1-Click Roll-Call quick action, gradebook marking queue, and course lesson planner.',
    icon: Layers,
    href: '/teacher',
    gradient: 'from-amber-600 to-orange-600',
    border: 'hover:border-amber-500/50',
    badge: 'Faculty Hub',
    features: ['1-Click Roll-Call', 'My Classes Today', 'Gradebook & Marking', 'Lesson Planner'],
  },
  {
    role: 'PARENT',
    title: 'Parent Portal',
    description: 'Multi-child switcher, live monthly attendance calendar, fee vouchers, and weekly AI progress digest.',
    icon: Users,
    href: '/parent',
    gradient: 'from-emerald-600 to-teal-600',
    border: 'hover:border-emerald-500/50',
    badge: 'Guardian Suite',
    features: ['Multi-Child Selector', 'Attendance Calendar', 'Fee Vouchers & 1Bill', 'Weekly AI Report'],
  },
  {
    role: 'ADMIN',
    title: 'Admin & Finance Console',
    description: 'Multi-campus governance, admissions pipeline conversion, fee collection KPIs, and cluster telemetry.',
    icon: ShieldCheck,
    href: '/admin',
    gradient: 'from-purple-600 to-indigo-700',
    border: 'hover:border-purple-500/50',
    badge: 'Executive Console',
    features: ['Multi-Campus Manager', 'Admissions Funnel', 'Fee Collection KPI', 'System Health'],
  },
]

export default function DashboardPortalSelectorPage() {
  return (
    <div className="space-y-8 max-w-6xl mx-auto py-4">
      <div className="text-center space-y-3">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20 text-xs font-semibold">
          <Sparkles className="size-3.5" />
          <span>CSG Learning Management System • Next-Gen EduOS</span>
        </div>
        <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-neutral-900 dark:text-white">
          Select Your Role-Gated Portal
        </h1>
        <p className="text-sm text-neutral-500 dark:text-neutral-400 max-w-xl mx-auto">
          Welcome to the unified CSG LMS portal environment. Select your authorized portal below to access customized dashboards, schedules, and tools.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {PORTALS.map((portal) => {
          const Icon = portal.icon
          return (
            <Link
              key={portal.role}
              href={portal.href}
              className={`group relative p-6 rounded-2xl bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 transition-all duration-300 hover:shadow-xl ${portal.border} flex flex-col justify-between`}
            >
              <div>
                <div className="flex items-center justify-between mb-4">
                  <div
                    className={`size-12 rounded-xl bg-gradient-to-tr ${portal.gradient} text-white flex items-center justify-center shadow-md`}
                  >
                    <Icon className="size-6" />
                  </div>
                  <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-neutral-100 dark:bg-neutral-800 text-neutral-600 dark:text-neutral-300">
                    {portal.badge}
                  </span>
                </div>

                <h2 className="text-lg font-bold text-neutral-900 dark:text-white group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">
                  {portal.title}
                </h2>
                <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-1.5 leading-relaxed">
                  {portal.description}
                </p>

                <div className="mt-4 pt-4 border-t border-neutral-100 dark:border-neutral-800/80 grid grid-cols-2 gap-2">
                  {portal.features.map((feat, idx) => (
                    <div
                      key={idx}
                      className="text-[11px] text-neutral-600 dark:text-neutral-400 flex items-center gap-1.5"
                    >
                      <span className="size-1.5 rounded-full bg-blue-500" />
                      <span>{feat}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="mt-6 pt-3 flex items-center justify-between text-xs font-semibold text-blue-600 dark:text-blue-400">
                <span>Enter Portal</span>
                <ArrowRight className="size-4 group-hover:translate-x-1 transition-transform" />
              </div>
            </Link>
          )
        })}
      </div>
    </div>
  )
}
