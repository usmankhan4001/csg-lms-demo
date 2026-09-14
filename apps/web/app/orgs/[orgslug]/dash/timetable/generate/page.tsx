import { getOrganizationContextInfo } from '@services/organizations/orgs'
import { Metadata } from 'next'
import React from 'react'
import TimetableGenerateClient from './client'

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
    title: 'Generate timetable — ' + org.name,
    description: `Assisted timetable generation for ${org.name}`,
    robots: {
      index: false,
      follow: false,
    },
  }
}

async function TimetableGenerateClientPage(params: any) {
  const orgslug = (await params.params).orgslug
  const org = await getOrganizationContextInfo(orgslug, {
    revalidate: 120,
    tags: ['organizations'],
  })

  return <TimetableGenerateClient org_id={org.id} orgslug={orgslug} />
}

export default TimetableGenerateClientPage
