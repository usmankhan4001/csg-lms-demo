'use client'

/**
 * Reusable UI Export Toolbar Component for CSG-EMS.
 *
 * Features:
 * - Direct format triggers: CSV (.csv), Excel XML (.xls/.xlsx compatible), and JSON (.json)
 * - Intelligent Batch Selection Counter: ("Export 25 selected" vs "Export all 120")
 * - Column Customizer: Popover / Dialog to select/deselect columns, select all, invert, and preview
 * - Privacy Shield: Optional PII masking toggle for compliance (GDPR / FERPA / School Privacy)
 * - Async / Server-side Streaming Export Support with fallback to Client-side Exporter
 * - Integrated Progress and Toast Notifications with react-hot-toast
 */

import React, { useState, useMemo } from 'react'
import toast from 'react-hot-toast'
import {
  Download,
  FileSpreadsheet,
  FileText,
  FileCode2,
  SlidersHorizontal,
  Check,
  Loader2,
  Shield,
  ShieldAlert,
  ChevronDown,
  CheckSquare,
  Square,
  Sparkles,
} from 'lucide-react'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import {
  executeDataExport,
  ExportColumn,
  ExportFormat,
  ExportMetadata,
} from '@/lib/export/data-export'

export interface DataExportToolbarProps<T = any> {
  /** The full dataset available locally */
  data: T[]
  /** Column definitions with formatters and accessors */
  columns: ExportColumn<T>[]
  /** Base filename without extension (e.g., 'students_roster', 'attendance_logs') */
  filenamePrefix?: string
  /** Human-readable title for export header and dialog */
  title?: string
  /** Selected record IDs if batch selection is active */
  selectedIds?: (string | number)[] | Set<string | number>
  /** Property key to match selectedIds against (defaults to 'id' or 'user_id') */
  idKey?: keyof T | string
  /** Total count if data is paginated or server-side */
  totalCount?: number
  /** Active filters for compliance audit trail */
  activeFilters?: Record<string, any>
  /** Organization or school name for header */
  organizationName?: string
  /** Current logged in user name or email */
  userName?: string
  /** Classification tier: CONFIDENTIAL | RESTRICTED | INTERNAL | PUBLIC */
  classification?: 'CONFIDENTIAL' | 'RESTRICTED' | 'INTERNAL' | 'PUBLIC'
  /** Async callback if exporting directly from backend streaming endpoint */
  onServerExport?: (
    format: ExportFormat,
    selectedOnly: boolean,
    columnKeys: string[],
    maskPii: boolean
  ) => Promise<void>
  /** Visual variant */
  variant?: 'default' | 'compact' | 'outline'
  /** Disable button state */
  disabled?: boolean
  /** Allow users to toggle PII masking */
  allowPiiMasking?: boolean
  /** Default PII masking state */
  defaultPiiMasked?: boolean
  className?: string
}

export function DataExportToolbar<T = any>({
  data = [],
  columns = [],
  filenamePrefix = 'export',
  title = 'Data Export',
  selectedIds,
  idKey = 'id',
  totalCount,
  activeFilters,
  organizationName = 'CSG Education',
  userName = 'User',
  classification = 'RESTRICTED',
  onServerExport,
  variant = 'default',
  disabled = false,
  allowPiiMasking = true,
  defaultPiiMasked = false,
  className = '',
}: DataExportToolbarProps<T>) {
  const [isExporting, setIsExporting] = useState<boolean>(false)
  const [columnModalOpen, setColumnModalOpen] = useState<boolean>(false)
  const [maskPii, setMaskPii] = useState<boolean>(defaultPiiMasked)
  const [exportTarget, setExportTarget] = useState<'all' | 'selected'>('all')

  const safeData = Array.isArray(data) ? data : []
  const safeColumns = Array.isArray(columns) ? columns : []

  // Available exportable columns
  const exportableColumns = useMemo(
    () => safeColumns.filter((c) => c.exportable !== false),
    [safeColumns]
  )

  // Track enabled columns (keyed by column.key)
  const [selectedColumnKeys, setSelectedColumnKeys] = useState<Set<string>>(() => {
    return new Set(exportableColumns.filter((c) => !c.hidden).map((c) => c.key))
  })

  // Selected records count
  const selectedCount = useMemo(() => {
    if (!selectedIds) return 0
    if (selectedIds instanceof Set) return selectedIds.size
    return selectedIds.length
  }, [selectedIds])

  const totalRecords = totalCount ?? safeData.length

  // Filter columns to export
  const activeColumnsToExport = useMemo(() => {
    return exportableColumns.filter((c) => selectedColumnKeys.has(c.key))
  }, [exportableColumns, selectedColumnKeys])

  const toggleColumn = (key: string) => {
    const next = new Set(selectedColumnKeys)
    if (next.has(key)) {
      if (next.size > 1) {
        next.delete(key)
      } else {
        toast.error('At least one column must be selected')
      }
    } else {
      next.add(key)
    }
    setSelectedColumnKeys(next)
  }

  const selectAllColumns = () => {
    setSelectedColumnKeys(new Set(exportableColumns.map((c) => c.key)))
  }

  const deselectAllColumns = () => {
    if (exportableColumns.length > 0) {
      setSelectedColumnKeys(new Set([exportableColumns[0].key]))
    }
  }

  const handleExport = async (format: ExportFormat, target: 'all' | 'selected' = 'all') => {
    if (data.length === 0 && !onServerExport) {
      toast.error('No data available to export')
      return
    }

    if (target === 'selected' && selectedCount === 0) {
      toast.error('No items selected for export')
      return
    }

    const toastId = toast.loading(`Preparing ${format.toUpperCase()} export...`)
    setIsExporting(true)

    try {
      if (onServerExport) {
        await onServerExport(
          format,
          target === 'selected',
          Array.from(selectedColumnKeys),
          maskPii
        )
        toast.success(`Export completed successfully!`, { id: toastId })
      } else {
        const metadata: ExportMetadata = {
          generatedBy: userName,
          organization: organizationName,
          timestamp: new Date(),
          activeFilters,
          classification,
          description: `${title} - Format: ${format.toUpperCase()}`,
        }

        const result = await executeDataExport(data, activeColumnsToExport, {
          format,
          filename: filenamePrefix,
          metadata,
          includeMetadata: true,
          maskPii,
          selectedIds: target === 'selected' ? selectedIds : undefined,
          idKey,
        })

        toast.success(
          `Exported ${result.recordCount} records (${format.toUpperCase()})`,
          { id: toastId }
        )
      }
    } catch (err: any) {
      console.error('Data export error:', err)
      toast.error(err?.message || 'Failed to generate export', { id: toastId })
    } finally {
      setIsExporting(false)
    }
  }

  return (
    <div className={`inline-flex items-center gap-2 ${className}`}>
      {/* Selection Badge when items are selected */}
      {selectedCount > 0 && (
        <div className="hidden sm:inline-flex items-center gap-1.5 px-2.5 py-1 bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800/60 rounded-lg text-xs font-semibold text-amber-800 dark:text-amber-300">
          <span className="inline-block w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
          <span>{selectedCount} selected</span>
        </div>
      )}

      {/* Main Export Dropdown Button */}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant={variant === 'outline' ? 'outline' : 'outline'}
            size="sm"
            disabled={disabled || isExporting}
            className="h-9 px-3 gap-2 bg-white dark:bg-zinc-900 border-zinc-200 dark:border-zinc-800 text-zinc-800 dark:text-zinc-200 hover:bg-zinc-50 dark:hover:bg-zinc-800 font-medium text-xs shadow-xs transition-all cursor-pointer"
          >
            {isExporting ? (
              <Loader2 className="w-4 h-4 animate-spin text-zinc-600 dark:text-zinc-400" />
            ) : (
              <Download className="w-4 h-4 text-zinc-600 dark:text-zinc-400" />
            )}
            <span>Export</span>
            <ChevronDown className="w-3.5 h-3.5 text-zinc-400 opacity-80" />
          </Button>
        </DropdownMenuTrigger>

        <DropdownMenuContent align="end" className="w-64 p-1.5 bg-white dark:bg-zinc-950 border border-zinc-200 dark:border-zinc-800 shadow-xl rounded-xl z-50">
          <DropdownMenuLabel className="px-2 py-1.5 text-xs font-semibold text-zinc-500 dark:text-zinc-400 flex items-center justify-between">
            <span>Choose Format</span>
            <span className="text-[10px] uppercase tracking-wider font-mono text-zinc-400">
              {totalRecords} rows
            </span>
          </DropdownMenuLabel>

          {/* Quick Format Options */}
          <DropdownMenuItem
            onClick={() => handleExport('csv', selectedCount > 0 && exportTarget === 'selected' ? 'selected' : 'all')}
            className="flex items-center gap-2.5 px-2.5 py-2 rounded-lg cursor-pointer text-xs font-medium text-zinc-800 dark:text-zinc-200 hover:bg-zinc-100 dark:hover:bg-zinc-900 focus:bg-zinc-100 dark:focus:bg-zinc-900"
          >
            <div className="w-7 h-7 rounded-md bg-emerald-50 dark:bg-emerald-950/50 flex items-center justify-center text-emerald-600 dark:text-emerald-400">
              <FileText className="w-4 h-4" />
            </div>
            <div className="flex flex-col flex-1">
              <span className="font-semibold text-zinc-900 dark:text-zinc-100">CSV Spreadsheet</span>
              <span className="text-[10px] text-zinc-500 dark:text-zinc-400">Standard RFC-4180 with UTF-8 BOM</span>
            </div>
          </DropdownMenuItem>

          <DropdownMenuItem
            onClick={() => handleExport('excel', selectedCount > 0 && exportTarget === 'selected' ? 'selected' : 'all')}
            className="flex items-center gap-2.5 px-2.5 py-2 rounded-lg cursor-pointer text-xs font-medium text-zinc-800 dark:text-zinc-200 hover:bg-zinc-100 dark:hover:bg-zinc-900 focus:bg-zinc-100 dark:focus:bg-zinc-900"
          >
            <div className="w-7 h-7 rounded-md bg-green-50 dark:bg-green-950/50 flex items-center justify-center text-green-600 dark:text-green-400">
              <FileSpreadsheet className="w-4 h-4" />
            </div>
            <div className="flex flex-col flex-1">
              <span className="font-semibold text-zinc-900 dark:text-zinc-100">Excel (.xlsx / .xls)</span>
              <span className="text-[10px] text-zinc-500 dark:text-zinc-400">Styled workbook with freeze panes</span>
            </div>
          </DropdownMenuItem>

          <DropdownMenuItem
            onClick={() => handleExport('json', selectedCount > 0 && exportTarget === 'selected' ? 'selected' : 'all')}
            className="flex items-center gap-2.5 px-2.5 py-2 rounded-lg cursor-pointer text-xs font-medium text-zinc-800 dark:text-zinc-200 hover:bg-zinc-100 dark:hover:bg-zinc-900 focus:bg-zinc-100 dark:focus:bg-zinc-900"
          >
            <div className="w-7 h-7 rounded-md bg-blue-50 dark:bg-blue-950/50 flex items-center justify-center text-blue-600 dark:text-blue-400">
              <FileCode2 className="w-4 h-4" />
            </div>
            <div className="flex flex-col flex-1">
              <span className="font-semibold text-zinc-900 dark:text-zinc-100">JSON Payload</span>
              <span className="text-[10px] text-zinc-500 dark:text-zinc-400">Structured data with audit metadata</span>
            </div>
          </DropdownMenuItem>

          {/* Batch Scope Selector if records are selected */}
          {selectedCount > 0 && (
            <>
              <DropdownMenuSeparator className="my-1 bg-zinc-100 dark:bg-zinc-800" />
              <DropdownMenuLabel className="px-2 py-1 text-[11px] font-semibold text-zinc-500 dark:text-zinc-400">
                Scope
              </DropdownMenuLabel>
              <div className="px-2 py-1 flex items-center gap-1.5 bg-zinc-50 dark:bg-zinc-900 rounded-lg text-xs">
                <button
                  type="button"
                  onClick={(e) => {
                    e.preventDefault()
                    e.stopPropagation()
                    setExportTarget('selected')
                  }}
                  className={`flex-1 py-1 px-2 rounded-md font-medium text-[11px] transition-all ${
                    exportTarget === 'selected'
                      ? 'bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 shadow-xs'
                      : 'text-zinc-500 hover:text-zinc-800'
                  }`}
                >
                  Selected ({selectedCount})
                </button>
                <button
                  type="button"
                  onClick={(e) => {
                    e.preventDefault()
                    e.stopPropagation()
                    setExportTarget('all')
                  }}
                  className={`flex-1 py-1 px-2 rounded-md font-medium text-[11px] transition-all ${
                    exportTarget === 'all'
                      ? 'bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 shadow-xs'
                      : 'text-zinc-500 hover:text-zinc-800'
                  }`}
                >
                  All ({totalRecords})
                </button>
              </div>
            </>
          )}

          <DropdownMenuSeparator className="my-1 bg-zinc-100 dark:bg-zinc-800" />

          {/* Customize Columns trigger */}
          <DropdownMenuItem
            onClick={() => setColumnModalOpen(true)}
            className="flex items-center justify-between px-2.5 py-1.5 rounded-lg cursor-pointer text-xs text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-900"
          >
            <div className="flex items-center gap-2">
              <SlidersHorizontal className="w-3.5 h-3.5 text-zinc-500" />
              <span>Customize Fields</span>
            </div>
            <span className="text-[10px] text-zinc-400 font-mono">
              {activeColumnsToExport.length}/{exportableColumns.length}
            </span>
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      {/* Field Selector & Privacy Customizer Dialog */}
      <Dialog open={columnModalOpen} onOpenChange={setColumnModalOpen}>
        <DialogContent className="max-w-md p-6 bg-white dark:bg-zinc-950 rounded-2xl border border-zinc-200 dark:border-zinc-800 shadow-2xl">
          <DialogHeader>
            <DialogTitle className="text-base font-bold text-zinc-900 dark:text-zinc-100 flex items-center gap-2">
              <SlidersHorizontal className="w-4 h-4 text-zinc-700 dark:text-zinc-300" />
              <span>Customize Export Fields</span>
            </DialogTitle>
            <DialogDescription className="text-xs text-zinc-500 dark:text-zinc-400">
              Select which fields and security masks should be applied in generated files.
            </DialogDescription>
          </DialogHeader>

          {/* Quick select buttons */}
          <div className="flex items-center justify-between py-2 border-b border-zinc-100 dark:border-zinc-800 text-xs">
            <span className="text-zinc-500 font-medium">
              {activeColumnsToExport.length} of {exportableColumns.length} fields included
            </span>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={selectAllColumns}
                className="text-xs font-semibold text-blue-600 hover:text-blue-700 dark:text-blue-400 cursor-pointer"
              >
                Select All
              </button>
              <span className="text-zinc-300">|</span>
              <button
                type="button"
                onClick={deselectAllColumns}
                className="text-xs font-semibold text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300 cursor-pointer"
              >
                Reset
              </button>
            </div>
          </div>

          {/* Column Checkboxes List */}
          <div className="max-h-60 overflow-y-auto space-y-1.5 py-2 pr-1">
            {exportableColumns.map((col) => {
              const isChecked = selectedColumnKeys.has(col.key)
              return (
                <div
                  key={col.key}
                  onClick={() => toggleColumn(col.key)}
                  className={`flex items-center justify-between p-2 rounded-lg cursor-pointer transition-all border ${
                    isChecked
                      ? 'bg-zinc-50 dark:bg-zinc-900/60 border-zinc-200 dark:border-zinc-800 text-zinc-900 dark:text-zinc-100'
                      : 'bg-transparent border-transparent text-zinc-400 hover:bg-zinc-50/50 dark:hover:bg-zinc-900/30'
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    {isChecked ? (
                      <CheckSquare className="w-4 h-4 text-black dark:text-white shrink-0" />
                    ) : (
                      <Square className="w-4 h-4 text-zinc-400 shrink-0" />
                    )}
                    <span className="text-xs font-medium">{col.label}</span>
                  </div>
                  {col.type && (
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-zinc-200/60 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400">
                      {col.type}
                    </span>
                  )}
                </div>
              )
            })}
          </div>

          {/* Privacy & Compliance Section */}
          {allowPiiMasking && (
            <div className="mt-2 p-3 bg-zinc-50 dark:bg-zinc-900/80 rounded-xl border border-zinc-200 dark:border-zinc-800">
              <label className="flex items-start gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={maskPii}
                  onChange={(e) => setMaskPii(e.target.checked)}
                  className="mt-0.5 rounded border-zinc-300 text-black focus:ring-black dark:border-zinc-700"
                />
                <div className="flex flex-col">
                  <span className="text-xs font-semibold text-zinc-900 dark:text-zinc-100 flex items-center gap-1.5">
                    <Shield className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
                    Mask Personally Identifiable Information (PII)
                  </span>
                  <span className="text-[11px] text-zinc-500 dark:text-zinc-400 mt-0.5">
                    Anonymize student emails, phone numbers, and national IDs for privacy compliance.
                  </span>
                </div>
              </label>
            </div>
          )}

          <DialogFooter className="gap-2 sm:gap-0 mt-4">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setColumnModalOpen(false)}
              className="text-xs font-medium"
            >
              Done
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
