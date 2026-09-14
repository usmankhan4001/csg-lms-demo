'use client'

import { DashPageShell } from '@/components/widgets'
import { SchoolSetupPanel } from '@/modules/sms/school-setup/components/SchoolSetupPanel'

export default function SchoolSetupClient({ org_id }: { org_id: number }) {
  return (
    <DashPageShell
      module="school-settings"
      title="School setup"
      description="Create the campus, academic year, terms and founding administrator. Everything is created together, or not at all."
    >
      <SchoolSetupPanel orgId={org_id} />
    </DashPageShell>
  )
}
