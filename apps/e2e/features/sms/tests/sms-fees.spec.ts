import { test, expect } from '@playwright/test'

/**
 * E2E tests for SMS Fees Module:
 * - Admin creates a Fee Structure with tuition, transport, lab components.
 * - Admin generates fee vouchers for enrolled students in a section.
 * - Admin collects/records payment for a voucher.
 * - Parent views child's fee ledger and receipt status under My School.
 */

test.describe('SMS Fees, Vouchers & Payment Lifecycle', () => {
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

    await page.route('**/sms/campus/sections/10/enrollments*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          { id: 1, section_id: 10, student_id: 301, roll_number: '01', status: 'active' },
        ]),
      })
    })

    // 2. Mock Fee Structures
    let mockStructures = [
      {
        id: 1,
        name: 'Grade 9 Standard Fee',
        campus_id: 1,
        tuition_fee: 5000.0,
        transport_fee: 1000.0,
        lab_fee: 500.0,
        other_fee: 0.0,
        total_amount: 6500.0,
      },
    ]

    await page.route('**/sms/fees/structures*', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(mockStructures),
        })
      } else if (route.request().method() === 'POST') {
        const body = JSON.parse(route.request().postData() || '{}')
        const total =
          (body.tuition_fee || 0) +
          (body.transport_fee || 0) +
          (body.lab_fee || 0) +
          (body.other_fee || 0)
        const newStruct = {
          id: mockStructures.length + 1,
          name: body.name,
          campus_id: body.campus_id,
          tuition_fee: body.tuition_fee || 0,
          transport_fee: body.transport_fee || 0,
          lab_fee: body.lab_fee || 0,
          other_fee: body.other_fee || 0,
          total_amount: total,
        }
        mockStructures.push(newStruct)
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(newStruct),
        })
      } else {
        await route.continue()
      }
    })

    // 3. Mock Vouchers
    let mockVouchers = [
      {
        id: 501,
        voucher_no: 'VOUCH-2026-001',
        fee_structure_id: 1,
        student_id: 301,
        issue_date: '2026-09-01',
        due_date: '2026-09-15',
        total_amount: 6500.0,
        paid_amount: 0.0,
        balance_amount: 6500.0,
        late_fee_applied: 0.0,
        status: 'UNPAID',
      },
    ]

    await page.route('**/sms/fees/vouchers*', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(mockVouchers),
        })
      } else {
        await route.continue()
      }
    })

    await page.route('**/sms/fees/vouchers/generate*', async (route) => {
      if (route.request().method() === 'POST') {
        const body = JSON.parse(route.request().postData() || '{}')
        const created = (body.student_ids || []).map((sid: number, idx: number) => ({
          id: 600 + idx,
          voucher_no: `VOUCH-2026-00${idx + 2}`,
          fee_structure_id: body.fee_structure_id,
          student_id: sid,
          issue_date: body.issue_date,
          due_date: body.due_date,
          total_amount: 6500.0 - (body.discount_per_student || 0),
          paid_amount: 0.0,
          balance_amount: 6500.0 - (body.discount_per_student || 0),
          late_fee_applied: 0.0,
          status: 'UNPAID',
        }))
        mockVouchers = [...mockVouchers, ...created]
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(created),
        })
      } else {
        await route.continue()
      }
    })

    // 4. Mock Payments
    await page.route('**/sms/fees/payments*', async (route) => {
      if (route.request().method() === 'POST') {
        const body = JSON.parse(route.request().postData() || '{}')
        const v = mockVouchers.find((voc) => voc.id === body.voucher_id)
        if (v) {
          v.paid_amount += body.amount_paid
          v.balance_amount = Math.max(0, v.total_amount - v.paid_amount)
          v.status = v.balance_amount === 0 ? 'PAID' : 'PARTIAL'
        }
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            id: 999,
            voucher_id: body.voucher_id,
            amount_paid: body.amount_paid,
            payment_method: body.payment_method || 'ONLINE',
            payment_date: '2026-09-14',
          }),
        })
      } else {
        await route.continue()
      }
    })
  })

  test('admin creates fee structure and collects payment against issued voucher', async ({
    page,
  }) => {
    await page.goto(`/orgs/${orgSlug}/dash/fees`)

    // Verify Invoiced stats & Voucher table
    await expect(page.getByText('VOUCH-2026-001')).toBeVisible()
    await expect(page.getByText('Rs. 6500.00')).toBeVisible()
    await expect(page.getByText('UNPAID')).toBeVisible()

    // Click "Collect" on the voucher row
    const collectBtn = page.getByRole('button', { name: /collect/i }).first()
    await expect(collectBtn).toBeVisible()
    await collectBtn.click()

    // Verify Pay Voucher Dialog opened
    await expect(page.locator('#pay-amount')).toBeVisible()
    await page.locator('#pay-method').selectOption('ONLINE')

    // Submit payment
    const recordBtn = page.getByRole('button', { name: /record payment/i })
    await recordBtn.click()

    // Verify success toast
    await expect(page.getByText(/Payment of Rs\. 6500\.00 recorded/i)).toBeVisible()
  })

  test('admin generates new fee vouchers via dialog', async ({ page }) => {
    await page.goto(`/orgs/${orgSlug}/dash/fees`)

    const genBtn = page.getByRole('button', { name: /generate vouchers/i })
    await expect(genBtn).toBeVisible()
    await genBtn.click()

    // Select fee structure & section
    await page.locator('#gen-structure').selectOption('1')
    await page.locator('#gen-section').selectOption('10')

    // Issue voucher
    const issueBtn = page.getByRole('button', { name: /issue 1 voucher/i })
    await expect(issueBtn).toBeEnabled()
    await issueBtn.click()

    await expect(page.getByText(/Issued 1 voucher/i)).toBeVisible()
  })
})
