/**
 * Shared formatting for the fees module.
 *
 * Defined once because every fees screen renders money, and three screens each
 * inventing their own `toFixed` is how a balance ends up displayed differently
 * on the voucher list and the student account -- which, for a bursar arguing
 * with a parent about what is owed, is worse than an ugly number.
 */

/**
 * Money for display.
 *
 * The backend declares every fee amount as a `float`, so this formats what the
 * server sent and never accumulates. Where a screen needs a total, it must
 * read the server's own summary field (`total_amount`, `paid_amount`,
 * `balance_amount`) rather than summing rows in the browser.
 *
 * Always two decimals, never abbreviated: "Rs. 1.2k" outstanding is not a
 * thing a bursar can act on, and rounding 0.51 to "Rs. 1" makes a balance look
 * settled when it is not.
 */
export function money(n: number): string {
  return `Rs. ${n.toFixed(2)}`
}

/**
 * Money that may genuinely be absent.
 *
 * The distinction this exists to preserve: a student with no fee record owes
 * NOTHING KNOWN, which is not the same as owing zero. Rendering an absent
 * figure as "Rs. 0.00" tells a bursar the family is square when in fact nobody
 * has billed them yet.
 */
export function moneyOrUnknown(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return 'Not recorded'
  return money(n)
}

/** A date the API gave us as `YYYY-MM-DD`, shown as-is. Parsing it into a
 * `Date` would shift it across a timezone boundary and move a due date by a
 * day, which changes whether a family is late. */
export function isoDate(value: string | null | undefined): string {
  if (!value) return '—'
  return value.slice(0, 10)
}

/** A timestamp, shown to the minute. */
export function isoDateTime(value: string | null | undefined): string {
  if (!value) return '—'
  return value.slice(0, 16).replace('T', ' ')
}

export function today(): string {
  return new Date().toISOString().slice(0, 10)
}

/**
 * How many days past its due date a voucher is, or null if it is not yet due.
 *
 * Compares date strings rather than `Date` objects for the timezone reason
 * above. Returns null -- not 0 -- for a voucher due today or later, so a caller
 * cannot accidentally render "0 days overdue" for something that is not
 * overdue at all.
 */
export function daysOverdue(dueDate: string | null | undefined, from: string = today()): number | null {
  if (!dueDate) return null
  const due = dueDate.slice(0, 10)
  if (due >= from) return null
  const ms = Date.parse(`${from}T00:00:00Z`) - Date.parse(`${due}T00:00:00Z`)
  if (Number.isNaN(ms)) return null
  return Math.floor(ms / 86_400_000)
}

/** Human label for a concession, which is either a percentage or a fixed
 * amount -- never both, and never neither. */
export function concessionValue(
  percentage: number | null | undefined,
  fixedAmount: number | null | undefined
): string {
  if (percentage !== null && percentage !== undefined) return `${percentage}%`
  if (fixedAmount !== null && fixedAmount !== undefined) return money(fixedAmount)
  // The backend enforces exactly one, so reaching here means the row is
  // malformed. Say so rather than printing a confident "0".
  return 'Not recorded'
}

/** Title-cases an enum value for display: STAFF_CHILD -> "Staff child". */
export function humanEnum(value: string): string {
  const lower = value.replace(/_/g, ' ').toLowerCase()
  return lower.charAt(0).toUpperCase() + lower.slice(1)
}
