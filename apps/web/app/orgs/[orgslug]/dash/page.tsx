'use client'
import SchoolDashboardHome from '@components/Dashboard/Home/SchoolDashboardHome'

/**
 * `/dash` is the school's home, not Learnhouse's course-authoring landing
 * page. SchoolDashboardHome is role-aware and keeps Learnhouse's own course
 * and member surfaces below the school's figures — a plain org admin with no
 * school role still gets them, since setting the school up needs those
 * screens.
 */
export default function DashboardPage() {
  return <SchoolDashboardHome />
}
