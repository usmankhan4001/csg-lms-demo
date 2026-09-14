import { getOrganizationContextInfo } from '@services/organizations/orgs'
import { Metadata } from 'next'
import React from 'react'
import SchoolSettingsClient from './client'

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
    title: 'School settings — ' + org.name,
    description: `Grading scale, fee policy and school profile for ${org.name}`,
    robots: {
      index: false,
      follow: false,
    },
  }
}

async function SchoolSettingsPage(params: any) {
  const orgslug = (await params.params).orgslug
  const org = await getOrganizationContextInfo(orgslug, {
    revalidate: 120,
    tags: ['organizations'],
  })

  return <SchoolSettingsClient org_id={org.id} orgslug={orgslug} />
}

export default SchoolSettingsPage
