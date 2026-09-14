import { getOrganizationContextInfo } from '@services/organizations/orgs'
import { Metadata } from 'next'
import React from 'react'
import AttendanceHistoryClient from './client'

type MetadataProps = {
  params: Promise<{ orgslug: string }>
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>
}

export async function generateMetadata(props: MetadataProps): Promise<Metadata> {
  const params = await props.params
  const org = await getOrganizationContextInfo(params.orgslug, {
    revalidate: 120,
    tags: ['organizations'],
  })

  return {
    title: 'Attendance history — ' + org.name,
    description: `Student attendance history and correction trail for ${org.name}`,
    robots: {
      index: false,
      follow: false,
    },
  }
}

async function AttendanceHistoryClientPage(params: any) {
  const orgslug = (await params.params).orgslug
  const org = await getOrganizationContextInfo(orgslug, {
    revalidate: 120,
    tags: ['organizations'],
  })

  return <AttendanceHistoryClient org_id={org.id} orgslug={orgslug} />
}

export default AttendanceHistoryClientPage
