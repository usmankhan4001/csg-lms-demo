import { getOrganizationContextInfo } from '@services/organizations/orgs'
import { Metadata } from 'next'
import React from 'react'
import ApplicationDetailClient from './client'

type MetadataProps = {
  params: Promise<{ orgslug: string; applicationId: string }>
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>
}

export async function generateMetadata(props: MetadataProps): Promise<Metadata> {
  const params = await props.params
  const org = await getOrganizationContextInfo(params.orgslug, {
    revalidate: 120,
    tags: ['organizations'],
  })

  return {
    // Deliberately the reference, not the child's name: page titles leak into
    // browser history, tab lists and shared screenshots, and an application
    // carries a real child's identity documents.
    title: `Application #${params.applicationId} — ` + org.name,
    description: `Admission application detail for ${org.name}`,
    robots: { index: false, follow: false },
  }
}

async function ApplicationDetailPage(params: any) {
  const p = await params.params
  const orgslug = p.orgslug
  const org = await getOrganizationContextInfo(orgslug, {
    revalidate: 120,
    tags: ['organizations'],
  })

  return (
    <ApplicationDetailClient
      org_id={org.id}
      orgslug={orgslug}
      applicationId={Number(p.applicationId)}
    />
  )
}

export default ApplicationDetailPage
