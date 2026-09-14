/**
 * CSV -> provisioning rows, parsed in the browser.
 *
 * Why the API takes JSON and the CSV is parsed here rather than uploaded:
 * a school's roster arrives as a spreadsheet, but a malformed line is
 * something the administrator can fix in the textarea in front of them. Doing
 * the split client-side means a missing column is reported instantly, against
 * the line they can see, instead of costing a round trip and coming back as a
 * row index into a payload they never saw. The API keeps ONE schema with real
 * validation, rather than a second, weaker, string-splitting path next to it.
 *
 * Deliberately small: quoted fields with embedded commas are supported because
 * names contain them ("Khan, Jr"), but nothing else is. This is not a CSV
 * library and should not grow into one.
 */

import type { ProvisionPersonPayload, ProvisionableRole } from './types'

export const CSV_COLUMNS = [
  'role',
  'email',
  'first_name',
  'last_name',
  'section_id',
  'academic_year_id',
  'roll_number',
  'child_student_id',
  'relationship',
] as const

export const CSV_TEMPLATE = [
  CSV_COLUMNS.join(','),
  'STUDENT,zara.k@example.com,Zara,Khan,12,3,7A-014,,',
  'TEACHER,n.aslam@example.com,Nadia,Aslam,,,,,',
  'PARENT,s.khan@example.com,Sara,Khan,,,,41,mother',
].join('\n')

const VALID_ROLES: ProvisionableRole[] = [
  'SCHOOL_ADMIN',
  'TEACHER',
  'STUDENT',
  'PARENT',
  'STAFF',
  'PSYCHOLOGIST',
]

export interface CsvParseRow {
  /** 0-based index among DATA rows, matching what the API reports back. */
  index: number
  /** 1-based line in the pasted text, so the administrator can find it. */
  line: number
  payload?: ProvisionPersonPayload
  error?: string
}

export interface CsvParseResult {
  rows: CsvParseRow[]
  /** A problem with the file itself rather than any one row. */
  fatal?: string
}

function splitLine(line: string): string[] {
  const out: string[] = []
  let field = ''
  let inQuotes = false
  for (let i = 0; i < line.length; i++) {
    const ch = line[i]
    if (inQuotes) {
      if (ch === '"' && line[i + 1] === '"') {
        field += '"'
        i++
      } else if (ch === '"') {
        inQuotes = false
      } else {
        field += ch
      }
    } else if (ch === '"') {
      inQuotes = true
    } else if (ch === ',') {
      out.push(field)
      field = ''
    } else {
      field += ch
    }
  }
  out.push(field)
  return out.map((f) => f.trim())
}

function optionalInt(raw: string, label: string): { value?: number; error?: string } {
  if (!raw) return {}
  const n = Number(raw)
  if (!Number.isInteger(n) || n <= 0) {
    return { error: `${label} must be a positive whole number, not "${raw}".` }
  }
  return { value: n }
}

export function parseProvisioningCsv(text: string, campusId?: number): CsvParseResult {
  const lines = text.split(/\r?\n/)
  const firstContent = lines.findIndex((l) => l.trim().length > 0)
  if (firstContent === -1) return { rows: [], fatal: 'Nothing to import — paste or upload a CSV first.' }

  const header = splitLine(lines[firstContent]).map((h) => h.toLowerCase())
  for (const required of ['role', 'email', 'first_name']) {
    if (!header.includes(required)) {
      return {
        rows: [],
        fatal:
          `The header row is missing "${required}". Expected columns: ` +
          `${CSV_COLUMNS.join(', ')} (only role, email and first_name are required).`,
      }
    }
  }

  const rows: CsvParseRow[] = []
  let index = 0

  for (let i = firstContent + 1; i < lines.length; i++) {
    if (!lines[i].trim()) continue
    const cells = splitLine(lines[i])
    const get = (name: string) => {
      const at = header.indexOf(name)
      return at === -1 ? '' : (cells[at] ?? '')
    }
    const row: CsvParseRow = { index, line: i + 1 }
    index++

    const role = get('role').toUpperCase()
    if (!VALID_ROLES.includes(role as ProvisionableRole)) {
      row.error =
        role === 'SUPER_ADMIN'
          ? 'SUPER_ADMIN cannot be created here. It is platform-wide access, not a school role.'
          : `"${get('role')}" is not a role. Use one of: ${VALID_ROLES.join(', ')}.`
      rows.push(row)
      continue
    }

    const email = get('email')
    if (!email || !email.includes('@')) {
      row.error = `"${email}" is not an email address. Every account needs one to set a password.`
      rows.push(row)
      continue
    }

    const firstName = get('first_name')
    if (!firstName) {
      row.error = 'first_name is empty. An account with no name shows as "Unnamed" everywhere.'
      rows.push(row)
      continue
    }

    const section = optionalInt(get('section_id'), 'section_id')
    const year = optionalInt(get('academic_year_id'), 'academic_year_id')
    const child = optionalInt(get('child_student_id'), 'child_student_id')
    const numericError = section.error || year.error || child.error
    if (numericError) {
      row.error = numericError
      rows.push(row)
      continue
    }

    // Caught here rather than server-side only, so the administrator sees it
    // against the line they are looking at instead of after an import run.
    if ((section.value === undefined) !== (year.value === undefined)) {
      row.error =
        'Enrolling a student needs BOTH section_id and academic_year_id. One without the other cannot be placed.'
      rows.push(row)
      continue
    }

    row.payload = {
      role: role as ProvisionableRole,
      email,
      first_name: firstName,
      last_name: get('last_name') || undefined,
      campus_id: campusId,
      section_id: section.value,
      academic_year_id: year.value,
      roll_number: get('roll_number') || undefined,
      child_student_id: child.value,
      relationship: get('relationship') || undefined,
    }
    rows.push(row)
  }

  if (rows.length === 0) {
    return { rows, fatal: 'The file has a header but no rows under it.' }
  }
  return { rows }
}
