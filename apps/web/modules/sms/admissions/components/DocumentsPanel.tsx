'use client'

/**
 * Supporting documents — upload, review, verify.
 *
 * A school CHECKS a birth certificate; it does not merely receive one. So
 * verification state is the primary column here, not an afterthought, and an
 * unchecked file reads as "Not checked" rather than a soothing "Pending".
 *
 * Documents are never addressable by URL. `DocumentRead` carries no path, and
 * the bytes are fetched with the session's Bearer token into a blob that is
 * revoked immediately (see `downloadDocument` in ../api.ts). Nothing about a
 * child's birth certificate ends up in browser history or a shared link.
 */

import { useRef, useState } from 'react'
import { Download, FileCheck2, Upload } from 'lucide-react'
import {
  DataTable,
  EmptyState,
  LH_INPUT,
  LH_PRIMARY_BUTTON,
  LH_SECONDARY_BUTTON,
  SchoolDialog,
  SchoolField,
  SectionCard,
  StatusChip,
} from '@/components/widgets'
import { ApiError } from '@/lib/api/api-client'
import { downloadDocument, uploadDocument, verifyDocument } from '../api'
import {
  DOCUMENT_TYPES,
  DOCUMENT_TYPE_LABEL,
  VERIFICATION_LABEL,
  VERIFICATION_TONE,
  formatDateTime,
} from '../presentation'
import type { DocumentRead, DocumentType, DocumentVerificationStatus } from '../types'

interface Props {
  applicationId: number
  documents: DocumentRead[]
  missingTypes: DocumentType[]
  documentsComplete: boolean
  /** Verification is a leadership act (SUPER_ADMIN/SCHOOL_ADMIN server-side). */
  canVerify: boolean
  onChanged: () => void
}

export function DocumentsPanel({
  applicationId,
  documents,
  missingTypes,
  documentsComplete,
  canVerify,
  onChanged,
}: Props) {
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [verifying, setVerifying] = useState<DocumentRead | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const [pendingType, setPendingType] = useState<DocumentType>('BIRTH_CERTIFICATE')

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    setError(null)
    try {
      await uploadDocument(applicationId, pendingType, file)
      onChanged()
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.kind === 'permission_denied'
            ? 'You need admissions access to upload documents.'
            : err.message
          : 'Could not upload that file.'
      )
    } finally {
      setUploading(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  async function handleDownload(doc: DocumentRead) {
    setError(null)
    try {
      await downloadDocument(doc.id, doc.original_filename ?? undefined)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not download the document.')
    }
  }

  return (
    <SectionCard
      id="documents"
      title="Supporting documents"
      description="Uploaded evidence and its verification state."
      icon={<FileCheck2 className="size-4 text-gray-500" />}
      action={
        <div className="flex items-center gap-2">
          <select
            id="doc-type-picker"
            aria-label="Document type to upload"
            className={LH_INPUT}
            value={pendingType}
            onChange={(e) => setPendingType(e.target.value as DocumentType)}
          >
            {DOCUMENT_TYPES.map((t) => (
              <option key={t} value={t}>
                {DOCUMENT_TYPE_LABEL[t]}
              </option>
            ))}
          </select>
          <button
            type="button"
            id="doc-upload-button"
            className={LH_SECONDARY_BUTTON}
            disabled={uploading}
            onClick={() => fileRef.current?.click()}
          >
            <Upload className="size-4" />
            <span>{uploading ? 'Uploading…' : 'Upload'}</span>
          </button>
          <input
            id="doc-file-input"
            ref={fileRef}
            type="file"
            className="hidden"
            onChange={handleUpload}
          />
        </div>
      }
    >
      {/* Completeness reflects VERIFIED documents only — an uploaded-but-
          unchecked certificate is not evidence the school checked anything. */}
      {missingTypes.length > 0 ? (
        <div className="mb-4 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900">
          Still required:{' '}
          {missingTypes.map((t) => DOCUMENT_TYPE_LABEL[t]).join(', ')}
          <span className="block text-xs text-amber-700">
            A document counts only once it has been verified, not merely uploaded.
          </span>
        </div>
      ) : documentsComplete ? (
        <div className="mb-4 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-900">
          All required documents verified.
        </div>
      ) : null}

      {error && <p className="mb-3 text-sm text-rose-600">{error}</p>}

      {documents.length === 0 ? (
        <EmptyState
          title="No documents uploaded"
          description="Upload a birth certificate and prior school record to move this application forward."
        />
      ) : (
        <DataTable
          rows={documents}
          rowKey={(r) => r.id}
          state="success"
          totalLabel={`${documents.length} document${documents.length === 1 ? '' : 's'}`}
          columns={[
            {
              key: 'type',
              header: 'Type',
              render: (r) => DOCUMENT_TYPE_LABEL[r.document_type],
            },
            {
              key: 'file',
              header: 'File',
              render: (r) => r.original_filename ?? 'Unnamed file',
            },
            {
              key: 'status',
              header: 'Verification',
              render: (r) => (
                <StatusChip
                  label={VERIFICATION_LABEL[r.verification_status]}
                  tone={VERIFICATION_TONE[r.verification_status]}
                />
              ),
            },
            {
              key: 'checked',
              header: 'Checked',
              render: (r) =>
                r.verified_at ? (
                  <span className="text-xs text-gray-600">
                    {formatDateTime(r.verified_at)}
                    {r.verified_by_user_id ? ` · by user #${r.verified_by_user_id}` : ''}
                  </span>
                ) : (
                  <span className="text-xs text-gray-400">Not checked</span>
                ),
            },
            {
              key: 'reason',
              header: 'Reason',
              render: (r) =>
                r.rejection_reason ? (
                  <span className="text-xs text-rose-700">{r.rejection_reason}</span>
                ) : (
                  <span className="text-xs text-gray-400">—</span>
                ),
            },
            {
              key: 'actions',
              header: '',
              align: 'right',
              render: (r) => (
                <div className="flex justify-end gap-2">
                  <button
                    type="button"
                    id={`doc-download-${r.id}`}
                    className={LH_SECONDARY_BUTTON}
                    onClick={() => handleDownload(r)}
                  >
                    <Download className="size-3.5" />
                    <span>Download</span>
                  </button>
                  {canVerify && (
                    <button
                      type="button"
                      id={`doc-verify-${r.id}`}
                      className={LH_SECONDARY_BUTTON}
                      onClick={() => setVerifying(r)}
                    >
                      <span>Review</span>
                    </button>
                  )}
                </div>
              ),
            },
          ]}
        />
      )}

      {verifying && (
        <VerifyDialog
          document={verifying}
          onClose={() => setVerifying(null)}
          onDone={() => {
            setVerifying(null)
            onChanged()
          }}
        />
      )}
    </SectionCard>
  )
}

function VerifyDialog({
  document,
  onClose,
  onDone,
}: {
  document: DocumentRead
  onClose: () => void
  onDone: () => void
}) {
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [status, setStatus] = useState<DocumentVerificationStatus>('VERIFIED')

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const form = new FormData(e.currentTarget)
    const reason = String(form.get('rejection_reason') ?? '').trim()

    // The service requires a reason on rejection; catching it here means the
    // reviewer is told before the round-trip, not after a 400.
    if (status === 'REJECTED' && !reason) {
      setError('A rejection needs a reason — the family has to know what to resubmit.')
      return
    }

    setSaving(true)
    setError(null)
    try {
      await verifyDocument(document.id, {
        verification_status: status,
        rejection_reason: status === 'REJECTED' ? reason : null,
      })
      onDone()
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.kind === 'permission_denied'
            ? 'Only school leadership can verify documents.'
            : err.message
          : 'Could not record that check.'
      )
    } finally {
      setSaving(false)
    }
  }

  return (
    <SchoolDialog
      open
      onOpenChange={(o) => !o && onClose()}
      title={`Review ${DOCUMENT_TYPE_LABEL[document.document_type]}`}
      description="Record whether this document has been checked and accepted."
      onSubmit={handleSubmit}
      footer={
        <button type="submit" disabled={saving} className={LH_PRIMARY_BUTTON}>
          <span>{saving ? 'Saving…' : 'Record check'}</span>
        </button>
      }
    >
      <SchoolField id="verify-status" label="Outcome" required>
        <select
          id="verify-status"
          name="verification_status"
          className={LH_INPUT}
          value={status}
          onChange={(e) => setStatus(e.target.value as DocumentVerificationStatus)}
        >
          <option value="VERIFIED">Verified — checked and accepted</option>
          <option value="REJECTED">Rejected — not acceptable</option>
          <option value="PENDING">Back to not checked</option>
        </select>
      </SchoolField>

      {status === 'REJECTED' && (
        <SchoolField
          id="verify-reason"
          label="Reason"
          required
          help="Told to the family so they know what to resubmit."
        >
          <input id="verify-reason" name="rejection_reason" className={LH_INPUT} />
        </SchoolField>
      )}

      {error && <p className="text-sm text-rose-600">{error}</p>}
    </SchoolDialog>
  )
}
