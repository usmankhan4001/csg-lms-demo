import { getOrganizationContextInfo } from '@services/organizations/orgs'
import { Metadata } from 'next'
import React from 'react'
import LeadDetailClient from './client'

type MetadataProps = {
  params: Promise<{ orgslug: string; leadId: string }>
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>
}

export async function generateMetadata(props: MetadataProps): Promise<Metadata> {
  const params = await props.params
  const org = await getOrganizationContextInfo(params.orgslug, {
    revalidate: 120,
    tags: ['organizations'],
  })

  return {
    // Deliberately not the student's name: page titles leak into browser
    // history and shared screenshots, and an admissions lead is a real child.
    title: `Lead #${params.leadId} — ` + org.name,
    description: `Admissions lead detail for ${org.name}`,
    robots: { index: false, follow: false },
  }
}

async function LeadDetailPage(params: any) {
  const p = await params.params
  const orgslug = p.orgslug
  const org = await getOrganizationContextInfo(orgslug, {
    revalidate: 120,
    tags: ['organizations'],
  })

  return <LeadDetailClient org_id={org.id} orgslug={orgslug} leadId={Number(p.leadId)} />
}

export default LeadDetailPage
