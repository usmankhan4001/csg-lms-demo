import { getOrganizationContextInfo } from '@services/organizations/orgs'
import { Metadata } from 'next'
import React from 'react'
import TimetableLessonsClient from './client'

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
    title: 'Lesson log — ' + org.name,
    description: `What was taught, and the handover for the next teacher for ${org.name}`,
    robots: {
      index: false,
      follow: false,
    },
  }
}

async function TimetableLessonsClientPage(params: any) {
  const orgslug = (await params.params).orgslug
  const org = await getOrganizationContextInfo(orgslug, {
    revalidate: 120,
    tags: ['organizations'],
  })

  return <TimetableLessonsClient org_id={org.id} orgslug={orgslug} />
}

export default TimetableLessonsClientPage
