import { getOrganizationContextInfo } from '@services/organizations/orgs'
import { Metadata } from 'next'
import React from 'react'
import RolesSettingsClient from './client'

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
    title: 'School roles — ' + org.name,
    description: `Assign school roles and guardian links for ${org.name}`,
    robots: {
      index: false,
      follow: false,
    },
  }
}

export default async function SchoolRolesPage(props: {
  params: Promise<{ orgslug: string }>
}) {
  const { orgslug } = await props.params
  const org = await getOrganizationContextInfo(orgslug, {
    revalidate: 120,
    tags: ['organizations'],
  })

  return <RolesSettingsClient org_id={org.id} />
}
