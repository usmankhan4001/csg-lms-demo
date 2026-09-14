'use client'

import { DashPageShell } from '@/components/widgets'
import { RoleManagementPanel } from '@/modules/sms/roles/components/RoleManagementPanel'

export default function RolesSettingsClient({ org_id }: { org_id: number }) {
  return (
    <DashPageShell
      module="school-settings"
      title="Roles"
      description="Assign and manage school-specific roles (Teacher, Student, Parent, Psychologist, Admin) for organization members."
    >
      <RoleManagementPanel orgId={org_id} />
    </DashPageShell>
  )
}
