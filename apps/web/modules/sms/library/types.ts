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
