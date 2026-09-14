'use client'

import React from 'react'
import FormLayout, {
  FormField,
  FormLabelAndMessage,
  Input,
} from '@components/Objects/StyledElements/Form/Form'
import * as Form from '@radix-ui/react-form'
import { AlertTriangle, CheckCircle } from 'lucide-react'
import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import { useFormik } from 'formik'
import { acceptSchoolInvite } from '@services/auth/auth'
import { getErrorMessage } from '@services/utils/ts/errorMessage'
import AuthLayout from '@components/Auth/AuthLayout'
import {
  PasswordStrengthIndicator,
  validatePasswordStrength,
} from '@components/Auth/PasswordStrengthIndicator'

/**
 * Where an invited person chooses their password.
 *
 * No account is ever created here and no password is ever pre-filled — the
 * account already exists with a deliberately unusable password, and this is the
 * only way its owner ever gets in.
 */
function AcceptInviteClient({ org }: { org: any }) {
  const searchParams = useSearchParams()
  const router = useRouter()

  const orgIdParam = searchParams.get('org_id')
  const email = searchParams.get('email') ?? ''
  const code = searchParams.get('code') ?? ''
  const orgId = orgIdParam ? Number(orgIdParam) : NaN

  const [error, setError] = React.useState<string>('')
  const [done, setDone] = React.useState(false)
  const [submitting, setSubmitting] = React.useState(false)

  // A link that is missing any part of itself cannot be repaired here, and
  // showing a password form that is guaranteed to fail would waste the
  // recipient's time and make them think they had done something wrong.
  const linkIsComplete = Boolean(email) && Boolean(code) && Number.isFinite(orgId)

  const formik = useFormik({
    initialValues: { new_password: '', confirm_password: '' },
    validate: (values) => {
      const errors: Record<string, string> = {}
      if (!values.new_password) {
        errors.new_password = 'Choose a password'
      } else if (!validatePasswordStrength(values.new_password).isValid) {
        errors.new_password = 'This password is not strong enough yet'
      }
      if (!values.confirm_password) {
        errors.confirm_password = 'Type the password again'
      } else if (values.confirm_password !== values.new_password) {
        errors.confirm_password = 'The two passwords do not match'
      }
      return errors
    },
    onSubmit: async (values) => {
      setSubmitting(true)
      setError('')
      const res = await acceptSchoolInvite(orgId, email, code, values.new_password)
      if (res.success === false) {
        // The backend answers every failure identically on purpose, so that
        // this page cannot be used to discover which addresses have accounts.
        setError(
          getErrorMessage(res.data?.detail, 'This invitation is no longer valid.')
        )
        setSubmitting(false)
        return
      }
      setDone(true)
      setSubmitting(false)
      setTimeout(() => router.push('/auth/login'), 2500)
    },
  })

  return (
    <AuthLayout
      org={org}
      welcomeText="Set your password"
      title="Welcome aboard."
      subtitle="Choose a password and your account is ready to use."
    >
      <div className="mx-6 md:mx-12 lg:mx-20 mt-6">
        {!linkIsComplete && (
          <div
            id="invite-link-broken"
            className="rounded-xl border border-red-100 bg-red-50 px-4 py-3 text-red-700 flex items-start gap-3"
          >
            <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
            <div className="text-sm">
              <p className="font-semibold">This invitation link is incomplete.</p>
              <p className="mt-1">
                Email programs sometimes shorten long links. Open the link from the
                original email again, or ask your school to send you a new
                invitation.
              </p>
            </div>
          </div>
        )}

        {error && (
          <div
            id="invite-error"
            className="rounded-xl border border-red-100 bg-red-50 px-4 py-3 text-red-700 flex items-start gap-3"
          >
            <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
            <div className="text-sm">
              <p className="font-semibold">{error}</p>
              <p className="mt-1">
                Invitations expire, and can only be used once. Ask your school to
                send a new one if this keeps happening.
              </p>
            </div>
          </div>
        )}

        {done && (
          <div
            id="invite-done"
            className="rounded-xl border border-green-100 bg-green-50 px-4 py-3 text-green-700 flex items-start gap-3"
          >
            <CheckCircle className="w-5 h-5 shrink-0 mt-0.5" />
            <div className="text-sm">
              <p className="font-semibold">Your password is set.</p>
              <p className="mt-1">Taking you to the sign-in page…</p>
            </div>
          </div>
        )}
      </div>

      {linkIsComplete && !done && (
        <div className="mx-6 md:mx-12 lg:mx-20 mt-6">
          <FormLayout onSubmit={formik.handleSubmit}>
            <p className="text-sm text-gray-500 mb-4">
              Setting the password for <span className="font-semibold">{email}</span>.
            </p>

            <FormField name="new_password">
              <FormLabelAndMessage label="New password" message={formik.errors.new_password} />
              <Form.Control asChild>
                <Input
                  id="invite-new-password"
                  onChange={formik.handleChange}
                  onBlur={formik.handleBlur}
                  value={formik.values.new_password}
                  type="password"
                  autoComplete="new-password"
                  required
                />
              </Form.Control>
              <PasswordStrengthIndicator password={formik.values.new_password} />
            </FormField>

            <FormField name="confirm_password">
              <FormLabelAndMessage
                label="Confirm password"
                message={formik.errors.confirm_password}
              />
              <Form.Control asChild>
                <Input
                  id="invite-confirm-password"
                  onChange={formik.handleChange}
                  onBlur={formik.handleBlur}
                  value={formik.values.confirm_password}
                  type="password"
                  autoComplete="new-password"
                  required
                />
              </Form.Control>
            </FormField>

            <div className="flex py-4">
              <Form.Submit asChild>
                <button
                  id="invite-submit"
                  type="submit"
                  disabled={submitting}
                  className="w-full bg-black text-white rounded-xl px-5 py-3 text-sm font-semibold disabled:opacity-60"
                >
                  {submitting ? 'Setting your password…' : 'Set password and continue'}
                </button>
              </Form.Submit>
            </div>
          </FormLayout>
        </div>
      )}

      <div className="mx-6 md:mx-12 lg:mx-20 mt-2 mb-8 text-sm text-gray-500">
        Already set a password?{' '}
        <Link href="/auth/login" className="font-semibold text-black">
          Sign in
        </Link>
      </div>
    </AuthLayout>
  )
}

export default AcceptInviteClient
