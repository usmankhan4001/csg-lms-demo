'use client'

import { useState } from 'react'
import Link from 'next/link'
import {
  LH_PAGE,
  LH_PRIMARY_BUTTON,
  LH_SECONDARY_BUTTON,
  ModuleTabs,
  SectionCard,
} from '@/components/widgets'
import AdmissionsCRMBoard from '@/modules/sms/revops/components/AdmissionsCRMBoard'
import { NetTuitionYieldModal } from '@/modules/ems/admissions/NetTuitionYieldModal'
import { Calculator, FileText, Layers, ListFilter, Sparkles, Users } from 'lucide-react'

interface AdmissionsDashClientProps {
  org_id: number
  orgslug: string
}

export default function AdmissionsDashClient({ org_id, orgslug }: AdmissionsDashClientProps) {
  const [isNtyOpen, setIsNtyOpen] = useState(false)

  return (
    <div className={LH_PAGE}>
      <div className="pt-6 pb-10">
        {/* Module Sub-Navigation Bar */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
          <ModuleTabs module="admissions" className="my-0" />
          <div className="flex items-center gap-2 flex-wrap">
            <button
              onClick={() => setIsNtyOpen(true)}
              className={`${LH_SECONDARY_BUTTON} text-xs flex items-center gap-1.5`}
            >
              <Calculator className="w-3.5 h-3.5 text-indigo-600" />
              NTY Yield Modeler
            </button>
            <Link
              href={`/orgs/${orgslug}/dash/admissions/applications`}
              className={`${LH_SECONDARY_BUTTON} text-xs flex items-center gap-1.5`}
            >
              <FileText className="w-3.5 h-3.5 text-slate-500" />
              Applications Table
            </Link>
            <Link
              href={`/orgs/${orgslug}/dash/admissions/leads`}
              className={`${LH_SECONDARY_BUTTON} text-xs flex items-center gap-1.5`}
            >
              <Users className="w-3.5 h-3.5 text-slate-500" />
              Leads Registry
            </Link>
          </div>
        </div>

        {/* Live Admissions CRM Kanban Board */}
        <AdmissionsCRMBoard />

        {/* Interactive Net Tuition Yield (NTY) Modeler Drawer/Modal */}
        <NetTuitionYieldModal
          isOpen={isNtyOpen}
          onClose={() => setIsNtyOpen(false)}
        />
      </div>
    </div>
  )
}


