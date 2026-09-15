'use client'

/**
 * Certificate templates — the design a certificate is printed from.
 *
 * `/dash/certificates-manager` has been linked from BOTH sidebars
 * (DashLeftMenu.tsx:790, DashMobileMenu.tsx:349) with no route behind it, so
 * every click produced a 404.
 *
 * Creating a template is `[SUPER_ADMIN, SCHOOL_ADMIN]` while ISSUING one is
 * open to teachers (`sms_certificates.py:32` vs `:49`). That split is real and
 * this screen respects it: a teacher can open the page and see what templates
 * exist, and gets an honest refusal if they try to create one.
 */

import { useState } from 'react'
import { FileBadge } from 'lucide-react'

import {
  DashPageShell,
  DataTable,
  SchoolDialog,
  SchoolField,
  SectionCard,
  StatusChip,
  LH_INPUT,
  LH_PRIMARY_BUTTON,
  LH_SECONDARY_BUTTON,
  type DataTableColumn,
  type DataTableState,
} from '@/components/widgets'
import { useApiResource } from '@/lib/api/useApiResource'
import { ApiError } from '@/lib/api/api-client'
import { createTemplate, listTemplates } from '@/modules/sms/certificates/api'
import {
  BORDER_STYLES,
  LAYOUT_TYPES,
  type CertificateTemplate,
} from '@/modules/sms/certificates/types'

export default function CertificateTemplatesClient({
  org_id,
  orgslug,
}: {
  org_id: number
  orgslug: string
}) {
  void org_id
  void orgslug

  const [createOpen, setCreateOpen] = useState(false)

  const templates = useApiResource<CertificateTemplate[]>(() => listTemplates(), [])
  const rows = templates.data ?? []

  const tableState: DataTableState =
    templates.status === 'loading'
      ? 'loading'
      : templates.status === 'error'
        ? 'error'
        : rows.length === 0
          ? 'empty'
          : 'success'

  const columns: DataTableColumn<CertificateTemplate>[] = [
    {
      key: 'title',
      header: 'Template',
      render: (row) => (
        <div className="min-w-0">
          <div className="font-medium truncate">{row.title}</div>
          {row.description ? (
            <div className="text-xs text-gray-500 truncate">{row.description}</div>
          ) : null}
        </div>
      ),
    },
    {
      key: 'issuer',
      header: 'Signed by',
      render: (row) => (
        <div className="min-w-0">
          <div className="truncate">{row.issuer_name}</div>
          <div className="text-xs text-gray-500 truncate">{row.issuer_title}</div>
        </div>
      ),
    },
    {
      key: 'layout',
      header: 'Layout',
      render: (row) => <StatusChip label={row.layout_type} tone="neutral" />,
    },
    {
      key: 'active',
      header: 'Status',
      render: (row) =>
        row.is_active ? (
          <StatusChip label="Active" tone="positive" />
        ) : (
          <StatusChip label="Inactive" tone="neutral" />
        ),
    },
  ]

  return (
    <DashPageShell
      title="Certificates"
      description="Templates a certificate is printed from. Issuing one is a separate step."
      module="certificates"
      action={
        <button
          type="button"
          id="certificates-new-template"
          className={LH_PRIMARY_BUTTON}
          onClick={() => setCreateOpen(true)}
        >
          New template
        </button>
      }
    >
      <SectionCard
        title="Templates"
        description={
          templates.status === 'success' && rows.length > 0
            ? `${rows.length} defined`
            : undefined
        }
      >
        <DataTable<CertificateTemplate>
          columns={columns}
          rows={rows}
          rowKey={(row) => row.id}
          state={tableState}
          error={templates.error}
          onRetry={templates.refetch}
          emptyIcon={FileBadge}
          emptyTitle="No templates defined"
          emptyDescription="A certificate needs a template before it can be issued. Create one to set the title, signatory and layout."
        />
      </SectionCard>

      <CreateTemplateDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onCreated={() => {
          setCreateOpen(false)
          templates.refetch()
        }}
      />
    </DashPageShell>
  )
}

function CreateTemplateDialog({
  open,
  onOpenChange,
  onCreated,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onCreated: () => void
}) {
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [issuerName, setIssuerName] = useState('')
  const [issuerTitle, setIssuerTitle] = useState('')
  const [layout, setLayout] = useState<string>(LAYOUT_TYPES[0])
  const [border, setBorder] = useState<string>(BORDER_STYLES[0])
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      await createTemplate({
        title: title.trim(),
        description: description.trim() || undefined,
        issuer_name: issuerName.trim(),
        issuer_title: issuerTitle.trim(),
        layout_type: layout,
        border_style: border,
      })
      setTitle('')
      setDescription('')
      onCreated()
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.kind === 'permission_denied'
            ? 'Designing a template is restricted to school administrators. You can still issue certificates from existing templates.'
            : err.message
          : 'Could not create this template.'
      )
    } finally {
      setSaving(false)
    }
  }

  return (
    <SchoolDialog
      open={open}
      onOpenChange={onOpenChange}
      title="New certificate template"
      description="The signatory here is printed on every certificate issued from this template."
      onSubmit={submit}
      footer={
        <>
          <button
            type="button"
            id="certificates-template-cancel"
            className={LH_SECONDARY_BUTTON}
            onClick={() => onOpenChange(false)}
          >
            Cancel
          </button>
          <button
            type="submit"
            id="certificates-template-submit"
            className={LH_PRIMARY_BUTTON}
            disabled={saving || !title.trim() || !issuerName.trim() || !issuerTitle.trim()}
          >
            {saving ? 'Creating…' : 'Create template'}
          </button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <SchoolField id="tpl-title" label="Title" required>
          <input
            id="tpl-title"
            className={LH_INPUT}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Certificate of Completion"
          />
        </SchoolField>

        <SchoolField id="tpl-description" label="Description">
          <input
            id="tpl-description"
            className={LH_INPUT}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Internal note — not printed"
          />
        </SchoolField>

        <SchoolField id="tpl-issuer-name" label="Signatory name" required>
          <input
            id="tpl-issuer-name"
            className={LH_INPUT}
            value={issuerName}
            onChange={(e) => setIssuerName(e.target.value)}
            placeholder="Full name as it should appear"
          />
        </SchoolField>

        <SchoolField id="tpl-issuer-title" label="Signatory title" required>
          <input
            id="tpl-issuer-title"
            className={LH_INPUT}
            value={issuerTitle}
            onChange={(e) => setIssuerTitle(e.target.value)}
            placeholder="Principal"
          />
        </SchoolField>

        <SchoolField id="tpl-layout" label="Layout">
          <select
            id="tpl-layout"
            className={LH_INPUT}
            value={layout}
            onChange={(e) => setLayout(e.target.value)}
          >
            {LAYOUT_TYPES.map((l) => (
              <option key={l} value={l}>
                {l}
              </option>
            ))}
          </select>
        </SchoolField>

        <SchoolField id="tpl-border" label="Border style">
          <select
            id="tpl-border"
            className={LH_INPUT}
            value={border}
            onChange={(e) => setBorder(e.target.value)}
          >
            {BORDER_STYLES.map((b) => (
              <option key={b} value={b}>
                {b.replace(/_/g, ' ')}
              </option>
            ))}
          </select>
        </SchoolField>

        {error ? <p className="text-sm text-red-600">{error}</p> : null}
      </div>
    </SchoolDialog>
  )
}
