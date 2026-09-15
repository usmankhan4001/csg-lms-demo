'use client'

import React from 'react'
import Link from 'next/link'
import {
  UserPlus,
  Sparkles,
  DollarSign,
  TrendingUp,
  Award,
  Users,
  CheckCircle2,
  Download,
  Calculator,
  ArrowUpRight
} from 'lucide-react'
import { useOrgMembership, useOrg } from '@components/Contexts/OrgContext'
import { PersonaSwitcher } from '@/components/ems/PersonaSwitcher'
import { AdmissionsKanbanStudio } from '@/modules/ems/admissions/AdmissionsKanbanStudio'

export default function AdmissionsPortalPage() {
  const { orgslug } = useOrgMembership()
  const org = useOrg() as any

  return (
    <div className="flex flex-col min-h-screen">
      {/* Persona Header Switcher */}
      <PersonaSwitcher
        currentPortal="admissions"
        breadcrumbs={[{ label: 'Admissions & RevOps Center' }]}
        actions={
          <div className="flex items-center gap-2">
            <span className="rounded-full bg-blue-50 px-3 py-1 text-xs font-bold text-blue-800 border border-blue-200">
              Fall 2026 Intake Active
            </span>
          </div>
        }
      />

      <main className="mx-auto w-full max-w-7xl px-4 py-8 sm:px-6 lg:px-8 space-y-6">
        {/* Top Header Summary */}
        <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-black tracking-tight text-gray-900 sm:text-3xl">
                Admissions & RevOps Center
              </h1>
              <span className="rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-extrabold text-blue-800 border border-blue-200">
                Yield: 104% of Target
              </span>
            </div>
            <p className="mt-1 text-sm text-gray-500">
              Interactive Kanban CRM, net tuition yield modeling & 1-click SIS student matriculation.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <Link
              href={`/orgs/${orgslug}/executive`}
              className="inline-flex items-center gap-1.5 text-xs font-semibold text-blue-600 hover:text-blue-800 transition"
            >
              <span>Executive Console</span>
              <ArrowUpRight className="size-3.5" />
            </Link>
          </div>
        </div>

        {/* Embedded Complete Admissions Kanban Studio */}
        <div className="rounded-3xl border border-gray-200/90 bg-white p-4 sm:p-6 shadow-xs">
          <AdmissionsKanbanStudio />
        </div>
      </main>
    </div>
  )
}
