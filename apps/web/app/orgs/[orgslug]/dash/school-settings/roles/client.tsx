'use client'

import React, { useState } from 'react'
import { DashPageShell } from '@/components/widgets'
import { RoleManagementPanel } from '@/modules/sms/roles/components/RoleManagementPanel'
import { RoleList } from '@/modules/ems/roles'
import { ShieldCheck, Users } from 'lucide-react'

export default function RolesSettingsClient({ org_id }: { org_id: number }) {
  const [activeTab, setActiveTab] = useState<'matrix' | 'directory'>('matrix')

  return (
    <DashPageShell
      module="school-settings"
      title="Roles & Permissions"
      description="Manage role definitions, customize fine-grained ERPNext-style permission matrices, and assign scoped access to staff and students."
    >
      <div className="space-y-6">
        {/* Sub Navigation Bar */}
        <div className="flex items-center gap-2 border-b border-border/60 pb-3">
          <button
            type="button"
            onClick={() => setActiveTab('matrix')}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all ${
              activeTab === 'matrix'
                ? 'bg-primary text-primary-foreground shadow-xs'
                : 'text-muted-foreground hover:bg-muted/50 hover:text-foreground'
            }`}
          >
            <ShieldCheck className="w-4 h-4" />
            <span>Role Definitions & Permission Matrix</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('directory')}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all ${
              activeTab === 'directory'
                ? 'bg-primary text-primary-foreground shadow-xs'
                : 'text-muted-foreground hover:bg-muted/50 hover:text-foreground'
            }`}
          >
            <Users className="w-4 h-4" />
            <span>Role Directory & Fast Assignment</span>
          </button>
        </div>

        {/* Tab Content */}
        {activeTab === 'matrix' ? (
          <RoleList orgId={org_id} />
        ) : (
          <RoleManagementPanel orgId={org_id} />
        )}
      </div>
    </DashPageShell>
  )
}
