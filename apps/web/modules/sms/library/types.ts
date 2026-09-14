/**
 * Types mirroring `apps/api/src/schemas/sms_library.py`.
 */

export type BookLoanStatus = 'BORROWED' | 'RETURNED' | 'OVERDUE'

export interface LibraryBookRead {
  id: number
  campus_id?: number | null
  isbn?: string | null
  title: string
  author: string
  category?: string | null
  total_copies: number
  available_copies: number
  digital_file_url?: string | null
  created_at: string
}

export interface LibraryBookCreate {
  campus_id?: number | null
  isbn?: string | null
  title: string
  author: string
  category?: string | null
  total_copies?: number
  digital_file_url?: string | null
}

export interface LibraryBookUpdate {
  campus_id?: number | null
  isbn?: string | null
  title?: string
  author?: string
  category?: string | null
  total_copies?: number
  available_copies?: number
  digital_file_url?: string | null
}

export interface BorrowBookRequest {
  book_id: number
  user_id: number
  borrowed_date?: string | null
  due_date?: string | null
}

export interface ReturnBookRequest {
  returned_date?: string | null
  fine_amount?: number | null
}

export interface CalculateFinesRequest {
  fine_per_day?: number
  as_of_date?: string | null
}

export interface BookLoanRead {
  id: number
  book_id: number
  user_id: number
  borrowed_date: string
  due_date: string
  returned_date?: string | null
  fine_amount: number
  status: BookLoanStatus
  created_at: string
  book_title?: string | null
}

export interface CalculateFinesResponse {
  updated_loans_count: number
  total_fines_accumulated: number
}

// ── Reservations (holds) ───────────────────────────────────────────────────
//
// A hold queues for a TITLE, never a specific copy. `LibraryBook` tracks
// `total_copies`/`available_copies` as counters with no per-copy row, so the
// library knows it holds three copies and how many are out, but not WHICH
// copy a loan refers to. Worth knowing before anyone builds stock-taking or
// "which copy did this child lose" on top of it.

export type ReservationStatus =
  | 'WAITING'
  | 'READY'
  | 'FULFILLED'
  | 'CANCELLED'
  | 'EXPIRED'

export interface ReservationRead {
  id: number
  book_id: number
  user_id: number
  campus_id: number | null
  status: ReservationStatus
  reserved_at: string
  /** Set when a copy is put aside at the desk. */
  ready_at: string | null
  /** When an uncollected hold lapses, so it stops blocking the queue. */
  expires_at: string | null
  closed_at: string | null
  notes: string | null
}

export interface ReservationWithPosition extends ReservationRead {
  /** 1-based place in the queue. 0 = a copy is held at the desk for this
   *  reader; -1 = the hold is closed. */
  queue_position: number
}
