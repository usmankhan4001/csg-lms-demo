import { getOrganizationContextInfo } from '@services/organizations/orgs'
import { Metadata } from 'next'
import React from 'react'
import ExamIncidentsClient from './client'

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
    title: 'Invigilation incidents — ' + org.name,
    description: `Invigilator records of what happened in exam rooms at ${org.name}`,
    robots: {
      index: false,
      follow: false,
    },
  }
}

async function ExamIncidentsPage(params: any) {
  const orgslug = (await params.params).orgslug
  const org = await getOrganizationContextInfo(orgslug, {
    revalidate: 120,
    tags: ['organizations'],
  })

  return <ExamIncidentsClient org_id={org.id} orgslug={orgslug} />
}

export default ExamIncidentsPage
