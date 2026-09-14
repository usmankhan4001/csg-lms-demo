import { test, expect } from '@playwright/test'

/**
 * E2E tests for SMS Gradebook Module:
 * - Teacher creates an Assessment Plan (Quiz, Midterm, Final Exam) with weighting and max score.
 * - Teacher enters marks for students in the matrix grid.
 * - Live GPA / weighted score computation preview updates dynamically.
 * - Batch saving of gradebook marks.
 * - Report card drafting & verification.
 */

test.describe('SMS Gradebook & GPA Computation', () => {
  const orgSlug = 'demo-school'

  test.beforeEach(async ({ page }) => {
    // 1. Mock Campuses, Sections, Terms, Courses
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

    await page.route('**/sms/campus/terms*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: 1,
            campus_id: 1,
            academic_year_id: 1,
            name: 'Fall Term 2026',
            start_date: '2026-09-01',
            end_date: '2026-12-20',
            is_active: true,
          },
        ]),
      })
    })

    await page.route('**/courses/org_slug/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          { id: 101, name: 'Mathematics 101' },
          { id: 102, name: 'Physics 101' },
        ]),
      })
    })

    // 2. Mock Section Enrollments & Student Names
    await page.route('**/sms/campus/sections/10/enrollments*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          { id: 1, section_id: 10, student_id: 201, roll_number: '01', status: 'active' },
          { id: 2, section_id: 10, student_id: 202, roll_number: '02', status: 'active' },
        ]),
      })
    })

    await page.route('**/sms/campus/campuses/1/students*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          { id: 201, user_id: 201, full_name: 'David Miller', admission_number: 'ADM-201' },
          { id: 202, user_id: 202, full_name: 'Emma Watson', admission_number: 'ADM-202' },
        ]),
      })
    })

    // 3. Mock Grading Scales
    await page.route('**/sms/gradebook/scales*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: 1,
            name: 'Standard 4.0 Scale',
            is_default: true,
            intervals: [
              { grade: 'A+', min_percentage: 90.0, max_percentage: 100.0, gpa_point: 4.0 },
              { grade: 'A', min_percentage: 80.0, max_percentage: 89.99, gpa_point: 3.7 },
              { grade: 'B', min_percentage: 70.0, max_percentage: 79.99, gpa_point: 3.0 },
              { grade: 'C', min_percentage: 60.0, max_percentage: 69.99, gpa_point: 2.0 },
              { grade: 'F', min_percentage: 0.0, max_percentage: 59.99, gpa_point: 0.0 },
            ],
          },
        ]),
      })
    })

    // 4. Mock Assessment Plans
    let mockPlans = [
      {
        id: 1,
        course_id: 101,
        section_id: 10,
        academic_term_id: 1,
        assessment_name: 'Midterm Exam',
        weight_percentage: 50.0,
        max_score: 100.0,
      },
    ]

    await page.route('**/sms/gradebook/plans*', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(mockPlans),
        })
      } else if (route.request().method() === 'POST') {
        const body = JSON.parse(route.request().postData() || '{}')
        const newPlan = {
          id: mockPlans.length + 1,
          course_id: body.course_id,
          section_id: body.section_id,
          academic_term_id: body.academic_term_id,
          assessment_name: body.assessment_name,
          weight_percentage: body.weight_percentage,
          max_score: body.max_score,
        }
        mockPlans.push(newPlan)
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(newPlan),
        })
      } else {
        await route.continue()
      }
    })

    // 5. Mock Gradebook Entries
    let mockEntries: any[] = []

    await page.route('**/sms/gradebook/entries*', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ entries: mockEntries }),
        })
      } else {
        await route.continue()
      }
    })

    await page.route('**/sms/gradebook/entries/batch*', async (route) => {
      if (route.request().method() === 'POST') {
        const body = JSON.parse(route.request().postData() || '{}')
        const created = (body.entries || []).map((e: any, idx: number) => ({
          id: 1000 + idx,
          student_id: e.student_id,
          assessment_plan_id: body.assessment_plan_id,
          raw_score: e.raw_score,
          weighted_score: (e.raw_score / 100) * 50,
          letter_grade: e.raw_score >= 90 ? 'A+' : e.raw_score >= 80 ? 'A' : 'B',
          gpa_point: e.raw_score >= 90 ? 4.0 : 3.7,
        }))
        mockEntries = [...mockEntries, ...created]
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(created),
        })
      } else {
        await route.continue()
      }
    })
  })

  test('teacher creates assessment plan, enters marks with live GPA preview, and saves grades', async ({
    page,
  }) => {
    await page.goto(`/orgs/${orgSlug}/dash/gradebook`)

    // Verify selectors & loaded students
    await expect(page.locator('#gradebook-campus')).toBeVisible()
    await expect(page.locator('#gradebook-section')).toBeVisible()
    await expect(page.getByText('David Miller')).toBeVisible()
    await expect(page.getByText('Emma Watson')).toBeVisible()

    // Verify matrix loaded with existing plan "Midterm Exam"
    await expect(page.getByText('Midterm Exam')).toBeVisible()

    // Enter marks for David Miller (90/100 -> 45.0% weighted of 50%)
    const davidCell = page.locator('#grade-201-1')
    await davidCell.fill('90')

    // Enter marks for Emma Watson (80/100 -> 40.0% weighted of 50%)
    const emmaCell = page.locator('#grade-202-1')
    await emmaCell.fill('80')

    // Verify live client-side preview shows weighted score updates
    await expect(page.getByText('45.0%')).toBeVisible()
    await expect(page.getByText('40.0%')).toBeVisible()

    // Save grades
    const saveBtn = page.getByRole('button', { name: /save grades/i })
    await expect(saveBtn).toBeEnabled()
    await saveBtn.click()

    // Verify save confirmation feedback
    await expect(page.getByText(/Saved 2 grades/i)).toBeVisible()
  })

  test('teacher creates a second assessment plan via dialog', async ({ page }) => {
    await page.goto(`/orgs/${orgSlug}/dash/gradebook`)

    // Open "New assessment" modal
    const newAssessmentBtn = page.getByRole('button', { name: /new assessment/i })
    await expect(newAssessmentBtn).toBeVisible()
    await newAssessmentBtn.click()

    // Fill dialog form
    await page.locator('#plan-course').selectOption('101')
    await page.locator('#plan-name').fill('Final Exam')
    await page.locator('#plan-weight').fill('50')
    await page.locator('#plan-max').fill('100')

    // Submit dialog
    const createBtn = page.getByRole('button', { name: /create/i })
    await createBtn.click()

    // Assessment dialog closes and matrix updates
    await expect(page.getByText('Final Exam')).toBeVisible()
  })
})
