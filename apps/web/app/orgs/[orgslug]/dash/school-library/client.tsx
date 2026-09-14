'use client'

/**
 * School Library, attached as a first-class Learnhouse dash module.
 *
 * Built rather than moved: `modules/sms/library` was API-only, with no UI
 * anywhere in the app.
 *
 * Routed at `/dash/school-library`, NOT `/dash/library` -- Learnhouse already
 * ships its own content/folder Library module there
 * (app/orgs/[orgslug]/dash/library, including a folder/[folderid] subtree).
 * Taking that path would have silently clobbered a working Learnhouse
 * feature. These are genuinely different things: that one holds course
 * content, this one holds physical books that get lent out.
 */

import { useState } from 'react'
import toast from 'react-hot-toast'
import { BookMarked, BookPlus, Library as LibraryIcon, Search } from 'lucide-react'
import {
  LH_GHOST_BUTTON,
  LH_INPUT,
  LH_PRIMARY_BUTTON,
  LH_SECONDARY_BUTTON,
  DashPageShell,
  DataTable,
  SchoolDialog,
  SchoolField,
  SectionCard,
  StatGrid,
  StatusChip,
} from '@/components/widgets'
import { useApiResource } from '@/lib/api/useApiResource'
import { useSchoolSession } from '@/lib/api/useSchoolSession'
import { listCampuses } from '@/modules/sms/campus/api'
import {
  borrowBook,
  calculateOverdueFines,
  createBook,
  listBooks,
  listLoans,
  returnBook,
} from '@/modules/sms/library/api'
import type { BookLoanStatus, LibraryBookRead } from '@/modules/sms/library/types'

interface SchoolLibraryDashClientProps {
  org_id: number
  orgslug: string
}

/** Adds a title to the catalog. `title` and `author` are the only fields the
 * backend requires (`LibraryBookCreate`); everything else is optional. */
function AddBookDialog({ campusId, onAdded }: { campusId?: number; onAdded: () => void }) {
  const [open, setOpen] = useState(false)
  const [title, setTitle] = useState('')
  const [author, setAuthor] = useState('')
  const [isbn, setIsbn] = useState('')
  const [category, setCategory] = useState('')
  const [copies, setCopies] = useState('1')
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit() {
    if (!title.trim() || !author.trim()) {
      toast.error('Title and author are both required.')
      return
    }
    const totalCopies = Number(copies)
    if (!Number.isInteger(totalCopies) || totalCopies < 1) {
      toast.error('Copies must be a whole number of at least 1.')
      return
    }
    setSubmitting(true)
    try {
      await createBook({
        title: title.trim(),
        author: author.trim(),
        isbn: isbn.trim() || null,
        category: category.trim() || null,
        total_copies: totalCopies,
        campus_id: campusId ?? null,
      })
      toast.success(`Added “${title.trim()}” to the catalog.`)
      setOpen(false)
      setTitle(''); setAuthor(''); setIsbn(''); setCategory(''); setCopies('1')
      onAdded()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not add the book.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <SchoolDialog
      open={open}
      onOpenChange={setOpen}
      trigger={
        <button type="button" className={LH_PRIMARY_BUTTON}>
          <BookPlus className="size-4" /> <span>Add book</span>
        </button>
      }
      title="Add a book to the catalog"
      footer={
        <>
          <button type="button" className={LH_GHOST_BUTTON} onClick={() => setOpen(false)} disabled={submitting}>
            Cancel
          </button>
          <button type="button" className={LH_PRIMARY_BUTTON} onClick={handleSubmit} disabled={submitting}>
            <span>{submitting ? 'Adding…' : 'Add book'}</span>
          </button>
        </>
      }
    >
      <SchoolField id="book-title" label="Title">
        <input id="book-title" className={LH_INPUT} value={title} onChange={(e) => setTitle(e.target.value)} />
      </SchoolField>
      <SchoolField id="book-author" label="Author">
        <input id="book-author" className={LH_INPUT} value={author} onChange={(e) => setAuthor(e.target.value)} />
      </SchoolField>
      <div className="grid grid-cols-2 gap-4">
        <SchoolField id="book-isbn" label="ISBN (optional)">
          <input id="book-isbn" className={LH_INPUT} value={isbn} onChange={(e) => setIsbn(e.target.value)} />
        </SchoolField>
        <SchoolField id="book-category" label="Category (optional)">
          <input id="book-category" className={LH_INPUT} value={category} onChange={(e) => setCategory(e.target.value)} />
        </SchoolField>
      </div>
      <SchoolField id="book-copies" label="Copies">
        <input id="book-copies" type="number" min="1" step="1" className={LH_INPUT} value={copies} onChange={(e) => setCopies(e.target.value)} />
      </SchoolField>
    </SchoolDialog>
  )
}

/** Issues a copy to a borrower. The borrower is entered as a user id: there
 * is no user-search endpoint in this module's API, and inventing a picker
 * from fabricated names would be worse than an honest id field. */
function BorrowDialog({ book, onBorrowed }: { book: LibraryBookRead; onBorrowed: () => void }) {
  const [open, setOpen] = useState(false)
  const [userId, setUserId] = useState('')
  const [dueDate, setDueDate] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit() {
    const uid = Number(userId)
    if (!Number.isInteger(uid) || uid <= 0) {
      toast.error('Enter the borrower’s numeric user id.')
      return
    }
    setSubmitting(true)
    try {
      await borrowBook({ book_id: book.id, user_id: uid, due_date: dueDate || null })
      toast.success(`“${book.title}” issued to user #${uid}.`)
      setOpen(false)
      setUserId(''); setDueDate('')
      onBorrowed()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not issue the book.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <SchoolDialog
      open={open}
      onOpenChange={setOpen}
      trigger={
        <button type="button" className={LH_SECONDARY_BUTTON} disabled={book.available_copies === 0}>
          <span>{book.available_copies === 0 ? 'All out' : 'Issue'}</span>
        </button>
      }
      title={`Issue “${book.title}”`}
      footer={
        <>
          <button type="button" className={LH_GHOST_BUTTON} onClick={() => setOpen(false)} disabled={submitting}>
            Cancel
          </button>
          <button type="button" className={LH_PRIMARY_BUTTON} onClick={handleSubmit} disabled={submitting}>
            <span>{submitting ? 'Issuing…' : 'Issue book'}</span>
          </button>
        </>
      }
    >
      <p className="text-sm text-gray-500">
        {book.available_copies} of {book.total_copies} copies available.
      </p>
      <SchoolField id="borrow-user" label="Borrower user id">
        <input id="borrow-user" type="number" min="1" className={LH_INPUT} value={userId} onChange={(e) => setUserId(e.target.value)} />
      </SchoolField>
      <SchoolField id="borrow-due" label="Due date (optional)" help="Defaults to 14 days from today.">
        <input id="borrow-due" type="date" className={LH_INPUT} value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
      </SchoolField>
    </SchoolDialog>
  )
}

const LOAN_TONE: Record<BookLoanStatus, 'positive' | 'caution' | 'critical'> = {
  RETURNED: 'positive',
  BORROWED: 'caution',
  OVERDUE: 'critical',
}

export default function SchoolLibraryDashClient({ org_id }: SchoolLibraryDashClientProps) {
  const { session } = useSchoolSession()
  const [campusId, setCampusId] = useState<number | undefined>(undefined)
  const [search, setSearch] = useState('')

  const campuses = useApiResource(() => listCampuses({ orgId: org_id, isActive: true }), [org_id], {
    isEmpty: (d) => d.length === 0,
  })

  const effectiveCampusId = campusId ?? session?.campus_id ?? campuses.data?.[0]?.id

  const books = useApiResource(
    () => listBooks({ campusId: effectiveCampusId, search: search.trim() || undefined }),
    [effectiveCampusId, search],
    { isEmpty: (d) => d.length === 0 }
  )

  const loans = useApiResource(() => listLoans({}), [], { isEmpty: (d) => d.length === 0 })

  const [returningId, setReturningId] = useState<number | null>(null)
  const [finesOpen, setFinesOpen] = useState(false)
  const [finePerDay, setFinePerDay] = useState('1')
  const [calculatingFines, setCalculatingFines] = useState(false)

  async function handleReturn(loanId: number, bookLabel: string) {
    setReturningId(loanId)
    try {
      const updated = await returnBook(loanId)
      toast.success(
        updated.fine_amount > 0
          ? `${bookLabel} returned — fine of Rs. ${updated.fine_amount.toFixed(2)} applied.`
          : `${bookLabel} returned.`
      )
      loans.refetch()
      books.refetch()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not record the return.')
    } finally {
      setReturningId(null)
    }
  }

  async function handleCalculateFines() {
    const rate = Number(finePerDay)
    if (!Number.isFinite(rate) || rate < 0) {
      toast.error('Enter a fine per day of zero or more.')
      return
    }
    setCalculatingFines(true)
    try {
      const result = await calculateOverdueFines({ fine_per_day: rate })
      toast.success(
        result.updated_loans_count === 0
          ? 'No overdue loans needed a fine.'
          : `Fines updated on ${result.updated_loans_count} loan${result.updated_loans_count === 1 ? '' : 's'} — Rs. ${result.total_fines_accumulated.toFixed(2)} total.`
      )
      setFinesOpen(false)
      loans.refetch()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not calculate fines.')
    } finally {
      setCalculatingFines(false)
    }
  }

  const bookRows = books.data ?? []
  const loanRows = loans.data ?? []
  const onLoan = loanRows.filter((l) => l.status !== 'RETURNED')
  const overdue = loanRows.filter((l) => l.status === 'OVERDUE')
  const totalCopies = bookRows.reduce((sum, b) => sum + b.total_copies, 0)

  return (
    <DashPageShell
      module="school-library"
      title="School Library"
      description="Book catalog and lending records."
      action={
        <div className="flex flex-wrap gap-2">
            {/*
              Bulk mutation: recalculates the fine on EVERY overdue loan in the
              school, so it asks first and states the blast radius. It is not a
              casual toolbar button.
            */}
            <SchoolDialog
              open={finesOpen}
              onOpenChange={setFinesOpen}
              trigger={
                <button type="button" className={LH_SECONDARY_BUTTON} disabled={overdue.length === 0}>
                  <span>Calculate overdue fines</span>
                </button>
              }
              title="Recalculate fines on all overdue loans?"
              footer={
                <>
                  <button type="button" className={LH_GHOST_BUTTON} onClick={() => setFinesOpen(false)} disabled={calculatingFines}>
                    Cancel
                  </button>
                  <button type="button" className={LH_PRIMARY_BUTTON} onClick={handleCalculateFines} disabled={calculatingFines}>
                    <span>
                      {calculatingFines ? 'Calculating…' : `Update ${overdue.length} loan${overdue.length === 1 ? '' : 's'}`}
                    </span>
                  </button>
                </>
              }
            >
              <p className="text-sm text-gray-500">
                This updates the fine on every overdue loan in the school —{' '}
                <strong className="text-gray-800">
                  {overdue.length} loan{overdue.length === 1 ? '' : 's'}
                </strong>{' '}
                right now — not just the ones shown below. Existing fine amounts will be
                overwritten with the recalculated value.
              </p>
              <SchoolField id="fine-per-day" label="Fine per overdue day (Rs.)">
                <input
                  id="fine-per-day"
                  type="number"
                  min="0"
                  step="0.01"
                  className={LH_INPUT}
                  value={finePerDay}
                  onChange={(e) => setFinePerDay(e.target.value)}
                />
              </SchoolField>
            </SchoolDialog>
            <AddBookDialog campusId={effectiveCampusId} onAdded={books.refetch} />
          </div>
      }
    >

      {/*
        Filters live here, NOT in the SectionCard `action` slot: that slot only
        renders in the 'success' state, so a search returning nothing would
        hide the search box itself -- leaving no way to clear the query.
      */}
      <div className="flex flex-wrap items-end gap-4 rounded-xl bg-white nice-shadow px-4 py-3">
        <label className="flex flex-col gap-1.5">
          <span className="text-xs font-medium text-gray-500">Search catalog</span>
          <span className="relative">
            <Search className="pointer-events-none absolute start-2.5 top-1/2 size-3.5 -translate-y-1/2 text-gray-500" />
            <input
              id="library-search"
              type="search"
              placeholder="Title or author"
              className="w-56 ps-8 pe-3 py-2 bg-white nice-shadow rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-black focus:ring-offset-2 border-0"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </span>
        </label>

        <label className="flex flex-col gap-1.5">
          <span className="text-xs font-medium text-gray-500">Campus</span>
          <select
            id="library-campus"
            className="px-3 py-2 bg-white nice-shadow rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-black focus:ring-offset-2 border-0"
            value={effectiveCampusId ?? ''}
            onChange={(e) => setCampusId(Number(e.target.value))}
          >
            {(campuses.data ?? []).map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
      </div>

      <StatGrid
        state={books.status === 'loading' || loans.status === 'loading' ? 'loading' : 'success'}
        columns={4}
        items={[
          { label: 'Titles', value: bookRows.length, icon: LibraryIcon, tone: 'neutral' },
          { label: 'Total copies', value: totalCopies, icon: LibraryIcon, tone: 'neutral' },
          { label: 'On loan', value: onLoan.length, icon: BookMarked, tone: 'neutral' },
          {
            label: 'Overdue',
            value: overdue.length,
            icon: BookMarked,
            tone: overdue.length > 0 ? 'critical' : 'positive',
          },
        ]}
      />

      <SectionCard
        id="catalog"
        title="Catalog"
        icon={<LibraryIcon className="size-4 text-gray-500" />}
        state={books.status}
        error={books.error ?? campuses.error}
        onRetry={books.refetch}
        emptyTitle={search ? 'No books match that search' : 'No books in the catalog yet'}
        emptyDescription={
          search ? 'Try a different title, author or category.' : 'Add books to start lending them out.'
        }
      >
        <div className="overflow-x-auto">
          <DataTable
            rows={bookRows}
            rowKey={(row) => row.id}
            state="success"
            className="[font-variant-numeric:tabular-nums]"
            totalLabel={`${bookRows.length} title${bookRows.length === 1 ? '' : 's'}`}
            columns={[
              { key: 'title', header: 'Title', render: (r) => r.title },
              { key: 'author', header: 'Author', render: (r) => r.author },
              { key: 'category', header: 'Category', render: (r) => r.category || '—' },
              { key: 'isbn', header: 'ISBN', render: (r) => r.isbn || '—' },
              {
                key: 'available',
                header: 'Available',
                align: 'right',
                render: (r) => (
                  <span className={r.available_copies === 0 ? 'text-gray-500' : undefined}>
                    {r.available_copies} / {r.total_copies}
                  </span>
                ),
              },
              {
                key: 'issue',
                header: '',
                align: 'right',
                render: (r) => <BorrowDialog book={r} onBorrowed={() => { loans.refetch(); books.refetch() }} />,
              },
            ]}
          />
        </div>
      </SectionCard>

      <SectionCard
        id="loans"
        title="Loans"
        description="Books currently out, and their return history."
        icon={<BookMarked className="size-4 text-gray-500" />}
        state={loans.status}
        error={loans.error}
        onRetry={loans.refetch}
        emptyTitle="Nothing has been borrowed yet"
        emptyDescription="Loans appear here once a book is issued to someone."
      >
        <div className="overflow-x-auto">
          <DataTable
            rows={loanRows}
            rowKey={(row) => row.id}
            state="success"
            className="[font-variant-numeric:tabular-nums]"
            totalLabel={`${onLoan.length} on loan · ${overdue.length} overdue`}
            columns={[
              {
                key: 'book',
                header: 'Book',
                render: (r) => r.book_title || `Book #${r.book_id}`,
              },
              { key: 'borrower', header: 'Borrower', render: (r) => `User #${r.user_id}` },
              { key: 'borrowed', header: 'Borrowed', render: (r) => r.borrowed_date },
              { key: 'due', header: 'Due', render: (r) => r.due_date },
              {
                key: 'returned',
                header: 'Returned',
                render: (r) => r.returned_date || '—',
              },
              {
                key: 'fine',
                header: 'Fine',
                align: 'right',
                render: (r) =>
                  r.fine_amount > 0 ? (
                    <span className="text-rose-600">Rs. {r.fine_amount.toFixed(2)}</span>
                  ) : (
                    '—'
                  ),
              },
              {
                key: 'status',
                header: 'Status',
                render: (r) => <StatusChip label={r.status} tone={LOAN_TONE[r.status]} />,
              },
              {
                key: 'return',
                header: '',
                align: 'right',
                render: (r) =>
                  r.status === 'RETURNED' ? (
                    <span className="text-xs text-gray-500">Returned</span>
                  ) : (
                    <button
                      type="button"
                      className={LH_SECONDARY_BUTTON}
                      disabled={returningId === r.id}
                      onClick={() => handleReturn(r.id, r.book_title || `Book #${r.book_id}`)}
                    >
                      <span>{returningId === r.id ? 'Returning…' : 'Return'}</span>
                    </button>
                  ),
              },
            ]}
          />
        </div>
      </SectionCard>
    </DashPageShell>
  )
}
