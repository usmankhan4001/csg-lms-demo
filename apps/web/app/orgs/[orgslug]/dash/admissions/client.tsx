'use client'

/**
 * Admissions CRM, attached as a first-class Learnhouse dash module.
 *
 * Ported by RE-RENDERING the existing board rather than copying it. The
 * source component is ~1,875 lines and was only recently wired to real data
 * (`getLeadPipeline` / `updateLeadStage`, with optimistic drag-drop and
 * rollback-on-failure). Duplicating that much code would create two copies
 * to keep in sync and risk transcribing the real wiring wrong -- the exact
 * thing worth preserving. One import keeps a single source of truth.
 *
 * The board now lives in `modules/sms/revops/components/`, alongside the
 * `Lead`/`StageId` types it shares with `adapt.ts`. Both previously lived in
 * the `app/(dashboard)/admissions/crm/page.tsx` ROUTE file, which is what
 * kept that parallel shell alive; the shell is now retired.
 */

import { useState } from 'react'
import { LH_PAGE, ModuleTabs } from '@/components/widgets'
import { AdmissionsKanbanStudio } from '@/modules/ems/admissions'
import AdmissionsCRMBoard from '@/modules/sms/revops/components/AdmissionsCRMBoard'
import { LayoutGrid, Layers } from 'lucide-react'

interface AdmissionsDashClientProps {
  org_id: number
  orgslug: string
}

export default function AdmissionsDashClient(props: AdmissionsDashClientProps) {
  const [viewMode, setViewMode] = useState<'kanban_studio' | 'legacy_board'>('kanban_studio')

  return (
    <div className={LH_PAGE}>
      <div className="pt-6 pb-10">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-5 mt-0">
          <ModuleTabs module="admissions" className="my-0" />
          <div className="flex items-center gap-1 bg-slate-200/80 dark:bg-slate-800 p-1 rounded-xl self-start sm:self-auto">
            <button
              onClick={() => setViewMode('kanban_studio')}
              className={`px-3 py-1.5 text-xs font-bold rounded-lg transition-all flex items-center gap-1.5 ${
                viewMode === 'kanban_studio'
                  ? 'bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 shadow-sm'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900'
              }`}
            >
              <Layers className="w-3.5 h-3.5 text-indigo-600" />
              Kanban Studio
            </button>
            <button
              onClick={() => setViewMode('legacy_board')}
              className={`px-3 py-1.5 text-xs font-bold rounded-lg transition-all flex items-center gap-1.5 ${
                viewMode === 'legacy_board'
                  ? 'bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 shadow-sm'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900'
              }`}
            >
              <LayoutGrid className="w-3.5 h-3.5 text-slate-500" />
              Table View
            </button>
          </div>
        </div>

        {viewMode === 'kanban_studio' ? (
          <AdmissionsKanbanStudio orgslug={props.orgslug} orgId={props.org_id} />
        ) : (
          <AdmissionsCRMBoard />
        )}
      </div>
    </div>
  )
}

