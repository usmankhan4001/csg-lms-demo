import { test, expect } from '@playwright/test'

/**
 * E2E tests for SMS Attendance Module:
 * - Teacher selects Campus and Section.
 * - Enrolled student roster is displayed.
 * - Teacher uses "Mark all" bulk buttons (e.g. Mark all Present).
 * - Teacher marks individual student as Late or Absent.
 * - Teacher submits roll-call register.
 * - Verification of payload and confirmation feedback.
 */

test.describe('SMS Attendance & Roll Call', () => {
  const orgSlug = 'demo-school'

  test.beforeEach(async ({ page }) => {
    // 1. Mock Campuses
    await page.route('**/sms/campus/campuses*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          { id: 1, org_id: 1, name: 'Main Campus', code: 'MAIN', is_active: true },
        ]),
      })
    })

    // 2. Mock Class Sections
    await page.route('**/sms/campus/campuses/1/sections*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: 10,
            campus_id: 1,
            academic_year_id: 1,
            grade_level: 'Grade 9',
            section_name: 'A',
            room_number: '101',
            is_active: true,
          },
        ]),
      })
    })

    // 3. Mock Section Enrollments
    await page.route('**/sms/campus/sections/10/enrollments*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          { id: 1, section_id: 10, student_id: 101, roll_number: '01', status: 'active' },
          { id: 2, section_id: 10, student_id: 102, roll_number: '02', status: 'active' },
          { id: 3, section_id: 10, student_id: 103, roll_number: '03', status: 'active' },
        ]),
      })
    })

    // 4. Mock Student Names Map
    await page.route('**/sms/campus/campuses/1/students*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          { id: 101, user_id: 101, full_name: 'Alice Smith', admission_number: 'ADM-001' },
          { id: 102, user_id: 102, full_name: 'Bob Johnson', admission_number: 'ADM-002' },
          { id: 103, user_id: 103, full_name: 'Charlie Brown', admission_number: 'ADM-003' },
        ]),
      })
    })

    // 5. Mock Submit Roll Call
    await page.route('**/sms/attendance/roll-call*', async (route) => {
      if (route.request().method() === 'POST') {
        const payload = JSON.parse(route.request().postData() || '{}')
        expect(payload.section_id).toBe(10)
        expect(payload.entries).toHaveLength(3)

        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            section_id: payload.section_id,
            date: payload.date || '2026-09-14',
            total_recorded: 3,
            entries: payload.entries,
          }),
        })
      } else {
        await route.continue()
      }
    })
  })

  test('teacher selects section, marks individual late/absent statuses, and saves register', async ({
    page,
  }) => {
    await page.goto(`/orgs/${orgSlug}/dash/attendance`)

    // Verify campus & section selector
    await expect(page.locator('#attendance-campus')).toBeVisible()
    await expect(page.locator('#attendance-section')).toBeVisible()

    // Wait for the roll call roster to load
    await expect(page.getByText('Alice Smith')).toBeVisible()
    await expect(page.getByText('Bob Johnson')).toBeVisible()
    await expect(page.getByText('Charlie Brown')).toBeVisible()

    // Test bulk "Mark all" action
    const markAllPresentBtn = page.locator('#rollcall-all-present')
    await expect(markAllPresentBtn).toBeVisible()
    await markAllPresentBtn.click()

    // Mark student 102 as ABSENT
    const bobAbsentRadio = page.locator('#rollcall-102-absent')
    await bobAbsentRadio.click()

    // Mark student 103 as LATE
    const charlieLateRadio = page.locator('#rollcall-103-late')
    await charlieLateRadio.click()

    // Check tally display
    await expect(page.getByText(/1 present · 1 absent · 1 late/i)).toBeVisible()

    // Submit register
    const submitBtn = page.locator('#rollcall-submit')
    await expect(submitBtn).toBeEnabled()
    await submitBtn.click()

    // Verify feedback notification
    await expect(page.getByText(/Register saved/i)).toBeVisible()
  })
})
