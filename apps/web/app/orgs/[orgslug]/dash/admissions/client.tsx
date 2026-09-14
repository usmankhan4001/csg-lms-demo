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

import { LH_PAGE, ModuleTabs } from '@/components/widgets'
import AdmissionsCRMBoard from '@/modules/sms/revops/components/AdmissionsCRMBoard'

interface AdmissionsDashClientProps {
  org_id: number
  orgslug: string
}

export default function AdmissionsDashClient(_props: AdmissionsDashClientProps) {
  // The board resolves its own org scope server-side from the caller's
  // principal (see sms_revops.py), so it takes no props today. org_id/orgslug
  // are accepted to match the dash module signature and for when the board
  // gains an explicit campus filter.
  // Only the surround is set to the Learnhouse dash ground here. The board's
  // own chrome (its gradient ribbon and breadcrumbs) still reads as the old
  // standalone page -- worth a restyle pass, but it is presentation only and
  // was deliberately left untouched while moving the file.
  return (
    <div className={LH_PAGE}>
      <div className="pt-6 pb-10">
        {/* The board brings its own header, so the tab strip is mounted
            directly rather than through DashPageShell -- without it this page
            would be the one admissions screen with no way to reach the rest
            of the module now that its siblings have left the sidebar. */}
        <ModuleTabs module="admissions" className="mb-5 mt-0" />
        <AdmissionsCRMBoard />
      </div>
    </div>
  )
}
