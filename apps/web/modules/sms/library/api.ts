/**
 * Real fetch calls against `apps/api/src/routers/sms_library.py`
 * (mounted at `/api/v1/sms/library`).
 */

import {
  apiDelete,
  apiGet,
  apiPatch,
  apiPost,
  apiPut,
  toQueryString,
} from '@/lib/api/api-client'
import type {
  BookLoanRead,
  ReservationRead,
  ReservationStatus,
  ReservationWithPosition,
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

// ── Reservations (holds) ───────────────────────────────────────────────────

/**
 * Place a hold. `userId` is only honoured for a librarian reserving on a
 * reader's behalf — a reader's own hold takes its identity from the session,
 * never from this field, so nobody can queue as someone else.
 */
export function reserveBook(
  bookId: number,
  userId?: number
): Promise<ReservationWithPosition> {
  return apiPost<ReservationWithPosition>('/sms/library/reservations', {
    book_id: bookId,
    user_id: userId ?? null,
  })
}

export function listReservations(
  params: {
    bookId?: number
    userId?: number
    reservationStatus?: ReservationStatus
    campusId?: number
  } = {}
): Promise<ReservationWithPosition[]> {
  const qs = toQueryString({
    book_id: params.bookId,
    user_id: params.userId,
    reservation_status: params.reservationStatus,
    campus_id: params.campusId,
  })
  return apiGet<ReservationWithPosition[]>(`/sms/library/reservations${qs}`)
}

/** A copy has come back and is being held at the desk for this reader. */
export function markReservationReady(
  reservationId: number,
  holdDays = 3
): Promise<ReservationRead> {
  return apiPatch<ReservationRead>(
    `/sms/library/reservations/${reservationId}/ready`,
    { hold_days: holdDays }
  )
}

/** Close a hold as FULFILLED, CANCELLED or EXPIRED. Live statuses are refused. */
export function closeReservation(
  reservationId: number,
  status: ReservationStatus
): Promise<ReservationRead> {
  return apiPatch<ReservationRead>(
    `/sms/library/reservations/${reservationId}/close`,
    { status }
  )
}

/**
 * Release holds nobody collected, so they stop blocking the queue. Returns
 * exactly what it expired — an empty list means nothing was stale, which is a
 * real answer and not a failure.
 */
export function expireStaleHolds(): Promise<ReservationRead[]> {
  return apiPost<ReservationRead[]>('/sms/library/reservations/expire-stale')
}
