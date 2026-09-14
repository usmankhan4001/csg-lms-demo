import { getOrganizationContextInfo } from '@services/organizations/orgs'
import { Metadata } from 'next'
import React from 'react'
import LiveClassDetailClient from './client'

type MetadataProps = {
  params: Promise<{ orgslug: string; classId: string }>
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>
}

export async function generateMetadata(props: MetadataProps): Promise<Metadata> {
  const params = await props.params
  const org = await getOrganizationContextInfo(params.orgslug, {
    revalidate: 120,
    tags: ['organizations'],
  })

  return {
    // Deliberately generic: a class title can name a section or a child's
    // group, and page titles land in browser history and screenshots.
    title: 'Live class — ' + org.name,
    robots: {
      index: false,
      follow: false,
    },
  }
}

async function LiveClassDetailPage(props: any) {
  const params = await props.params
  const orgslug = params.orgslug
  const classId = Number(params.classId)

  return <LiveClassDetailClient classId={classId} orgslug={orgslug} />
}

export default LiveClassDetailPage
