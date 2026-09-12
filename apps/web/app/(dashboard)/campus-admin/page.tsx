'use client'

/**
 * Campus / School Admin dashboard -- thin composition over the real SMS
 * modules. Campus scoping comes from the caller's real session `org_id`
 * (resolved server-side by `sms_campus.py` from the principal, not passed
 * explicitly here) -- see `lib/api/useSchoolSession.ts`.
 *
 * Admissions CRM (`/admissions/crm`) is a separate, already-real page owned
 * by a parallel in-flight AI RevOps workstream (see AGENT scope boundary)
 * and is linked from the sidebar, not duplicated here.
 */

import { Building2, CreditCard, ScrollText, Users } from 'lucide-react'
import { DataTable, EmptyState, SectionCard, StatGrid, StatusChip } from '@/components/widgets'
import { useApiResource } from '@/lib/api/useApiResource'
import { useSchoolSession } from '@/lib/api/useSchoolSession'
import { listCampuses } from '@/modules/sms/campus/api'
import { getTrialBalance, listChartOfAccounts } from '@/modules/sms/financials/api'
import { listStaffLeaves, listStaffProfiles } from '@/modules/sms/hr_payroll/api'

export default function CampusAdminDashboardPage() {
  const { checked } = useSchoolSession()

  const campuses = useApiResource(() => listCampuses(), [])
  const staff = useApiResource(() => listStaffProfiles(), [])
  const pendingLeaves = useApiResource(() => listStaffLeaves({ status: 'PENDING' }), [])
  const trialBalance = useApiResource(() => getTrialBalance(), [])
  const accounts = useApiResource(() => listChartOfAccounts(), [], { isEmpty: (d) => d.length === 0 })

  const activeStaffCount = (staff.data ?? []).filter((s) => s.is_active).length

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-foreground">Campus Admin Console</h1>
        <p className="text-sm text-muted-foreground">Campuses, finance and staff, in one place.</p>
      </div>

      {!checked ? (
        <StatGrid state="loading" items={[]} />
      ) : (
        <>
          <StatGrid
            state={campuses.status === 'loading' || staff.status === 'loading' || trialBalance.status === 'loading' ? 'loading' : 'success'}
            columns={4}
            items={[
              { label: 'Campuses', value: campuses.data?.length ?? 0, icon: Building2, tone: 'neutral' },
              { label: 'Active staff', value: activeStaffCount, icon: Users, tone: 'positive' },
              {
                label: 'Trial balance',
                value: trialBalance.data ? `Rs. ${trialBalance.data.total_debit.toFixed(0)}` : '—',
                icon: ScrollText,
                tone: trialBalance.data?.is_balanced ? 'positive' : 'caution',
                hint: trialBalance.data ? (trialBalance.data.is_balanced ? 'Balanced' : 'Out of balance') : undefined,
              },
              {
                label: 'Pending staff leaves',
                value: pendingLeaves.data?.length ?? 0,
                icon: Users,
                tone: (pendingLeaves.data?.length ?? 0) > 0 ? 'caution' : 'positive',
              },
            ]}
          />

          <SectionCard
            id="campuses"
            title="Campuses"
            icon={<Building2 className="size-4 text-muted-foreground" />}
            state={campuses.status}
            error={campuses.error}
            onRetry={campuses.refetch}
            emptyTitle="No campuses yet"
            emptyDescription="Add your first campus to start enrolling students."
          >
            <DataTable
              rows={campuses.data ?? []}
              rowKey={(row) => row.id}
              state="success"
              columns={[
                { key: 'name', header: 'Campus', render: (r) => r.name },
                { key: 'code', header: 'Code', render: (r) => r.code },
                { key: 'address', header: 'Address', render: (r) => r.address ?? '—' },
                { key: 'status', header: 'Status', render: (r) => <StatusChip label={r.is_active ? 'Active' : 'Inactive'} tone={r.is_active ? 'positive' : 'neutral'} /> },
              ]}
            />
          </SectionCard>

          <SectionCard
            id="finance"
            title="Finance"
            icon={<CreditCard className="size-4 text-muted-foreground" />}
            state={accounts.status === 'loading' ? 'loading' : accounts.status === 'error' ? 'error' : 'success'}
            error={accounts.error}
            onRetry={accounts.refetch}
          >
            {trialBalance.data && (
              <div className="mb-4 grid grid-cols-3 gap-3">
                <div className="rounded-lg border border-border p-3">
                  <p className="text-xs text-muted-foreground">Total debit</p>
                  <p className="text-lg font-semibold tabular-nums text-foreground">Rs. {trialBalance.data.total_debit.toFixed(2)}</p>
                </div>
                <div className="rounded-lg border border-border p-3">
                  <p className="text-xs text-muted-foreground">Total credit</p>
                  <p className="text-lg font-semibold tabular-nums text-foreground">Rs. {trialBalance.data.total_credit.toFixed(2)}</p>
                </div>
                <div className="rounded-lg border border-border p-3">
                  <p className="text-xs text-muted-foreground">Balanced</p>
                  <p className="text-lg font-semibold text-foreground">{trialBalance.data.is_balanced ? 'Yes' : 'No'}</p>
                </div>
              </div>
            )}
            {accounts.data && accounts.data.length === 0 ? (
              <EmptyState title="No chart of accounts yet" description="Set up accounts to start tracking the ledger." />
            ) : (
              <DataTable
                rows={accounts.data ?? []}
                rowKey={(row) => row.id}
                state="success"
                columns={[
                  { key: 'code', header: 'Code', render: (r) => r.account_code },
                  { key: 'name', header: 'Account', render: (r) => r.account_name },
                  { key: 'type', header: 'Type', render: (r) => r.account_type },
                  { key: 'balance', header: 'Balance', align: 'right', render: (r) => `Rs. ${r.balance.toFixed(2)}` },
                ]}
              />
            )}
          </SectionCard>

          <SectionCard
            id="people"
            title="People"
            icon={<Users className="size-4 text-muted-foreground" />}
            state={staff.status}
            error={staff.error}
            onRetry={staff.refetch}
            emptyTitle="No staff registered yet"
            emptyDescription="Add staff profiles to start managing HR & payroll."
          >
            <DataTable
              rows={staff.data ?? []}
              rowKey={(row) => row.id}
              state="success"
              totalLabel={`${staff.data?.length ?? 0} staff member${(staff.data?.length ?? 0) === 1 ? '' : 's'}`}
              columns={[
                { key: 'name', header: 'Name', render: (r) => r.full_name },
                { key: 'designation', header: 'Designation', render: (r) => r.designation },
                { key: 'department', header: 'Department', render: (r) => r.department },
                { key: 'contract', header: 'Contract', render: (r) => r.contract_type },
                { key: 'status', header: 'Status', render: (r) => <StatusChip label={r.is_active ? 'Active' : 'Inactive'} tone={r.is_active ? 'positive' : 'neutral'} /> },
              ]}
            />
          </SectionCard>
        </>
      )}
    </div>
  )
}
