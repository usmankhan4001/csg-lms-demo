'use client'

/**
 * Per-user school identity, in a modal on the Learnhouse Users table.
 *
 * Mirrors `UserDossierModal` (the analytics dossier next to it) so the two
 * per-user surfaces behave identically — same Dialog, same sizing, opened
 * from the same Actions column.
 */

import { Dialog, DialogContent } from '@components/ui/dialog'
import SchoolIdentityPanel from './SchoolIdentityPanel'

interface SchoolIdentityModalProps {
  userId: number | null
  orgId: number | undefined
  userLabel?: string
  canManage?: boolean
  onOpenChange: (_open: boolean) => void
}

export default function SchoolIdentityModal({
  userId,
  orgId,
  userLabel,
  canManage,
  onOpenChange,
}: SchoolIdentityModalProps) {
  return (
    <Dialog open={userId != null} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto bg-[#f8f8f8] p-6 sm:p-8">
        {userId != null && orgId != null ? (
          <SchoolIdentityPanel
            userId={userId}
            orgId={orgId}
            userLabel={userLabel}
            canManage={canManage}
          />
        ) : (
          <div className="py-20 text-center text-sm text-gray-500">
            No organization context available.
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
