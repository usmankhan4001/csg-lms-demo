'use client'
import { useOrg } from '@components/Contexts/OrgContext'
import { signOut } from '@components/Contexts/AuthContext'
import { useSchoolSession } from '@/lib/api/useSchoolSession'
import {
  House,
  BookOpen,
  Files,
  Users,
  CurrencyCircleDollar,
  Buildings,
  Globe,
  Question,
  Gear,
  SignOut,
  SidebarSimple,
  Check,
  CaretDown,
  PencilSimple,
  ChatsCircle,
  Book,
  ChatCircleDots,
  Headphones,
  ChartBar,
  Heartbeat,
  DotsThree,
  UsersThree,
  Shield,
  UserPlus,
  ClipboardText,
  Palette,
  Rocket,
  Robot,
  LinkSimple,
  Key,
  Lock,
  Wrench,
  ChartLine,
  MagnifyingGlass,
  Bank,
  Books,
  CalendarBlank,
  ChartLineUp,
  ChatCircle,
  Exam,
  CalendarCheck,
  ChalkboardSimple,
  Cube,
  GraduationCap,
  IdentificationBadge,
  Receipt,
  ShoppingBag,
  FolderSimple,
  Plus,
  Code,
  Lightning,
  ShieldCheck,
  Scales,
  Student,
  SealCheck,
  Trophy,
  Warehouse,
  Compass,
  VideoCamera,
} from '@phosphor-icons/react'
import { motion } from 'motion/react'
import { DiscordIcon } from '@components/Objects/Icons/DiscordIcon'
import CommandPaletteTrigger from '@components/Dashboard/CommandPalette/CommandPaletteTrigger'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import React, { useEffect, useState } from 'react'
import UserAvatar from '../../Objects/UserAvatar'
import AdminAuthorization from '@components/Security/AdminAuthorization'
import { useLHSession } from '@components/Contexts/LHSessionContext'
import { getUriWithOrg, getAPIUrl, getMainDomainUri, isMultiOrgModeEnabled } from '@services/config/config'
import { useTranslation } from 'react-i18next'
import { changeLanguage } from '@/lib/i18n'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@components/ui/tooltip"
import {
  HoverMenu,
  HoverMenuContent,
  HoverMenuItem,
  HoverMenuLabel,
  HoverMenuSeparator,
} from "@components/ui/hover-menu"
import { FeedbackModal } from '@components/Objects/Modals/FeedbackModal'
import { AVAILABLE_LANGUAGES } from '@/lib/languages'
import OrgSquareLogo, { hasOrgLogo } from '@components/Objects/Org/OrgSquareLogo'
import { cn } from '@/lib/utils'
import { useQuery } from '@tanstack/react-query'
import { queryKeys } from '@/lib/query/keys'
import { RequestBodyWithAuthHeader } from '@services/utils/ts/requests'
import { getAssignmentsFromACourse } from '@services/courses/assignments'
import { getDeploymentMode } from '@services/config/config'
import PlanBadge from '@components/Dashboard/Shared/PlanRestricted/PlanBadge'
import { usePlan } from '@components/Hooks/usePlan'
import { planMeetsRequirement } from '@services/plans/plans'
import useAdminStatus from '@components/Hooks/useAdminStatus'
import { useLHAnalytics, AnalyticsEvent } from '@services/analytics'
import OnboardingSidebarBox from '@components/Dashboard/Onboarding/OnboardingSidebarBox'
import { useOnboarding } from '@components/Hooks/useOnboarding'

// Scattered night-sky starfield for the free-plan upgrade box. Fixed positions
// (top/left %) so the constellation is stable across renders; `north` is the
// brighter amber guide star. dim/bright drive the idle twinkle amplitude.
const UPGRADE_STARS: {
  top: string; left: string; size: number; delay: number; dim: number; bright: number; north?: boolean
}[] = [
  { top: '8%', left: '50%', size: 2.5, delay: 0.0, dim: 0.5, bright: 1, north: true },
  { top: '14%', left: '12%', size: 1, delay: 0.6, dim: 0.15, bright: 0.6 },
  { top: '10%', left: '30%', size: 1.5, delay: 1.1, dim: 0.2, bright: 0.7 },
  { top: '22%', left: '20%', size: 1, delay: 0.3, dim: 0.15, bright: 0.55 },
  { top: '30%', left: '38%', size: 1, delay: 1.5, dim: 0.1, bright: 0.5 },
  { top: '18%', left: '66%', size: 1.5, delay: 0.9, dim: 0.2, bright: 0.75 },
  { top: '26%', left: '78%', size: 1, delay: 0.2, dim: 0.15, bright: 0.6 },
  { top: '12%', left: '88%', size: 1, delay: 1.8, dim: 0.1, bright: 0.5 },
  { top: '34%', left: '60%', size: 1, delay: 1.3, dim: 0.15, bright: 0.55 },
  { top: '6%', left: '72%', size: 1, delay: 0.5, dim: 0.1, bright: 0.5 },
  { top: '32%', left: '90%', size: 1.5, delay: 1.0, dim: 0.2, bright: 0.65 },
  { top: '20%', left: '44%', size: 1, delay: 2.0, dim: 0.1, bright: 0.45 },
]

function DashLeftMenu() {
  const org = useOrg() as any
  const session = useLHSession() as any
  const { t, i18n } = useTranslation()
  const { track } = useLHAnalytics('dashboard')
  const pathname = usePathname() || ''
  const [isCollapsed, setIsCollapsed] = useState(false)
  const [upgradeHovered, setUpgradeHovered] = useState(false)
  // Onboarding takes over the search slot until setup is complete / dismissed.
  const onboarding = useOnboarding()
  const showOnboarding =
    !isCollapsed && onboarding.welcomeSeen && !onboarding.dismissed && !onboarding.allCompleted

  const isActivePath = (path: string) => {
    if (path === '/dash') {
      return pathname === '/dash' || pathname === '/dash/'
    }
    return pathname === path || pathname.startsWith(path + '/')
  }
  const [recentAssignments, setRecentAssignments] = useState<any[]>([])
  const [feedbackModalOpen, setFeedbackModalOpen] = useState(false)
  const access_token = session?.data?.tokens?.access_token

  // Fetch recent courses
  const { data: coursesData } = useQuery({
    queryKey: [...queryKeys.courses.list(org?.slug || ''), 'recent', 8],
    queryFn: async () => {
      const url = `${getAPIUrl()}courses/org_slug/${org.slug}/page/1/limit/8`
      const res = await fetch(url, RequestBodyWithAuthHeader('GET', null, null, access_token))
      if (!res.ok) throw new Error('Failed to fetch courses')
      return res.json()
    },
    enabled: !!org?.slug,
    staleTime: 60_000,
  })
  const recentCourses = coursesData?.slice(0, 8) || []

  // Lazy-load assignments only when the assignments hover menu is opened
  const [assignmentsFetched, setAssignmentsFetched] = useState(false)

  const fetchAssignments = () => {
    if (assignmentsFetched || !coursesData || !access_token) return
    setAssignmentsFetched(true)
    const coursesToFetch = coursesData.slice(0, 5)
    const promises = coursesToFetch.map((course: any) =>
      getAssignmentsFromACourse(course.course_uuid, access_token)
    )
    Promise.all(promises).then((results) => {
      const allAssignments: any[] = []
      results.forEach((res: any, index: number) => {
        if (res?.data) {
          res.data.forEach((assignment: any) => {
            allAssignments.push({
              ...assignment,
              courseName: coursesToFetch[index].name
            })
          })
        }
      })
      setRecentAssignments(allAssignments.slice(0, 8))
    }).catch(() => {})
  }

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('dash-menu-collapsed')
      if (saved !== null) {
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setIsCollapsed(saved === 'true')
      }
    }
  }, [])

  const toggleCollapse = () => {
    const newState = !isCollapsed
    setIsCollapsed(newState)
    localStorage.setItem('dash-menu-collapsed', String(newState))
  }


  async function logOutUI() {
    await signOut({ redirect: true, callbackUrl: getUriWithOrg(org.slug, '/login') })
  }


  const plan = usePlan()
  const mode = getDeploymentMode()
  // Only org managers (admins/superadmins) see billing surfaces — non-admins
  // shouldn't manage the plan/subscription.
  const { canManageOrg } = useAdminStatus()

  if (!org || !session) return null
  const planLabel =
    mode === 'ee' ? 'Enterprise Edition' :
    mode === 'oss' ? 'OSS' :
    plan  // SaaS: show actual plan name

  // Multi-org (SaaS) hub: the apex /home, /new, /billing routes only exist in
  // multi tenancy. The user's organizations (deduped) come from the session.
  const multiOrg = isMultiOrgModeEnabled()
  const myOrgs: any[] = (() => {
    const roles = session?.data?.roles || []
    const seen = new Set<number>()
    const orgs: any[] = []
    for (const r of roles) {
      const o = r?.org
      if (o && o.id != null && !seen.has(o.id)) { seen.add(o.id); orgs.push(o) }
    }
    return orgs
  })()
  const planPillColor =
    mode === 'ee' ? 'bg-amber-400/15 text-amber-300' :
    mode === 'oss' ? 'bg-green-400/15 text-green-300' :
    plan === 'enterprise' ? 'bg-amber-400/15 text-amber-300' :
    plan === 'pro' ? 'bg-purple-400/15 text-purple-300' :
    plan === 'standard' ? 'bg-blue-400/15 text-blue-300' :
    'bg-white/[0.08] text-white/50'

  // Feature visibility from API resolved_features
  const rf = org?.config?.config?.resolved_features
  const isEnabled = (feature: string) => rf?.[feature]?.enabled === true

  const showLibrary = isEnabled('folders')
  const showCommunities = isEnabled('communities')
  const showPodcasts = isEnabled('podcasts')
  const showBoards = isEnabled('boards')
  const showPlaygrounds = isEnabled('playgrounds')
  // School (SMS) modules attach here exactly like Learnhouse's own: one
  // resolved_features flag per module, already served by the backend's
  // resolve_all_features(). Disabling a module in org settings removes it
  // from the nav entirely rather than showing it disabled, matching how
  // boards/podcasts/playgrounds behave above.
  // School modules are gated on TWO things: the org's feature toggle (does
  // this deployment run the module at all) AND the viewer's school role (is
  // this their job). A teacher with sms_hr_payroll enabled org-wide still has
  // no business seeing salaries, so the feature flag alone is not enough.
  // Roles come from GET /sms/me, the same server-side resolution the backend
  // authorizes requests with -- this hides the nav entry, it does not replace
  // that check.
  const { session: schoolSession } = useSchoolSession()
  const schoolRoles = schoolSession?.roles ?? []
  const isSuper = schoolRoles.includes('SUPER_ADMIN')
  const isSchoolAdmin = isSuper || schoolRoles.includes('SCHOOL_ADMIN')
  const isTeacher = schoolRoles.includes('TEACHER')
  const isSchoolStaff = schoolRoles.includes('STAFF')
  // Learnhouse org admins who hold no school role keep full visibility --
  // otherwise setting up the school would be impossible, since granting the
  // first SMS role requires reaching these screens.
  const noSchoolRole = schoolRoles.length === 0
  const canAdminister = isSchoolAdmin || noSchoolRole
  const canTeach = canAdminister || isTeacher
  const canBackOffice = canAdminister || isSchoolStaff

  const showAttendance = isEnabled('sms_attendance') && canTeach
  const showGradebook = isEnabled('sms_gradebook') && canTeach
  const showExams = isEnabled('sms_exam') && canTeach
  const showTimetable = isEnabled('sms_timetable') && canTeach
  const showFees = isEnabled('sms_fees') && canBackOffice
  const showFinancials = isEnabled('sms_financials') && canBackOffice
  const showHr = isEnabled('sms_hr_payroll') && canAdminister
  // Named school-library, not library: Learnhouse already owns /dash/library
  // (its own content/folder library). Two different things, two routes.
  const showSchoolLibrary = isEnabled('sms_library') && canBackOffice
  // Gated on tutor_counseling, the flag that actually exists -- there is no
  // `tutor_socratic` in resolve.py despite the name appearing in planning
  // docs. Oversight is a teacher's job, hence canTeach rather than admin-only.
  const showAiTutor = isEnabled('tutor_counseling') && canTeach
  const showRevOpsInsights = isEnabled('revops') && canAdminister
  // Messaging/notifications have no feature flag, deliberately: they reach
  // every role including parents and students, so they are structural like
  // Campus rather than admin-only like Payroll. Visible to anyone holding a
  // school role (and to org admins, who need it to set the school up).
  const showMessages = schoolRoles.length > 0 || noSchoolRole
  const SCHOOL_GROUP_HEADING =
    'px-3 pb-1 pt-4 text-[10px] font-semibold uppercase tracking-wider text-white/40'
  const showAdmissions = isEnabled('revops') && canAdminister
  // Campus is the school's structural root (campuses -> years -> terms ->
  // sections). Nothing else in the school system works until one exists, so
  // it is deliberately always on rather than behind a toggle, mirroring how
  // Learnhouse hardcodes courses/usergroups as always-on features.
  // Cross-module reporting: office data (fees and admissions sit next to
  // academics), so administer-gated like the rest of this group.
  const showReports = isEnabled('sms_reports') && canAdminister
  // School settings carries NO feature flag on purpose: it is where module
  // toggles are administered, so gating it behind one would let a school
  // switch off the page that switches things back on.
  const showSchoolSettings = canAdminister
  const showRoles = canAdminister
  const showFacilities = canAdminister
  const showAlumni = canAdminister
  const showLiveClasses = canTeach
  const showPathways = canTeach
  const showGamification = canTeach
  const showCertificates = canTeach
  const showDiscipline = canTeach
  // Counselling is PSYCHOLOGIST-or-leadership, deliberately NOT `teach`:
  // a teacher must not learn that a child is seeing a counsellor.
  const showCounseling = isEnabled('tutor_counseling') && (canAdminister || schoolRoles.includes('PSYCHOLOGIST'))
  const showCampus = canAdminister && (isEnabled('sms_attendance') || isEnabled('sms_gradebook') || isEnabled('sms_timetable'))
  const showPayments = isEnabled('payments')

  return (
    <TooltipProvider delayDuration={0}>
    <nav
      aria-label={t('dashboard.nav.sidebar_navigation')}
      className={cn(
        "flex flex-col text-white h-screen sticky top-0 z-overlay border-e border-white/[0.08] bg-[#0f0f10] transition-all duration-300",
        isCollapsed ? "w-[72px]" : "w-64"
      )}
    >
      {/* Header with Logo and Toggle */}
      <div className={cn(
        "relative flex items-center h-16 border-b border-white/[0.08] px-4 shrink-0",
        isCollapsed ? "justify-center" : "justify-between"
      )}>
        <Link
          className={cn("flex items-center transition-opacity hover:opacity-70", isCollapsed ? "" : "space-x-3")}
          href={'/'}
        >
          {planMeetsRequirement(plan, 'standard') && hasOrgLogo(org) ? (
            <div className="h-9 w-9 rounded-lg overflow-hidden bg-white shrink-0">
              <OrgSquareLogo org={org} wideInsetClassName="p-1" fallback={null} />
            </div>
          ) : (
            <img
              src="/lrn-dash.svg"
              alt="Learnhouse logo"
              className="h-8 w-8"
            />
          )}
          {!isCollapsed && (
            <div className="flex flex-col min-w-0">
              <span className="font-semibold text-sm text-white truncate">
                {org?.name}
              </span>
              <span className={cn(
                "mt-0.5 inline-flex w-fit items-center px-1.5 py-0.5 rounded-md text-[9px] font-bold uppercase tracking-wider",
                planPillColor
              )}>
                {planLabel}
              </span>
            </div>
          )}
        </Link>

        {!isCollapsed && (
          <button
            aria-label={t('dashboard.nav.collapse_sidebar')}
            onClick={toggleCollapse}
            className="p-2 rounded-lg text-white/40 hover:text-white hover:bg-white/[0.08] transition-all"
          >
            <SidebarSimple size={18} weight="fill" />
          </button>
        )}

        {/* Onboarding progress reuses this header's bottom border as its track —
            a neon purple gradient that glows out from the border. */}
        {showOnboarding && (
          <>
            {/* faint full-width track so the border reads as purple even at 0% */}
            <div className="absolute -bottom-px start-0 end-0 h-[2px] bg-indigo-500/15" />
            <motion.div
              className="absolute -bottom-px start-0 h-[2px] rounded-e-full"
              style={{
                background: 'linear-gradient(90deg, #6366f1 0%, #8b5cf6 55%, #a855f7 100%)',
                boxShadow:
                  '0 0 6px rgba(139,92,246,0.85), 0 0 14px rgba(168,85,247,0.55), 0 0 2px rgba(99,102,241,0.9)',
              }}
              initial={false}
              animate={{ width: `${Math.max(onboarding.progress * 100, 6)}%` }}
              transition={{ duration: 0.5, ease: 'easeOut' }}
            />
          </>
        )}
      </div>

      {/* Search trigger — replaced by the onboarding progress in this slot until
          setup is complete (then the search box returns). */}
      <div className={cn('px-3', showOnboarding ? 'pt-2' : 'pt-3')}>
        {showOnboarding ? (
          <OnboardingSidebarBox />
        ) : (
          <CommandPaletteTrigger isCollapsed={isCollapsed} />
        )}
      </div>

      {/* Main Navigation - Vertically Centered */}
      {/* Scrolls internally rather than centering. `justify-center` overflows
          in BOTH directions once the list is taller than the viewport, which
          put the top items out of reach and read as the sidebar vanishing on
          scroll -- the school modules made the menu long enough to hit it.
          `min-h-0` is required: a flex child defaults to min-height:auto and
          would otherwise refuse to shrink, so overflow-y-auto never engages. */}
      <div className="flex-1 min-h-0 overflow-y-auto py-4 px-3 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
        <AdminAuthorization authorizationMode="component">
          <div className="space-y-1">
            <MenuLink
              href="/dash"
              icon={<House size={20} weight="fill" />}
              label={t('common.home')}
              isCollapsed={isCollapsed}
              active={isActivePath('/dash')}
              onClick={() => track(AnalyticsEvent.DashboardNavClicked, { section: 'home' })}
            />

            {/* Courses with hover menu */}
            <HoverMenu
              content={
                <HoverMenuContent className="w-64">
                  <HoverMenuLabel className="text-white/70 font-medium">{t('courses.courses')}</HoverMenuLabel>
                  <HoverMenuSeparator />
                  <HoverMenuItem asChild>
                    <Link href="/dash/courses" className="flex items-center gap-2 px-3 py-2 text-sm text-white/70 hover:text-white hover:bg-white/[0.08] cursor-pointer transition-colors">
                      <BookOpen size={16} weight="fill" />
                      <span>{t('common.all_courses')}</span>
                    </Link>
                  </HoverMenuItem>
                  {recentCourses.length > 0 && (
                    <>
                      <HoverMenuSeparator />
                      <HoverMenuLabel className="text-white/40">{t('common.recent')}</HoverMenuLabel>
                      {recentCourses.map((course: any) => (
                        <HoverMenuItem key={course.course_uuid} asChild>
                          <Link
                            href={`/dash/courses/course/${course.course_uuid.replace('course_', '')}/settings`}
                            className="flex items-center gap-2 px-3 py-2 text-sm text-white/70 hover:text-white hover:bg-white/[0.08] cursor-pointer transition-colors"
                          >
                            <PencilSimple size={14} className="text-white/40" />
                            <span className="truncate">{course.name}</span>
                          </Link>
                        </HoverMenuItem>
                      ))}
                    </>
                  )}
                </HoverMenuContent>
              }
            >
              {(() => {
                const active = isActivePath('/dash/courses')
                return (
                  <Link
                    href="/dash/courses"
                    aria-label={t('dashboard.nav.open_courses_menu')}
                    aria-current={active ? 'page' : undefined}
                    className={cn(
                      "relative flex items-center w-full rounded-lg transition-all",
                      active
                        ? "text-white bg-white/[0.08]"
                        : "text-white/50 hover:text-white hover:bg-white/[0.08]",
                      isCollapsed ? "justify-center h-10" : "px-3 py-2 gap-3"
                    )}
                  >
                    {active && (
                      <span
                        aria-hidden="true"
                        className="absolute start-0.5 top-1/2 -translate-y-1/2 h-5 w-[3px] bg-white rounded-full"
                      />
                    )}
                    <span className="relative flex items-center justify-center">
                      <BookOpen size={20} weight="fill" />
                      {isCollapsed && (
                        <CaretDown aria-hidden="true" size={8} weight="bold" className={cn("absolute -end-2.5", active ? "text-white/60" : "text-white/30")} />
                      )}
                    </span>
                    {!isCollapsed && (
                      <>
                        <span className="text-sm font-medium flex-1 text-start">{t('courses.courses')}</span>
                        <CaretDown aria-hidden="true" size={14} weight="bold" className={active ? "text-white/70" : "text-white/40"} />
                      </>
                    )}
                  </Link>
                )
              })()}
            </HoverMenu>

            {/* Assignments with hover menu */}
            <div onMouseEnter={fetchAssignments}>
            <HoverMenu
              content={
                <HoverMenuContent className="w-72">
                  <HoverMenuLabel className="text-white/70 font-medium">{t('common.assignments')}</HoverMenuLabel>
                  <HoverMenuSeparator />
                  <HoverMenuItem asChild>
                    <Link href="/dash/assignments" className="flex items-center gap-2 px-3 py-2 text-sm text-white/70 hover:text-white hover:bg-white/[0.08] cursor-pointer transition-colors">
                      <Files size={16} weight="fill" />
                      <span>{t('common.all_assignments')}</span>
                    </Link>
                  </HoverMenuItem>
                  {recentAssignments.length > 0 && (
                    <>
                      <HoverMenuSeparator />
                      <HoverMenuLabel className="text-white/40">{t('common.recent')}</HoverMenuLabel>
                      {recentAssignments.map((assignment: any) => (
                        <HoverMenuItem key={assignment.assignment_uuid} asChild>
                          <Link
                            href={`/dash/assignments/${assignment.assignment_uuid.replace('assignment_', '')}?subpage=editor`}
                            className="flex items-center gap-2 px-3 py-2 text-sm text-white/70 hover:text-white hover:bg-white/[0.08] cursor-pointer transition-colors"
                          >
                            <PencilSimple size={14} className="text-white/40" />
                            <div className="flex flex-col min-w-0">
                              <span className="truncate">{assignment.title}</span>
                              <span className="text-xs text-white/30 truncate">{assignment.courseName}</span>
                            </div>
                          </Link>
                        </HoverMenuItem>
                      ))}
                    </>
                  )}
                </HoverMenuContent>
              }
            >
              {(() => {
                const active = isActivePath('/dash/assignments')
                return (
                  <Link
                    href="/dash/assignments"
                    aria-label={t('dashboard.nav.open_assignments_menu')}
                    aria-current={active ? 'page' : undefined}
                    className={cn(
                      "relative flex items-center w-full rounded-lg transition-all",
                      active
                        ? "text-white bg-white/[0.08]"
                        : "text-white/50 hover:text-white hover:bg-white/[0.08]",
                      isCollapsed ? "justify-center h-10" : "px-3 py-2 gap-3"
                    )}
                  >
                    {active && (
                      <span
                        aria-hidden="true"
                        className="absolute start-0.5 top-1/2 -translate-y-1/2 h-5 w-[3px] bg-white rounded-full"
                      />
                    )}
                    <span className="relative flex items-center justify-center">
                      <Files size={20} weight="fill" />
                      {isCollapsed && (
                        <CaretDown aria-hidden="true" size={8} weight="bold" className={cn("absolute -end-2.5", active ? "text-white/60" : "text-white/30")} />
                      )}
                    </span>
                    {!isCollapsed && (
                      <>
                        <span className="text-sm font-medium flex-1 text-start">{t('common.assignments')}</span>
                        <CaretDown aria-hidden="true" size={14} weight="bold" className={active ? "text-white/70" : "text-white/40"} />
                      </>
                    )}
                  </Link>
                )
              })()}
            </HoverMenu>
            </div>
            {showLibrary && (
              <MenuLink
                href="/dash/library"
                icon={<FolderSimple size={20} weight="fill" />}
                label={t('library.library')}
                isCollapsed={isCollapsed}
                active={isActivePath('/dash/library')}
              />
            )}
            {showCommunities && (
              <MenuLink
                href="/dash/communities"
                icon={<ChatsCircle size={20} weight="fill" />}
                label={t('communities.title')}
                isCollapsed={isCollapsed}
                active={isActivePath('/dash/communities')}
              />
            )}
            {showPodcasts && (
              <MenuLink
                href="/dash/podcasts"
                icon={<Headphones size={20} weight="fill" />}
                label={t('podcasts.podcasts')}
                isCollapsed={isCollapsed}
                active={isActivePath('/dash/podcasts')}
              />
            )}
            {showBoards && (
              <MenuLink
                href="/dash/boards"
                icon={<ChalkboardSimple size={20} weight="fill" />}
                label={t('boards.boards')}
                isCollapsed={isCollapsed}
                active={isActivePath('/dash/boards')}
              />
            )}
            {showPlaygrounds && (
              <MenuLink
                href="/dash/playgrounds"
                icon={<Cube size={20} weight="fill" />}
                label={t('common.playgrounds')}
                isCollapsed={isCollapsed}
                active={isActivePath('/dash/playgrounds')}
              />
            )}
            {/* School (SMS) modules, grouped under a heading so they read as
                one system rather than nine loose entries beside Learnhouse's
                own. Each is gated on its resolved_features flag AND the
                viewer's school role. Ordered to follow the school day: set up
                the campus, admit students, run the timetable, take
                attendance, mark work, then the back office. The heading is
                suppressed when collapsed (icons only) and when the viewer can
                see none of them. */}
            {/* Grouped into the four jobs a school actually has, rather than
                one flat list of thirteen: set the school up, teach, handle
                money, and the rest. Each heading hides when the viewer can
                see nothing under it (role-gated) and when collapsed to icons. */}
            {(showSchoolSettings || showRoles || showReports || showCampus || showFacilities || showAdmissions || showAlumni || showRevOpsInsights) && !isCollapsed && (
              <div className={SCHOOL_GROUP_HEADING}>School setup</div>
            )}
            {showSchoolSettings && (
              <MenuLink
                href="/dash/school-settings"
                icon={<Gear size={20} weight="fill" />}
                label="School settings"
                isCollapsed={isCollapsed}
                active={isActivePath('/dash/school-settings')}
              />
            )}
            {showRoles && (
              <MenuLink
                href="/dash/school-settings/roles"
                icon={<ShieldCheck size={20} weight="fill" />}
                label="Roles &amp; Permissions"
                isCollapsed={isCollapsed}
                active={isActivePath('/dash/school-settings/roles')}
              />
            )}
            {showCampus && (
              <MenuLink
                href="/dash/campus"
                icon={<Buildings size={20} weight="fill" />}
                label="Campus"
                isCollapsed={isCollapsed}
                active={isActivePath('/dash/campus')}
              />
            )}
            {showFacilities && (
              <MenuLink
                href="/dash/facilities"
                icon={<Warehouse size={20} weight="fill" />}
                label="Facilities"
                isCollapsed={isCollapsed}
                active={isActivePath('/dash/facilities')}
              />
            )}
            {showAdmissions && (
              <MenuLink
                href="/dash/admissions"
                icon={<UserPlus size={20} weight="fill" />}
                label="Admissions"
                isCollapsed={isCollapsed}
                active={isActivePath('/dash/admissions')}
              />
            )}
            {showAlumni && (
              <MenuLink
                href="/dash/alumni"
                icon={<Student size={20} weight="fill" />}
                label="Alumni"
                isCollapsed={isCollapsed}
                active={isActivePath('/dash/alumni')}
              />
            )}
            {showRevOpsInsights && (
              <MenuLink
                href="/dash/revops"
                icon={<ChartLineUp size={20} weight="fill" />}
                label="Admissions Insights"
                isCollapsed={isCollapsed}
                active={isActivePath('/dash/revops')}
              />
            )}
            {showReports && (
              <MenuLink
                href="/dash/reports"
                icon={<ChartBar size={20} weight="fill" />}
                label="Reports"
                isCollapsed={isCollapsed}
                active={isActivePath('/dash/reports')}
              />
            )}
            {/* showCounseling belongs here: its entries render inside this
                group, but it was missing from the condition -- so a
                PSYCHOLOGIST holding no teaching role saw Counselling floating
                under no heading at all. */}
            {(showTimetable ||
              showAttendance ||
              showGradebook ||
              showExams ||
              showLiveClasses ||
              showPathways ||
              showGamification ||
              showCertificates ||
              showAiTutor ||
              showCounseling ||
              showDiscipline) &&
              !isCollapsed && <div className={SCHOOL_GROUP_HEADING}>Teaching</div>}
            {showTimetable && (
              <MenuLink
                href="/dash/timetable"
                icon={<CalendarBlank size={20} weight="fill" />}
                label="Timetable"
                isCollapsed={isCollapsed}
                active={isActivePath('/dash/timetable')}
              />
            )}
            {showAttendance && (
              <MenuLink
                href="/dash/attendance"
                icon={<CalendarCheck size={20} weight="fill" />}
                label="Attendance"
                isCollapsed={isCollapsed}
                active={isActivePath('/dash/attendance')}
              />
            )}
            {showGradebook && (
              <MenuLink
                href="/dash/gradebook"
                icon={<GraduationCap size={20} weight="fill" />}
                label="Gradebook"
                isCollapsed={isCollapsed}
                active={isActivePath('/dash/gradebook')}
              />
            )}
            {showExams && (
              <MenuLink
                href="/dash/exams"
                icon={<Exam size={20} weight="fill" />}
                label="Exams"
                isCollapsed={isCollapsed}
                active={isActivePath('/dash/exams')}
              />
            )}
            {showLiveClasses && (
              <MenuLink
                href="/dash/live-classes"
                icon={<VideoCamera size={20} weight="fill" />}
                label="Live Classes"
                isCollapsed={isCollapsed}
                active={isActivePath('/dash/live-classes')}
              />
            )}
            {showPathways && (
              <MenuLink
                href="/dash/pathways"
                icon={<Compass size={20} weight="fill" />}
                label="Pathways"
                isCollapsed={isCollapsed}
                active={isActivePath('/dash/pathways')}
              />
            )}
            {showGamification && (
              <MenuLink
                href="/dash/gamification"
                icon={<Trophy size={20} weight="fill" />}
                label="Gamification"
                isCollapsed={isCollapsed}
                active={isActivePath('/dash/gamification')}
              />
            )}
            {showCertificates && (
              <MenuLink
                href="/dash/certificates-manager"
                icon={<SealCheck size={20} weight="fill" />}
                label="Certificates"
                isCollapsed={isCollapsed}
                active={isActivePath('/dash/certificates-manager')}
              />
            )}
            {showAiTutor && (
              <MenuLink
                href="/dash/ai-tutor"
                icon={<Robot size={20} weight="fill" />}
                label="AI Tutor"
                isCollapsed={isCollapsed}
                active={isActivePath('/dash/ai-tutor')}
              />
            )}
            {showCounseling && (
              <MenuLink
                href="/dash/counseling"
                icon={<Heartbeat size={20} weight="fill" />}
                label="Counselling"
                isCollapsed={isCollapsed}
                active={isActivePath('/dash/counseling')}
              />
            )}
            {showDiscipline && (
              <MenuLink
                href="/dash/discipline"
                icon={<Scales size={20} weight="fill" />}
                label="Discipline"
                isCollapsed={isCollapsed}
                active={isActivePath('/dash/discipline')}
              />
            )}
            {(showFees || showFinancials || showHr) && !isCollapsed && (
              <div className={SCHOOL_GROUP_HEADING}>Finance &amp; staff</div>
            )}
            {showFees && (
              <MenuLink
                href="/dash/fees"
                icon={<Receipt size={20} weight="fill" />}
                label="Fees"
                isCollapsed={isCollapsed}
                active={isActivePath('/dash/fees')}
              />
            )}
            {showFinancials && (
              <MenuLink
                href="/dash/financials"
                icon={<Bank size={20} weight="fill" />}
                label="Financials"
                isCollapsed={isCollapsed}
                active={isActivePath('/dash/financials')}
              />
            )}
            {showHr && (
              <MenuLink
                href="/dash/hr"
                icon={<IdentificationBadge size={20} weight="fill" />}
                label="Staff & Payroll"
                isCollapsed={isCollapsed}
                active={isActivePath('/dash/hr')}
              />
            )}
            {(showSchoolLibrary || showMessages) && !isCollapsed && (
              <div className={SCHOOL_GROUP_HEADING}>Resources</div>
            )}
            {showSchoolLibrary && (
              <MenuLink
                href="/dash/school-library"
                icon={<Books size={20} weight="fill" />}
                label="School Library"
                isCollapsed={isCollapsed}
                active={isActivePath('/dash/school-library')}
              />
            )}
            {showMessages && (
              <MenuLink
                href="/dash/messages"
                icon={<ChatCircle size={20} weight="fill" />}
                label="Messages"
                isCollapsed={isCollapsed}
                active={isActivePath('/dash/messages')}
              />
            )}
            {/* Users with hover menu */}
            <HoverMenu
              content={
                <HoverMenuContent className="w-64">
                  <HoverMenuLabel className="text-white/70 font-medium">{t('common.users')}</HoverMenuLabel>
                  <HoverMenuSeparator />
                  <HoverMenuItem asChild>
                    <Link href="/dash/users/settings/users" className="flex items-center gap-2 px-3 py-2 text-sm text-white/70 hover:text-white hover:bg-white/[0.08] cursor-pointer transition-colors">
                      <Users size={16} weight="fill" />
                      <span>{t('dashboard.users.settings.tabs.users')}</span>
                    </Link>
                  </HoverMenuItem>
                  <HoverMenuItem asChild>
                    <Link href="/dash/users/settings/usergroups" className="flex items-center gap-2 px-3 py-2 text-sm text-white/70 hover:text-white hover:bg-white/[0.08] cursor-pointer transition-colors">
                      <UsersThree size={16} weight="fill" />
                      <span className="flex items-center">{t('dashboard.users.settings.tabs.usergroups')}<PlanBadge currentPlan={plan} requiredPlan="standard" variant="dark" /></span>
                    </Link>
                  </HoverMenuItem>
                  <HoverMenuItem asChild>
                    <Link href="/dash/users/settings/roles" className="flex items-center gap-2 px-3 py-2 text-sm text-white/70 hover:text-white hover:bg-white/[0.08] cursor-pointer transition-colors">
                      <Shield size={16} weight="fill" />
                      <span className="flex items-center">{t('dashboard.users.settings.tabs.roles')}<PlanBadge currentPlan={plan} requiredPlan="pro" variant="dark" /></span>
                    </Link>
                  </HoverMenuItem>
                  <HoverMenuItem asChild>
                    <Link href="/dash/users/settings/signups" className="flex items-center gap-2 px-3 py-2 text-sm text-white/70 hover:text-white hover:bg-white/[0.08] cursor-pointer transition-colors">
                      <ClipboardText size={16} weight="fill" />
                      <span>{t('dashboard.users.settings.tabs.signups')}</span>
                    </Link>
                  </HoverMenuItem>
                  <HoverMenuItem asChild>
                    <Link href="/dash/users/settings/add" className="flex items-center gap-2 px-3 py-2 text-sm text-white/70 hover:text-white hover:bg-white/[0.08] cursor-pointer transition-colors">
                      <UserPlus size={16} weight="fill" />
                      <span>{t('dashboard.users.settings.tabs.add')}</span>
                    </Link>
                  </HoverMenuItem>
                </HoverMenuContent>
              }
            >
              {(() => {
                const active = isActivePath('/dash/users')
                return (
                  <Link
                    href="/dash/users/settings/users"
                    aria-label={t('dashboard.nav.open_users_menu')}
                    aria-current={active ? 'page' : undefined}
                    className={cn(
                      "relative flex items-center w-full rounded-lg transition-all",
                      active
                        ? "text-white bg-white/[0.08]"
                        : "text-white/50 hover:text-white hover:bg-white/[0.08]",
                      isCollapsed ? "justify-center h-10" : "px-3 py-2 gap-3"
                    )}
                  >
                    {active && (
                      <span
                        aria-hidden="true"
                        className="absolute start-0.5 top-1/2 -translate-y-1/2 h-5 w-[3px] bg-white rounded-full"
                      />
                    )}
                    <span className="relative flex items-center justify-center">
                      <Users size={20} weight="fill" />
                      {isCollapsed && (
                        <CaretDown aria-hidden="true" size={8} weight="bold" className={cn("absolute -end-2.5", active ? "text-white/60" : "text-white/30")} />
                      )}
                    </span>
                    {!isCollapsed && (
                      <>
                        <span className="text-sm font-medium flex-1 text-start">{t('common.users')}</span>
                        <CaretDown aria-hidden="true" size={14} weight="bold" className={active ? "text-white/70" : "text-white/40"} />
                      </>
                    )}
                  </Link>
                )
              })()}
            </HoverMenu>

            {showPayments && (
              <MenuLink
                href="/dash/payments/overview"
                icon={<CurrencyCircleDollar size={20} weight="fill" />}
                label={t('common.payments')}
                isCollapsed={isCollapsed}
                active={isActivePath('/dash/payments')}
              />
            )}

            {/* Organization with hover menu */}
            <HoverMenu
              content={
                <HoverMenuContent className="w-64">
                  <HoverMenuLabel className="text-white/70 font-medium">{t('common.organization')}</HoverMenuLabel>
                  <HoverMenuSeparator />
                  <HoverMenuItem asChild>
                    <Link href="/dash/org/settings/general" className="flex items-center gap-2 px-3 py-2 text-sm text-white/70 hover:text-white hover:bg-white/[0.08] cursor-pointer transition-colors">
                      <Gear size={16} weight="fill" />
                      <span>{t('dashboard.organization.settings.tabs.general')}</span>
                    </Link>
                  </HoverMenuItem>
                  <HoverMenuItem asChild>
                    <Link href="/dash/org/settings/branding" className="flex items-center gap-2 px-3 py-2 text-sm text-white/70 hover:text-white hover:bg-white/[0.08] cursor-pointer transition-colors">
                      <Palette size={16} weight="fill" />
                      <span>{t('dashboard.organization.settings.tabs.branding')}</span>
                    </Link>
                  </HoverMenuItem>
                  <HoverMenuItem asChild>
                    <Link href="/dash/org/settings/landing" className="flex items-center gap-2 px-3 py-2 text-sm text-white/70 hover:text-white hover:bg-white/[0.08] cursor-pointer transition-colors">
                      <Rocket size={16} weight="fill" />
                      <span>{t('dashboard.organization.settings.tabs.landing')}</span>
                    </Link>
                  </HoverMenuItem>
                  <HoverMenuItem asChild>
                    <Link href="/dash/org/settings/ai" className="flex items-center gap-2 px-3 py-2 text-sm text-white/70 hover:text-white hover:bg-white/[0.08] cursor-pointer transition-colors">
                      <Robot size={16} weight="fill" />
                      <span className="flex items-center">{t('dashboard.organization.settings.tabs.ai')}<PlanBadge currentPlan={plan} requiredPlan="standard" variant="dark" /></span>
                    </Link>
                  </HoverMenuItem>
                  {canManageOrg && (
                    <HoverMenuItem asChild>
                      <Link href="/dash/org/settings/usage" className="flex items-center gap-2 px-3 py-2 text-sm text-white/70 hover:text-white hover:bg-white/[0.08] cursor-pointer transition-colors">
                        <ChartBar size={16} weight="fill" />
                        <span>{t('dashboard.organization.settings.tabs.usage') || 'Usage'}</span>
                      </Link>
                    </HoverMenuItem>
                  )}
                  <HoverMenuItem asChild>
                    <Link href="/dash/org/settings/other" className="flex items-center gap-2 px-3 py-2 text-sm text-white/70 hover:text-white hover:bg-white/[0.08] cursor-pointer transition-colors">
                      <Wrench size={16} weight="fill" />
                      <span>{t('dashboard.organization.settings.tabs.other')}</span>
                    </Link>
                  </HoverMenuItem>
                </HoverMenuContent>
              }
            >
              {(() => {
                const active = isActivePath('/dash/org')
                return (
                  <Link
                    href="/dash/org/settings/general"
                    aria-label={t('dashboard.nav.open_organization_menu')}
                    aria-current={active ? 'page' : undefined}
                    className={cn(
                      "relative flex items-center w-full rounded-lg transition-all",
                      active
                        ? "text-white bg-white/[0.08]"
                        : "text-white/50 hover:text-white hover:bg-white/[0.08]",
                      isCollapsed ? "justify-center h-10" : "px-3 py-2 gap-3"
                    )}
                  >
                    {active && (
                      <span
                        aria-hidden="true"
                        className="absolute start-0.5 top-1/2 -translate-y-1/2 h-5 w-[3px] bg-white rounded-full"
                      />
                    )}
                    <span className="relative flex items-center justify-center">
                      <Buildings size={20} weight="fill" />
                      {isCollapsed && (
                        <CaretDown aria-hidden="true" size={8} weight="bold" className={cn("absolute -end-2.5", active ? "text-white/60" : "text-white/30")} />
                      )}
                    </span>
                    {!isCollapsed && (
                      <>
                        <span className="text-sm font-medium flex-1 text-start">{t('common.organization')}</span>
                        <CaretDown aria-hidden="true" size={14} weight="bold" className={active ? "text-white/70" : "text-white/40"} />
                      </>
                    )}
                  </Link>
                )
              })()}
            </HoverMenu>

            {/* Developers with hover menu */}
            <HoverMenu
              content={
                <HoverMenuContent className="w-64">
                  <HoverMenuLabel className="text-white/70 font-medium">{t('dashboard.developers.breadcrumb', { defaultValue: 'Developers' })}</HoverMenuLabel>
                  <HoverMenuSeparator />
                  <HoverMenuItem asChild>
                    <Link href="/dash/developers/api" className="flex items-center gap-2 px-3 py-2 text-sm text-white/70 hover:text-white hover:bg-white/[0.08] cursor-pointer transition-colors">
                      <Key size={16} weight="fill" />
                      <span className="flex items-center">{t('dashboard.organization.settings.tabs.api', { defaultValue: 'API Access' })}<PlanBadge currentPlan={plan} requiredPlan="pro" variant="dark" /></span>
                    </Link>
                  </HoverMenuItem>
                  <HoverMenuItem asChild>
                    <Link href="/dash/developers/automations" className="flex items-center gap-2 px-3 py-2 text-sm text-white/70 hover:text-white hover:bg-white/[0.08] cursor-pointer transition-colors">
                      <Lightning size={16} weight="fill" />
                      <span className="flex items-center">{t('dashboard.organization.settings.tabs.automations', { defaultValue: 'Automations' })}<PlanBadge currentPlan={plan} requiredPlan="pro" variant="dark" /></span>
                    </Link>
                  </HoverMenuItem>
                  <HoverMenuItem asChild>
                    <Link href="/dash/developers/domains" className="flex items-center gap-2 px-3 py-2 text-sm text-white/70 hover:text-white hover:bg-white/[0.08] cursor-pointer transition-colors">
                      <LinkSimple size={16} weight="fill" />
                      <span className="flex items-center">{t('dashboard.organization.settings.tabs.domains', { defaultValue: 'Domains' })}<PlanBadge currentPlan={plan} requiredPlan="standard" variant="dark" /></span>
                    </Link>
                  </HoverMenuItem>
                  <HoverMenuItem asChild>
                    <Link href="/dash/developers/seo" className="flex items-center gap-2 px-3 py-2 text-sm text-white/70 hover:text-white hover:bg-white/[0.08] cursor-pointer transition-colors">
                      <MagnifyingGlass size={16} weight="fill" />
                      <span>SEO</span>
                    </Link>
                  </HoverMenuItem>
                  <HoverMenuItem asChild>
                    <Link href="/dash/developers/sso" className="flex items-center gap-2 px-3 py-2 text-sm text-white/70 hover:text-white hover:bg-white/[0.08] cursor-pointer transition-colors">
                      <Lock size={16} weight="fill" />
                      <span className="flex items-center">{t('dashboard.organization.settings.tabs.sso', { defaultValue: 'SSO' })}<PlanBadge currentPlan={plan} requiredPlan="enterprise" variant="dark" /></span>
                    </Link>
                  </HoverMenuItem>
                </HoverMenuContent>
              }
            >
              {(() => {
                const active = isActivePath('/dash/developers')
                return (
                  <Link
                    href="/dash/developers/api"
                    aria-label={t('dashboard.nav.open_developers_menu')}
                    aria-current={active ? 'page' : undefined}
                    className={cn(
                      "relative flex items-center w-full rounded-lg transition-all",
                      active
                        ? "text-white bg-white/[0.08]"
                        : "text-white/50 hover:text-white hover:bg-white/[0.08]",
                      isCollapsed ? "justify-center h-10" : "px-3 py-2 gap-3"
                    )}
                  >
                    {active && (
                      <span
                        aria-hidden="true"
                        className="absolute start-0.5 top-1/2 -translate-y-1/2 h-5 w-[3px] bg-white rounded-full"
                      />
                    )}
                    <span className="relative flex items-center justify-center">
                      <Code size={20} weight="fill" />
                      {isCollapsed && (
                        <CaretDown aria-hidden="true" size={8} weight="bold" className={cn("absolute -end-2.5", active ? "text-white/60" : "text-white/30")} />
                      )}
                    </span>
                    {!isCollapsed && (
                      <>
                        <span className="text-sm font-medium flex-1 text-start">{t('dashboard.developers.breadcrumb', { defaultValue: 'Developers' })}</span>
                        <CaretDown aria-hidden="true" size={14} weight="bold" className={active ? "text-white/70" : "text-white/40"} />
                      </>
                    )}
                  </Link>
                )
              })()}
            </HoverMenu>

            {/* Analytics with hover menu */}
            <HoverMenu
              content={
                <HoverMenuContent className="w-64">
                  <HoverMenuLabel className="text-white/70 font-medium">Analytics</HoverMenuLabel>
                  <HoverMenuSeparator />
                  <HoverMenuItem asChild>
                    <Link href="/dash/analytics" className="flex items-center gap-2 px-3 py-2 text-sm text-white/70 hover:text-white hover:bg-white/[0.08] cursor-pointer transition-colors">
                      <ChartBar size={16} weight="fill" />
                      <span>{t('analytics.tabs.overview')}</span>
                    </Link>
                  </HoverMenuItem>
                  <HoverMenuItem asChild>
                    <Link href="/dash/analytics" className="flex items-center gap-2 px-3 py-2 text-sm text-white/70 hover:text-white hover:bg-white/[0.08] cursor-pointer transition-colors">
                      <ChartLine size={16} weight="fill" />
                      <span className="flex items-center">{t('analytics.tabs.advanced')}<PlanBadge currentPlan={plan} requiredPlan="enterprise" variant="dark" /></span>
                    </Link>
                  </HoverMenuItem>
                </HoverMenuContent>
              }
            >
              {(() => {
                const active = isActivePath('/dash/analytics')
                return (
                  <Link
                    href="/dash/analytics"
                    aria-label={t('common.analytics')}
                    aria-current={active ? 'page' : undefined}
                    className={cn(
                      "relative flex items-center w-full rounded-lg transition-all",
                      active
                        ? "text-white bg-white/[0.08]"
                        : "text-white/50 hover:text-white hover:bg-white/[0.08]",
                      isCollapsed ? "justify-center h-10" : "px-3 py-2 gap-3"
                    )}
                  >
                    {active && (
                      <span
                        aria-hidden="true"
                        className="absolute start-0.5 top-1/2 -translate-y-1/2 h-5 w-[3px] bg-white rounded-full"
                      />
                    )}
                    <span className="relative flex items-center justify-center">
                      <ChartBar size={20} weight="fill" />
                      {isCollapsed && (
                        <CaretDown aria-hidden="true" size={8} weight="bold" className={cn("absolute -end-2.5", active ? "text-white/60" : "text-white/30")} />
                      )}
                    </span>
                    {!isCollapsed && (
                      <>
                        <span className="text-sm font-medium flex-1 text-start">{t('common.analytics')}</span>
                        <CaretDown aria-hidden="true" size={14} weight="bold" className={active ? "text-white/70" : "text-white/40"} />
                      </>
                    )}
                  </Link>
                )
              })()}
            </HoverMenu>

            {/* Disabled features shown in an "Other" hover menu */}
            {(!showCommunities || !showPodcasts || !showBoards || !showPlaygrounds || !showPayments) && (
              <HoverMenu
                content={
                  <HoverMenuContent className="w-64">
                    <HoverMenuLabel className="flex items-center justify-between text-white/70 font-medium">
                      <span>{t('common.other')}</span>
                      <span className="text-[9px] font-medium uppercase tracking-wider px-1.5 py-0.5 rounded bg-white/[0.06] text-white/25">
                        {t('common.disabled')}
                      </span>
                    </HoverMenuLabel>
                    <HoverMenuSeparator />
                    {!showCommunities && (
                      <HoverMenuItem asChild>
                        <Link href="/dash/communities" className="flex items-center gap-2 px-3 py-2 text-sm text-white/30 hover:text-white/50 hover:bg-white/[0.05] cursor-pointer transition-colors">
                          <ChatsCircle size={16} weight="fill" />
                          <span>{t('communities.title')}</span>
                        </Link>
                      </HoverMenuItem>
                    )}
                    {!showPodcasts && (
                      <HoverMenuItem asChild>
                        <Link href="/dash/podcasts" className="flex items-center gap-2 px-3 py-2 text-sm text-white/30 hover:text-white/50 hover:bg-white/[0.05] cursor-pointer transition-colors">
                          <Headphones size={16} weight="fill" />
                          <span>{t('podcasts.podcasts')}</span>
                        </Link>
                      </HoverMenuItem>
                    )}
                    {!showBoards && (
                      <HoverMenuItem asChild>
                        <Link href="/dash/boards" className="flex items-center gap-2 px-3 py-2 text-sm text-white/30 hover:text-white/50 hover:bg-white/[0.05] cursor-pointer transition-colors">
                          <ChalkboardSimple size={16} weight="fill" />
                          <span>{t('common.boards')}</span>
                        </Link>
                      </HoverMenuItem>
                    )}
                    {!showPlaygrounds && (
                      <HoverMenuItem asChild>
                        <Link href="/dash/playgrounds" className="flex items-center gap-2 px-3 py-2 text-sm text-white/30 hover:text-white/50 hover:bg-white/[0.05] cursor-pointer transition-colors">
                          <Cube size={16} weight="fill" />
                          <span>{t('common.playgrounds')}</span>
                        </Link>
                      </HoverMenuItem>
                    )}
                    {!showPayments && (
                      <HoverMenuItem asChild>
                        <Link href="/dash/payments/overview" className="flex items-center gap-2 px-3 py-2 text-sm text-white/30 hover:text-white/50 hover:bg-white/[0.05] cursor-pointer transition-colors">
                          <CurrencyCircleDollar size={16} weight="fill" />
                          <span>{t('common.payments')}</span>
                        </Link>
                      </HoverMenuItem>
                    )}
                  </HoverMenuContent>
                }
              >
                <button
                  aria-label={t('dashboard.nav.other')}
                  className={cn(
                    "flex items-center w-full rounded-lg text-white/30 hover:text-white/50 hover:bg-white/[0.05] transition-all",
                    isCollapsed ? "justify-center h-10" : "px-3 py-2 gap-3"
                  )}
                >
                  <span className="relative flex items-center justify-center">
                    <DotsThree size={20} weight="bold" />
                    {isCollapsed && (
                      <CaretDown aria-hidden="true" size={8} weight="bold" className="absolute -end-2.5 text-white/20" />
                    )}
                  </span>
                  {!isCollapsed && (
                    <>
                      <span className="text-sm font-medium flex-1 text-start">{t('common.other')}</span>
                      <CaretDown aria-hidden="true" size={14} weight="bold" className="text-white/20" />
                    </>
                  )}
                </button>
              </HoverMenu>
            )}
          </div>
        </AdminAuthorization>
      </div>

      {/* Free-plan upgrade box — replaces the old full-width top banner.
          Sits in the sidebar's empty space; multi-org / SaaS, free plan only.
          Twinkling stars on top; on hover it reveals the premium features the
          org is missing, the gold glow swells and the button sweeps a shimmer. */}
      {multiOrg && plan === 'free' && !isCollapsed && canManageOrg && (
        <motion.div
          className="relative overflow-hidden shrink-0 px-4 pt-6 pb-4"
          onHoverStart={() => setUpgradeHovered(true)}
          onHoverEnd={() => setUpgradeHovered(false)}
        >
          {/* Blueprint grid — same motif as the login/home pages, fading in
              from the bottom. No card/border; it blends into the sidebar. */}
          <div
            className="absolute inset-0 pointer-events-none"
            style={{
              backgroundImage: `
                linear-gradient(rgba(255,255,255,0.05) 1px, transparent 1px),
                linear-gradient(90deg, rgba(255,255,255,0.05) 1px, transparent 1px),
                linear-gradient(rgba(255,255,255,0.025) 1px, transparent 1px),
                linear-gradient(90deg, rgba(255,255,255,0.025) 1px, transparent 1px)`,
              backgroundSize: '56px 56px, 56px 56px, 14px 14px, 14px 14px',
              maskImage: 'linear-gradient(to top, black 0%, transparent 80%)',
              WebkitMaskImage: 'linear-gradient(to top, black 0%, transparent 80%)',
            }}
          />
          {/* Gold glow rising from the bottom — swells on hover. */}
          <motion.div
            className="absolute inset-x-0 bottom-0 h-2/3 pointer-events-none"
            initial={false}
            animate={{ opacity: upgradeHovered ? 1 : 0.5 }}
            transition={{ duration: 0.45, ease: 'easeOut' }}
            style={{
              background:
                'radial-gradient(120% 90% at 50% 100%, rgba(250,204,21,0.12), rgba(255,255,255,0.05) 38%, transparent 72%)',
            }}
          />
          {/* Night-sky starfield — scattered points of light that twinkle and
              brighten on hover. The single amber "north star" is the plan you're
              reaching for; the white stars are the features it unlocks below. */}
          <div className="absolute inset-x-0 top-0 h-1/2 pointer-events-none">
            {UPGRADE_STARS.map((s, i) => (
              <motion.span
                key={i}
                className="absolute rounded-full"
                style={{
                  top: s.top,
                  left: s.left,
                  width: s.size,
                  height: s.size,
                  background: s.north ? 'rgb(252,211,77)' : 'rgba(255,255,255,0.95)',
                  boxShadow: s.north
                    ? '0 0 6px 1px rgba(250,204,21,0.7)'
                    : s.size >= 2
                      ? '0 0 4px 0.5px rgba(255,255,255,0.6)'
                      : 'none',
                }}
                animate={{
                  opacity: upgradeHovered ? [s.dim + 0.2, 1, s.dim + 0.2] : [s.dim, s.bright, s.dim],
                  scale: upgradeHovered ? [1, s.north ? 1.5 : 1.7, 1] : [1, 1.2, 1],
                }}
                transition={{
                  duration: (upgradeHovered ? 1.3 : 2.4) + s.size * 0.3,
                  repeat: Infinity,
                  delay: s.delay,
                  ease: 'easeInOut',
                }}
              />
            ))}
          </div>

          <motion.div layout className="relative">
            {/* Plan badge + CTA headline (replaces the plain "Free plan" title). */}
            <span className="inline-flex items-center px-1.5 py-0.5 rounded-md bg-white/10 text-white/55 text-[8px] font-bold uppercase tracking-wider">
              {t('plan.free_plan_title', { defaultValue: 'Free plan' })}
            </span>
            <p className="mt-2 text-[13px] font-bold text-white leading-tight">
              {t('plan.free_plan_cta', { defaultValue: 'Unlock the full platform' })}
            </p>

            {/* Stable one-line pitch — no layout shift on hover; hover only
                intensifies the gold glow / starfield / button halo. */}
            <p className="mt-1 text-[11px] leading-relaxed text-white/40">
              {t('plan.free_plan_desc', {
                defaultValue: 'Everything you need to teach, sell & grow.',
              })}
            </p>

            <motion.a
              href={getMainDomainUri(`/billing?org=${org?.slug ?? ''}`)}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              animate={{
                boxShadow: upgradeHovered
                  ? '0 0 0 1px rgba(250,204,21,0.5), 0 8px 24px -6px rgba(250,204,21,0.35)'
                  : '0 0 0 0 rgba(250,204,21,0)',
              }}
              transition={{ duration: 0.35 }}
              className="mt-3 relative overflow-hidden flex items-center justify-center gap-1.5 w-full rounded-lg bg-white text-[#0f0f10] text-[13px] font-semibold py-2"
            >
              <span className="relative z-10 flex items-center gap-1.5">
                <Rocket size={13} weight="duotone" />
                {t('plan.upgrade', { defaultValue: 'Upgrade' })}
              </span>
              {/* Diagonal shimmer sweep across the button. */}
              <motion.span
                aria-hidden
                className="absolute top-0 bottom-0 w-1/3 -skew-x-12 pointer-events-none"
                style={{
                  background:
                    'linear-gradient(90deg, transparent, rgba(0,0,0,0.07), transparent)',
                }}
                animate={{ left: ['-40%', '140%'] }}
                transition={{
                  duration: 1.5,
                  repeat: Infinity,
                  repeatDelay: upgradeHovered ? 0.4 : 2,
                  ease: 'easeInOut',
                }}
              />
            </motion.a>
          </motion.div>
        </motion.div>
      )}

      {/* Bottom Section */}
      <div className="border-t border-white/[0.08] py-3 px-3 shrink-0">
        <div className="space-y-1">
          {/* Expand button when collapsed */}
          {isCollapsed && (
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  aria-label={t('dashboard.nav.expand_sidebar')}
                  onClick={toggleCollapse}
                  className="flex items-center justify-center w-full h-10 rounded-lg text-white/40 hover:text-white hover:bg-white/[0.08] transition-all"
                >
                  <SidebarSimple size={20} weight="fill" />
                </button>
              </TooltipTrigger>
              <TooltipContent side="right" className="z-tooltip bg-[#1a1a1b] border-white/10 text-white text-xs px-2 py-1 shadow-lg shadow-black/20">
                {t('common.expand')}
              </TooltipContent>
            </Tooltip>
          )}

          {/* Language Switcher with hover menu */}
          <HoverMenu
            align="end"
            content={
              <HoverMenuContent className="w-64 max-h-96 overflow-y-auto [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
                <HoverMenuLabel className="flex items-center gap-2 text-white/70 font-medium">
                  <Globe size={16} weight="fill" />
                  <span>{t('common.language')}</span>
                </HoverMenuLabel>
                <HoverMenuSeparator />
                {AVAILABLE_LANGUAGES.map((language) => (
                  <HoverMenuItem
                    key={language.code}
                    onClick={() => changeLanguage(language.code)}
                    className="flex items-center justify-between px-3 py-2.5 cursor-pointer text-white/70 hover:text-white hover:bg-white/[0.08] transition-colors"
                  >
                    <div className="flex flex-col">
                      <span className="font-medium text-sm">{language.nativeName}</span>
                      <span className="text-xs text-white/40">{t(language.translationKey)}</span>
                    </div>
                    {i18n.language.split('-')[0] === language.code && (
                      <Check size={16} weight="bold" className="text-green-500" />
                    )}
                  </HoverMenuItem>
                ))}
              </HoverMenuContent>
            }
          >
            <button aria-label={t('dashboard.nav.open_language_menu')} className={cn(
              "flex items-center w-full rounded-lg text-white/50 hover:text-white hover:bg-white/[0.08] transition-all group",
              isCollapsed ? "justify-center h-10" : "px-3 py-2 gap-3"
            )}>
              <Globe size={20} weight="fill" />
              {!isCollapsed && (
                <span className="text-sm font-medium">{t('common.language')}</span>
              )}
            </button>
          </HoverMenu>

          {/* Help with hover menu */}
          <HoverMenu
            align="end"
            content={
              <HoverMenuContent className="w-56">
                <HoverMenuLabel className="flex items-center gap-2 text-white/70 font-medium">
                  <Question size={16} weight="fill" />
                  <span>{t('common.help')}</span>
                </HoverMenuLabel>
                <HoverMenuSeparator />
                <HoverMenuItem asChild>
                  <a
                    href="https://docs.learnhouse.app"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-2 px-3 py-2 text-sm text-white/70 hover:text-white hover:bg-white/[0.08] cursor-pointer transition-colors"
                  >
                    <Book size={16} weight="fill" />
                    <span>{t('common.help_menu.documentation')}</span>
                  </a>
                </HoverMenuItem>
                <HoverMenuItem asChild>
                  <a
                    href="https://learnhouse.app"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-2 px-3 py-2 text-sm text-white/70 hover:text-white hover:bg-white/[0.08] cursor-pointer transition-colors"
                  >
                    <Globe size={16} weight="fill" />
                    <span>{t('common.help_menu.website')}</span>
                  </a>
                </HoverMenuItem>
                <HoverMenuItem asChild>
                  <a
                    href="https://discord.gg/learnhouse"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-2 px-3 py-2 text-sm text-white/70 hover:text-white hover:bg-white/[0.08] cursor-pointer transition-colors"
                  >
                    <DiscordIcon size={16} />
                    <span>{t('common.help_menu.discord')}</span>
                  </a>
                </HoverMenuItem>
                <HoverMenuSeparator />
                <HoverMenuItem
                  onClick={() => setFeedbackModalOpen(true)}
                  className="flex items-center gap-2 px-3 py-2 text-sm text-white/70 hover:text-white hover:bg-white/[0.08] cursor-pointer transition-colors"
                >
                  <ChatCircleDots size={16} weight="fill" />
                  <span>{t('common.help_menu.report_feedback')}</span>
                </HoverMenuItem>
              </HoverMenuContent>
            }
          >
            <button aria-label={t('dashboard.nav.open_help_menu')} className={cn(
              "flex items-center w-full rounded-lg text-white/50 hover:text-white hover:bg-white/[0.08] transition-all group",
              isCollapsed ? "justify-center h-10" : "px-3 py-2 gap-3"
            )}>
              <Question size={20} weight="fill" />
              {!isCollapsed && (
                <span className="text-sm font-medium">{t('common.help')}</span>
              )}
            </button>
          </HoverMenu>

          {/* My Organizations with hover menu (multi-org / SaaS only) */}
          {multiOrg && (
            <HoverMenu
              align="end"
              content={
                <HoverMenuContent className="w-64 max-h-96 overflow-y-auto">
                  <HoverMenuLabel className="flex items-center gap-2 text-white/70 font-medium">
                    <Buildings size={16} weight="fill" />
                    <span>{t('common.organizations', { defaultValue: 'Organizations' })}</span>
                  </HoverMenuLabel>
                  <HoverMenuSeparator />
                  <HoverMenuItem asChild>
                    <a href={getMainDomainUri('/home')} className="flex items-center gap-2 px-3 py-2 text-sm text-white/70 hover:text-white hover:bg-white/[0.08] cursor-pointer transition-colors">
                      <House size={16} weight="fill" />
                      <span>{t('common.home', { defaultValue: 'Home' })}</span>
                    </a>
                  </HoverMenuItem>
                  {canManageOrg && (
                    <HoverMenuItem asChild>
                      <a href={getMainDomainUri(`/billing?org=${org?.slug ?? ''}`)} className="flex items-center gap-2 px-3 py-2 text-sm text-white/70 hover:text-white hover:bg-white/[0.08] cursor-pointer transition-colors">
                        <CurrencyCircleDollar size={16} weight="fill" />
                        <span>{t('common.billing', { defaultValue: 'Billing' })}</span>
                      </a>
                    </HoverMenuItem>
                  )}
                  {myOrgs.length > 0 && <HoverMenuSeparator />}
                  {myOrgs.map((o: any) => (
                    <HoverMenuItem key={o.id} asChild>
                      <a href={getUriWithOrg(o.slug, '/')} className={cn(
                        "flex items-center gap-2 px-3 py-2 text-sm hover:text-white hover:bg-white/[0.08] cursor-pointer transition-colors",
                        o.id === org?.id ? "text-white" : "text-white/70"
                      )}>
                        <Buildings size={16} weight="fill" />
                        <span className="truncate flex-1">{o.name}</span>
                        {o.id === org?.id && <Check size={14} weight="bold" className="text-green-500" />}
                      </a>
                    </HoverMenuItem>
                  ))}
                  <HoverMenuSeparator />
                  <HoverMenuItem asChild>
                    <a href={getMainDomainUri('/new')} className="flex items-center gap-2 px-3 py-2 text-sm font-semibold text-white/80 hover:text-white hover:bg-white/[0.08] cursor-pointer transition-colors">
                      <Plus size={16} weight="bold" />
                      <span>{t('common.create_organization', { defaultValue: 'Create organization' })}</span>
                    </a>
                  </HoverMenuItem>
                </HoverMenuContent>
              }
            >
              <button aria-label={t('dashboard.nav.open_organizations_menu')} className={cn(
                "flex items-center w-full rounded-lg text-white/50 hover:text-white hover:bg-white/[0.08] transition-all group",
                isCollapsed ? "justify-center h-10" : "px-3 py-2 gap-3"
              )}>
                <Buildings size={20} weight="fill" />
                {!isCollapsed && (
                  <span className="text-sm font-medium">{t('common.organizations', { defaultValue: 'Organizations' })}</span>
                )}
              </button>
            </HoverMenu>
          )}

          {/* User Menu with hover menu */}
          <HoverMenu
            align="end"
            content={
              <HoverMenuContent className="w-56">
                <div className="px-3 py-2">
                  <p className="text-sm font-semibold text-white/90">{session?.data?.user?.username}</p>
                  <p className="text-xs text-white/40">{session?.data?.user?.email}</p>
                </div>
                <HoverMenuSeparator />
                <HoverMenuItem asChild>
                  <Link href="/account/general" className="flex items-center gap-2 px-3 py-2 text-sm text-white/70 hover:text-white hover:bg-white/[0.08] cursor-pointer transition-colors">
                    <Gear size={16} weight="fill" />
                    <span>{t('common.settings')}</span>
                  </Link>
                </HoverMenuItem>
                <HoverMenuItem asChild>
                  <Link href={getUriWithOrg(org?.slug, '/account/purchases')} className="flex items-center gap-2 px-3 py-2 text-sm text-white/70 hover:text-white hover:bg-white/[0.08] cursor-pointer transition-colors">
                    <ShoppingBag size={16} weight="fill" />
                    <span>{t('account.purchases')}</span>
                  </Link>
                </HoverMenuItem>
                <HoverMenuSeparator />
                <HoverMenuItem
                  onClick={() => logOutUI()}
                  className="flex items-center gap-2 px-3 py-2 text-sm text-red-500 hover:text-red-400 hover:bg-white/[0.08] cursor-pointer transition-colors"
                >
                  <SignOut size={16} weight="fill" data-dir-flip />
                  <span>{t('user.sign_out')}</span>
                </HoverMenuItem>
              </HoverMenuContent>
            }
          >
            <button className={cn(
              "flex items-center w-full rounded-lg text-white/50 hover:text-white hover:bg-white/[0.08] transition-all group",
              isCollapsed ? "justify-center h-10" : "px-3 py-2 gap-3"
            )}>
              <UserAvatar width={24} rounded="rounded-full" shadow="shadow-none" />
              {!isCollapsed && (
                <div className="flex flex-col min-w-0 flex-1 text-start">
                  <span className="text-sm font-medium truncate text-white/90">{session?.data?.user?.username}</span>
                  <span className="text-xs text-white/40 truncate">{session?.data?.user?.email}</span>
                </div>
              )}
            </button>
          </HoverMenu>
        </div>
      </div>
    </nav>

      {/* Feedback Modal */}
      <FeedbackModal
        open={feedbackModalOpen}
        onOpenChange={setFeedbackModalOpen}
        theme="dark"
        userName={session?.data?.user?.username}
        userEmail={session?.data?.user?.email}
      />
    </TooltipProvider>
  )
}

const MenuLink = ({ href, icon, label, isCollapsed, isExternal, active, onClick }: {
  href: string
  icon: React.ReactNode
  label: string
  isCollapsed: boolean
  isExternal?: boolean
  active?: boolean
  onClick?: () => void
}) => {
  const content = (
    <div
      className={cn(
        "relative flex items-center w-full rounded-lg transition-all",
        active
          ? "text-white bg-white/[0.08]"
          : "text-white/50 hover:text-white hover:bg-white/[0.08]",
        isCollapsed ? "justify-center h-10" : "px-3 py-2 gap-3"
      )}
    >
      {active && (
        <span
          aria-hidden="true"
          className="absolute start-0.5 top-1/2 -translate-y-1/2 h-5 w-[3px] bg-white rounded-full"
        />
      )}
      {icon}
      {!isCollapsed && (
        <span className="text-sm font-medium">{label}</span>
      )}
    </div>
  )

  const ariaCurrent = active ? 'page' : undefined
  const linkElement = isExternal ? (
    <a href={href} target="_blank" rel="noopener noreferrer" aria-label={label} onClick={onClick}>
      {content}
    </a>
  ) : (
    <Link aria-label={label} aria-current={ariaCurrent} href={href} onClick={onClick}>
      {content}
    </Link>
  )

  if (isCollapsed) {
    return (
      <Tooltip>
        <TooltipTrigger asChild>
          {linkElement}
        </TooltipTrigger>
        <TooltipContent side="right" className="z-tooltip bg-[#1a1a1b] border-white/10 text-white text-xs px-2 py-1 shadow-lg shadow-black/20">
          {label}
        </TooltipContent>
      </Tooltip>
    )
  }

  return linkElement
}

export default DashLeftMenu
