'use client'

import * as React from 'react'
import { type LucideIcon } from 'lucide-react'
import { Skeleton } from '@/components/ui/skeleton'
import { EmptyState, type EmptyStateAction } from './EmptyState'
import { ApiError } from '@/lib/api/api-client'
import { cn } from '@/lib/utils'

/**
 * Generic list/table renderer implementing DESIGN-SYSTEM.md §6: sticky
 * header, a stated total ("1–25 of 348"), and the shared loading/empty/error
 * treatment so no module re-implements this per page.
 *
 * Sorting/server-side pagination are left to the caller (pass already-sorted
 * / already-paginated `rows` and render `totalLabel` + your own pager) --
 * this component focuses on the state model and consistent row rendering.
 */

export interface DataTableColumn<T> {
  key: string
  header: string
  render: (row: T) => React.ReactNode
  align?: 'left' | 'right' | 'center'
  className?: string
}

export type DataTableState = 'loading' | 'empty' | 'error' | 'success'

export interface DataTableProps<T> {
  columns: DataTableColumn<T>[]
  rows: T[]
  rowKey: (row: T, index: number) => string | number
  state?: DataTableState
  error?: ApiError | null
  onRetry?: () => void
  emptyTitle?: string
  emptyDescription?: string
  emptyAction?: EmptyStateAction
  emptyIcon?: LucideIcon
  /** e.g. "1–25 of 348" -- shown under the table per DESIGN-SYSTEM.md §6. */
  totalLabel?: string
  skeletonRows?: number
  onRowClick?: (row: T) => void
  className?: string
}

const ALIGN_CLASS: Record<'left' | 'right' | 'center', string> = {
  left: 'text-start',
  right: 'text-end',
  center: 'text-center',
}

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  state = 'success',
  error,
  onRetry,
  emptyTitle = 'No results yet',
  emptyDescription,
  emptyAction,
  emptyIcon,
  totalLabel,
  skeletonRows = 5,
  onRowClick,
  className,
}: DataTableProps<T>) {
  const colCount = columns.length

  return (
    <div className={cn('overflow-x-auto', className)}>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-gray-400 text-xs uppercase tracking-wider border-b border-gray-100">
            {columns.map((col) => (
              <th key={col.key} className={cn('pb-2 font-medium', ALIGN_CLASS[col.align ?? 'left'], col.className)}>
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {state === 'loading' &&
            Array.from({ length: skeletonRows }).map((_, i) => (
              <tr key={`skeleton-${i}`} className="border-b border-gray-50">
                {columns.map((col) => (
                  <td key={col.key} className="py-2.5">
                    <Skeleton className="h-4 w-full max-w-[160px]" />
                  </td>
                ))}
              </tr>
            ))}

          {state === 'error' && (
            <tr>
              <td colSpan={colCount} className="p-0">
                <EmptyState
                  tone="critical"
                  title="Couldn't load this table"
                  description={error?.message || 'The server did not respond in time.'}
                  code={error?.code}
                  action={onRetry ? { label: 'Retry', onClick: onRetry } : undefined}
                />
              </td>
            </tr>
          )}

          {state === 'empty' && (
            <tr>
              <td colSpan={colCount} className="p-0">
                <EmptyState title={emptyTitle} description={emptyDescription} action={emptyAction} icon={emptyIcon} />
              </td>
            </tr>
          )}

          {state === 'success' &&
            rows.map((row, index) => (
              <tr
                key={rowKey(row, index)}
                className={cn(
                  'border-b border-gray-50 text-gray-700',
                  onRowClick && 'cursor-pointer hover:bg-gray-50 transition-colors'
                )}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
              >
                {columns.map((col) => (
                  <td key={col.key} className={cn('py-2.5', ALIGN_CLASS[col.align ?? 'left'], col.className)}>
                    {col.render(row)}
                  </td>
                ))}
              </tr>
            ))}
        </tbody>
      </table>
      {state === 'success' && totalLabel && (
        <div className="pt-3 text-xs text-gray-400">{totalLabel}</div>
      )}
    </div>
  )
}
