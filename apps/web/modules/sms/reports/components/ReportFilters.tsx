'use client'

/**
 * The filter bar shared by the four per-domain report tabs.
 *
 * Extracted rather than copied four times for the same reason
 * `presentation.ts` exists: a campus selector that defaults differently on
 * two screens reports on two different schools while looking identical, and
 * the reader has no way to tell. One implementation, one defaulting rule.
 *
 * Each report passes only the filters its domain understands. Grades take a
 * term and no date range (a grade belongs to a term, not a week); admissions
 * take neither, because a funnel is a snapshot of where leads stand now.
 */

import type { CampusRead } from '@/modules/sms/campus/types'

const SELECT_CLASS =
  'px-3 py-2 bg-white nice-shadow rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-black focus:ring-offset-2 border-0'

export interface ReportFiltersProps {
  campuses: CampusRead[]
  campusId: number | undefined
  onCampusChange: (id: number) => void
  /** Rendered only when the report understands a date window. */
  dateFrom?: string
  dateTo?: string
  onDateFromChange?: (value: string) => void
  onDateToChange?: (value: string) => void
  /** Free-text term id, for reports scoped by term rather than by date. */
  academicTermId?: string
  onAcademicTermChange?: (value: string) => void
  idPrefix: string
}

export function ReportFilters({
  campuses,
  campusId,
  onCampusChange,
  dateFrom,
  dateTo,
  onDateFromChange,
  onDateToChange,
  academicTermId,
  onAcademicTermChange,
  idPrefix,
}: ReportFiltersProps) {
  const showDates = onDateFromChange !== undefined && onDateToChange !== undefined
  const showTerm = onAcademicTermChange !== undefined
  const showCampus = campuses.length > 1

  if (!showCampus && !showDates && !showTerm) return null

  return (
    <div className="flex flex-wrap items-end gap-4">
      {showCampus && (
        <label className="flex flex-col gap-1.5">
          <span className="text-xs font-medium text-gray-500">Reporting on</span>
          <select
            id={`${idPrefix}-campus`}
            className={SELECT_CLASS}
            value={campusId ?? ''}
            onChange={(e) => onCampusChange(Number(e.target.value))}
          >
            {campuses.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
      )}

      {showDates && (
        <>
          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-gray-500">From</span>
            <input
              id={`${idPrefix}-date-from`}
              type="date"
              className={SELECT_CLASS}
              value={dateFrom ?? ''}
              onChange={(e) => onDateFromChange?.(e.target.value)}
            />
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-gray-500">To</span>
            <input
              id={`${idPrefix}-date-to`}
              type="date"
              className={SELECT_CLASS}
              value={dateTo ?? ''}
              onChange={(e) => onDateToChange?.(e.target.value)}
            />
          </label>
          {/* An unset range is not an error: the API reports over everything
              recorded. Saying so stops a reader assuming the blank fields are
              the reason a figure is missing. */}
          <p className="pb-2 text-xs text-gray-400">
            Leave blank to cover every record.
          </p>
        </>
      )}

      {showTerm && (
        <label className="flex flex-col gap-1.5">
          <span className="text-xs font-medium text-gray-500">Academic term</span>
          <input
            id={`${idPrefix}-term`}
            type="number"
            min={1}
            placeholder="All terms"
            className={SELECT_CLASS}
            value={academicTermId ?? ''}
            onChange={(e) => onAcademicTermChange?.(e.target.value)}
          />
        </label>
      )}
    </div>
  )
}
