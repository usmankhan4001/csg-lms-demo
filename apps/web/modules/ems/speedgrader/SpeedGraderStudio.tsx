'use client'

import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import {
  ChevronLeft,
  ChevronRight,
  Sparkles,
  Award,
  Clock,
  CheckCircle2,
  AlertTriangle,
  FileText,
  Video,
  Code2,
  BookOpen,
  Send,
  Save,
  RotateCcw,
  Edit3,
  Check,
  RefreshCw,
  Maximize2,
  Download,
  Copy,
  Sliders,
  Keyboard,
  Eye,
  MessageSquare,
  HelpCircle,
  X,
  Play,
  Pause,
  Volume2,
  ExternalLink,
  ShieldCheck,
  User,
  Layers,
} from 'lucide-react'
import {
  Rubric,
  SpeedGraderStudentSubmission,
  LatePenaltyCalculation,
  SubmissionContentType,
  SubmissionAnnotation,
} from './types'
import {
  SCIENCE_LAB_RUBRIC,
  calculateLatePenalty,
  computeRubricScore,
  draftAIFeedbackForSubmission,
} from './rubric-presets'
import { RubricEditor } from './RubricEditor'
import { LH_CARD, LH_PRIMARY_BUTTON, LH_SECONDARY_BUTTON } from '@/components/widgets/lh-styles'

export interface SpeedGraderStudioProps {
  rubric?: Rubric
  submissions?: SpeedGraderStudentSubmission[]
  assignmentTitle?: string
  dueDate?: string
  onSaveGrade?: (submissionId: string, data: Partial<SpeedGraderStudentSubmission>) => void
  onClose?: () => void
}

// Sample mock submissions for demonstration / default state
const MOCK_SUBMISSIONS: SpeedGraderStudentSubmission[] = [
  {
    id: 'sub-1',
    userId: 'usr-1',
    studentName: 'Alexandria Rivera',
    studentUsername: 'arivera',
    studentEmail: 'arivera@csg-edu.org',
    submissionDate: '2026-09-14T18:30:00Z',
    dueDate: '2026-09-14T23:59:00Z',
    status: 'SUBMITTED',
    attemptNumber: 1,
    contentType: 'rich_text',
    content: {
      text: `# Investigation of Enzymatic Reaction Rates Under Variable Thermal Gradients

## 1. Abstract & Theoretical Framework
This investigation examines the catalytic kinetics of bovine catalase in decomposing hydrogen peroxide ($H_2O_2$) across a regulated thermal continuum ($10^\\circ\\text{C}$ to $65^\\circ\\text{C}$). We hypothesized that catalytic turnover rates would conform to the Arrhenius transition-state model up to a critical thermal denaturation threshold at $42.5^\\circ\\text{C}$, beyond which irreversible tertiary conformational collapse would precipitate an abrupt cessation of enzymatic activity.

## 2. Experimental Methodology
Assays were conducted using spectrophotometric absorbance at $\\lambda = 240\\,\\text{nm}$. Substrate concentrations were standardized at $10\\,\\text{mM}\\,H_2O_2$ in $50\\,\\text{mM}$ sodium phosphate buffer (pH 7.0). Reaction vessels were equilibrated for 15 minutes in circulating water baths prior to enzyme injection ($0.05\\,\\text{mg/mL}$ final concentration). Initial reaction velocities ($V_0$) were derived from the linear kinetic window over the initial 30 seconds.

## 3. Quantitative Data & Statistical Analysis
| Temperature (°C) | Mean $V_0$ ($\mu\text{mol}\cdot\text{s}^{-1}$) | Standard Error ($\pm\text{SE}$) | $p$-value (vs $25^\circ\text{C}$) |
|---|---|---|---|
| 10.0 | 1.42 | 0.08 | < 0.01 |
| 20.0 | 2.89 | 0.12 | < 0.05 |
| 30.0 | 4.95 | 0.15 | - |
| 40.0 | 6.81 | 0.19 | < 0.01 |
| 50.0 | 1.10 | 0.22 | < 0.001 |
| 60.0 | 0.04 | 0.01 | < 0.0001 |

Arrhenius linearization yielded an apparent activation energy $E_a = 34.2\\,\\text{kJ/mol}$ ($R^2 = 0.984$). The thermal denaturation transition was observed between $44.0^\\circ\\text{C}$ and $48.5^\\circ\\text{C}$, corroborated by circular dichroism spectroscopy demonstrating $\\alpha$-helical unwinding.

## 4. Synthesis & Systematic Errors
The empirical observations validate our initial hypothesis. Minor systematic errors arose from evaporative condensation at higher thermal points ($>55^\\circ\\text{C}$), which slightly altered buffer osmolarity. Future extensions will employ pressurized optical cuvettes to prevent meniscus distortion.`,
    },
    rubricScores: {
      'crit-hypothesis': 'exemplary',
      'crit-data-analysis': 'exemplary',
      'crit-conclusion': 'proficient',
      'crit-formatting': 'exemplary',
    },
    teacherFeedback: '',
  },
  {
    id: 'sub-2',
    userId: 'usr-2',
    studentName: 'Marcus Vance',
    studentUsername: 'mvance',
    studentEmail: 'mvance@csg-edu.org',
    submissionDate: '2026-09-16T08:15:00Z', // 32 hours late
    dueDate: '2026-09-14T23:59:00Z',
    status: 'LATE',
    attemptNumber: 1,
    contentType: 'code',
    content: {
      codeLanguage: 'python',
      code: `"""
Enzyme Kinetics Computational Simulation Engine
Author: Marcus Vance
Evaluates Arrhenius rate constants and Michaelis-Menten kinetics.
"""

import numpy as np
import scipy.optimize as opt
import matplotlib.pyplot as plt

class CatalaseSimulation:
    def __init__(self, e_a: float = 34200.0, r_const: float = 8.314):
        self.e_a = e_a
        self.r_const = r_const
        self.temps_c = np.array([10.0, 20.0, 30.0, 40.0, 50.0, 60.0])
        self.temps_k = self.temps_c + 273.15
        self.observed_rates = np.array([1.42, 2.89, 4.95, 6.81, 1.10, 0.04])

    def arrhenius_model(self, t_k: np.ndarray, a_preexp: float) -> np.ndarray:
        """Calculates theoretical rate constant based on transition state theory."""
        return a_preexp * np.exp(-self.e_a / (self.r_const * t_k))

    def fit_parameters(self):
        """Fit empirical parameters up to denaturation optimum."""
        valid_mask = self.temps_c <= 40.0
        popt, pcov = opt.curve_fit(
            self.arrhenius_model,
            self.temps_k[valid_mask],
            self.observed_rates[valid_mask],
            p0=[1e6]
        )
        return popt[0], pcov

if __name__ == "__main__":
    sim = CatalaseSimulation()
    a_fit, _ = sim.fit_parameters()
    print(f"Computed Pre-exponential Factor A: {a_fit:.2e} s^-1")
`,
    },
    rubricScores: {
      'crit-hypothesis': 'proficient',
      'crit-data-analysis': 'exemplary',
      'crit-conclusion': 'developing',
      'crit-formatting': 'proficient',
    },
    teacherFeedback: '',
  },
  {
    id: 'sub-3',
    userId: 'usr-3',
    studentName: 'Elena Rostova',
    studentUsername: 'erostova',
    studentEmail: 'erostova@csg-edu.org',
    submissionDate: '2026-09-14T21:45:00Z',
    dueDate: '2026-09-14T23:59:00Z',
    status: 'SUBMITTED',
    attemptNumber: 1,
    contentType: 'pdf',
    content: {
      pdfUrl: 'https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf',
      text: 'Lab Report Document: Comparative Analysis of Catalase Kinetics (Elena Rostova - Chem 301). Submitted via embedded PDF.',
    },
    rubricScores: {
      'crit-hypothesis': 'exemplary',
      'crit-data-analysis': 'proficient',
      'crit-conclusion': 'exemplary',
      'crit-formatting': 'exemplary',
    },
    teacherFeedback: '',
  },
  {
    id: 'sub-4',
    userId: 'usr-4',
    studentName: 'Devon Chen',
    studentUsername: 'dchen',
    studentEmail: 'dchen@csg-edu.org',
    submissionDate: '2026-09-14T22:10:00Z',
    dueDate: '2026-09-14T23:59:00Z',
    status: 'SUBMITTED',
    attemptNumber: 1,
    contentType: 'video',
    content: {
      videoUrl: 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4',
      videoDurationSeconds: 184,
      text: 'Oral Presentation & Lab Bench Demonstration: Real-time Spectrophotometric Assay walkthrough and data collection methodology.',
    },
    rubricScores: {
      'crit-hypothesis': 'proficient',
      'crit-data-analysis': 'developing',
      'crit-conclusion': 'proficient',
      'crit-formatting': 'developing',
    },
    teacherFeedback: '',
  },
]

export const SpeedGraderStudio: React.FC<SpeedGraderStudioProps> = ({
  rubric: initialRubric = SCIENCE_LAB_RUBRIC,
  submissions: initialSubmissions = MOCK_SUBMISSIONS,
  assignmentTitle = 'Lab Report: Enzyme Kinetics & Thermal Denaturation',
  dueDate = '2026-09-14T23:59:00Z',
  onSaveGrade,
  onClose,
}) => {
  const [rubric, setRubric] = useState<Rubric>(initialRubric)
  const [submissions, setSubmissions] = useState<SpeedGraderStudentSubmission[]>(initialSubmissions)
  const [currentIndex, setCurrentIndex] = useState<number>(0)
  const [activeCriterionId, setActiveCriterionId] = useState<string>(
    initialRubric.criteria[0]?.id || ''
  )
  const [activeTab, setActiveTab] = useState<'submission' | 'rubric-editor'>('submission')
  const [showShortcutsModal, setShowShortcutsModal] = useState<boolean>(false)
  const [feedbackInput, setFeedbackInput] = useState<string>('')
  const [aiDraft, setAiDraft] = useState<string>('')
  const [isDraftingAI, setIsDraftingAI] = useState<boolean>(false)
  const [isEditingDraft, setIsEditingDraft] = useState<boolean>(false)
  const [saveSuccessNotification, setSaveSuccessNotification] = useState<string | null>(null)
  const [videoPlaying, setVideoPlaying] = useState<boolean>(false)
  const [videoPlaybackRate, setVideoPlaybackRate] = useState<number>(1.0)
  const [activeViewerType, setActiveViewerType] = useState<SubmissionContentType>('rich_text')

  const videoRef = useRef<HTMLVideoElement>(null)
  const currentSubmission = submissions[currentIndex] || submissions[0]

  // Synchronize state when switching current student
  useEffect(() => {
    if (currentSubmission) {
      setFeedbackInput(currentSubmission.teacherFeedback || '')
      setAiDraft(currentSubmission.aiDraftedFeedback || '')
      setActiveViewerType(currentSubmission.contentType)
    }
  }, [currentIndex, currentSubmission])

  // Active criterion object
  const activeCriterion = useMemo(() => {
    return (
      rubric.criteria.find((c) => c.id === activeCriterionId) ||
      rubric.criteria[0]
    )
  }, [rubric.criteria, activeCriterionId])

  // Rubric Score Computation
  const rubricScoreData = useMemo(() => {
    return computeRubricScore(rubric, currentSubmission?.rubricScores || {})
  }, [rubric, currentSubmission?.rubricScores])

  // Late Penalty Decay Calculation
  const latePenaltyCalc: LatePenaltyCalculation = useMemo(() => {
    if (!currentSubmission) {
      return {
        isLate: false,
        hoursLate: 0,
        daysLate: 0,
        penaltyPercent: 0,
        rawScore: 0,
        deductionPoints: 0,
        finalDecayedScore: 0,
        decayRateDisplay: '',
      }
    }
    return calculateLatePenalty(
      currentSubmission.submissionDate,
      currentSubmission.dueDate || dueDate,
      rubric.latePenaltyConfig,
      rubricScoreData.rawScore
    )
  }, [currentSubmission, dueDate, rubric.latePenaltyConfig, rubricScoreData.rawScore])

  // Calculate letter grade
  const letterGrade = useMemo(() => {
    const pct = (latePenaltyCalc.finalDecayedScore / (rubricScoreData.maxPossibleScore || 100)) * 100
    if (pct >= 90) return 'A'
    if (pct >= 80) return 'B'
    if (pct >= 70) return 'C'
    if (pct >= 60) return 'D'
    return 'F'
  }, [latePenaltyCalc.finalDecayedScore, rubricScoreData.maxPossibleScore])

  // Select a rubric level for the active criterion
  const handleSelectLevel = useCallback(
    (criterionId: string, levelId: string) => {
      setSubmissions((prev) => {
        const next = [...prev]
        const sub = { ...next[currentIndex] }
        sub.rubricScores = {
          ...(sub.rubricScores || {}),
          [criterionId]: levelId,
        }
        next[currentIndex] = sub
        return next
      })
    },
    [currentIndex]
  )

  // Navigate next / previous student
  const handleNextStudent = useCallback(() => {
    if (currentIndex < submissions.length - 1) {
      setCurrentIndex((prev) => prev + 1)
    }
  }, [currentIndex, submissions.length])

  const handlePrevStudent = useCallback(() => {
    if (currentIndex > 0) {
      setCurrentIndex((prev) => prev - 1)
    }
  }, [currentIndex])

  // Save current student grade & advance
  const handleSaveAndAdvance = useCallback(() => {
    if (!currentSubmission) return

    const updatedData: Partial<SpeedGraderStudentSubmission> = {
      rubricScores: currentSubmission.rubricScores,
      teacherFeedback: feedbackInput,
      rawScore: rubricScoreData.rawScore,
      finalScore: latePenaltyCalc.finalDecayedScore,
      status: 'GRADED',
      gradedAt: new Date().toISOString(),
    }

    if (onSaveGrade) {
      onSaveGrade(currentSubmission.id, updatedData)
    }

    setSaveSuccessNotification(`Grade saved for ${currentSubmission.studentName}`)
    setTimeout(() => setSaveSuccessNotification(null), 2500)

    if (currentIndex < submissions.length - 1) {
      setCurrentIndex((prev) => prev + 1)
    }
  }, [
    currentSubmission,
    feedbackInput,
    rubricScoreData.rawScore,
    latePenaltyCalc.finalDecayedScore,
    onSaveGrade,
    currentIndex,
    submissions.length,
  ])

  // AI Feedback Generation
  const handleGenerateAIFeedback = () => {
    setIsDraftingAI(true)
    setTimeout(() => {
      const generated = draftAIFeedbackForSubmission(
        currentSubmission.studentName,
        rubric,
        currentSubmission.rubricScores || {},
        latePenaltyCalc,
        currentSubmission.content.text
      )
      setAiDraft(generated)
      setIsDraftingAI(false)
    }, 450)
  }

  const handleAcceptAIDraft = () => {
    setFeedbackInput(aiDraft)
    setSaveSuccessNotification('AI Feedback applied to remarks')
    setTimeout(() => setSaveSuccessNotification(null), 2000)
  }

  // Keyboard Shortcuts Listener
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ignore keyboard shortcuts if typing inside input / textarea
      const target = e.target as HTMLElement
      if (
        target.tagName === 'INPUT' ||
        target.tagName === 'TEXTAREA' ||
        target.isContentEditable
      ) {
        // Allow Cmd+Enter or Ctrl+Enter even in textareas
        if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
          e.preventDefault()
          handleSaveAndAdvance()
        }
        return
      }

      // Keys 1 - 4: Rubric Levels on active criterion
      if (['1', '2', '3', '4'].includes(e.key) && activeCriterion) {
        e.preventDefault()
        const levelIndex = parseInt(e.key, 10) - 1
        const level = activeCriterion.levels[levelIndex]
        if (level) {
          handleSelectLevel(activeCriterion.id, level.id)
        }
      }

      // Arrow Up / Down: Switch active criteria
      if (e.key === 'ArrowUp') {
        e.preventDefault()
        const critIdx = rubric.criteria.findIndex((c) => c.id === activeCriterionId)
        if (critIdx > 0) {
          setActiveCriterionId(rubric.criteria[critIdx - 1].id)
        }
      }

      if (e.key === 'ArrowDown') {
        e.preventDefault()
        const critIdx = rubric.criteria.findIndex((c) => c.id === activeCriterionId)
        if (critIdx < rubric.criteria.length - 1) {
          setActiveCriterionId(rubric.criteria[critIdx + 1].id)
        }
      }

      // Arrow Left / Right or '[' / ']': Switch Student
      if (e.key === 'ArrowLeft' || e.key === '[') {
        e.preventDefault()
        handlePrevStudent()
      }
      if (e.key === 'ArrowRight' || e.key === ']') {
        e.preventDefault()
        handleNextStudent()
      }

      // Enter: Save and next
      if (e.key === 'Enter') {
        e.preventDefault()
        handleSaveAndAdvance()
      }

      // '?' or '/' with Shift: Toggle shortcuts cheat sheet
      if (e.key === '?' || (e.shiftKey && e.key === '/')) {
        e.preventDefault()
        setShowShortcutsModal((prev) => !prev)
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [
    activeCriterion,
    activeCriterionId,
    rubric.criteria,
    handleSelectLevel,
    handleNextStudent,
    handlePrevStudent,
    handleSaveAndAdvance,
  ])

  // Video Speed Controller
  const handleSetVideoSpeed = (rate: number) => {
    setVideoPlaybackRate(rate)
    if (videoRef.current) {
      videoRef.current.playbackRate = rate
    }
  }

  return (
    <div className="flex flex-col w-full h-screen bg-[#f3f4f6] text-gray-900 overflow-hidden select-none font-sans">
      {/* Top Navbar Header */}
      <header className="h-14 bg-black text-white px-4 sm:px-6 flex items-center justify-between shrink-0 shadow-md z-20">
        <div className="flex items-center space-x-3 min-w-0">
          <div className="p-1.5 bg-white/10 rounded-lg">
            <Award size={18} className="text-amber-400" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center space-x-2">
              <span className="text-xs font-mono font-bold uppercase tracking-wider text-amber-400 bg-amber-400/10 px-2 py-0.5 rounded">
                SpeedGrader 2.0
              </span>
              <h1 className="text-sm font-bold truncate text-white">{assignmentTitle}</h1>
            </div>
          </div>
        </div>

        {/* Center / Navigation Bar */}
        <div className="flex items-center space-x-3">
          <div className="flex items-center bg-white/10 rounded-lg p-1 space-x-1">
            <button
              onClick={handlePrevStudent}
              disabled={currentIndex === 0}
              className="p-1.5 text-white/80 hover:text-white hover:bg-white/10 disabled:opacity-30 rounded transition-colors"
              title="Previous Student (Left Arrow / [)"
            >
              <ChevronLeft size={16} />
            </button>

            <span className="text-xs font-semibold px-2 text-white">
              Student {currentIndex + 1} of {submissions.length}
            </span>

            <button
              onClick={handleNextStudent}
              disabled={currentIndex === submissions.length - 1}
              className="p-1.5 text-white/80 hover:text-white hover:bg-white/10 disabled:opacity-30 rounded transition-colors"
              title="Next Student (Right Arrow / ])"
            >
              <ChevronRight size={16} />
            </button>
          </div>

          {/* Quick Shortcuts Pill */}
          <button
            onClick={() => setShowShortcutsModal(true)}
            className="flex items-center space-x-1.5 bg-white/10 hover:bg-white/20 text-xs font-semibold px-3 py-1.5 rounded-lg transition-colors"
          >
            <Keyboard size={14} className="text-emerald-400" />
            <span className="hidden sm:inline">Shortcuts (1-4, Enter)</span>
          </button>

          {/* Close button if provided */}
          {onClose && (
            <button
              onClick={onClose}
              className="p-1.5 text-white/70 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
              title="Close SpeedGrader"
            >
              <X size={18} />
            </button>
          )}
        </div>
      </header>

      {/* Main Split-Screen Studio Workspace */}
      <div className="flex flex-1 w-full overflow-hidden">
        {/* LEFT COLUMN: Multi-Modal Submission Viewer */}
        <section className="w-1/2 flex flex-col bg-white border-r border-gray-200 overflow-hidden">
          {/* Submission Format Switcher & Meta Bar */}
          <div className="h-12 bg-gray-50 border-b border-gray-200 px-4 flex items-center justify-between shrink-0">
            <div className="flex items-center space-x-2">
              <span className="text-xs font-bold text-gray-500 uppercase tracking-wider">
                Submission Viewer:
              </span>
              <div className="flex items-center bg-gray-200/70 p-0.5 rounded-lg">
                <button
                  onClick={() => setActiveViewerType('rich_text')}
                  className={`flex items-center space-x-1 px-2.5 py-1 rounded-md text-xs font-bold transition-all ${
                    activeViewerType === 'rich_text'
                      ? 'bg-white text-black shadow-sm'
                      : 'text-gray-600 hover:text-black'
                  }`}
                >
                  <FileText size={12} />
                  <span>Rich Text</span>
                </button>
                <button
                  onClick={() => setActiveViewerType('pdf')}
                  className={`flex items-center space-x-1 px-2.5 py-1 rounded-md text-xs font-bold transition-all ${
                    activeViewerType === 'pdf'
                      ? 'bg-white text-black shadow-sm'
                      : 'text-gray-600 hover:text-black'
                  }`}
                >
                  <BookOpen size={12} />
                  <span>PDF Doc</span>
                </button>
                <button
                  onClick={() => setActiveViewerType('code')}
                  className={`flex items-center space-x-1 px-2.5 py-1 rounded-md text-xs font-bold transition-all ${
                    activeViewerType === 'code'
                      ? 'bg-white text-black shadow-sm'
                      : 'text-gray-600 hover:text-black'
                  }`}
                >
                  <Code2 size={12} />
                  <span>Code</span>
                </button>
                <button
                  onClick={() => setActiveViewerType('video')}
                  className={`flex items-center space-x-1 px-2.5 py-1 rounded-md text-xs font-bold transition-all ${
                    activeViewerType === 'video'
                      ? 'bg-white text-black shadow-sm'
                      : 'text-gray-600 hover:text-black'
                  }`}
                >
                  <Video size={12} />
                  <span>Video</span>
                </button>
              </div>
            </div>

            <div className="flex items-center space-x-2 text-xs text-gray-500 font-medium">
              <span className="bg-gray-100 px-2 py-0.5 rounded text-[11px] font-mono">
                Attempt #{currentSubmission.attemptNumber || 1}
              </span>
            </div>
          </div>

          {/* Submission Render Area */}
          <div className="flex-1 overflow-y-auto p-6 bg-white selection:bg-amber-100">
            {activeViewerType === 'rich_text' && (
              <div className="max-w-3xl mx-auto space-y-4 text-gray-800 leading-relaxed font-serif text-sm">
                <div className="bg-amber-50/50 border border-amber-200 rounded-lg p-3 font-sans text-xs text-amber-900 flex items-center justify-between">
                  <span>
                    Word Count: ~{(currentSubmission.content.text || '').split(/\s+/).length} words • Reading Time: ~2 min
                  </span>
                  <span className="font-semibold text-[11px] text-amber-700">Original Submission</span>
                </div>
                <div className="whitespace-pre-wrap font-sans text-xs leading-relaxed text-gray-800">
                  {currentSubmission.content.text || 'No textual content submitted.'}
                </div>
              </div>
            )}

            {activeViewerType === 'pdf' && (
              <div className="h-full flex flex-col items-center justify-center space-y-4 bg-gray-50 rounded-xl border border-dashed border-gray-300 p-8">
                <div className="p-4 bg-rose-50 text-rose-600 rounded-full">
                  <FileText size={36} />
                </div>
                <div className="text-center space-y-1">
                  <h3 className="text-sm font-bold text-gray-800">
                    PDF Document Attached
                  </h3>
                  <p className="text-xs text-gray-500 max-w-sm">
                    {currentSubmission.content.pdfUrl || 'Lab_Report_Submission_Draft_Final.pdf'}
                  </p>
                </div>
                <div className="flex items-center space-x-2">
                  <a
                    href={currentSubmission.content.pdfUrl || '#'}
                    target="_blank"
                    rel="noreferrer"
                    className="bg-black hover:bg-gray-800 text-white text-xs font-bold px-4 py-2 rounded-lg flex items-center space-x-1.5 shadow-sm"
                  >
                    <Eye size={13} />
                    <span>Open In New Tab</span>
                  </a>
                </div>
              </div>
            )}

            {activeViewerType === 'code' && (
              <div className="h-full flex flex-col rounded-xl overflow-hidden border border-gray-800 bg-[#1e1e1e] text-gray-200">
                <div className="h-9 bg-[#2d2d2d] px-3 flex items-center justify-between border-b border-gray-700 text-xs font-mono">
                  <div className="flex items-center space-x-2">
                    <span className="w-2.5 h-2.5 rounded-full bg-red-500 inline-block" />
                    <span className="w-2.5 h-2.5 rounded-full bg-yellow-500 inline-block" />
                    <span className="w-2.5 h-2.5 rounded-full bg-green-500 inline-block" />
                    <span className="text-gray-400 ms-2 font-bold">
                      {currentSubmission.content.codeLanguage || 'python'}.py
                    </span>
                  </div>
                  <button
                    onClick={() => navigator.clipboard.writeText(currentSubmission.content.code || '')}
                    className="text-gray-400 hover:text-white flex items-center space-x-1 text-[11px]"
                  >
                    <Copy size={12} />
                    <span>Copy Code</span>
                  </button>
                </div>
                <div className="flex-1 overflow-auto p-4 font-mono text-xs leading-5">
                  <pre className="text-emerald-400 whitespace-pre-wrap">
                    {currentSubmission.content.code || '// No code submitted'}
                  </pre>
                </div>
              </div>
            )}

            {activeViewerType === 'video' && (
              <div className="h-full flex flex-col items-center justify-center space-y-4 bg-gray-900 rounded-xl p-6 text-white">
                <div className="w-full aspect-video bg-black rounded-lg overflow-hidden relative flex items-center justify-center">
                  <video
                    ref={videoRef}
                    src={currentSubmission.content.videoUrl}
                    controls
                    className="w-full h-full object-contain"
                  />
                </div>
                {/* Custom Video Controls Bar */}
                <div className="flex items-center space-x-3 text-xs bg-white/10 px-4 py-2 rounded-xl">
                  <span className="font-bold text-gray-300">Playback Speed:</span>
                  {[0.75, 1.0, 1.25, 1.5, 2.0].map((rate) => (
                    <button
                      key={rate}
                      onClick={() => handleSetVideoSpeed(rate)}
                      className={`px-2 py-0.5 rounded font-bold transition-colors ${
                        videoPlaybackRate === rate ? 'bg-amber-400 text-black' : 'hover:bg-white/20 text-white'
                      }`}
                    >
                      {rate}x
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </section>

        {/* RIGHT COLUMN: Interactive Analytical Rubric Matrix & Evaluation Panel */}
        <section className="w-1/2 flex flex-col bg-[#f8f8f8] overflow-y-auto">
          {/* Student Profile Card & Late Penalty Decay Banner */}
          <div className="p-5 bg-white border-b border-gray-200 space-y-4 shadow-sm">
            <div className="flex items-start justify-between">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 rounded-full bg-gradient-to-tr from-black to-gray-700 text-white font-bold flex items-center justify-center text-sm shadow">
                  {currentSubmission.studentName
                    .split(' ')
                    .map((n) => n[0])
                    .join('')}
                </div>
                <div>
                  <h2 className="text-base font-bold text-gray-900 leading-tight">
                    {currentSubmission.studentName}
                  </h2>
                  <p className="text-xs text-gray-400 font-medium">
                    {currentSubmission.studentEmail} • @{currentSubmission.studentUsername}
                  </p>
                </div>
              </div>

              {/* Status Chip */}
              <div className="flex items-center space-x-2">
                <span
                  className={`text-xs font-bold px-2.5 py-1 rounded-full flex items-center space-x-1.5 ${
                    currentSubmission.status === 'LATE'
                      ? 'bg-rose-50 text-rose-700 border border-rose-200'
                      : currentSubmission.status === 'GRADED'
                      ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                      : 'bg-blue-50 text-blue-700 border border-blue-200'
                  }`}
                >
                  <Clock size={12} />
                  <span>{currentSubmission.status}</span>
                </span>
              </div>
            </div>

            {/* Late Penalty Decay Banner */}
            {latePenaltyCalc.isLate ? (
              <div className="bg-rose-50 border border-rose-200 rounded-xl p-3 flex items-center justify-between text-xs">
                <div className="flex items-center space-x-2.5">
                  <div className="p-1.5 bg-rose-600 text-white rounded-lg">
                    <AlertTriangle size={15} />
                  </div>
                  <div>
                    <span className="font-bold text-rose-950 block">
                      Late Decay Applied ({latePenaltyCalc.decayRateDisplay})
                    </span>
                    <span className="text-rose-700 text-[11px]">
                      Submitted {latePenaltyCalc.hoursLate} hrs overdue ({latePenaltyCalc.daysLate} days) • -
                      {latePenaltyCalc.penaltyPercent}% penalty (-{latePenaltyCalc.deductionPoints} pts)
                    </span>
                  </div>
                </div>
                <div className="text-right">
                  <span className="text-[10px] uppercase font-bold text-rose-400 block">Decayed Total</span>
                  <span className="text-sm font-extrabold text-rose-900">
                    {latePenaltyCalc.finalDecayedScore} / {rubricScoreData.maxPossibleScore} pts
                  </span>
                </div>
              </div>
            ) : (
              <div className="bg-emerald-50/70 border border-emerald-200/60 rounded-xl p-2.5 flex items-center justify-between text-xs text-emerald-800">
                <div className="flex items-center space-x-2">
                  <ShieldCheck size={15} className="text-emerald-600" />
                  <span className="font-semibold text-emerald-900">
                    On-Time Submission: Full credit eligible (Zero penalty decay)
                  </span>
                </div>
                <span className="text-[11px] font-bold text-emerald-700">
                  {rubricScoreData.rawScore} / {rubricScoreData.maxPossibleScore} pts
                </span>
              </div>
            )}
          </div>

          {/* Criteria Matrix Scoring List */}
          <div className="p-5 space-y-4 flex-1">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-gray-700 uppercase tracking-wider flex items-center space-x-1.5">
                <Award size={14} className="text-amber-500" />
                <span>Analytical Rubric Matrix (Keyboard: 1-4, Arrows)</span>
              </span>
              <span className="text-xs font-bold text-gray-500">
                Progress: {rubricScoreData.criterionBreakdown.filter((c) => c.levelName !== 'Unscored').length} /{' '}
                {rubric.criteria.length} Scored
              </span>
            </div>

            <div className="space-y-3">
              {rubric.criteria.map((crit, idx) => {
                const isFocused = crit.id === activeCriterionId
                const selectedLevelId = currentSubmission.rubricScores?.[crit.id]

                return (
                  <div
                    key={crit.id}
                    onClick={() => setActiveCriterionId(crit.id)}
                    className={`rounded-xl p-4 transition-all bg-white nice-shadow cursor-pointer ${
                      isFocused ? 'ring-2 ring-black' : 'hover:border-gray-300'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center space-x-2">
                        <span className="text-[10px] font-mono font-bold bg-gray-100 text-gray-800 px-1.5 py-0.5 rounded">
                          C{idx + 1}
                        </span>
                        <h3 className="text-xs font-bold text-gray-900">{crit.title}</h3>
                      </div>
                      <span className="text-xs font-bold text-gray-500">
                        Weight: {crit.weight}% (Max {crit.maxPoints} pts)
                      </span>
                    </div>

                    <p className="text-[11px] text-gray-500 mb-3 line-clamp-1">{crit.description}</p>

                    {/* 4 Interactive Level Tiles (Exemplary, Proficient, Developing, Novice) */}
                    <div className="grid grid-cols-4 gap-2">
                      {crit.levels.map((level, lvlIdx) => {
                        const isSelected = selectedLevelId === level.id
                        const keyNum = lvlIdx + 1

                        const levelColorMap: Record<
                          string,
                          { bgActive: string; textActive: string; borderActive: string }
                        > = {
                          exemplary: {
                            bgActive: 'bg-emerald-600',
                            textActive: 'text-white',
                            borderActive: 'border-emerald-600',
                          },
                          proficient: {
                            bgActive: 'bg-blue-600',
                            textActive: 'text-white',
                            borderActive: 'border-blue-600',
                          },
                          developing: {
                            bgActive: 'bg-amber-500',
                            textActive: 'text-white',
                            borderActive: 'border-amber-500',
                          },
                          novice: {
                            bgActive: 'bg-rose-600',
                            textActive: 'text-white',
                            borderActive: 'border-rose-600',
                          },
                        }
                        const style = levelColorMap[level.id] || {
                          bgActive: 'bg-black',
                          textActive: 'text-white',
                          borderActive: 'border-black',
                        }

                        return (
                          <button
                            key={level.id}
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation()
                              setActiveCriterionId(crit.id)
                              handleSelectLevel(crit.id, level.id)
                            }}
                            className={`flex flex-col text-left p-2.5 rounded-lg border text-xs transition-all relative ${
                              isSelected
                                ? `${style.bgActive} ${style.textActive} shadow-md`
                                : 'bg-gray-50/80 border-gray-200 text-gray-700 hover:bg-gray-100 hover:border-gray-300'
                            }`}
                          >
                            <div className="flex items-center justify-between w-full mb-1">
                              <span
                                className={`text-[9px] font-mono px-1 py-0.2 rounded font-bold ${
                                  isSelected ? 'bg-white/20 text-white' : 'bg-gray-200 text-gray-700'
                                }`}
                              >
                                #{keyNum}
                              </span>
                              <span className="font-extrabold text-[11px]">{level.points} pts</span>
                            </div>
                            <span className="font-bold text-[11px] truncate">{level.name}</span>
                            <span
                              className={`text-[9px] line-clamp-2 mt-1 ${
                                isSelected ? 'text-white/80' : 'text-gray-500'
                              }`}
                            >
                              {level.description}
                            </span>
                          </button>
                        )
                      })}
                    </div>
                  </div>
                )
              })}
            </div>

            {/* AI Feedback Drafter & Remarks Section */}
            <div className={`${LH_CARD} p-4 space-y-3`}>
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <Sparkles size={16} className="text-amber-500" />
                  <h4 className="text-xs font-bold text-gray-900 uppercase tracking-wider">
                    AI Rubric-Grounded Feedback Drafter
                  </h4>
                </div>
                <button
                  onClick={handleGenerateAIFeedback}
                  disabled={isDraftingAI}
                  className="text-xs font-bold bg-amber-50 hover:bg-amber-100 text-amber-900 border border-amber-200 px-3 py-1 rounded-lg flex items-center space-x-1.5 transition-colors disabled:opacity-50"
                >
                  <RefreshCw size={12} className={isDraftingAI ? 'animate-spin' : ''} />
                  <span>{aiDraft ? 'Regenerate Draft' : 'Draft Feedback'}</span>
                </button>
              </div>

              {/* AI Draft Preview / Action Box */}
              {aiDraft && (
                <div className="bg-amber-50/70 border border-amber-200 rounded-xl p-3.5 space-y-2.5">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-bold text-amber-950 flex items-center space-x-1">
                      <Sparkles size={12} className="text-amber-600" />
                      <span>AI Synthesized Feedback Draft</span>
                    </span>
                    <div className="flex items-center space-x-1.5">
                      <button
                        onClick={() => setIsEditingDraft(!isEditingDraft)}
                        className="text-[11px] font-bold text-amber-800 hover:text-black px-2 py-0.5 bg-white/70 rounded border border-amber-200"
                      >
                        {isEditingDraft ? 'Done Editing' : 'Edit'}
                      </button>
                      <button
                        onClick={handleAcceptAIDraft}
                        className="text-[11px] font-bold text-white bg-black hover:bg-gray-800 px-2.5 py-0.5 rounded shadow-sm flex items-center space-x-1"
                      >
                        <Check size={11} />
                        <span>Accept</span>
                      </button>
                    </div>
                  </div>

                  {isEditingDraft ? (
                    <textarea
                      rows={6}
                      value={aiDraft}
                      onChange={(e) => setAiDraft(e.target.value)}
                      className="w-full text-xs font-normal p-2 bg-white border border-amber-200 rounded-lg focus:outline-none"
                    />
                  ) : (
                    <p className="text-xs text-gray-700 whitespace-pre-wrap leading-relaxed max-h-48 overflow-y-auto">
                      {aiDraft}
                    </p>
                  )}
                </div>
              )}

              {/* Teacher Remarks / Comment Textarea */}
              <div className="space-y-1 pt-1">
                <label className="text-xs font-bold text-gray-700">Teacher Final Remarks & Feedback</label>
                <textarea
                  rows={4}
                  value={feedbackInput}
                  onChange={(e) => setFeedbackInput(e.target.value)}
                  className="w-full text-xs p-3 bg-gray-50 border border-gray-200 rounded-lg focus:bg-white focus:outline-none focus:ring-2 focus:ring-black/10"
                  placeholder="Enter personalized feedback or accept the AI draft above..."
                />
              </div>
            </div>
          </div>

          {/* Sticky Score Summary Bar & Save Actions */}
          <div className="sticky bottom-0 bg-white border-t border-gray-200 p-4 shadow-lg flex items-center justify-between z-10">
            <div className="flex items-center space-x-4">
              <div className="flex flex-col">
                <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">
                  Final Evaluated Grade
                </span>
                <div className="flex items-baseline space-x-2">
                  <span className="text-2xl font-black text-gray-900">
                    {latePenaltyCalc.finalDecayedScore}
                  </span>
                  <span className="text-xs font-bold text-gray-400">
                    / {rubricScoreData.maxPossibleScore} pts
                  </span>
                  <span className="text-xs font-extrabold bg-black text-white px-2 py-0.5 rounded">
                    {letterGrade} ({((latePenaltyCalc.finalDecayedScore / (rubricScoreData.maxPossibleScore || 100)) * 100).toFixed(0)}%)
                  </span>
                </div>
              </div>
            </div>

            <div className="flex items-center space-x-2.5">
              {saveSuccessNotification && (
                <span className="text-xs font-bold text-emerald-600 bg-emerald-50 px-3 py-1.5 rounded-full flex items-center space-x-1 animate-fade-in">
                  <CheckCircle2 size={13} />
                  <span>{saveSuccessNotification}</span>
                </span>
              )}

              <button
                onClick={handleSaveAndAdvance}
                className={`${LH_PRIMARY_BUTTON} flex items-center space-x-2 py-2 px-5 text-xs font-bold`}
              >
                <Save size={14} />
                <span>Save & Next (Enter)</span>
              </button>
            </div>
          </div>
        </section>
      </div>

      {/* Keyboard Shortcuts Cheatsheet Modal */}
      {showShortcutsModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 space-y-4 nice-shadow animate-scale-in">
            <div className="flex items-center justify-between border-b border-gray-100 pb-3">
              <div className="flex items-center space-x-2">
                <Keyboard size={20} className="text-black" />
                <h3 className="text-base font-bold text-gray-900">SpeedGrader Keyboard Shortcuts</h3>
              </div>
              <button
                onClick={() => setShowShortcutsModal(false)}
                className="p-1 hover:bg-gray-100 rounded-lg text-gray-400 hover:text-black"
              >
                <X size={16} />
              </button>
            </div>

            <div className="space-y-2.5 text-xs text-gray-700">
              <div className="flex items-center justify-between p-2 bg-gray-50 rounded-lg">
                <span className="font-semibold">Select Rubric Level (1-4)</span>
                <div className="flex space-x-1">
                  <kbd className="px-2 py-1 bg-white border border-gray-200 rounded font-mono font-bold shadow-sm">1</kbd>
                  <kbd className="px-2 py-1 bg-white border border-gray-200 rounded font-mono font-bold shadow-sm">2</kbd>
                  <kbd className="px-2 py-1 bg-white border border-gray-200 rounded font-mono font-bold shadow-sm">3</kbd>
                  <kbd className="px-2 py-1 bg-white border border-gray-200 rounded font-mono font-bold shadow-sm">4</kbd>
                </div>
              </div>

              <div className="flex items-center justify-between p-2 bg-gray-50 rounded-lg">
                <span className="font-semibold">Navigate Criteria</span>
                <div className="flex space-x-1">
                  <kbd className="px-2 py-1 bg-white border border-gray-200 rounded font-mono font-bold shadow-sm">↑</kbd>
                  <kbd className="px-2 py-1 bg-white border border-gray-200 rounded font-mono font-bold shadow-sm">↓</kbd>
                </div>
              </div>

              <div className="flex items-center justify-between p-2 bg-gray-50 rounded-lg">
                <span className="font-semibold">Previous / Next Student</span>
                <div className="flex space-x-1">
                  <kbd className="px-2 py-1 bg-white border border-gray-200 rounded font-mono font-bold shadow-sm">← / [</kbd>
                  <kbd className="px-2 py-1 bg-white border border-gray-200 rounded font-mono font-bold shadow-sm">→ / ]</kbd>
                </div>
              </div>

              <div className="flex items-center justify-between p-2 bg-gray-50 rounded-lg">
                <span className="font-semibold">Save Grade & Advance Student</span>
                <kbd className="px-2 py-1 bg-black text-white rounded font-mono font-bold shadow-sm">Enter</kbd>
              </div>

              <div className="flex items-center justify-between p-2 bg-gray-50 rounded-lg">
                <span className="font-semibold">Toggle This Cheat Sheet</span>
                <kbd className="px-2 py-1 bg-white border border-gray-200 rounded font-mono font-bold shadow-sm">?</kbd>
              </div>
            </div>

            <button
              onClick={() => setShowShortcutsModal(false)}
              className="w-full py-2 bg-black text-white text-xs font-bold rounded-lg hover:bg-gray-800 transition-colors"
            >
              Got it
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
