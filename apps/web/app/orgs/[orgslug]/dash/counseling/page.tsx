import { getOrganizationContextInfo } from '@services/organizations/orgs'
import { Metadata } from 'next'
import React from 'react'
import CounselingDashClient from './client'

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

  // No student identifier in the title -- page titles land in browser
  // history, screenshots and screen shares.
  return {
    title: 'Counselling — ' + org.name,
    description: 'Confidential counselling records for ' + org.name,
    robots: {
      index: false,
      follow: false,
    },
  }
}

async function Page(params: any) {
  const orgslug = (await params.params).orgslug
  const org = await getOrganizationContextInfo(orgslug, {
    revalidate: 120,
    tags: ['organizations'],
  })

  return <CounselingDashClient org_id={org.id} orgslug={orgslug} />
}

export default Page
