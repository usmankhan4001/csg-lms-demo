import { getOrganizationContextInfo } from '@services/organizations/orgs'
import { Metadata } from 'next'
import React from 'react'
import DigestClient from './client'

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
    // No student identifier in the title: a page title lands in browser
    // history, screenshots and screen-share, so it must never name a child.
    title: 'Family digest — ' + org.name,
    description: `Weekly guardian digest preview for ${org.name}`,
    robots: {
      index: false,
      follow: false,
    },
  }
}

async function DigestClientPage(params: any) {
  const orgslug = (await params.params).orgslug
  const org = await getOrganizationContextInfo(orgslug, {
    revalidate: 120,
    tags: ['organizations'],
  })

  return <DigestClient org_id={org.id} orgslug={orgslug} />
}

export default DigestClientPage
