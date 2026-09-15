import { getOrganizationContextInfo } from '@services/organizations/orgs'
import { Metadata } from 'next'
import React from 'react'
import SittingsClient from './client'

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
    title: 'Sittings — ' + org.name,
    description: `Which sections sit each exam, in which room, and when the room actually ran, for ${org.name}`,
    robots: {
      index: false,
      follow: false,
    },
  }
}

async function SittingsPage(params: any) {
  const orgslug = (await params.params).orgslug
  const org = await getOrganizationContextInfo(orgslug, {
    revalidate: 120,
    tags: ['organizations'],
  })

  return <SittingsClient org_id={org.id} orgslug={orgslug} />
}

export default SittingsPage
