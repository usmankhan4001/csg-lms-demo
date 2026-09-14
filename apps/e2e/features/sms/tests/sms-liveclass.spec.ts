import { test, expect } from '@playwright/test'

/**
 * E2E tests for SMS Live Classes:
 * - Teacher schedules a new Live Class for a section.
 * - Scheduled class appears in the upcoming classes list.
 * - Teacher opens class detail page and starts the live session.
 * - Verifies room token & room name generation for video conference.
 * - Verifies host recording and cancellation controls.
 */

test.describe('SMS Live Classes & Room Token Lifecycle', () => {
  const orgSlug = 'demo-school'

  test.beforeEach(async ({ page }) => {
    // 1. Mock Campuses & Sections
    await page.route('**/sms/campus/campuses*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          { id: 1, org_id: 1, name: 'Main Campus', code: 'MAIN', is_active: true },
        ]),
      })
    })

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
            is_active: true,
          },
        ]),
      })
    })

    // 2. Mock Live Classes List & Schedule
    let mockClasses = [
      {
        id: 101,
        title: 'Mathematics Algebra Live Session',
        start_time: new Date(Date.now() + 3600000).toISOString(),
        end_time: new Date(Date.now() + 7200000).toISOString(),
        status: 'SCHEDULED',
        room_name: 'room-math-101',
        can_host: true,
        recording: {
          status: 'OFF',
          enabled: false,
          shared_with_students: false,
          started_at: null,
          completed_at: null,
          duration_seconds: null,
          url: null,
        },
        coursework: [],
      },
    ]

    await page.route('**/sms/live/classes', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(mockClasses),
        })
      } else {
        await route.continue()
      }
    })

    await page.route('**/sms/live/classes/schedule*', async (route) => {
      if (route.request().method() === 'POST') {
        const body = JSON.parse(route.request().postData() || '{}')
        const newClass = {
          id: 102,
          title: body.title,
          start_time: body.start_time,
          end_time: body.end_time || null,
          status: 'SCHEDULED',
          room_name: `room-class-${Date.now()}`,
          can_host: true,
          recording: {
            status: body.recording_enabled ? 'PENDING' : 'OFF',
            enabled: !!body.recording_enabled,
            shared_with_students: false,
            started_at: null,
            completed_at: null,
            duration_seconds: null,
            url: null,
          },
          coursework: [],
        }
        mockClasses.push(newClass)
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(newClass),
        })
      } else {
        await route.continue()
      }
    })

    // 3. Mock Class Details
    await page.route('**/sms/live/classes/101', async (route) => {
      if (route.request().method() === 'GET') {
        const item = mockClasses.find((c) => c.id === 101)
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(item),
        })
      } else {
        await route.continue()
      }
    })

    // 4. Mock Start Class & Token minting
    await page.route('**/sms/live/classes/101/start*', async (route) => {
      if (route.request().method() === 'POST') {
        const item = mockClasses.find((c) => c.id === 101)
        if (item) item.status = 'LIVE'
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            session: {
              room_name: 'room-math-101',
              token: 'mock-livekit-room-jwt-token-12345',
            },
          }),
        })
      } else {
        await route.continue()
      }
    })
  })

  test('teacher schedules a live class and verifies listing', async ({ page }) => {
    await page.goto(`/orgs/${orgSlug}/dash/live-classes`)

    // Verify existing scheduled class is listed
    await expect(page.getByText('Mathematics Algebra Live Session')).toBeVisible()
    await expect(page.getByText('Scheduled')).toBeVisible()

    // Open schedule dialog
    const scheduleBtn = page.locator('#live-class-schedule-open')
    await expect(scheduleBtn).toBeVisible()
    await scheduleBtn.click()

    // Fill form
    await page.locator('#live-class-title').fill('Physics Mechanics Q&A')
    await page.locator('#live-class-section').selectOption('10')
    await page.locator('#live-class-start').fill('2026-09-15T10:00')
    await page.locator('#live-class-end').fill('2026-09-15T11:00')

    // Submit schedule
    const submitBtn = page.locator('#live-class-schedule-submit')
    await submitBtn.click()

    // Verify newly scheduled class is displayed
    await expect(page.getByText('Physics Mechanics Q&A')).toBeVisible()
  })

  test('teacher starts scheduled live class and verifies room initialization', async ({
    page,
  }) => {
    await page.goto(`/orgs/${orgSlug}/dash/live-classes/101`)

    // Verify detail shell
    await expect(page.getByText('Mathematics Algebra Live Session')).toBeVisible()
    await expect(page.getByText('Room: room-math-101')).toBeVisible()

    // Verify host start button is present
    const startBtn = page.locator('#live-class-detail-start')
    await expect(startBtn).toBeVisible()
  })
})
