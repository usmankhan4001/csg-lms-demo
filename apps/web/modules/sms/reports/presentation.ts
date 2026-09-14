/**
 * The one place a `Metric` becomes text.
 *
 * Extracted from the reports page so the school dashboard renders absence the
 * SAME way. Two copies of "how do we show a missing figure" is exactly the
 * drift this codebase has been burned by: a rate that reads `0%` on one screen
 * and "Not recorded" on another describes the same school two different ways,
 * and only one of them is true.
 *
 * The rule: a null metric is stated, never zeroed. A head teacher seeing
 * "0% attendance" reads "nobody came to school". The truth is usually that
 * nobody marked a register — and those demand opposite actions.
 */

import type { Metric } from './types'

/** Absence is stated, never zeroed. */
export function formatMetric(metric: Metric): string {
  if (!metric.has_data || metric.value === null) return 'Not recorded'
  switch (metric.unit) {
    case 'percent':
      return `${metric.value}%`
    case 'gpa':
      return metric.value.toFixed(2)
    case 'currency':
      return `Rs. ${metric.value.toLocaleString()}`
    default:
      return String(metric.value)
  }
}

/**
 * Sub-label under a stat: either what the figure is built on, or why it is
 * missing. The "why" is the load-bearing half — it is what turns an empty
 * tile from a worry into an instruction.
 */
export function metricHint(metric: Metric): string | undefined {
  if (!metric.has_data) return metric.no_data_reason ?? undefined
  return metric.sample_size > 0
    ? `over ${metric.sample_size} record${metric.sample_size === 1 ? '' : 's'}`
    : undefined
}

/**
 * Tone for a metric tile. A missing figure is NEUTRAL, never positive:
 * styling absent data as good news is how a fabricated reassurance starts.
 */
export function metricTone(metric: Metric): 'neutral' | 'positive' {
  return metric.has_data && metric.value !== null ? 'positive' : 'neutral'
}

/** Currency for figures the API returns as a bare number (counts, not Metrics). */
export function currency(amount: number): string {
  return `Rs. ${amount.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`
}
