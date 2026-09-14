'use client'

/**
 * Bank reconciliation -- attributing received money to the family that sent it.
 *
 * This is the screen that made the bank-transfer endpoints worth building. A
 * payment can otherwise only be recorded if the office ALREADY knows which
 * voucher it belongs to, but a transfer arrives as an amount, a date and
 * whatever reference the payer typed. Forty of those on a Monday morning are
 * not matchable by hand.
 *
 * The design rule here is that NOTHING on this screen attributes money without
 * a human pressing a button. Suggestions are candidates with their evidence
 * stated; a wrong automatic match moves real money against the wrong family
 * and is discovered weeks later when someone is chased for a fee they paid.
 */

import { useState } from 'react'
import toast from 'react-hot-toast'
import { Banknote, Link2, ListChecks, Upload } from 'lucide-react'
import {
  DashPageShell,
  DataTable,
  EmptyState,
  LH_GHOST_BUTTON,
  LH_INPUT,
  LH_PRIMARY_BUTTON,
  LH_SECONDARY_BUTTON,
  SchoolDialog,
  SchoolField,
  SectionCard,
  StatGrid,
  StatusChip,
} from '@/components/widgets'
import type { DataTableColumn } from '@/components/widgets'
import { useApiResource } from '@/lib/api/useApiResource'
import { listCampuses } from '@/modules/sms/campus/api'
import {
  importBankTransfers,
  listUnmatchedTransfers,
  matchTransfer,
  suggestTransferMatches,
} from '@/modules/sms/fees/api'
import { isoDate, money } from '@/modules/sms/fees/format'
import type { BankTransferLine, BankTransferRead } from '@/modules/sms/fees/types'

interface Props {
  org_id: number
  orgslug: string
}

/**
 * Parses pasted statement lines into transfer rows.
 *
 * Deliberately a dumb, explicit format (date, amount, reference, payer, note)
 * rather than an attempt to sniff a bank's own CSV export. The backend refuses
 * to guess at a bank column for the same reason: a misread column attributes
 * somebody's money to a stranger. Anything unparseable is reported with its
 * line number rather than skipped.
 */
function parseStatementLines(raw: string): { rows: BankTransferLine[]; errors: string[] } {
  const rows: BankTransferLine[] = []
  const errors: string[] = []

  raw
    .split('\n')
    .map((l) => l.trim())
    .forEach((line, i) => {
      if (!line) return
      const lineNo = i + 1
      const parts = line.split(',').map((p) => p.trim())
      const [date, amount, reference, payer, note] = parts

      if (!date || !/^\d{4}-\d{2}-\d{2}$/.test(date)) {
        errors.push(`Line ${lineNo}: date must be YYYY-MM-DD.`)
        return
      }
      const parsed = Number(amount)
      if (!amount || Number.isNaN(parsed) || parsed <= 0) {
        errors.push(`Line ${lineNo}: amount must be a number greater than zero.`)
        return
      }
      rows.push({
        transfer_date: date,
        amount: parsed,
        bank_reference: reference || null,
        payer_name: payer || null,
        payer_note: note || null,
      })
    })

  return { rows, errors }
}

function ImportTransfersDialog({
  campusId,
  onImported,
}: {
  campusId?: number
  onImported: () => void
}) {
  const [open, setOpen] = useState(false)
  const [raw, setRaw] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const { rows, errors } = parseStatementLines(raw)

  async function handleSubmit() {
    if (rows.length === 0) {
      toast.error('Nothing to import — add at least one statement line.')
      return
    }
    if (errors.length > 0) {
      toast.error('Fix the lines listed below before importing.')
      return
    }
    if (rows.length > 500) {
      toast.error('Import at most 500 lines at a time.')
      return
    }
    setSubmitting(true)
    try {
      const created = await importBankTransfers({ rows, campus_id: campusId ?? null })
      toast.success(
        `Imported ${created.length} line${created.length === 1 ? '' : 's'} into the queue.`
      )
      setOpen(false)
      setRaw('')
      onImported()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not import those lines.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <SchoolDialog
      open={open}
      onOpenChange={setOpen}
      trigger={
        <button type="button" className={LH_SECONDARY_BUTTON}>
          <Upload className="size-4" /> <span>Import statement lines</span>
        </button>
      }
      title="Import bank statement lines"
      description="One line per transfer. Importing only queues them — nothing is attributed to a family until you match it."
      footer={
        <>
          <button
            type="button"
            className={LH_GHOST_BUTTON}
            onClick={() => setOpen(false)}
            disabled={submitting}
          >
            Cancel
          </button>
          <button
            type="button"
            className={LH_PRIMARY_BUTTON}
            onClick={handleSubmit}
            disabled={submitting || rows.length === 0 || errors.length > 0}
          >
            <span>
              {submitting
                ? 'Importing…'
                : `Import ${rows.length} line${rows.length === 1 ? '' : 's'}`}
            </span>
          </button>
        </>
      }
    >
      <SchoolField
        id="import-rows"
        label="Statement lines"
        required
        help="Comma-separated: date, amount, bank reference, payer name, payer note. Only date and amount are required."
      >
        <textarea
          id="import-rows"
          className={`${LH_INPUT} min-h-40 font-mono text-xs`}
          value={raw}
          onChange={(e) => setRaw(e.target.value)}
          placeholder={'2026-09-01, 45000, TRX88213, Ayesha Khan, Fee for Ali\n2026-09-01, 32000, TRX88214, Bilal Ahmed,'}
        />
      </SchoolField>

      {rows.length > 0 && errors.length === 0 ? (
        <p className="text-sm text-gray-600">
          {rows.length} line{rows.length === 1 ? '' : 's'} ready to queue.
        </p>
      ) : null}

      {errors.length > 0 ? (
        <div className="rounded-lg bg-red-50 px-3 py-2.5">
          <p className="text-sm font-medium text-red-800">
            {errors.length} line{errors.length === 1 ? '' : 's'} cannot be read
          </p>
          <ul className="mt-1 list-disc ps-5 text-xs text-red-700">
            {errors.slice(0, 8).map((e) => (
              <li key={e}>{e}</li>
            ))}
          </ul>
          {errors.length > 8 ? (
            <p className="mt-1 text-xs text-red-700">…and {errors.length - 8} more.</p>
          ) : null}
        </div>
      ) : null}
    </SchoolDialog>
  )
}

/**
 * The match step. Opens on one transfer, lists candidate vouchers with the
 * evidence each was found on, and requires an explicit choice.
 */
function MatchTransferDialog({
  transfer,
  onClose,
  onMatched,
}: {
  transfer: BankTransferRead | null
  onClose: () => void
  onMatched: () => void
}) {
  const [matching, setMatching] = useState<number | null>(null)

  const suggestions = useApiResource(
    () => (transfer ? suggestTransferMatches(transfer.id) : Promise.resolve([])),
    [transfer?.id],
    { skip: !transfer }
  )

  async function handleMatch(voucherId: number) {
    if (!transfer) return
    setMatching(voucherId)
    try {
      await matchTransfer({ transfer_id: transfer.id, voucher_id: voucherId })
      toast.success('Transfer attributed and payment recorded.')
      onMatched()
      onClose()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not match that transfer.')
    } finally {
      setMatching(null)
    }
  }

  return (
    <SchoolDialog
      open={transfer !== null}
      onOpenChange={(open) => {
        if (!open) onClose()
      }}
      title="Match this transfer"
      description={
        transfer
          ? `${money(transfer.amount)} received ${isoDate(transfer.transfer_date)}${
              transfer.payer_name ? ` from ${transfer.payer_name}` : ''
            }.`
          : undefined
      }
      footer={
        <button type="button" className={LH_GHOST_BUTTON} onClick={onClose}>
          Close
        </button>
      }
    >
      {transfer ? (
        <div className="rounded-lg bg-gray-50 px-3 py-2.5 text-xs text-gray-600">
          <div>
            <span className="font-medium text-gray-700">Reference:</span>{' '}
            {transfer.bank_reference || 'None given'}
          </div>
          <div>
            <span className="font-medium text-gray-700">Payer note:</span>{' '}
            {transfer.payer_note || 'None given'}
          </div>
        </div>
      ) : null}

      <SectionCard
        title="Candidate vouchers"
        description="Candidates only — choosing one records a real payment against that family."
        icon={<Link2 className="size-4 text-gray-500" />}
        state={suggestions.status}
        error={suggestions.error}
        onRetry={suggestions.refetch}
        emptyTitle="No candidates found"
        emptyDescription="Nothing matched on voucher number, amount or student id. Find the voucher on the Vouchers tab and record the payment there."
      >
        <ul className="flex flex-col gap-2">
          {(suggestions.data ?? []).map((s) => (
            <li
              key={s.voucher.id}
              className="flex flex-wrap items-center justify-between gap-3 rounded-lg bg-white px-3 py-2.5 nice-shadow"
            >
              <div className="min-w-0">
                <div className="text-sm font-medium text-gray-900">
                  {s.voucher.voucher_no} — student #{s.voucher.student_id}
                </div>
                <div className="text-xs text-gray-500">
                  Outstanding {money(s.voucher.balance_amount)} · due{' '}
                  {isoDate(s.voucher.due_date)}
                </div>
                {s.matched_on.length > 0 ? (
                  <ul className="mt-1 flex flex-wrap gap-1">
                    {s.matched_on.map((m) => (
                      <li
                        key={m}
                        className="rounded bg-emerald-50 px-1.5 py-0.5 text-[11px] text-emerald-800"
                      >
                        {m}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-1 text-[11px] text-gray-500">
                    Listed as a possibility, but nothing specific lined up.
                  </p>
                )}
              </div>
              <button
                type="button"
                className={LH_PRIMARY_BUTTON}
                onClick={() => handleMatch(s.voucher.id)}
                disabled={matching !== null}
              >
                <span>{matching === s.voucher.id ? 'Matching…' : 'Match'}</span>
              </button>
            </li>
          ))}
        </ul>
      </SectionCard>
    </SchoolDialog>
  )
}

export default function FeesReconciliationClient(_props: Props) {
  const [campusId, setCampusId] = useState<number | undefined>(undefined)
  const [active, setActive] = useState<BankTransferRead | null>(null)

  const campuses = useApiResource(() => listCampuses(), [])
  const effectiveCampusId = campusId ?? campuses.data?.[0]?.id

  const transfers = useApiResource(
    () => listUnmatchedTransfers({ campusId: effectiveCampusId }),
    [effectiveCampusId],
    { skip: effectiveCampusId === undefined }
  )

  const rows = transfers.data ?? []

  // Summing the QUEUE is legitimate -- this is "how much money is sitting
  // unattributed", which is a property of the list in front of the user, not a
  // ledger balance. Ledger totals still come from the server.
  const queuedTotal = rows.reduce((s, t) => s + t.amount, 0)
  const oldest = rows.reduce<string | null>(
    (acc, t) => (acc === null || t.transfer_date < acc ? t.transfer_date : acc),
    null
  )

  const columns: DataTableColumn<BankTransferRead>[] = [
    {
      key: 'date',
      header: 'Received',
      render: (t) => <span className="tabular-nums">{isoDate(t.transfer_date)}</span>,
    },
    {
      key: 'amount',
      header: 'Amount',
      align: 'right',
      render: (t) => <span className="tabular-nums font-medium">{money(t.amount)}</span>,
    },
    {
      key: 'payer',
      header: 'Payer',
      render: (t) => t.payer_name || <span className="text-gray-400">Not given</span>,
    },
    {
      key: 'reference',
      header: 'Reference',
      render: (t) => (
        <span className="font-mono text-xs">
          {t.bank_reference || <span className="text-gray-400">None</span>}
        </span>
      ),
    },
    {
      key: 'note',
      header: 'Payer note',
      render: (t) => t.payer_note || <span className="text-gray-400">None</span>,
    },
    {
      key: 'status',
      header: 'Status',
      render: (t) => <StatusChip tone="caution" label="Unattributed" />,
    },
    {
      key: 'action',
      header: '',
      align: 'right',
      render: (t) => (
        <button type="button" className={LH_SECONDARY_BUTTON} onClick={() => setActive(t)}>
          <Link2 className="size-4" /> <span>Find match</span>
        </button>
      ),
    },
  ]

  return (
    <DashPageShell
      title="Bank reconciliation"
      description="Money received that nobody has attributed to a family yet."
      module="fees"
      action={
        <ImportTransfersDialog campusId={effectiveCampusId} onImported={transfers.refetch} />
      }
    >
      <StatGrid
        state={transfers.status === 'loading' ? 'loading' : 'success'}
        columns={3}
        items={[
          {
            label: 'Waiting to be attributed',
            value: String(rows.length),
            icon: ListChecks,
            tone: rows.length > 0 ? 'caution' : 'positive',
          },
          {
            label: 'Value in the queue',
            value: money(queuedTotal),
            icon: Banknote,
            tone: 'neutral',
          },
          {
            label: 'Oldest unattributed',
            value: oldest ? isoDate(oldest) : 'Nothing queued',
            icon: Banknote,
            tone: 'neutral',
          },
        ]}
      />

      <SectionCard
        title="Campus"
        state={campuses.status === 'loading' ? 'loading' : campuses.status}
        error={campuses.error}
        onRetry={campuses.refetch}
        emptyTitle="No campuses set up yet"
        emptyDescription="Add a campus before reconciling bank transfers."
      >
        <label className="flex flex-col gap-1.5">
          <span className="text-xs font-medium text-gray-500">Campus</span>
          <select
            id="recon-campus"
            className="px-3 py-2 bg-white nice-shadow rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-black focus:ring-offset-2 border-0"
            value={effectiveCampusId ?? ''}
            onChange={(e) => setCampusId(Number(e.target.value))}
          >
            {(campuses.data ?? []).map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
      </SectionCard>

      <SectionCard
        title="Unattributed transfers"
        description="Each one is money the school has received but cannot yet credit to a family."
        icon={<Banknote className="size-4 text-gray-500" />}
      >
        <DataTable
          columns={columns}
          rows={rows}
          rowKey={(t) => t.id}
          state={transfers.status}
          error={transfers.error}
          onRetry={transfers.refetch}
          emptyTitle="Nothing waiting"
          emptyDescription="Every transfer imported so far has been attributed to a family."
          emptyIcon={ListChecks}
          totalLabel={
            rows.length > 0 ? `${rows.length} transfer${rows.length === 1 ? '' : 's'}` : undefined
          }
        />
      </SectionCard>

      <MatchTransferDialog
        transfer={active}
        onClose={() => setActive(null)}
        onMatched={transfers.refetch}
      />
    </DashPageShell>
  )
}
