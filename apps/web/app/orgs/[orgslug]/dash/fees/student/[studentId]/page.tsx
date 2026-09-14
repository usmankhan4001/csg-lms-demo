import { getOrganizationContextInfo } from '@services/organizations/orgs'
import { Metadata } from 'next'
import { notFound } from 'next/navigation'
import React from 'react'
import StudentFeeAccountClient from './client'

type MetadataProps = {
  params: Promise<{ orgslug: string; studentId: string }>
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>
}

export async function generateMetadata(props: MetadataProps): Promise<Metadata> {
  const params = await props.params
  const org = await getOrganizationContextInfo(params.orgslug, {
    revalidate: 120,
    tags: ['organizations'],
  })

  return {
    title: `Fee account — ${org.name}`,
    description: `Fee vouchers, payments, concessions and refunds for one student at ${org.name}`,
    robots: {
      index: false,
      follow: false,
    },
  }
}

async function StudentFeeAccountPage(props: any) {
  const params = await props.params
  const orgslug = params.orgslug as string

  // A non-numeric id can only come from a hand-typed or broken URL. 404 rather
  // than passing NaN to the API, which would produce a confusing 422 on a
  // screen the user cannot correct.
  const studentId = Number(params.studentId)
  if (!Number.isInteger(studentId) || studentId <= 0) {
    notFound()
  }

  const org = await getOrganizationContextInfo(orgslug, {
    revalidate: 120,
    tags: ['organizations'],
  })

  return (
    <StudentFeeAccountClient org_id={org.id} orgslug={orgslug} studentId={studentId} />
  )
}

export default StudentFeeAccountPage
