'use client'

/**
 * M34 — the knowledge base the admissions agents draw on.
 *
 * The point of this screen is not storage, it is REVIEW: an agent answering a
 * family quotes what is in here, so a human needs to be able to find the
 * claims nobody has backed with a source before one reaches a parent. That is
 * why `is_sourceless` is a first-class filter and a visible marker rather than
 * two empty columns a reviewer has to notice.
 */

import { useMemo, useState } from 'react'
import { BookOpen, Search, ShieldAlert } from 'lucide-react'
import {
  DashPageShell,
  DataTable,
  LH_INPUT,
  LH_PRIMARY_BUTTON,
  LH_SECONDARY_BUTTON,
  SchoolDialog,
  SchoolField,
  SectionCard,
  StatGrid,
  StatusChip,
} from '@/components/widgets'
import { ApiError } from '@/lib/api/api-client'
import { useApiResource } from '@/lib/api/useApiResource'
import {
  createKnowledgeEntry,
  listKnowledgeEntries,
  searchKnowledgeEntries,
  updateKnowledgeEntry,
} from '@/modules/sms/revops-admin/api'
import {
  describeKnowledgeStatus,
  describeSource,
  isQuotableWithConfidence,
} from '@/modules/sms/revops-admin/presentation'
import type {
  KnowledgeEntryRead,
  KnowledgeEntryStatus,
  KnowledgeEntryWrite,
} from '@/modules/sms/revops-admin/types'

interface KnowledgeClientProps {
  org_id: number
  orgslug: string
}

const STATUSES: KnowledgeEntryStatus[] = ['DRAFT', 'PUBLISHED', 'ARCHIVED']

function EntryDialog({
  entry,
  onDone,
}: {
  entry?: KnowledgeEntryRead
  onDone: () => void
}) {
  const [open, setOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const editing = entry !== undefined

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const form = new FormData(e.currentTarget)
    const title = String(form.get('title') ?? '').trim()
    const body = String(form.get('body') ?? '').trim()

    if (!title || !body) {
      setError('A title and body are required.')
      return
    }

    // A source is NEVER synthesised. Empty stays empty, and the server reports
    // the entry as sourceless so a reviewer can find it.
    const payload: KnowledgeEntryWrite = {
      title,
      body,
      category: String(form.get('category') ?? '').trim() || null,
      source_label: String(form.get('source_label') ?? '').trim() || null,
      source_url: String(form.get('source_url') ?? '').trim() || null,
      status: (form.get('status') as KnowledgeEntryStatus) || 'DRAFT',
    }

    setSaving(true)
    setError(null)
    try {
      if (editing && entry) await updateKnowledgeEntry(entry.id, payload)
      else await createKnowledgeEntry(payload)
      setOpen(false)
      onDone()
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.kind === 'permission_denied'
            ? 'You need back-office access to change the knowledge base.'
            : err.message
          : 'Could not save. Try again.'
      )
    } finally {
      setSaving(false)
    }
  }

  return (
    <SchoolDialog
      open={open}
      onOpenChange={setOpen}
      trigger={
        <button type="button" className={editing ? LH_SECONDARY_BUTTON : LH_PRIMARY_BUTTON}>
          <span>{editing ? 'Edit' : 'New entry'}</span>
        </button>
      }
      title={editing ? 'Edit knowledge entry' : 'New knowledge entry'}
      description="Content the admissions agents may quote. An entry saved without a source is stored sourceless and flagged for review — nothing is invented to fill the gap."
      onSubmit={handleSubmit}
      footer={
        <button type="submit" disabled={saving} className={LH_PRIMARY_BUTTON}>
          <span>{saving ? 'Saving…' : 'Save'}</span>
        </button>
      }
    >
      <SchoolField id="kb-title" label="Title" required>
        <input id="kb-title" name="title" className={LH_INPUT} defaultValue={entry?.title} />
      </SchoolField>

      <SchoolField id="kb-body" label="Body" required>
        <textarea
          id="kb-body"
          name="body"
          rows={6}
          className={LH_INPUT}
          defaultValue={entry?.body}
        />
      </SchoolField>

      <SchoolField id="kb-category" label="Category">
        <input
          id="kb-category"
          name="category"
          className={LH_INPUT}
          defaultValue={entry?.category ?? ''}
          placeholder="e.g. fees, curriculum, admissions"
        />
      </SchoolField>

      <SchoolField
        id="kb-source-label"
        label="Source"
        help="Where this claim comes from. Left blank, the entry is marked sourceless rather than given a made-up citation."
      >
        <input
          id="kb-source-label"
          name="source_label"
          className={LH_INPUT}
          defaultValue={entry?.source_label ?? ''}
          placeholder="e.g. 2026 fee schedule, board minutes"
        />
      </SchoolField>

      <SchoolField id="kb-source-url" label="Source link">
        <input
          id="kb-source-url"
          name="source_url"
          className={LH_INPUT}
          defaultValue={entry?.source_url ?? ''}
        />
      </SchoolField>

      <SchoolField
        id="kb-status"
        label="Status"
        help="Only PUBLISHED entries are served to the agents. A draft is your working note."
      >
        <select
          id="kb-status"
          name="status"
          className={LH_INPUT}
          defaultValue={entry?.status ?? 'DRAFT'}
        >
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {describeKnowledgeStatus(s).label}
            </option>
          ))}
        </select>
      </SchoolField>

      {error && <p className="text-sm text-rose-600">{error}</p>}
    </SchoolDialog>
  )
}

export default function RevOpsKnowledgeClient({ org_id }: KnowledgeClientProps) {
  const [statusFilter, setStatusFilter] = useState<KnowledgeEntryStatus | ''>('')
  const [sourcelessOnly, setSourcelessOnly] = useState(false)
  const [query, setQuery] = useState('')
  const [activeQuery, setActiveQuery] = useState('')
  const [includeDrafts, setIncludeDrafts] = useState(false)

  const entries = useApiResource(
    () =>
      activeQuery
        ? searchKnowledgeEntries({ q: activeQuery, include_drafts: includeDrafts })
        : listKnowledgeEntries({ status: statusFilter || undefined }),
    [activeQuery, includeDrafts, statusFilter],
    { isEmpty: (d) => d.length === 0 }
  )

  const rows = useMemo(() => {
    const all = entries.data ?? []
    return sourcelessOnly ? all.filter((e) => e.is_sourceless) : all
  }, [entries.data, sourcelessOnly])

  const all = entries.data ?? []
  const sourcelessCount = all.filter((e) => e.is_sourceless).length
  const publishedCount = all.filter((e) => e.status === 'PUBLISHED').length
  const quotableCount = all.filter(isQuotableWithConfidence).length

  return (
    <DashPageShell
      title="Knowledge base"
      description="What the admissions agents are allowed to draw on when answering a family."
      module="revops"
    >
      <StatGrid
        state={entries.status === 'loading' ? 'loading' : 'success'}
        columns={3}
        items={[
          { label: 'Entries', value: all.length, icon: BookOpen, tone: 'neutral' },
          { label: 'Published', value: publishedCount, icon: BookOpen, tone: 'neutral' },
          {
            label: 'Without a source',
            value: sourcelessCount,
            icon: ShieldAlert,
            tone: sourcelessCount > 0 ? 'caution' : 'positive',
          },
        ]}
      />

      {sourcelessCount > 0 && (
        <div className="rounded-lg bg-amber-50 px-3 py-2.5 text-sm text-amber-900">
          <strong>
            {sourcelessCount} {sourcelessCount === 1 ? 'entry has' : 'entries have'} no source
            recorded.
          </strong>{' '}
          An agent can quote a published entry to a family, so anything unbacked is worth reading
          before it is published. {quotableCount} of {all.length} are published and sourced.
        </div>
      )}

      <SectionCard
        id="kb-search"
        title="Find an entry"
        description="Keyword search over the title, body and category — not a semantic search, so exact words matter."
        icon={<Search className="size-4 text-gray-500" />}
      >
        <div className="flex flex-wrap items-end gap-4">
          <div className="flex flex-col gap-1.5">
            <label htmlFor="kb-search-q" className="text-xs font-medium text-gray-500">
              Search
            </label>
            <input
              id="kb-search-q"
              className={LH_INPUT}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') setActiveQuery(query.trim())
              }}
              placeholder="e.g. scholarship"
            />
          </div>
          <button
            type="button"
            id="kb-search-go"
            className={LH_SECONDARY_BUTTON}
            onClick={() => setActiveQuery(query.trim())}
          >
            <span>Search</span>
          </button>
          {activeQuery && (
            <button
              type="button"
              id="kb-search-clear"
              className={LH_SECONDARY_BUTTON}
              onClick={() => {
                setQuery('')
                setActiveQuery('')
              }}
            >
              <span>Clear</span>
            </button>
          )}

          {activeQuery && (
            <label className="flex items-center gap-2 text-sm text-gray-700">
              <input
                id="kb-include-drafts"
                type="checkbox"
                checked={includeDrafts}
                onChange={(e) => setIncludeDrafts(e.target.checked)}
              />
              <span>Include drafts</span>
            </label>
          )}

          {!activeQuery && (
            <div className="flex flex-col gap-1.5">
              <label htmlFor="kb-status-filter" className="text-xs font-medium text-gray-500">
                Status
              </label>
              <select
                id="kb-status-filter"
                className={LH_INPUT}
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value as KnowledgeEntryStatus | '')}
              >
                <option value="">All</option>
                {STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {describeKnowledgeStatus(s).label}
                  </option>
                ))}
              </select>
            </div>
          )}

          <label className="flex items-center gap-2 text-sm text-gray-700">
            <input
              id="kb-sourceless-only"
              type="checkbox"
              checked={sourcelessOnly}
              onChange={(e) => setSourcelessOnly(e.target.checked)}
            />
            <span>Only entries without a source</span>
          </label>
        </div>

        {activeQuery && !includeDrafts && (
          <p className="mt-3 text-xs text-gray-500">
            Searching published entries only — the same set an agent can quote. Tick “include
            drafts” to see working notes as well.
          </p>
        )}
      </SectionCard>

      <SectionCard
        id="kb-entries"
        title={activeQuery ? `Results for “${activeQuery}”` : 'All entries'}
        icon={<BookOpen className="size-4 text-gray-500" />}
        state={entries.status === 'loading' ? 'loading' : entries.status}
        error={entries.error}
        onRetry={entries.refetch}
        action={<EntryDialog onDone={entries.refetch} />}
        emptyTitle={activeQuery ? 'Nothing matched' : 'No entries yet'}
        emptyDescription={
          activeQuery
            ? 'No published entry contains those words. This is keyword search, so try a different phrasing.'
            : 'The admissions agents have no approved content to draw on yet.'
        }
      >
        <DataTable
          rows={rows}
          rowKey={(r) => r.id}
          state="success"
          totalLabel={`${rows.length} ${rows.length === 1 ? 'entry' : 'entries'}`}
          columns={[
            { key: 'title', header: 'Title', render: (r) => r.title },
            { key: 'category', header: 'Category', render: (r) => r.category ?? '—' },
            {
              key: 'source',
              header: 'Source',
              render: (r) =>
                r.is_sourceless ? (
                  <StatusChip label="No source" tone="caution" />
                ) : (
                  <span className="text-sm text-gray-700">{describeSource(r)}</span>
                ),
            },
            {
              key: 'status',
              header: 'Status',
              render: (r) => {
                const s = describeKnowledgeStatus(r.status)
                return <StatusChip label={s.label} tone={s.tone} />
              },
            },
            {
              key: 'actions',
              header: '',
              render: (r) => <EntryDialog entry={r} onDone={entries.refetch} />,
            },
          ]}
        />
      </SectionCard>
    </DashPageShell>
  )
}
