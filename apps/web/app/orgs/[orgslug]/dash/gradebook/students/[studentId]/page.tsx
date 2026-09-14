import { getOrganizationContextInfo } from '@services/organizations/orgs'
import { Metadata } from 'next'
import React from 'react'
import StudentGradesClient from './client'

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

  // Deliberately NOT the student's name: a page title leaks into browser
  // history, screenshots and shared links.
  return {
    title: 'Student grades — ' + org.name,
    description: `Cumulative grades and report-card history for ${org.name}`,
    robots: {
      index: false,
      follow: false,
    },
  }
}

async function StudentGradesPage(params: any) {
  const resolved = await params.params
  const orgslug = resolved.orgslug
  const org = await getOrganizationContextInfo(orgslug, {
    revalidate: 120,
    tags: ['organizations'],
  })

  return (
    <StudentGradesClient
      org_id={org.id}
      orgslug={orgslug}
      studentId={Number(resolved.studentId)}
    />
  )
}

export default StudentGradesPage
