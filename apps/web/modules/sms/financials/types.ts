/**
 * Types mirroring `apps/api/src/schemas/sms_financials.py`.
 */

export type AccountType = 'ASSET' | 'LIABILITY' | 'EQUITY' | 'REVENUE' | 'EXPENSE'

export interface ChartOfAccountsRead {
  id: number
  account_code: string
  account_name: string
  account_type: AccountType
  campus_id?: number | null
  is_active: boolean
  description?: string | null
  balance: number
  created_at: string
}

export interface ChartOfAccountsCreate {
  account_code: string
  account_name: string
  account_type: AccountType
  campus_id?: number | null
  is_active?: boolean
  description?: string | null
  initial_balance?: number
}

export interface JournalEntryLineCreate {
  account_id: number
  debit_amount?: number
  credit_amount?: number
  description?: string | null
}

export interface JournalEntryLineRead {
  id: number
  entry_id: number
  account_id: number
  debit_amount: number
  credit_amount: number
  description?: string | null
}

export interface JournalEntryCreate {
  campus_id?: number | null
  entry_date: string
  reference_no?: string | null
  description?: string | null
  lines: JournalEntryLineCreate[]
}

export interface JournalEntryRead {
  id: number
  campus_id?: number | null
  entry_date: string
  reference_no: string
  description?: string | null
  total_debit: number
  total_credit: number
  created_at: string
  lines: JournalEntryLineRead[]
}

export interface TrialBalanceItemRead {
  account_id: number
  account_code: string
  account_name: string
  account_type: AccountType
  debit_balance: number
  credit_balance: number
}

export interface TrialBalanceResponse {
  campus_id?: number | null
  items: TrialBalanceItemRead[]
  total_debit: number
  total_credit: number
  is_balanced: boolean
}
