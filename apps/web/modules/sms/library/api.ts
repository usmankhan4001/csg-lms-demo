/**
 * Real fetch calls against `apps/api/src/routers/sms_library.py`
 * (mounted at `/api/v1/sms/library`).
 */

import { apiDelete, apiGet, apiPost, apiPut, toQueryString } from '@/lib/api/api-client'
import type {
  BookLoanRead,
  BookLoanStatus,
  BorrowBookRequest,
  CalculateFinesRequest,
  CalculateFinesResponse,
  LibraryBookCreate,
  LibraryBookRead,
  LibraryBookUpdate,
  ReturnBookRequest,
} from './types'

export function listBooks(params: { campusId?: number; category?: string; search?: string; availableOnly?: boolean } = {}): Promise<LibraryBookRead[]> {
  const qs = toQueryString({
    campus_id: params.campusId,
    category: params.category,
    search: params.search,
    available_only: params.availableOnly,
  })
  return apiGet<LibraryBookRead[]>(`/sms/library/books${qs}`)
}

export function createBook(payload: LibraryBookCreate): Promise<LibraryBookRead> {
  return apiPost<LibraryBookRead>('/sms/library/books', payload)
}

export function getBook(bookId: number): Promise<LibraryBookRead> {
  return apiGet<LibraryBookRead>(`/sms/library/books/${bookId}`)
}

export function updateBook(bookId: number, payload: LibraryBookUpdate): Promise<LibraryBookRead> {
  return apiPut<LibraryBookRead>(`/sms/library/books/${bookId}`, payload)
}

export function deleteBook(bookId: number): Promise<void> {
  return apiDelete<void>(`/sms/library/books/${bookId}`)
}

export function borrowBook(payload: BorrowBookRequest): Promise<BookLoanRead> {
  return apiPost<BookLoanRead>('/sms/library/loans/borrow', payload)
}

export function returnBook(loanId: number, payload?: ReturnBookRequest): Promise<BookLoanRead> {
  return apiPost<BookLoanRead>(`/sms/library/loans/${loanId}/return`, payload)
}

export function listLoans(params: { userId?: number; bookId?: number; status?: BookLoanStatus } = {}): Promise<BookLoanRead[]> {
  const qs = toQueryString({ user_id: params.userId, book_id: params.bookId, status: params.status })
  return apiGet<BookLoanRead[]>(`/sms/library/loans${qs}`)
}

export function calculateOverdueFines(payload?: CalculateFinesRequest): Promise<CalculateFinesResponse> {
  return apiPost<CalculateFinesResponse>('/sms/library/loans/calculate-fines', payload)
}
