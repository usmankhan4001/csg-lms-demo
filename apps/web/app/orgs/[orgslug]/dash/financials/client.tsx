'use client'

/**
 * Financials, attached as a first-class Learnhouse dash module.
 *
 * Net-new: `modules/sms/financials/api.ts` existed but nothing ever rendered
 * it. Shows the two things a double-entry ledger exists to give you -- a
 * trial balance that proves the books balance, and a journal you can correct
 * only by reversal.
 *
 * The reversal relationship is surfaced in both directions because that IS
 * the ledger's integrity story: an append-only book is only trustworthy if a
 * correction visibly points at what it corrected. `reverses_entry_id` comes
 * back from the API (schemas/sms_financials.py) but is missing from the
 * shared frontend type, so it's declared locally rather than editing that
 * shared file from inside this module.
 *
 * There is no `is_reversed` flag on an entry; "has been reversed" is derived
 * from whether any other entry points back at it.
 */

import { useMemo, useState } from 'react'
import { BookOpen, Scale, Undo2 } from 'lucide-react'
import { DashPageShell, DataTable, SectionCard, StatGrid, StatusChip } from '@/components/widgets'
import { Button } from '@/components/ui/button'
import { apiPost } from '@/lib/api/api-client'
import { useApiResource } from '@/lib/api/useApiResource'
import { listCampuses } from '@/modules/sms/campus/api'
import { getTrialBalance, listJournalEntries } from '@/modules/sms/financials/api'
import type { JournalEntryRead } from '@/modules/sms/financials/types'

/** `reverses_entry_id` is returned by the API but absent from the shared type. */
type JournalEntryWithReversal = JournalEntryRead & { reverses_entry_id?: number | null }

function money(n: number): string {
  return `Rs. ${n.toFixed(2)}`
}

interface FinancialsDashClientProps {
  org_id: number
  orgslug: string
}

export default function FinancialsDashClient({ org_id }: FinancialsDashClientProps) {
  const [campusId, setCampusId] = useState<number | ''>('')
  const [reversingId, setReversingId] = useState<number | null>(null)
  const [reversalNote, setReversalNote] = useState<string | null>(null)

  const campuses = useApiResource(() => listCampuses({ orgId: org_id, isActive: true }), [org_id])
  const scopeCampusId = campusId === '' ? undefined : campusId

  const trialBalance = useApiResource(() => getTrialBalance(scopeCampusId), [scopeCampusId], {
    isEmpty: (d) => d.items.length === 0,
  })

  const entries = useApiResource(() => listJournalEntries(scopeCampusId), [scopeCampusId], {
    isEmpty: (d) => d.length === 0,
  })

  const entryRows = (entries.data ?? []) as JournalEntryWithReversal[]

  // An entry is "reversed" when some other entry points back at it.
  const reversedIds = useMemo(() => {
    const s = new Set<number>()
    for (const e of entryRows) {
      if (e.reverses_entry_id != null) s.add(e.reverses_entry_id)
    }
    return s
  }, [entryRows])

  async function handleReverse(entryId: number) {
    setReversingId(entryId)
    setReversalNote(null)
    try {
      // Called directly: modules/sms/financials/api.ts has no wrapper for the
      // reversal endpoint yet, and that shared file is outside this scope.
      await apiPost<JournalEntryWithReversal>(
        `/sms/financials/journal-entries/${entryId}/reverse`
      )
      setReversalNote(`Entry #${entryId} reversed. The correcting entry now points back at it.`)
      entries.refetch()
      trialBalance.refetch()
    } catch {
      setReversalNote(
        `Couldn't reverse entry #${entryId}. It may already be reversed, or be a reversal itself.`
      )
    } finally {
      setReversingId(null)
    }
  }

  const tb = trialBalance.data

  return (
    <DashPageShell
      title={"Financials"}
      description="Trial balance and the double-entry journal behind it."
    >
      <StatGrid
        state={trialBalance.status === 'loading' ? 'loading' : 'success'}
        columns={3}
        items={[
          {
            label: 'Total debits',
            value: tb ? money(tb.total_debit) : '—',
            icon: Scale,
            tone: 'neutral',
          },
          {
            label: 'Total credits',
            value: tb ? money(tb.total_credit) : '—',
            icon: Scale,
            tone: 'neutral',
          },
          {
            label: 'Books balanced',
            value: tb ? (tb.is_balanced ? 'Yes' : 'No') : '—',
            icon: Scale,
            tone: tb ? (tb.is_balanced ? 'positive' : 'critical') : 'neutral',
          },
        ]}
      />

      {(campuses.data ?? []).length > 0 && (
        <SectionCard title="Scope" icon={<BookOpen className="size-4 text-gray-500" />}>
          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-gray-500">Campus</span>
            <select
              id="financials-campus"
              className="w-64 px-3 py-2 bg-white nice-shadow rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-black focus:ring-offset-2 border-0"
              value={campusId}
              onChange={(e) => setCampusId(e.target.value === '' ? '' : Number(e.target.value))}
            >
              <option value="">All campuses</option>
              {(campuses.data ?? []).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
        </SectionCard>
      )}

      <SectionCard
        id="trial-balance"
        title="Trial balance"
        description={tb && !tb.is_balanced ? 'Debits and credits do not agree' : undefined}
        icon={<Scale className="size-4 text-gray-500" />}
        state={trialBalance.status}
        error={trialBalance.error}
        onRetry={trialBalance.refetch}
        emptyTitle="No accounts yet"
        emptyDescription="Add accounts to the chart of accounts to see a trial balance."
      >
        <DataTable
          rows={tb?.items ?? []}
          rowKey={(row) => row.account_id}
          state="success"
          columns={[
            { key: 'code', header: 'Code', render: (r) => r.account_code },
            { key: 'name', header: 'Account', render: (r) => r.account_name },
            { key: 'type', header: 'Type', render: (r) => <StatusChip label={r.account_type} tone="info" /> },
            {
              key: 'debit',
              header: 'Debit',
              align: 'right',
              className: 'tabular-nums',
              render: (r) => (r.debit_balance ? money(r.debit_balance) : '—'),
            },
            {
              key: 'credit',
              header: 'Credit',
              align: 'right',
              className: 'tabular-nums',
              render: (r) => (r.credit_balance ? money(r.credit_balance) : '—'),
            },
          ]}
        />
      </SectionCard>

      <SectionCard
        id="journal"
        title="Journal entries"
        description="Corrections are posted as reversals — entries are never edited or deleted."
        icon={<BookOpen className="size-4 text-gray-500" />}
        state={entries.status}
        error={entries.error}
        onRetry={entries.refetch}
        emptyTitle="No journal entries yet"
        emptyDescription="Posted entries and their reversals will appear here."
      >
        {reversalNote && <p className="mb-3 text-sm text-gray-500">{reversalNote}</p>}
        <DataTable
          rows={entryRows}
          rowKey={(row) => row.id}
          state="success"
          totalLabel={`${entryRows.length} entr${entryRows.length === 1 ? 'y' : 'ies'}`}
          columns={[
            { key: 'ref', header: 'Reference', render: (r) => r.reference_no },
            { key: 'date', header: 'Date', render: (r) => r.entry_date },
            {
              key: 'desc',
              header: 'Description',
              render: (r) => r.description || '—',
            },
            {
              key: 'debit',
              header: 'Debit',
              align: 'right',
              className: 'tabular-nums',
              render: (r) => money(r.total_debit),
            },
            {
              key: 'credit',
              header: 'Credit',
              align: 'right',
              className: 'tabular-nums',
              render: (r) => money(r.total_credit),
            },
            {
              key: 'state',
              header: 'State',
              render: (r) =>
                r.reverses_entry_id != null ? (
                  <StatusChip label={`Reverses #${r.reverses_entry_id}`} tone="info" icon={Undo2} />
                ) : reversedIds.has(r.id) ? (
                  <StatusChip label="Reversed" tone="caution" />
                ) : (
                  <StatusChip label="Posted" tone="positive" />
                ),
            },
            {
              key: 'action',
              header: '',
              align: 'right',
              render: (r) =>
                r.reverses_entry_id == null && !reversedIds.has(r.id) ? (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleReverse(r.id)}
                    disabled={reversingId === r.id}
                  >
                    {reversingId === r.id ? 'Reversing…' : 'Reverse'}
                  </Button>
                ) : (
                  <span className="text-xs text-gray-500">—</span>
                ),
            },
          ]}
        />
      </SectionCard>
    </DashPageShell>
  )
}
