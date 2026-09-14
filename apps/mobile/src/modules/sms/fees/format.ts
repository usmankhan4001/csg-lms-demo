/**
 * Matches the web dashboard's fee formatting (`apps/web/app/orgs/[orgslug]/
 * dash/fees/client.tsx:65`) so a parent sees the same figure written the same
 * way on both clients.
 */
export function formatMoney(amount: number): string {
  return `Rs. ${amount.toFixed(2)}`
}

/**
 * A voucher is overdue when it still owes money past its due date. Derived,
 * because `VoucherStatus` has no OVERDUE member -- it is UNPAID | PARTIAL |
 * PAID | CANCELLED and nothing else.
 */
export function isOverdue(dueDate: string, balanceAmount: number): boolean {
  if (balanceAmount <= 0) return false
  return dueDate < new Date().toISOString().slice(0, 10)
}
