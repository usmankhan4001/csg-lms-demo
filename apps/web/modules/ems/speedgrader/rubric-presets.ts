/**
 * CSG-EMS Rubric Templates & Calculation Helpers
 */

import { LatePenaltyCalculation, LatePenaltyConfig, Rubric, RubricCriterion, SpeedGraderStudentSubmission } from './types'

export const DEFAULT_LATE_PENALTY_CONFIG: LatePenaltyConfig = {
  enabled: true,
  decayPercentPer24h: 5, // -5% per 24h
  maxPenaltyPercent: 50,
  gracePeriodHours: 1,
}

export const SCIENCE_LAB_RUBRIC: Rubric = {
  id: 'rubric-science-lab',
  title: 'Scientific Method & Lab Report Analytical Rubric',
  description: 'Standard analytical rubric evaluating hypothesis formulation, methodology, data analysis, and synthesis of conclusions.',
  scaleType: 'percentage',
  totalPoints: 100,
  latePenaltyConfig: DEFAULT_LATE_PENALTY_CONFIG,
  criteria: [
    {
      id: 'crit-hypothesis',
      title: 'Hypothesis & Theoretical Framework',
      description: 'Clarity, testability, and theoretical grounding of the stated research question and hypothesis.',
      weight: 25,
      maxPoints: 25,
      levels: [
        {
          id: 'exemplary',
          name: 'Exemplary',
          points: 25,
          percentage: 100,
          description: 'Hypothesis is clearly stated, rigorously testable, and deeply grounded in published scientific literature with explicit dependent/independent variables.',
          color: 'emerald',
        },
        {
          id: 'proficient',
          name: 'Proficient',
          points: 20,
          percentage: 80,
          description: 'Hypothesis is testable with identified variables and adequate theoretical justification, though minor literature ties are omitted.',
          color: 'blue',
        },
        {
          id: 'developing',
          name: 'Developing',
          points: 15,
          percentage: 60,
          description: 'Hypothesis is overly broad or ambiguous; independent/dependent variables are poorly differentiated.',
          color: 'amber',
        },
        {
          id: 'novice',
          name: 'Novice',
          points: 10,
          percentage: 40,
          description: 'Hypothesis is missing, untestable, or lacks scientific rationale.',
          color: 'rose',
        },
      ],
    },
    {
      id: 'crit-data-analysis',
      title: 'Data Collection & Quantitative Analysis',
      description: 'Precision of experimental measurements, statistical error propagation, and graphical representations.',
      weight: 35,
      maxPoints: 35,
      levels: [
        {
          id: 'exemplary',
          name: 'Exemplary',
          points: 35,
          percentage: 100,
          description: 'Data is complete with rigorous uncertainty intervals, error bars, publication-quality graphs, and appropriate statistical tests (p-values, regression).',
          color: 'emerald',
        },
        {
          id: 'proficient',
          name: 'Proficient',
          points: 28,
          percentage: 80,
          description: 'Data is well organized with labeled graphs and basic error analysis, with minor omissions in statistical rigor.',
          color: 'blue',
        },
        {
          id: 'developing',
          name: 'Developing',
          points: 21,
          percentage: 60,
          description: 'Data contains computational errors, incomplete axes labels, or missing uncertainty estimates.',
          color: 'amber',
        },
        {
          id: 'novice',
          name: 'Novice',
          points: 14,
          percentage: 40,
          description: 'Raw data is disorganized, charts are unreadable, or measurements lack units and context.',
          color: 'rose',
        },
      ],
    },
    {
      id: 'crit-conclusion',
      title: 'Conclusion & Error Synthesis',
      description: 'Interpretation of results against hypothesis, analysis of systemic limitations, and proposed future investigations.',
      weight: 25,
      maxPoints: 25,
      levels: [
        {
          id: 'exemplary',
          name: 'Exemplary',
          points: 25,
          percentage: 100,
          description: 'Flawless synthesis connecting observations to initial hypothesis, identifying nuanced systemic errors and proposing actionable extensions.',
          color: 'emerald',
        },
        {
          id: 'proficient',
          name: 'Proficient',
          points: 20,
          percentage: 80,
          description: 'Solid conclusion supported by empirical evidence with thoughtful consideration of lab limitations.',
          color: 'blue',
        },
        {
          id: 'developing',
          name: 'Developing',
          points: 15,
          percentage: 60,
          description: 'Conclusion simply restates the data without analytical insight; limitations are generic or superficial.',
          color: 'amber',
        },
        {
          id: 'novice',
          name: 'Novice',
          points: 10,
          percentage: 40,
          description: 'Conclusion is unsupported by experimental data or completely absent.',
          color: 'rose',
        },
      ],
    },
    {
      id: 'crit-formatting',
      title: 'Academic Structure & Citations',
      description: 'Adherence to scientific report formatting standards, IEEE/APA citations, and technical communication.',
      weight: 15,
      maxPoints: 15,
      levels: [
        {
          id: 'exemplary',
          name: 'Exemplary',
          points: 15,
          percentage: 100,
          description: 'Impeccable academic formatting, precise technical terminology, and flawless citation of primary literature.',
          color: 'emerald',
        },
        {
          id: 'proficient',
          name: 'Proficient',
          points: 12,
          percentage: 80,
          description: 'Clean formatting and mostly accurate citations with rare stylistic discrepancies.',
          color: 'blue',
        },
        {
          id: 'developing',
          name: 'Developing',
          points: 9,
          percentage: 60,
          description: 'Noticeable formatting inconsistencies or improper citation mechanics.',
          color: 'amber',
        },
        {
          id: 'novice',
          name: 'Novice',
          points: 6,
          percentage: 40,
          description: 'Disorganized structure, poor readability, and missing citations.',
          color: 'rose',
        },
      ],
    },
  ],
}

export const ESSAY_WRITING_RUBRIC: Rubric = {
  id: 'rubric-essay-writing',
  title: 'Critical Essay & Analytical Argumentation Rubric',
  description: 'Evaluates thesis defense, textual evidence synthesis, rhetorical organization, and stylistic mechanics.',
  scaleType: 'percentage',
  totalPoints: 100,
  latePenaltyConfig: DEFAULT_LATE_PENALTY_CONFIG,
  criteria: [
    {
      id: 'crit-thesis',
      title: 'Thesis & Argument Structure',
      description: 'Originality, nuance, and continuous argumentative line of reasoning.',
      weight: 30,
      maxPoints: 30,
      levels: [
        {
          id: 'exemplary',
          name: 'Exemplary',
          points: 30,
          percentage: 100,
          description: 'Compelling, highly nuanced thesis sustained through logical transitions and complex argumentative counterpoints.',
          color: 'emerald',
        },
        {
          id: 'proficient',
          name: 'Proficient',
          points: 24,
          percentage: 80,
          description: 'Clear, defendable thesis with structured argument flow and logical transitions.',
          color: 'blue',
        },
        {
          id: 'developing',
          name: 'Developing',
          points: 18,
          percentage: 60,
          description: 'Thesis is simplistic or predictable; argument wanders from core premise.',
          color: 'amber',
        },
        {
          id: 'novice',
          name: 'Novice',
          points: 12,
          percentage: 40,
          description: 'Thesis is unclear or missing; lacks recognizable logical structure.',
          color: 'rose',
        },
      ],
    },
    {
      id: 'crit-evidence',
      title: 'Evidence & Textual Synthesis',
      description: 'Quality, relevance, and analytical depth of primary and secondary source integration.',
      weight: 40,
      maxPoints: 40,
      levels: [
        {
          id: 'exemplary',
          name: 'Exemplary',
          points: 40,
          percentage: 100,
          description: 'Seamless integration of relevant quotes with penetrating analytical commentary and context.',
          color: 'emerald',
        },
        {
          id: 'proficient',
          name: 'Proficient',
          points: 32,
          percentage: 80,
          description: 'Effective use of textual evidence with sound explanatory analysis.',
          color: 'blue',
        },
        {
          id: 'developing',
          name: 'Developing',
          points: 24,
          percentage: 60,
          description: 'Evidence is quoted without adequate explanation or relies on plot summary.',
          color: 'amber',
        },
        {
          id: 'novice',
          name: 'Novice',
          points: 16,
          percentage: 40,
          description: 'Insufficient or inaccurate evidence; assertions lack textual backing.',
          color: 'rose',
        },
      ],
    },
    {
      id: 'crit-mechanics',
      title: 'Voice, Style & Grammar',
      description: 'Sophistication of academic diction, syntax variation, and grammatical accuracy.',
      weight: 30,
      maxPoints: 30,
      levels: [
        {
          id: 'exemplary',
          name: 'Exemplary',
          points: 30,
          percentage: 100,
          description: 'Elegant academic prose, varied sentence rhythms, and flawless grammar and mechanics.',
          color: 'emerald',
        },
        {
          id: 'proficient',
          name: 'Proficient',
          points: 24,
          percentage: 80,
          description: 'Clear, fluent writing with precise vocabulary and minimal mechanical errors.',
          color: 'blue',
        },
        {
          id: 'developing',
          name: 'Developing',
          points: 18,
          percentage: 60,
          description: 'Repetitive phrasing, awkward syntax, or frequent grammatical missteps that distract the reader.',
          color: 'amber',
        },
        {
          id: 'novice',
          name: 'Novice',
          points: 12,
          percentage: 40,
          description: 'Severe grammatical errors impeding comprehension and clarity.',
          color: 'rose',
        },
      ],
    },
  ],
}

export const CODE_REVIEW_RUBRIC: Rubric = {
  id: 'rubric-code-review',
  title: 'Software Engineering & Architecture Rubric',
  description: 'Evaluates algorithmic efficiency, clean code practices, modularity, test coverage, and documentation.',
  scaleType: 'percentage',
  totalPoints: 100,
  latePenaltyConfig: DEFAULT_LATE_PENALTY_CONFIG,
  criteria: [
    {
      id: 'crit-correctness',
      title: 'Functional Correctness & Algorithmic Efficiency',
      description: 'Passes edge cases, meets computational complexity constraints (Big-O), and handles error states gracefully.',
      weight: 40,
      maxPoints: 40,
      levels: [
        {
          id: 'exemplary',
          name: 'Exemplary',
          points: 40,
          percentage: 100,
          description: 'All edge cases solved with optimal time/space complexity, robust error handling, and zero memory leaks.',
          color: 'emerald',
        },
        {
          id: 'proficient',
          name: 'Proficient',
          points: 32,
          percentage: 80,
          description: 'Core logic functions correctly; handles standard edge cases with minor sub-optimal complexity in secondary routines.',
          color: 'blue',
        },
        {
          id: 'developing',
          name: 'Developing',
          points: 24,
          percentage: 60,
          description: 'Code breaks on boundary conditions or exhibits obvious performance bottlenecks.',
          color: 'amber',
        },
        {
          id: 'novice',
          name: 'Novice',
          points: 16,
          percentage: 40,
          description: 'Fails standard test suites; core requirements incomplete or throwing fatal runtime exceptions.',
          color: 'rose',
        },
      ],
    },
    {
      id: 'crit-modularity',
      title: 'Clean Architecture & Modularity',
      description: 'Separation of concerns, DRY principles, meaningful abstractions, and maintainable type safety.',
      weight: 30,
      maxPoints: 30,
      levels: [
        {
          id: 'exemplary',
          name: 'Exemplary',
          points: 30,
          percentage: 100,
          description: 'Exceptional architectural isolation, decoupled components, clean abstractions, and airtight typing.',
          color: 'emerald',
        },
        {
          id: 'proficient',
          name: 'Proficient',
          points: 24,
          percentage: 80,
          description: 'Logical module breakdown with good function sizing and standard naming conventions.',
          color: 'blue',
        },
        {
          id: 'developing',
          name: 'Developing',
          points: 18,
          percentage: 60,
          description: 'Spaghetti code tendencies, overly monolithic functions, or excessive duplicate code blocks.',
          color: 'amber',
        },
        {
          id: 'novice',
          name: 'Novice',
          points: 12,
          percentage: 40,
          description: 'Unstructured script without modular encapsulation or proper variable scoping.',
          color: 'rose',
        },
      ],
    },
    {
      id: 'crit-tests-docs',
      title: 'Test Coverage & Technical Documentation',
      description: 'Unit/Integration test suites, docstrings, architectural diagrams, and setup instructions.',
      weight: 30,
      maxPoints: 30,
      levels: [
        {
          id: 'exemplary',
          name: 'Exemplary',
          points: 30,
          percentage: 100,
          description: 'Exceeds 90% unit test coverage, comprehensive regression tests, and clear README with architectural justification.',
          color: 'emerald',
        },
        {
          id: 'proficient',
          name: 'Proficient',
          points: 24,
          percentage: 80,
          description: 'Good test coverage for primary happy paths and clear function docstrings.',
          color: 'blue',
        },
        {
          id: 'developing',
          name: 'Developing',
          points: 18,
          percentage: 60,
          description: 'Sparse unit tests; sparse or outdated documentation.',
          color: 'amber',
        },
        {
          id: 'novice',
          name: 'Novice',
          points: 12,
          percentage: 40,
          description: 'No tests provided; undocumented and difficult to verify.',
          color: 'rose',
        },
      ],
    },
  ],
}

export const RUBRIC_PRESETS: Rubric[] = [
  SCIENCE_LAB_RUBRIC,
  ESSAY_WRITING_RUBRIC,
  CODE_REVIEW_RUBRIC,
]

// Calculation Utilities

export function calculateLatePenalty(
  submissionDateStr: string,
  dueDateStr: string,
  config: LatePenaltyConfig,
  rawScore: number
): LatePenaltyCalculation {
  if (!config.enabled || !submissionDateStr || !dueDateStr) {
    return {
      isLate: false,
      hoursLate: 0,
      daysLate: 0,
      penaltyPercent: 0,
      rawScore,
      deductionPoints: 0,
      finalDecayedScore: rawScore,
      decayRateDisplay: `-${config.decayPercentPer24h}% / 24h`,
    }
  }

  const subDate = new Date(submissionDateStr)
  const dueDate = new Date(dueDateStr)
  const diffMs = subDate.getTime() - dueDate.getTime()

  // Within grace period or on time
  const graceMs = config.gracePeriodHours * 3600 * 1000
  if (diffMs <= graceMs) {
    return {
      isLate: false,
      hoursLate: 0,
      daysLate: 0,
      penaltyPercent: 0,
      rawScore,
      deductionPoints: 0,
      finalDecayedScore: rawScore,
      decayRateDisplay: `-${config.decayPercentPer24h}% / 24h`,
    }
  }

  const hoursLate = Math.max(0, Math.ceil(diffMs / (3600 * 1000)))
  // Continuous decay or 24h block decay
  const daysLateFraction = hoursLate / 24
  const rawPenalty = daysLateFraction * config.decayPercentPer24h
  const cappedPenalty = Math.min(rawPenalty, config.maxPenaltyPercent)
  const deductionPoints = Math.round(((rawScore * cappedPenalty) / 100) * 10) / 10
  const finalDecayedScore = Math.max(0, Math.round((rawScore - deductionPoints) * 10) / 10)

  return {
    isLate: true,
    hoursLate,
    daysLate: Math.round(daysLateFraction * 10) / 10,
    penaltyPercent: Math.round(cappedPenalty * 10) / 10,
    rawScore,
    deductionPoints,
    finalDecayedScore,
    decayRateDisplay: `-${config.decayPercentPer24h}% / 24h (Cap: ${config.maxPenaltyPercent}%)`,
  }
}

export function computeRubricScore(
  rubric: Rubric,
  selectedScores: Record<string, string> // criterionId -> levelId
): {
  rawScore: number
  maxPossibleScore: number
  percentage: number
  isComplete: boolean
  criterionBreakdown: Array<{
    criterionId: string
    title: string
    weight: number
    awardedPoints: number
    maxPoints: number
    levelName: string
    levelColor?: string
  }>
} {
  let rawScore = 0
  let maxPossibleScore = 0
  let answeredCount = 0

  const breakdown = rubric.criteria.map((crit) => {
    maxPossibleScore += crit.maxPoints
    const selectedLevelId = selectedScores[crit.id]
    const level = crit.levels.find((l) => l.id === selectedLevelId)

    if (level) {
      answeredCount++
      rawScore += level.points
      return {
        criterionId: crit.id,
        title: crit.title,
        weight: crit.weight,
        awardedPoints: level.points,
        maxPoints: crit.maxPoints,
        levelName: level.name,
        levelColor: level.color,
      }
    }

    return {
      criterionId: crit.id,
      title: crit.title,
      weight: crit.weight,
      awardedPoints: 0,
      maxPoints: crit.maxPoints,
      levelName: 'Unscored',
      levelColor: 'gray',
    }
  })

  const isComplete = answeredCount === rubric.criteria.length
  const percentage = maxPossibleScore > 0 ? Math.round((rawScore / maxPossibleScore) * 1000) / 10 : 0

  return {
    rawScore,
    maxPossibleScore,
    percentage,
    isComplete,
    criterionBreakdown: breakdown,
  }
}

/**
 * Generate structured, contextual AI feedback based on analytical rubric matrix scores
 */
export function draftAIFeedbackForSubmission(
  studentName: string,
  rubric: Rubric,
  selectedScores: Record<string, string>,
  penaltyCalc?: LatePenaltyCalculation,
  submissionContext?: string
): string {
  const { criterionBreakdown, percentage, isComplete } = computeRubricScore(rubric, selectedScores)

  const exemplaryItems = criterionBreakdown.filter((c) => c.awardedPoints / c.maxPoints >= 0.85)
  const proficientItems = criterionBreakdown.filter((c) => c.awardedPoints / c.maxPoints >= 0.7 && c.awardedPoints / c.maxPoints < 0.85)
  const growthItems = criterionBreakdown.filter((c) => c.awardedPoints / c.maxPoints < 0.7 && c.levelName !== 'Unscored')

  const parts: string[] = []

  // Greeting & Overall Summary
  if (percentage >= 85) {
    parts.push(`Excellent work on this assignment, ${studentName}! Your submission demonstrates strong analytical rigor and a clear mastery of the core competencies evaluated. (Overall: ${percentage.toFixed(1)}%)`)
  } else if (percentage >= 70) {
    parts.push(`Solid effort on this assignment, ${studentName}. You have established a good foundational grasp of key concepts, with specific opportunities to deepen your analytical execution. (Overall: ${percentage.toFixed(1)}%)`)
  } else {
    parts.push(`Thank you for submitting your work, ${studentName}. While you have made a good start, there are several key areas where further development and revisions are necessary to meet the course benchmarks. (Overall: ${percentage.toFixed(1)}%)`)
  }

  // Key Strengths
  if (exemplaryItems.length > 0) {
    parts.push(`\n**Notable Strengths:**`)
    exemplaryItems.forEach((item) => {
      const crit = rubric.criteria.find((c) => c.id === item.criterionId)
      const level = crit?.levels.find((l) => l.points === item.awardedPoints)
      parts.push(`• **${item.title}**: Demonstrated exceptional performance (${item.awardedPoints}/${item.maxPoints} pts). ${level?.description || 'Met exemplary standards.'}`)
    })
  }

  // Proficient Areas
  if (proficientItems.length > 0) {
    parts.push(`\n**Proficient Execution:**`)
    proficientItems.forEach((item) => {
      parts.push(`• **${item.title}** (${item.awardedPoints}/${item.maxPoints} pts): Meets expected course standards with solid execution.`)
    })
  }

  // Actionable Areas for Growth
  if (growthItems.length > 0) {
    parts.push(`\n**Actionable Recommendations for Growth:**`)
    growthItems.forEach((item) => {
      const crit = rubric.criteria.find((c) => c.id === item.criterionId)
      const level = crit?.levels.find((l) => l.points === item.awardedPoints)
      parts.push(`• **${item.title}** (${item.awardedPoints}/${item.maxPoints} pts): ${level?.description || 'Needs targeted improvement.'} Consider revising this section by strengthening supporting evidence and systematic error verification.`)
    })
  }

  // Late submission note if applicable
  if (penaltyCalc && penaltyCalc.isLate) {
    parts.push(`\n*Note on Submission Timeline: This work was submitted ${penaltyCalc.hoursLate} hours past the deadline. An automated decay penalty of ${penaltyCalc.penaltyPercent}% (-${penaltyCalc.deductionPoints} pts) was applied per course policy.*`)
  }

  parts.push(`\nKeep up the dedicated effort. Feel free to reach out during office hours if you would like to discuss any of these rubric points in detail!`)

  return parts.join('\n')
}
