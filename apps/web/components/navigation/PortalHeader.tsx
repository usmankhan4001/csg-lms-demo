'use client'

import React, { useState, useRef, useEffect } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import {
  Menu,
  Bell,
  Search,
  Building2,
  Calendar,
  ChevronDown,
  Check,
  User,
  LogOut,
  Settings,
  Sparkles,
  CreditCard,
  CheckSquare,
  BookOpen,
  HelpCircle,
  ExternalLink,
  Shield,
  Layers,
  GraduationCap,
  Users,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import {
  UserRole,
  Campus,
  AcademicTerm,
  NotificationItem,
  CAMPUSES,
  ACADEMIC_TERMS,
  INITIAL_NOTIFICATIONS,
  SAMPLE_USERS,
} from './types'

interface PortalHeaderProps {
  currentRole: UserRole
  onRoleChange?: (role: UserRole) => void
  onToggleMobileSidebar?: () => void
  activeCampus?: Campus
  onCampusChange?: (campus: Campus) => void
  activeTerm?: AcademicTerm
  onTermChange?: (term: AcademicTerm) => void
  className?: string
}

export function PortalHeader({
  currentRole,
  onRoleChange,
  onToggleMobileSidebar,
  activeCampus = CAMPUSES[0],
  onCampusChange,
  activeTerm = ACADEMIC_TERMS[0],
  onTermChange,
  className,
}: PortalHeaderProps) {
  const router = useRouter()
  const [selectedCampus, setSelectedCampus] = useState<Campus>(activeCampus)
  const [selectedTerm, setSelectedTerm] = useState<AcademicTerm>(activeTerm)
  const [campusDropdownOpen, setCampusDropdownOpen] = useState(false)
  const [termDropdownOpen, setTermDropdownOpen] = useState(false)
  const [notifPopoverOpen, setNotifPopoverOpen] = useState(false)
  const [profileDropdownOpen, setProfileDropdownOpen] = useState(false)
  const [searchOpen, setSearchOpen] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [notifications, setNotifications] = useState<NotificationItem[]>(INITIAL_NOTIFICATIONS)
  const [notifFilter, setNotifFilter] = useState<'all' | 'unread' | 'academic' | 'finance'>('all')

  const campusRef = useRef<HTMLDivElement>(null)
  const termRef = useRef<HTMLDivElement>(null)
  const notifRef = useRef<HTMLDivElement>(null)
  const profileRef = useRef<HTMLDivElement>(null)

  const user = SAMPLE_USERS[currentRole]

  // Close dropdowns when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (campusRef.current && !campusRef.current.contains(event.target as Node)) {
        setCampusDropdownOpen(false)
      }
      if (termRef.current && !termRef.current.contains(event.target as Node)) {
        setTermDropdownOpen(false)
      }
      if (notifRef.current && !notifRef.current.contains(event.target as Node)) {
        setNotifPopoverOpen(false)
      }
      if (profileRef.current && !profileRef.current.contains(event.target as Node)) {
        setProfileDropdownOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleSelectCampus = (campus: Campus) => {
    setSelectedCampus(campus)
    if (onCampusChange) onCampusChange(campus)
    setCampusDropdownOpen(false)
  }

  const handleSelectTerm = (term: AcademicTerm) => {
    setSelectedTerm(term)
    if (onTermChange) onTermChange(term)
    setTermDropdownOpen(false)
  }

  const handleMarkAllRead = () => {
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })))
  }

  const handleMarkRead = (id: string) => {
    setNotifications((prev) =>
      prev.map((n) => (n.id === id ? { ...n, read: true } : n))
    )
  }

  const unreadCount = notifications.filter((n) => !n.read).length

  const filteredNotifications = notifications.filter((n) => {
    if (notifFilter === 'unread') return !n.read
    if (notifFilter === 'academic') return n.category === 'academic' || n.category === 'ai_tutor'
    if (notifFilter === 'finance') return n.category === 'finance'
    return true
  })

  const getCategoryIcon = (category: NotificationItem['category']) => {
    switch (category) {
      case 'academic':
        return <BookOpen className="size-4 text-blue-500" />
      case 'finance':
        return <CreditCard className="size-4 text-amber-500" />
      case 'attendance':
        return <CheckSquare className="size-4 text-emerald-500" />
      case 'ai_tutor':
        return <Sparkles className="size-4 text-purple-500" />
      default:
        return <Bell className="size-4 text-neutral-500" />
    }
  }

  const handleQuickRoleSwitch = (role: UserRole) => {
    setProfileDropdownOpen(false)
    if (onRoleChange) onRoleChange(role)
    const paths: Record<UserRole, string> = {
      STUDENT: '/student',
      TEACHER: '/teacher',
      PARENT: '/parent',
      ADMIN: '/admin',
    }
    router.push(paths[role])
  }

  return (
    <header
      className={cn(
        'sticky top-0 z-20 w-full h-16 bg-white/95 dark:bg-neutral-900/95 backdrop-blur-md border-b border-neutral-200 dark:border-neutral-800 px-4 md:px-6 flex items-center justify-between gap-3',
        className
      )}
    >
      {/* Left section: Mobile menu trigger & Campus / Term badges */}
      <div className="flex items-center gap-3 min-w-0">
        <button
          onClick={onToggleMobileSidebar}
          className="md:hidden p-2 rounded-lg text-neutral-600 dark:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-colors focus:outline-hidden focus:ring-2 focus:ring-blue-500"
          aria-label="Open portal navigation sidebar"
        >
          <Menu className="size-5" />
        </button>

        {/* Campus Selector Dropdown */}
        <div className="relative" ref={campusRef}>
          <button
            onClick={() => setCampusDropdownOpen(!campusDropdownOpen)}
            className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg border border-neutral-200 dark:border-neutral-700/80 bg-neutral-50 dark:bg-neutral-800/60 hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-colors text-start focus:outline-hidden focus:ring-2 focus:ring-blue-500 text-xs font-medium text-neutral-800 dark:text-neutral-200 max-w-[200px] sm:max-w-xs truncate shadow-2xs"
            aria-label="Select Campus"
            aria-expanded={campusDropdownOpen}
          >
            <Building2 className="size-3.5 text-blue-500 shrink-0" />
            <span className="truncate">{selectedCampus.name}</span>
            <ChevronDown
              className={cn(
                'size-3.5 text-neutral-400 shrink-0 transition-transform duration-200',
                campusDropdownOpen && 'rotate-180'
              )}
            />
          </button>

          {campusDropdownOpen && (
            <div className="absolute top-full start-0 mt-1.5 w-72 p-1.5 bg-white dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-700 rounded-xl shadow-xl z-50 animate-in fade-in slide-in-from-top-1 duration-150">
              <div className="px-2.5 py-1 text-[11px] font-semibold text-neutral-400 uppercase tracking-wider">
                Select Active Campus
              </div>
              {CAMPUSES.map((c) => {
                const isSelected = selectedCampus.id === c.id
                return (
                  <button
                    key={c.id}
                    onClick={() => handleSelectCampus(c)}
                    className={cn(
                      'w-full flex items-start gap-2.5 px-2.5 py-2 rounded-lg text-start transition-colors',
                      isSelected
                        ? 'bg-blue-500/10 text-blue-700 dark:text-blue-300 font-semibold'
                        : 'text-neutral-700 dark:text-neutral-300 hover:bg-neutral-50 dark:hover:bg-neutral-700/50'
                    )}
                  >
                    <Building2
                      className={cn(
                        'size-4 mt-0.5 shrink-0',
                        isSelected ? 'text-blue-600' : 'text-neutral-400'
                      )}
                    />
                    <div className="flex-1 min-w-0">
                      <div className="text-xs font-medium truncate">{c.name}</div>
                      <div className="text-[11px] text-neutral-400 dark:text-neutral-500">
                        {c.city} • {c.studentCount} Students
                      </div>
                    </div>
                    {isSelected && <Check className="size-4 text-blue-600 shrink-0 mt-0.5" />}
                  </button>
                )
              })}
            </div>
          )}
        </div>

        {/* Academic Term Badge & Dropdown */}
        <div className="relative hidden sm:block" ref={termRef}>
          <button
            onClick={() => setTermDropdownOpen(!termDropdownOpen)}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-emerald-500/20 bg-emerald-500/10 hover:bg-emerald-500/15 transition-colors text-start focus:outline-hidden focus:ring-2 focus:ring-emerald-500 text-xs font-semibold text-emerald-700 dark:text-emerald-300 shadow-2xs"
            aria-label="Select Academic Term"
            aria-expanded={termDropdownOpen}
          >
            <span className="size-1.5 rounded-full bg-emerald-500 animate-pulse" />
            <span>{selectedTerm.name}</span>
            <ChevronDown
              className={cn(
                'size-3 text-emerald-600 dark:text-emerald-400 shrink-0 transition-transform duration-200',
                termDropdownOpen && 'rotate-180'
              )}
            />
          </button>

          {termDropdownOpen && (
            <div className="absolute top-full start-0 mt-1.5 w-60 p-1.5 bg-white dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-700 rounded-xl shadow-xl z-50 animate-in fade-in slide-in-from-top-1 duration-150">
              <div className="px-2.5 py-1 text-[11px] font-semibold text-neutral-400 uppercase tracking-wider">
                Academic Session
              </div>
              {ACADEMIC_TERMS.map((t) => {
                const isSelected = selectedTerm.id === t.id
                return (
                  <button
                    key={t.id}
                    onClick={() => handleSelectTerm(t)}
                    className={cn(
                      'w-full flex items-center justify-between px-2.5 py-2 rounded-lg text-xs transition-colors text-start',
                      isSelected
                        ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 font-semibold'
                        : 'text-neutral-700 dark:text-neutral-300 hover:bg-neutral-50 dark:hover:bg-neutral-700/50'
                    )}
                  >
                    <div className="flex items-center gap-2">
                      <Calendar className="size-3.5 text-neutral-400" />
                      <span>{t.name}</span>
                    </div>
                    {t.isCurrent && (
                      <span className="px-1.5 py-0.5 rounded text-[10px] bg-emerald-100 dark:bg-emerald-900/50 text-emerald-700 dark:text-emerald-300">
                        Active
                      </span>
                    )}
                  </button>
                )
              })}
            </div>
          )}
        </div>
      </div>

      {/* Right section: Search bar, Notifications, Profile Menu */}
      <div className="flex items-center gap-2.5 shrink-0">
        {/* Quick Search Button / Input */}
        <div className="relative">
          {searchOpen ? (
            <div className="flex items-center gap-1.5 bg-neutral-100 dark:bg-neutral-800 rounded-lg px-2.5 py-1 border border-neutral-300 dark:border-neutral-700 shadow-2xs">
              <Search className="size-3.5 text-neutral-400" />
              <input
                type="text"
                autoFocus
                placeholder="Search courses, students, vouchers..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onBlur={() => !searchQuery && setSearchOpen(false)}
                className="bg-transparent border-none text-xs text-neutral-900 dark:text-neutral-100 placeholder:text-neutral-400 focus:outline-hidden w-40 sm:w-60"
              />
            </div>
          ) : (
            <button
              onClick={() => setSearchOpen(true)}
              className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg border border-neutral-200 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-800 text-neutral-500 hover:text-neutral-900 dark:hover:text-white hover:bg-neutral-100 dark:hover:bg-neutral-700 transition-colors text-xs font-normal"
              title="Search portal (Press ⌘K)"
            >
              <Search className="size-3.5 text-neutral-400" />
              <span className="hidden lg:inline text-neutral-400">Search portal...</span>
              <kbd className="hidden lg:inline-block px-1.5 py-0.5 text-[10px] bg-neutral-200 dark:bg-neutral-700 rounded text-neutral-500 font-mono">
                ⌘K
              </kbd>
            </button>
          )}
        </div>

        {/* Notifications Popover */}
        <div className="relative" ref={notifRef}>
          <button
            onClick={() => setNotifPopoverOpen(!notifPopoverOpen)}
            className="relative p-2 rounded-lg border border-neutral-200 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-800 text-neutral-600 dark:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-700 transition-colors focus:outline-hidden focus:ring-2 focus:ring-blue-500"
            aria-label="Open notifications"
            aria-expanded={notifPopoverOpen}
          >
            <Bell className="size-4" />
            {unreadCount > 0 && (
              <span className="absolute -top-1 -end-1 size-4 rounded-full bg-rose-500 text-white text-[10px] font-bold flex items-center justify-center animate-bounce shadow-xs">
                {unreadCount}
              </span>
            )}
          </button>

          {notifPopoverOpen && (
            <div className="absolute top-full end-0 mt-2 w-80 sm:w-96 bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 rounded-2xl shadow-2xl z-50 overflow-hidden animate-in fade-in slide-in-from-top-2 duration-150">
              {/* Notification Header */}
              <div className="p-3.5 border-b border-neutral-100 dark:border-neutral-800 flex items-center justify-between bg-neutral-50/70 dark:bg-neutral-800/40">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-bold text-neutral-900 dark:text-white">
                    Notifications
                  </span>
                  {unreadCount > 0 && (
                    <span className="px-1.5 py-0.5 rounded-full text-[11px] font-semibold bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20">
                      {unreadCount} new
                    </span>
                  )}
                </div>
                {unreadCount > 0 && (
                  <button
                    onClick={handleMarkAllRead}
                    className="text-xs text-blue-600 dark:text-blue-400 hover:underline font-medium"
                  >
                    Mark all as read
                  </button>
                )}
              </div>

              {/* Filter tabs */}
              <div className="flex items-center gap-1 p-2 border-b border-neutral-100 dark:border-neutral-800 bg-neutral-50/30 dark:bg-neutral-900/30 text-xs">
                {(['all', 'unread', 'academic', 'finance'] as const).map((filter) => (
                  <button
                    key={filter}
                    onClick={() => setNotifFilter(filter)}
                    className={cn(
                      'px-2.5 py-1 rounded-md capitalize font-medium transition-colors',
                      notifFilter === filter
                        ? 'bg-blue-600 text-white shadow-2xs'
                        : 'text-neutral-500 hover:text-neutral-900 dark:hover:text-white hover:bg-neutral-100 dark:hover:bg-neutral-800'
                    )}
                  >
                    {filter}
                  </button>
                ))}
              </div>

              {/* Notification List */}
              <div className="max-h-80 overflow-y-auto divide-y divide-neutral-100 dark:divide-neutral-800/60">
                {filteredNotifications.length === 0 ? (
                  <div className="p-6 text-center text-xs text-neutral-400">
                    No notifications in this category.
                  </div>
                ) : (
                  filteredNotifications.map((n) => (
                    <div
                      key={n.id}
                      onClick={() => handleMarkRead(n.id)}
                      className={cn(
                        'p-3 hover:bg-neutral-50 dark:hover:bg-neutral-800/50 transition-colors cursor-pointer flex items-start gap-3',
                        !n.read && 'bg-blue-500/5 dark:bg-blue-500/10'
                      )}
                    >
                      <div className="size-8 rounded-lg bg-neutral-100 dark:bg-neutral-800 flex items-center justify-center shrink-0 mt-0.5">
                        {getCategoryIcon(n.category)}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between gap-1 mb-0.5">
                          <h4 className="text-xs font-semibold text-neutral-900 dark:text-neutral-100 truncate">
                            {n.title}
                          </h4>
                          {!n.read && (
                            <span className="size-2 rounded-full bg-blue-500 shrink-0" />
                          )}
                        </div>
                        <p className="text-[11px] text-neutral-500 dark:text-neutral-400 line-clamp-2 leading-relaxed">
                          {n.description}
                        </p>
                        <span className="text-[10px] text-neutral-400 dark:text-neutral-500 mt-1 inline-block">
                          {n.timestamp}
                        </span>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </div>

        {/* User Profile Dropdown */}
        <div className="relative" ref={profileRef}>
          <button
            onClick={() => setProfileDropdownOpen(!profileDropdownOpen)}
            className="flex items-center gap-2 p-1 rounded-full border border-neutral-200 dark:border-neutral-700 hover:ring-2 hover:ring-blue-500/40 transition-all focus:outline-hidden"
            aria-label="Open profile menu"
            aria-expanded={profileDropdownOpen}
          >
            <div className="size-8 rounded-full bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center text-white text-xs font-bold shadow-xs">
              {user.name.charAt(0)}
            </div>
          </button>

          {profileDropdownOpen && (
            <div className="absolute top-full end-0 mt-2 w-72 bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 rounded-2xl shadow-2xl z-50 p-2 overflow-hidden animate-in fade-in slide-in-from-top-2 duration-150">
              {/* Profile details */}
              <div className="p-3 rounded-xl bg-neutral-50 dark:bg-neutral-800/60 mb-2 border border-neutral-100 dark:border-neutral-800">
                <div className="text-xs font-bold text-neutral-900 dark:text-white truncate">
                  {user.name}
                </div>
                <div className="text-[11px] text-neutral-500 dark:text-neutral-400 truncate">
                  {user.email}
                </div>
                <div className="mt-2 flex items-center gap-1.5">
                  <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20">
                    {user.role}
                  </span>
                  <span className="text-[11px] text-neutral-500 dark:text-neutral-400 truncate">
                    {selectedCampus.code}
                  </span>
                </div>
              </div>

              {/* Fast Portal Jump List */}
              <div className="px-2 py-1 text-[11px] font-semibold text-neutral-400 uppercase tracking-wider">
                Quick Portal Switcher
              </div>
              <div className="grid grid-cols-2 gap-1.5 mb-2">
                <button
                  onClick={() => handleQuickRoleSwitch('STUDENT')}
                  className={cn(
                    'flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium text-start transition-colors',
                    currentRole === 'STUDENT'
                      ? 'bg-blue-500/15 text-blue-700 dark:text-blue-300 font-semibold'
                      : 'hover:bg-neutral-100 dark:hover:bg-neutral-800 text-neutral-700 dark:text-neutral-300'
                  )}
                >
                  <GraduationCap className="size-3.5 text-blue-500" />
                  <span>Student</span>
                </button>
                <button
                  onClick={() => handleQuickRoleSwitch('TEACHER')}
                  className={cn(
                    'flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium text-start transition-colors',
                    currentRole === 'TEACHER'
                      ? 'bg-amber-500/15 text-amber-700 dark:text-amber-300 font-semibold'
                      : 'hover:bg-neutral-100 dark:hover:bg-neutral-800 text-neutral-700 dark:text-neutral-300'
                  )}
                >
                  <Layers className="size-3.5 text-amber-500" />
                  <span>Teacher</span>
                </button>
                <button
                  onClick={() => handleQuickRoleSwitch('PARENT')}
                  className={cn(
                    'flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium text-start transition-colors',
                    currentRole === 'PARENT'
                      ? 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 font-semibold'
                      : 'hover:bg-neutral-100 dark:hover:bg-neutral-800 text-neutral-700 dark:text-neutral-300'
                  )}
                >
                  <Users className="size-3.5 text-emerald-500" />
                  <span>Parent</span>
                </button>
                <button
                  onClick={() => handleQuickRoleSwitch('ADMIN')}
                  className={cn(
                    'flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium text-start transition-colors',
                    currentRole === 'ADMIN'
                      ? 'bg-purple-500/15 text-purple-700 dark:text-purple-300 font-semibold'
                      : 'hover:bg-neutral-100 dark:hover:bg-neutral-800 text-neutral-700 dark:text-neutral-300'
                  )}
                >
                  <Shield className="size-3.5 text-purple-500" />
                  <span>Admin</span>
                </button>
              </div>

              <div className="h-px bg-neutral-100 dark:bg-neutral-800 my-1" />

              <Link
                href="/auth/logout"
                className="w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-xs text-rose-600 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-950/30 transition-colors font-medium"
              >
                <LogOut className="size-4" />
                <span>Sign Out</span>
              </Link>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
