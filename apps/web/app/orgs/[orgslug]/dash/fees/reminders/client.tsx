'use client'

/**
 * Fee reminders -- what the school actually told families, and what actually
 * left the building.
 *
 * The `recipients` and `delivered` columns are separate on purpose. They differ
 * whenever mail is unconfigured, and that difference is the entire point of
 * this screen: a school must be able to see that reminders did NOT go out,
 * rather than assume they did and then chase a family who was never told.
 * Showing only "12 reminders sent" would hide exactly the failure that matters.
 */

import { useState } from 'react'
import { BellRing, MailWarning, Send } from 'lucide-react'
import {
  DashPageShell,
  DataTable,
  LH_INPUT,
  SectionCard,
  StatGrid,
  StatusChip,
} from '@/components/widgets'
import type { DataTableColumn, StatusTone } from '@/components/widgets'
import { useApiResource } from '@/lib/api/useApiResource'
import { listFeeReminders } from '@/modules/sms/fees/api'
import { humanEnum, isoDate, money } from '@/modules/sms/fees/format'
import type { FeeReminderKind, FeeReminderLogRead } from '@/modules/sms/fees/types'

interface Props {
  org_id: number
  orgslug: string
}

const KIND_TONE: Record<FeeReminderKind, StatusTone> = {
  UPCOMING: 'neutral',
  DUE_TODAY: 'caution',
  OVERDUE: 'critical',
}

export default function FeesRemindersClient(_props: Props) {
  const [studentFilter, setStudentFilter] = useState('')

  const parsedStudentId = studentFilter.trim() === '' ? undefined : Number(studentFilter.trim())
  const validStudentId =
    parsedStudentId !== undefined && Number.isInteger(parsedStudentId) && parsedStudentId > 0
      ? parsedStudentId
      : undefined

  const reminders = useApiResource(
    () => listFeeReminders({ studentId: validStudentId }),
    [validStudentId]
  )

  const rows = reminders.data ?? []

  const intended = rows.reduce((s, r) => s + r.recipients, 0)
  const actuallyDelivered = rows.reduce((s, r) => s + r.delivered, 0)
  const undelivered = intended - actuallyDelivered

  const columns: DataTableColumn<FeeReminderLogRead>[] = [
    {
      key: 'sent',
      header: 'Sent',
      render: (r) => <span className="tabular-nums">{isoDate(r.sent_on)}</span>,
    },
    {
      key: 'kind',
      header: 'Kind',
      render: (r) => <StatusChip tone={KIND_TONE[r.kind]} label={humanEnum(r.kind)} />,
    },
    {
      key: 'student',
      header: 'Student',
      render: (r) => <span className="tabular-nums">#{r.student_id}</span>,
    },
    {
      key: 'voucher',
      header: 'Voucher',
      render: (r) => <span className="tabular-nums">#{r.voucher_id}</span>,
    },
    {
      key: 'balance',
      header: 'Balance when sent',
      align: 'right',
      render: (r) => <span className="tabular-nums">{money(r.balance_at_send)}</span>,
    },
    {
      key: 'recipients',
      header: 'Addressed to',
      align: 'right',
      render: (r) => <span className="tabular-nums">{r.recipients}</span>,
    },
    {
      key: 'delivered',
      header: 'Accepted by mail',
      align: 'right',
      render: (r) =>
        r.delivered < r.recipients ? (
          <span className="tabular-nums font-medium text-red-700">
            {r.delivered} of {r.recipients}
          </span>
        ) : (
          <span className="tabular-nums">{r.delivered}</span>
        ),
    },
    {
      key: 'outcome',
      header: 'Outcome',
      render: (r) =>
        r.delivered === 0 && r.recipients > 0 ? (
          <StatusChip tone="critical" label="Nobody reached" />
        ) : r.delivered < r.recipients ? (
          <StatusChip tone="caution" label="Partly delivered" />
        ) : (
          <StatusChip tone="positive" label="Delivered" />
        ),
    },
  ]

  return (
    <DashPageShell
      title="Fee reminders"
      description="Every reminder this system tried to send, and whether it actually reached anyone."
      module="fees"
    >
      <StatGrid
        state={reminders.status === 'loading' ? 'loading' : 'success'}
        columns={3}
        items={[
          {
            label: 'Reminders logged',
            value: String(rows.length),
            icon: BellRing,
            tone: 'neutral',
          },
          {
            label: 'Recipients addressed',
            value: String(intended),
            icon: Send,
            tone: 'neutral',
          },
          {
            label: 'Never delivered',
            value: String(undelivered),
            icon: MailWarning,
            // Undelivered mail is a failure worth flagging red, because the
            // family believes they were never chased -- and they are right.
            tone: undelivered > 0 ? 'critical' : 'positive',
          },
        ]}
      />

      {undelivered > 0 ? (
        <div className="rounded-xl bg-red-50 px-4 py-3">
          <p className="text-sm font-medium text-red-900">
            {undelivered} reminder{undelivered === 1 ? '' : 's'} never left the system
          </p>
          <p className="mt-0.5 text-sm text-red-800">
            The mail provider did not accept them, usually because email is not configured. Those
            families have not been told they owe anything — chasing them for late payment would be
            unfair until this is fixed.
          </p>
        </div>
      ) : null}

      <SectionCard title="Filter" icon={<BellRing className="size-4 text-gray-500" />}>
        <label className="flex flex-col gap-1.5" htmlFor="reminders-student">
          <span className="text-xs font-medium text-gray-500">Student id</span>
          <input
            id="reminders-student"
            className={`${LH_INPUT} max-w-48`}
            inputMode="numeric"
            value={studentFilter}
            onChange={(e) => setStudentFilter(e.target.value)}
            placeholder="All students"
          />
        </label>
      </SectionCard>

      <SectionCard
        title="Reminder log"
        description="Append-only. This is what was attempted, not what the school intended to attempt."
        icon={<Send className="size-4 text-gray-500" />}
      >
        <DataTable
          columns={columns}
          rows={rows}
          rowKey={(r) => r.id}
          state={reminders.status}
          error={reminders.error}
          onRetry={reminders.refetch}
          emptyTitle={validStudentId ? 'No reminders for this student' : 'No reminders sent yet'}
          emptyDescription={
            validStudentId
              ? 'This family has not been chased about a fee balance.'
              : 'Nothing has been sent. This is not the same as everyone having paid — check Arrears for who owes money.'
          }
          emptyIcon={BellRing}
          totalLabel={
            rows.length > 0 ? `${rows.length} reminder${rows.length === 1 ? '' : 's'}` : undefined
          }
        />
      </SectionCard>
    </DashPageShell>
  )
}
