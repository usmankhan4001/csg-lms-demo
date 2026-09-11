'use client'

import * as React from 'react'
import { type LucideIcon } from 'lucide-react'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
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
      <Table>
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            {columns.map((col) => (
              <TableHead key={col.key} className={cn(ALIGN_CLASS[col.align ?? 'left'], col.className)}>
                {col.header}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {state === 'loading' &&
            Array.from({ length: skeletonRows }).map((_, i) => (
              <TableRow key={`skeleton-${i}`}>
                {columns.map((col) => (
                  <TableCell key={col.key}>
                    <Skeleton className="h-4 w-full max-w-[160px]" />
                  </TableCell>
                ))}
              </TableRow>
            ))}

          {state === 'error' && (
            <TableRow className="hover:bg-transparent">
              <TableCell colSpan={colCount} className="p-0">
                <EmptyState
                  tone="critical"
                  title="Couldn't load this table"
                  description={error?.message || 'The server did not respond in time.'}
                  code={error?.code}
                  action={onRetry ? { label: 'Retry', onClick: onRetry } : undefined}
                />
              </TableCell>
            </TableRow>
          )}

          {state === 'empty' && (
            <TableRow className="hover:bg-transparent">
              <TableCell colSpan={colCount} className="p-0">
                <EmptyState title={emptyTitle} description={emptyDescription} action={emptyAction} icon={emptyIcon} />
              </TableCell>
            </TableRow>
          )}

          {state === 'success' &&
            rows.map((row, index) => (
              <TableRow
                key={rowKey(row, index)}
                className={cn(onRowClick && 'cursor-pointer')}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
              >
                {columns.map((col) => (
                  <TableCell key={col.key} className={cn(ALIGN_CLASS[col.align ?? 'left'], col.className)}>
                    {col.render(row)}
                  </TableCell>
                ))}
              </TableRow>
            ))}
        </TableBody>
      </Table>
      {state === 'success' && totalLabel && (
        <div className="border-t border-border px-2 py-2.5 text-xs text-muted-foreground">{totalLabel}</div>
      )}
    </div>
  )
}
