import { getOrganizationContextInfo } from '@services/organizations/orgs'
import { getAuthOrgSlug } from '@services/org/orgResolution'
import AcceptInviteClient from './accept-invite'
import { Metadata } from 'next'
import { Suspense } from 'react'
import PageLoading from '@components/Objects/Loaders/PageLoading'

export async function generateMetadata(): Promise<Metadata> {
  const orgslug = await getAuthOrgSlug()

  if (!orgslug) {
    return { title: 'Set your password — CSG LMS' }
  }

  let org: any = null
  try {
    org = await getOrganizationContextInfo(orgslug, {
      revalidate: 60,
      tags: ['organizations'],
    })
  } catch {
    // Stale cookie or unknown org — fall back to a generic title.
  }

  return {
    title: 'Set your password' + ` — ${org?.name || 'CSG LMS'}`,
    robots: { index: false, follow: false },
  }
}

/**
 * Where an invited person lands from their email.
 *
 * Deliberately does NOT require the org slug cookie to resolve: the recipient
 * arrives from an email link, often in a browser that has never visited this
 * school before, so there is no session and may be no cookie. Everything the
 * acceptance needs — org, address, token — travels in the link itself and is
 * verified server-side.
 */
const AcceptInvitePage = async () => {
  const orgslug = await getAuthOrgSlug()

  let org: any = null
  if (orgslug) {
    try {
      org = await getOrganizationContextInfo(orgslug, {
        revalidate: 60,
        tags: ['organizations'],
      })
    } catch {
      org = null
    }
  }

  return (
    <Suspense fallback={<PageLoading />}>
      <AcceptInviteClient org={org} />
    </Suspense>
  )
}

export default AcceptInvitePage
