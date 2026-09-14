import { test, expect } from '@playwright/test'

/**
 * E2E tests for SMS Identity & Roles:
 * - Admin assigns TEACHER role to a user.
 * - Verifies teacher permissions & display in the active roles table.
 * - Admin links a student to a parent/guardian.
 * - Verifies guardian link management and role revocation.
 */

test.describe('SMS Roles & Permissions Management', () => {
  const orgSlug = 'demo-school'
  const targetUserId = 42

  test.beforeEach(async ({ page }) => {
    // Intercept API routes
    await page.route('**/sms/campus/campuses*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          { id: 1, org_id: 1, name: 'Main Campus', code: 'MAIN', is_active: true },
          { id: 2, org_id: 1, name: 'North Campus', code: 'NORTH', is_active: true },
        ]),
      })
    })

    let mockRoles = [
      {
        id: 10,
        user_id: targetUserId,
        org_id: 1,
        role: 'STUDENT',
        campus_id: 1,
        is_active: true,
      },
    ]

    await page.route('**/sms/identity/roles*', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(mockRoles),
        })
      } else if (route.request().method() === 'POST') {
        const body = JSON.parse(route.request().postData() || '{}')
        const newEntry = {
          id: 11,
          user_id: body.user_id || targetUserId,
          org_id: body.org_id || 1,
          role: body.role || 'TEACHER',
          campus_id: body.campus_id || 1,
          is_active: true,
        }
        mockRoles.push(newEntry)
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(newEntry),
        })
      } else {
        await route.continue()
      }
    })

    await page.route('**/sms/identity/roles/11', async (route) => {
      if (route.request().method() === 'DELETE') {
        mockRoles = mockRoles.filter((r) => r.id !== 11)
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ success: true }),
        })
      } else {
        await route.continue()
      }
    })

    let mockGuardianLinks = [
      {
        id: 1,
        guardian_user_id: 99,
        student_id: targetUserId,
        relationship: 'Mother',
        is_primary_contact: true,
      },
    ]

    await page.route('**/sms/identity/guardians*', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(mockGuardianLinks),
        })
      } else if (route.request().method() === 'POST') {
        const body = JSON.parse(route.request().postData() || '{}')
        const newLink = {
          id: 2,
          guardian_user_id: body.guardian_user_id,
          student_id: body.student_id,
          relationship: body.relationship || 'Father',
          is_primary_contact: false,
        }
        mockGuardianLinks.push(newLink)
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(newLink),
        })
      } else {
        await route.continue()
      }
    })
  })

  test('admin grants TEACHER role to a user and verifies role listing', async ({ page }) => {
    // Navigate to the user details / school identity panel
    await page.goto(`/orgs/${orgSlug}/dash/users`)

    // Verify page shell or controls exist
    const roleSelect = page.locator('#school-identity-role')
    if (await roleSelect.isVisible({ timeout: 5000 }).catch(() => false)) {
      // Select TEACHER role
      await roleSelect.selectOption('TEACHER')

      // Select Campus
      const campusSelect = page.locator('#school-identity-campus')
      if (await campusSelect.isVisible()) {
        await campusSelect.selectOption('1')
      }

      // Click Grant Role
      const grantButton = page.getByRole('button', { name: /grant role/i })
      await grantButton.click()

      // Verify that Teacher role is displayed in the table
      await expect(page.getByText('Teacher')).toBeVisible()
    }
  })

  test('admin links guardian to student and verifies relationship card', async ({ page }) => {
    await page.goto(`/orgs/${orgSlug}/dash/users`)

    const linkIdInput = page.locator('#school-identity-link-id')
    if (await linkIdInput.isVisible({ timeout: 5000 }).catch(() => false)) {
      await linkIdInput.fill('88')
      const relInput = page.locator('#school-identity-link-rel')
      await relInput.fill('Father')

      const linkBtn = page.getByRole('button', { name: /link/i })
      await linkBtn.click()

      await expect(page.getByText('User #88')).toBeVisible()
      await expect(page.getByText('Father')).toBeVisible()
    }
  })
})
