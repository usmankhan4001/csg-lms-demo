/**
 * Real fetch calls against `apps/api/src/routers/sms_financials.py`
 * (mounted at `/api/v1/sms/financials`).
 */

import { apiGet, apiPost, toQueryString } from '@/lib/api/api-client'
import type {
  AccountType,
  ChartOfAccountsCreate,
  ChartOfAccountsRead,
  JournalEntryCreate,
  JournalEntryRead,
  TrialBalanceResponse,
} from './types'

export function listChartOfAccounts(params: { campusId?: number; accountType?: AccountType; isActive?: boolean } = {}): Promise<ChartOfAccountsRead[]> {
  const qs = toQueryString({ campus_id: params.campusId, account_type: params.accountType, is_active: params.isActive })
  return apiGet<ChartOfAccountsRead[]>(`/sms/financials/accounts${qs}`)
}

export function createChartOfAccount(payload: ChartOfAccountsCreate): Promise<ChartOfAccountsRead> {
  return apiPost<ChartOfAccountsRead>('/sms/financials/accounts', payload)
}

export function getChartOfAccount(accountId: number): Promise<ChartOfAccountsRead> {
  return apiGet<ChartOfAccountsRead>(`/sms/financials/accounts/${accountId}`)
}

export function createJournalEntry(payload: JournalEntryCreate): Promise<JournalEntryRead> {
  return apiPost<JournalEntryRead>('/sms/financials/journal-entries', payload)
}

export function listJournalEntries(campusId?: number): Promise<JournalEntryRead[]> {
  return apiGet<JournalEntryRead[]>(`/sms/financials/journal-entries${toQueryString({ campus_id: campusId })}`)
}

export function getJournalEntry(entryId: number): Promise<JournalEntryRead> {
  return apiGet<JournalEntryRead>(`/sms/financials/journal-entries/${entryId}`)
}

export function getTrialBalance(campusId?: number): Promise<TrialBalanceResponse> {
  return apiGet<TrialBalanceResponse>(`/sms/financials/trial-balance${toQueryString({ campus_id: campusId })}`)
}
