'use client'
import { useState, useCallback, useEffect } from 'react'

export type OnboardingStep = {
  id: string
  title: string
  description: string
  // CTA label + where it goes. `hrefType: 'root'` targets the org's public site
  // (the shareable school), everything else is a /dash/* path.
  action: string
  href: string
  hrefType?: 'org' | 'root'
  // Steps with no navigable completion signal complete when their CTA is clicked.
  completeOnClick?: boolean
  // Regex (source string) on the pathname that auto-completes the step.
  completePath?: string
  completed: boolean
  requiredPlan?: string
  skipped?: boolean
}

type OnboardingState = {
  completedSteps: string[]
  skippedSteps: string[]
  minimized: boolean
  expanded: boolean
  showAllSteps: boolean
  dismissed: boolean
  welcomeSeen: boolean
}

const STORAGE_KEY = 'lh_onboarding'

// Outcome-framed onboarding for a SCHOOL, not a solo course creator.
//
// The previous six steps were Learnhouse's own: create a course, add a lesson,
// brand it, share the link, invite learners, open a community. Sound advice for
// one person selling a course; close to useless for an administrator standing
// up a school, who cannot take a register, bill a family or admit a pupil until
// a campus, an academic year and a roll of people exist.
//
// These seven ladder across all four pillars of this platform -- school
// management, learning, admissions, and the AI tutor -- in dependency order:
// nothing here asks for something the previous step has not already created.
// Each title is the WIN; the action is only the means.
const DEFAULT_STEPS: Omit<OnboardingStep, 'completed'>[] = [
  {
    id: 'school_structure',
    title: 'Your school exists',
    description:
      'Create your campus, academic year and terms. Every register, report card and invoice hangs off these — nothing else works until they do.',
    action: 'Set up the school',
    href: '/dash/school-settings/setup',
    completePath: '/dash/school-settings/setup',
  },
  {
    id: 'invite_people',
    title: 'Staff and families can sign in',
    description:
      'Add teachers, students and parents — one at a time or by pasting a spreadsheet. Everyone is emailed an invite and chooses their own password.',
    action: 'Add people',
    href: '/dash/school-settings/people',
    completePath: '/dash/school-settings/people',
  },
  {
    id: 'class_timetable',
    title: 'Every class knows where to be',
    description:
      'Build the timetable and assign teachers to sections, so lessons, cover and live classes all have a schedule behind them.',
    action: 'Build the timetable',
    href: '/dash/timetable',
    completePath: '/dash/timetable',
  },
  {
    id: 'first_register',
    title: 'Attendance is running',
    description:
      'Take a roll call. From the first register, absences reach parents and persistent patterns surface to your pastoral team.',
    action: 'Take a register',
    href: '/dash/attendance',
    completePath: '/dash/attendance',
  },
  {
    id: 'publish_course',
    title: 'There is something to learn',
    description:
      'Publish a course with real material. This is what students open, what the gradebook marks, and what the AI tutor is allowed to teach from.',
    action: 'Create a course',
    href: '/dash/courses?new=true',
    completePath: '/dash/courses/course/[^/]+/(general|content)',
  },
  {
    id: 'admissions_open',
    title: 'Enquiries become enrolments',
    description:
      'Open your admissions pipeline so a new family can be captured, followed up and enrolled — turning into a real student account at the end.',
    action: 'Open admissions',
    href: '/dash/admissions',
    completePath: '/dash/admissions',
  },
  {
    id: 'tutor_and_safeguarding',
    title: 'The AI tutor is on — and safe',
    description:
      'Switch on the tutor and record your school’s own crisis helpline numbers. Until you do, a student who discloses self-harm is told their school has not added any — so this step is not optional.',
    action: 'Configure the tutor',
    href: '/dash/ai-tutor',
    completePath: '/dash/(ai-tutor|school-settings)$',
  },
]

// Raw step definitions (incl. completion-path regexes) for the headless tracker.
export const ONBOARDING_STEP_DEFS = DEFAULT_STEPS

function loadState(): OnboardingState {
  if (typeof window === 'undefined') {
    return { completedSteps: [], skippedSteps: [], minimized: false, expanded: false, showAllSteps: false, dismissed: false, welcomeSeen: false }
  }
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) {
      const parsed = JSON.parse(raw)
      return {
        completedSteps: parsed.completedSteps || [],
        skippedSteps: parsed.skippedSteps || [],
        minimized: parsed.minimized || false,
        expanded: parsed.expanded || false,
        showAllSteps: parsed.showAllSteps || false,
        dismissed: parsed.dismissed || false,
        welcomeSeen: parsed.welcomeSeen || false,
      }
    }
  } catch {
    /* ignore */
  }
  return { completedSteps: [], skippedSteps: [], minimized: false, expanded: false, showAllSteps: false, dismissed: false, welcomeSeen: false }
}

function saveState(state: OnboardingState) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
    window.dispatchEvent(new Event('lh_onboarding_change'))
  } catch {
    /* ignore */
  }
}

export function useOnboarding() {
  const [state, setState] = useState<OnboardingState>(loadState)

  const applyLocalChange = useCallback(
    (updater: (_prev: OnboardingState) => OnboardingState) => {
      setState((prev) => {
        const next = updater(prev)
        if (next !== prev) {
          saveState(next)
        }
        return next
      })
    },
    []
  )

  // Listen for changes from other instances of this hook
  useEffect(() => {
    const handler = () => {
      setState((prev) => {
        const loaded = loadState()
        if (JSON.stringify(loaded) === JSON.stringify(prev)) return prev
        return loaded
      })
    }
    window.addEventListener('lh_onboarding_change', handler)
    return () => window.removeEventListener('lh_onboarding_change', handler)
  }, [])

  const steps: OnboardingStep[] = DEFAULT_STEPS.map((s) => ({
    ...s,
    completed: state.completedSteps.includes(s.id) || state.skippedSteps.includes(s.id),
    skipped: state.skippedSteps.includes(s.id),
  }))

  const currentStepIndex = steps.findIndex((s) => !s.completed)
  const currentStep = currentStepIndex >= 0 ? steps[currentStepIndex] : null
  const allCompleted = steps.every((s) => s.completed)
  const progress = steps.length > 0 ? steps.filter((s) => s.completed).length / steps.length : 0

  const completeStep = useCallback((stepId: string) => {
    applyLocalChange((prev) => {
      if (prev.completedSteps.includes(stepId)) return prev
      return { ...prev, completedSteps: [...prev.completedSteps, stepId] }
    })
  }, [applyLocalChange])

  const toggleMinimized = useCallback(() => {
    applyLocalChange((prev) => ({ ...prev, minimized: !prev.minimized }))
  }, [applyLocalChange])

  const toggleExpanded = useCallback(() => {
    applyLocalChange((prev) => ({ ...prev, expanded: !prev.expanded }))
  }, [applyLocalChange])

  const toggleShowAllSteps = useCallback(() => {
    applyLocalChange((prev) => ({ ...prev, showAllSteps: !prev.showAllSteps }))
  }, [applyLocalChange])

  const dismiss = useCallback(() => {
    applyLocalChange((prev) => (prev.dismissed ? prev : { ...prev, dismissed: true }))
  }, [applyLocalChange])

  const markWelcomeSeen = useCallback(() => {
    applyLocalChange((prev) => (prev.welcomeSeen ? prev : { ...prev, welcomeSeen: true }))
  }, [applyLocalChange])

  const skipStep = useCallback((stepId: string) => {
    applyLocalChange((prev) => {
      if (prev.skippedSteps.includes(stepId)) return prev
      return { ...prev, skippedSteps: [...prev.skippedSteps, stepId] }
    })
  }, [applyLocalChange])

  const reset = useCallback(() => {
    applyLocalChange(() => ({ completedSteps: [], skippedSteps: [], minimized: false, expanded: false, showAllSteps: false, dismissed: false, welcomeSeen: false }))
  }, [applyLocalChange])

  return {
    steps,
    currentStep,
    currentStepIndex,
    allCompleted,
    progress,
    minimized: state.minimized,
    expanded: state.expanded,
    showAllSteps: state.showAllSteps,
    dismissed: state.dismissed,
    welcomeSeen: state.welcomeSeen,
    completeStep,
    dismiss,
    markWelcomeSeen,
    toggleMinimized,
    toggleExpanded,
    toggleShowAllSteps,
    skipStep,
    reset,
  }
}
