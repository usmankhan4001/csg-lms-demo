'use client'

import { DashPageShell } from '@/components/widgets'
import { PeopleProvisioningPanel } from '@/modules/sms/roles/components/PeopleProvisioningPanel'

export default function SchoolPeopleClient({ org_id }: { org_id: number }) {
  return (
    <DashPageShell
      module="school-settings"
      title="People"
      description="Create teacher, student, parent and staff accounts. Nobody is given a password here — each person sets their own."
    >
      <PeopleProvisioningPanel orgId={org_id} />
    </DashPageShell>
  )
}
