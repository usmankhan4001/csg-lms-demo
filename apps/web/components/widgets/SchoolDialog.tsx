'use client'

/**
 * The school modules' dialog shell.
 *
 * Why this exists: Learnhouse's own `DialogContent` (components/ui/dialog.tsx)
 * deliberately ships with `gap-0` and NO padding -- every consumer supplies
 * its own, and Learnhouse's own modals do it as `p-6 pb-2` on the header,
 * `px-6 pb-2` on the body, `p-6 pt-2` on the footer (see
 * components/Objects/Modals/FeedbackModal.tsx).
 *
 * The school dialogs were written against shadcn's upstream default, which
 * DOES pad (`p-6 gap-4`). Dropped into this Dialog they rendered with zero
 * padding: the title sat on top of the first field label, the close button
 * overlapped the content, and the page behind showed through the edges.
 *
 * Encoding the convention once here means a dialog cannot silently regress
 * to that again, and every school form matches Learnhouse's own modals.
 */

import * as React from 'react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { cn } from '@/lib/utils'

export interface SchoolDialogProps {
  open?: boolean
  onOpenChange?: (open: boolean) => void
  /** The element that opens the dialog. Omit for a controlled dialog. */
  trigger?: React.ReactNode
  title: string
  description?: string
  children: React.ReactNode
  /** Footer actions (submit/cancel). Rendered with Learnhouse's footer padding. */
  footer?: React.ReactNode
  /** Wraps header/body/footer in a <form> so Enter submits, as a form should. */
  onSubmit?: (e: React.FormEvent<HTMLFormElement>) => void
  className?: string
}

export function SchoolDialog({
  open,
  onOpenChange,
  trigger,
  title,
  description,
  children,
  footer,
  onSubmit,
  className,
}: SchoolDialogProps) {
  const body = (
    <>
      {/* pe-10 on the header keeps the title clear of the absolutely
          positioned close button Radix renders at end-4 top-4. */}
      <DialogHeader className="p-6 pb-2 pe-10">
        <DialogTitle className="text-lg font-bold text-gray-900">{title}</DialogTitle>
        {description && (
          <DialogDescription className="text-sm text-gray-500">{description}</DialogDescription>
        )}
      </DialogHeader>

      <div className="flex flex-col gap-4 px-6 py-4">{children}</div>

      {footer && <DialogFooter className="gap-2 p-6 pt-2">{footer}</DialogFooter>}
    </>
  )

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      {trigger && <DialogTrigger asChild>{trigger}</DialogTrigger>}
      <DialogContent className={cn('sm:max-w-lg', className)}>
        {onSubmit ? <form onSubmit={onSubmit}>{body}</form> : body}
      </DialogContent>
    </Dialog>
  )
}

/** A labelled field row, so every school form spaces its inputs identically. */
export function SchoolField({
  id,
  label,
  required,
  help,
  children,
}: {
  id: string
  label: string
  required?: boolean
  help?: string
  children: React.ReactNode
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-sm font-medium text-gray-700">
        {label}
        {required && <span className="ms-0.5 text-rose-500">*</span>}
      </label>
      {children}
      {help && <p className="text-xs text-gray-400">{help}</p>}
    </div>
  )
}
