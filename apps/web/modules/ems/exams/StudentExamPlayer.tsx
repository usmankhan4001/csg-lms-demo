'use client'

import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import {
  Clock,
  CheckCircle2,
  AlertTriangle,
  Flag,
  ChevronLeft,
  ChevronRight,
  Maximize2,
  Minimize2,
  Calculator as CalcIcon,
  BookOpen,
  Wifi,
  WifiOff,
  Save,
  ShieldAlert,
  ShieldCheck,
  Send,
  HelpCircle,
  RotateCcw,
  Check,
  Layers,
  ZoomIn,
  ZoomOut,
  User,
  AlertCircle,
} from 'lucide-react'
import {
  CBTQuestion,
  StudentAnswer,
  ExamSessionState,
  KeystrokeLogEntry,
  AutosaveBufferState,
  QuestionStatus,
} from './types'
import { ScientificCalculatorModal } from './ScientificCalculatorModal'
import { FormulaReferenceModal } from './FormulaReferenceModal'

export interface StudentExamPlayerProps {
  examId: string | number
  examTitle: string
  courseName?: string
  studentId: string | number
  studentName: string
  durationMinutes: number
  questions: CBTQuestion[]
  initialAnswers?: Record<string, StudentAnswer>
  onAutosave?: (answers: Record<string, StudentAnswer>) => Promise<boolean>
  onSubmitExam?: (answers: Record<string, StudentAnswer>, incidentLogs: string[]) => Promise<void>
  onExit?: () => void
}

export const StudentExamPlayer: React.FC<StudentExamPlayerProps> = ({
  examId,
  examTitle,
  courseName,
  studentId,
  studentName,
  durationMinutes,
  questions,
  initialAnswers,
  onAutosave,
  onSubmitExam,
  onExit,
}) => {
  // ── State: Navigation & Current Question ──────────────────────────────────
  const [currentIndex, setCurrentIndex] = useState<number>(0)
  const currentQuestion = questions[currentIndex] || questions[0]

  // ── State: Answers & Keystrokes ──────────────────────────────────────────
  const [answers, setAnswers] = useState<Record<string, StudentAnswer>>(() => {
    if (initialAnswers) return initialAnswers
    // Load cached answers from localStorage if available
    try {
      const cached = localStorage.getItem(`cbt_answers_${examId}_${studentId}`)
      if (cached) return JSON.parse(cached)
    } catch {
      // Ignore storage errors
    }
    const init: Record<string, StudentAnswer> = {}
    questions.forEach((q) => {
      init[q.id] = {
        questionId: q.id,
        selectedOptionIds: [],
        textResponse: '',
        flaggedForReview: false,
        lastModified: Date.now(),
        timeSpentSeconds: 0,
      }
    })
    return init
  })

  // ── State: Timer ─────────────────────────────────────────────────────────
  const [secondsRemaining, setSecondsRemaining] = useState<number>(() => {
    try {
      const cachedExp = localStorage.getItem(`cbt_expiry_${examId}_${studentId}`)
      if (cachedExp) {
        const diff = Math.floor((parseInt(cachedExp, 10) - Date.now()) / 1000)
        return Math.max(0, diff)
      }
    } catch {
      // Ignore
    }
    return durationMinutes * 60
  })

  // ── State: Network & Autosave Buffer ──────────────────────────────────────
  const [isOnline, setIsOnline] = useState<boolean>(true)
  const [autosaveState, setAutosaveState] = useState<AutosaveBufferState>({
    pendingCount: 0,
    lastSavedAt: Date.now(),
    syncStatus: 'SYNCED',
  })
  const keystrokeBufferRef = useRef<KeystrokeLogEntry[]>([])
  const saveTimeoutRef = useRef<NodeJS.Timeout | null>(null)

  // ── State: Lockdown & Proctoring Incidents ────────────────────────────────
  const [isFullscreen, setIsFullscreen] = useState<boolean>(false)
  const [incidentLogs, setIncidentLogs] = useState<string[]>([])
  const [warningMessage, setWarningMessage] = useState<string | null>(null)

  // ── State: Modals & Tools ─────────────────────────────────────────────────
  const [isCalcOpen, setIsCalcOpen] = useState<boolean>(false)
  const [isFormulaOpen, setIsFormulaOpen] = useState<boolean>(false)
  const [isSubmitModalOpen, setIsSubmitModalOpen] = useState<boolean>(false)
  const [isPaletteOpen, setIsPaletteOpen] = useState<boolean>(true)
  const [paletteFilter, setPaletteFilter] = useState<'ALL' | 'ANSWERED' | 'UNANSWERED' | 'FLAGGED'>('ALL')
  const [fontSizeLevel, setFontSizeLevel] = useState<'normal' | 'large' | 'xlarge'>('normal')
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false)

  // ── Fullscreen & Lockdown Event Handlers ──────────────────────────────────
  const toggleFullscreen = useCallback(async () => {
    try {
      if (!document.fullscreenElement) {
        await document.documentElement.requestFullscreen()
        setIsFullscreen(true)
      } else {
        await document.exitFullscreen()
        setIsFullscreen(false)
      }
    } catch (err) {
      console.warn('Fullscreen request failed:', err)
    }
  }, [])

  useEffect(() => {
    const handleFullscreenChange = () => {
      const inFull = !!document.fullscreenElement
      setIsFullscreen(inFull)
      if (!inFull) {
        const log = `Exited fullscreen mode at ${new Date().toLocaleTimeString()}`
        setIncidentLogs((prev) => [...prev, log])
        setWarningMessage('Warning: Fullscreen lockdown exited. Please stay in fullscreen during the exam.')
      }
    }

    const handleVisibilityChange = () => {
      if (document.hidden) {
        const log = `Browser tab switched/hidden at ${new Date().toLocaleTimeString()}`
        setIncidentLogs((prev) => [...prev, log])
        setWarningMessage('Warning: Browser window/tab lost focus. This incident has been logged.')
      }
    }

    const handleWindowBlur = () => {
      const log = `Window lost focus at ${new Date().toLocaleTimeString()}`
      setIncidentLogs((prev) => [...prev, log])
    }

    document.addEventListener('fullscreenchange', handleFullscreenChange)
    document.addEventListener('visibilitychange', handleVisibilityChange)
    window.addEventListener('blur', handleWindowBlur)

    return () => {
      document.removeEventListener('fullscreenchange', handleFullscreenChange)
      document.removeEventListener('visibilitychange', handleVisibilityChange)
      window.removeEventListener('blur', handleWindowBlur)
    }
  }, [])

  // ── Network Connectivity Listeners ────────────────────────────────────────
  useEffect(() => {
    const handleOnline = () => {
      setIsOnline(true)
      // Flush buffered changes immediately upon reconnection
      triggerAutosave(true)
    }
    const handleOffline = () => {
      setIsOnline(false)
      setAutosaveState((prev) => ({
        ...prev,
        syncStatus: 'OFFLINE_BUFFERED',
      }))
    }

    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)

    return () => {
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
    }
  }, [answers])

  // ── Countdown Timer ───────────────────────────────────────────────────────
  useEffect(() => {
    // Record expiry timestamp in localStorage
    const expiry = Date.now() + secondsRemaining * 1000
    try {
      localStorage.setItem(`cbt_expiry_${examId}_${studentId}`, String(expiry))
    } catch {}

    const interval = setInterval(() => {
      setSecondsRemaining((prev) => {
        if (prev <= 1) {
          clearInterval(interval)
          handleAutoSubmitOnTimeout()
          return 0
        }
        return prev - 1
      })
    }, 1000)

    return () => clearInterval(interval)
  }, [])

  // Time-spent tracker per question
  useEffect(() => {
    const timer = setInterval(() => {
      if (!currentQuestion) return
      setAnswers((prev) => {
        const curr = prev[currentQuestion.id]
        if (!curr) return prev
        return {
          ...prev,
          [currentQuestion.id]: {
            ...curr,
            timeSpentSeconds: curr.timeSpentSeconds + 1,
          },
        }
      })
    }, 1000)
    return () => clearInterval(timer)
  }, [currentQuestion?.id])

  // ── Offline Buffer & Autosave Engine ──────────────────────────────────────
  const triggerAutosave = useCallback(
    async (immediate: boolean = false) => {
      // 1. Always write to local storage first (instant durability)
      try {
        localStorage.setItem(`cbt_answers_${examId}_${studentId}`, JSON.stringify(answers))
      } catch {}

      if (!onAutosave) {
        setAutosaveState({
          pendingCount: 0,
          lastSavedAt: Date.now(),
          syncStatus: 'SYNCED',
        })
        return
      }

      if (!navigator.onLine) {
        setAutosaveState((prev) => ({
          ...prev,
          syncStatus: 'OFFLINE_BUFFERED',
          pendingCount: prev.pendingCount + 1,
        }))
        return
      }

      setAutosaveState((prev) => ({
        ...prev,
        syncStatus: 'SAVING',
      }))

      try {
        const success = await onAutosave(answers)
        if (success) {
          keystrokeBufferRef.current = []
          setAutosaveState({
            pendingCount: 0,
            lastSavedAt: Date.now(),
            syncStatus: 'SYNCED',
          })
        } else {
          setAutosaveState((prev) => ({
            ...prev,
            syncStatus: 'ERROR',
            errorMessage: 'Sync error - retrying in background',
          }))
        }
      } catch (err: any) {
        setAutosaveState((prev) => ({
          ...prev,
          syncStatus: 'OFFLINE_BUFFERED',
          pendingCount: prev.pendingCount + 1,
          errorMessage: err?.message || 'Offline save buffered',
        }))
      }
    },
    [answers, examId, studentId, onAutosave]
  )

  // Debounced autosave whenever answers change
  const scheduleAutosave = useCallback(() => {
    setAutosaveState((prev) => ({
      ...prev,
      pendingCount: prev.pendingCount + 1,
    }))
    if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current)
    saveTimeoutRef.current = setTimeout(() => {
      triggerAutosave(false)
    }, 2000)
  }, [triggerAutosave])

  // ── Answer Manipulation Handlers ──────────────────────────────────────────
  const handleSelectOption = (optionId: string) => {
    if (!currentQuestion) return

    setAnswers((prev) => {
      const currentAnswer = prev[currentQuestion.id] || {
        questionId: currentQuestion.id,
        selectedOptionIds: [],
        textResponse: '',
        flaggedForReview: false,
        lastModified: Date.now(),
        timeSpentSeconds: 0,
      }

      let newSelected: string[] = []
      if (currentQuestion.type === 'MULTIPLE_CHOICE') {
        newSelected = currentAnswer.selectedOptionIds.includes(optionId)
          ? currentAnswer.selectedOptionIds.filter((id) => id !== optionId)
          : [...currentAnswer.selectedOptionIds, optionId]
      } else {
        newSelected = [optionId]
      }

      // Log keystroke / interaction
      keystrokeBufferRef.current.push({
        questionId: currentQuestion.id,
        timestamp: Date.now(),
        keyStrokeType: 'OPTION_SELECT',
        payload: optionId,
      })

      return {
        ...prev,
        [currentQuestion.id]: {
          ...currentAnswer,
          selectedOptionIds: newSelected,
          lastModified: Date.now(),
        },
      }
    })

    scheduleAutosave()
  }

  const handleTextChange = (text: string) => {
    if (!currentQuestion) return

    setAnswers((prev) => {
      const currentAnswer = prev[currentQuestion.id] || {
        questionId: currentQuestion.id,
        selectedOptionIds: [],
        textResponse: '',
        flaggedForReview: false,
        lastModified: Date.now(),
        timeSpentSeconds: 0,
      }

      keystrokeBufferRef.current.push({
        questionId: currentQuestion.id,
        timestamp: Date.now(),
        keyStrokeType: 'TEXT_INPUT',
        payload: text.slice(-1),
      })

      return {
        ...prev,
        [currentQuestion.id]: {
          ...currentAnswer,
          textResponse: text,
          lastModified: Date.now(),
        },
      }
    })

    scheduleAutosave()
  }

  const toggleFlagForReview = () => {
    if (!currentQuestion) return

    setAnswers((prev) => {
      const currentAnswer = prev[currentQuestion.id] || {
        questionId: currentQuestion.id,
        selectedOptionIds: [],
        textResponse: '',
        flaggedForReview: false,
        lastModified: Date.now(),
        timeSpentSeconds: 0,
      }

      const nextFlag = !currentAnswer.flaggedForReview

      keystrokeBufferRef.current.push({
        questionId: currentQuestion.id,
        timestamp: Date.now(),
        keyStrokeType: 'FLAG_TOGGLE',
        payload: String(nextFlag),
      })

      return {
        ...prev,
        [currentQuestion.id]: {
          ...currentAnswer,
          flaggedForReview: nextFlag,
          lastModified: Date.now(),
        },
      }
    })

    scheduleAutosave()
  }

  const handleClearAnswer = () => {
    if (!currentQuestion) return
    setAnswers((prev) => ({
      ...prev,
      [currentQuestion.id]: {
        ...(prev[currentQuestion.id] || {
          questionId: currentQuestion.id,
          flaggedForReview: false,
          timeSpentSeconds: 0,
        }),
        selectedOptionIds: [],
        textResponse: '',
        lastModified: Date.now(),
      },
    }))
    scheduleAutosave()
  }

  // ── Palette Status Resolution ─────────────────────────────────────────────
  const getQuestionStatus = (questionId: string): QuestionStatus => {
    const ans = answers[questionId]
    if (!ans) return 'UNANSWERED'
    if (ans.flaggedForReview) return 'FLAGGED'
    const isAnswered =
      ans.selectedOptionIds.length > 0 || (ans.textResponse && ans.textResponse.trim().length > 0)
    return isAnswered ? 'ANSWERED' : 'UNANSWERED'
  }

  const paletteStats = useMemo(() => {
    let answered = 0
    let flagged = 0
    let unanswered = 0

    questions.forEach((q) => {
      const status = getQuestionStatus(q.id)
      if (status === 'FLAGGED') flagged++
      else if (status === 'ANSWERED') answered++
      else unanswered++
    })

    return { answered, flagged, unanswered, total: questions.length }
  }, [answers, questions])

  const filteredQuestions = useMemo(() => {
    return questions.filter((q) => {
      const st = getQuestionStatus(q.id)
      if (paletteFilter === 'ANSWERED') return st === 'ANSWERED'
      if (paletteFilter === 'FLAGGED') return st === 'FLAGGED'
      if (paletteFilter === 'UNANSWERED') return st === 'UNANSWERED'
      return true
    })
  }, [questions, answers, paletteFilter])

  // ── Submission Handlers ───────────────────────────────────────────────────
  const handleAutoSubmitOnTimeout = async () => {
    setIsSubmitting(true)
    try {
      if (onSubmitExam) {
        await onSubmitExam(answers, [...incidentLogs, 'Exam auto-submitted on time limit expiration'])
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleConfirmSubmit = async () => {
    setIsSubmitting(true)
    try {
      if (onSubmitExam) {
        await onSubmitExam(answers, incidentLogs)
      }
      setIsSubmitModalOpen(false)
    } finally {
      setIsSubmitting(false)
    }
  }

  // ── Format Timer (HH:MM:SS) ───────────────────────────────────────────────
  const formatTime = (secs: number) => {
    const hrs = Math.floor(secs / 3600)
    const mins = Math.floor((secs % 3600) / 60)
    const s = secs % 60
    if (hrs > 0) {
      return `${hrs.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
    }
    return `${mins.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
  }

  const isTimeCritical = secondsRemaining <= 60
  const isTimeWarning = secondsRemaining <= 300 && !isTimeCritical

  const currentAnswer = currentQuestion ? answers[currentQuestion.id] : null

  return (
    <div className="fixed inset-0 z-40 bg-neutral-950 text-neutral-100 flex flex-col select-none overflow-hidden font-sans">
      {/* ── TOP LOCKDOWN BAR ─────────────────────────────────────────────── */}
      <header className="h-16 px-6 bg-neutral-900 border-b border-neutral-800 flex items-center justify-between shrink-0 shadow-md">
        {/* Left: Exam Info & Candidate */}
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-blue-600/20 text-blue-400 border border-blue-500/30">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="font-bold text-sm tracking-wide text-white">{examTitle}</h1>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-300 font-semibold uppercase tracking-wider">
                  CBT Mode
                </span>
              </div>
              <p className="text-xs text-neutral-400">
                {courseName ? `${courseName} • ` : ''}Candidate: <span className="text-neutral-200 font-medium">{studentName}</span> (ID: {studentId})
              </p>
            </div>
          </div>
        </div>

        {/* Center: Live Timer Display */}
        <div className="flex items-center gap-3">
          <div
            className={`flex items-center gap-2 px-4 py-2 rounded-xl border font-mono font-bold text-base tracking-wider transition-all ${
              isTimeCritical
                ? 'bg-red-950/80 border-red-600 text-red-400 animate-pulse shadow-lg shadow-red-900/30'
                : isTimeWarning
                ? 'bg-amber-950/60 border-amber-500 text-amber-300'
                : 'bg-neutral-800/80 border-neutral-700 text-neutral-200'
            }`}
          >
            <Clock className={`w-4 h-4 ${isTimeCritical ? 'text-red-400' : isTimeWarning ? 'text-amber-400' : 'text-blue-400'}`} />
            <span>{formatTime(secondsRemaining)}</span>
          </div>

          {/* Network / Autosave Status Badge */}
          <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-neutral-800/60 border border-neutral-700/60 text-xs">
            {isOnline ? (
              <Wifi className="w-3.5 h-3.5 text-emerald-400" />
            ) : (
              <WifiOff className="w-3.5 h-3.5 text-amber-400" />
            )}
            <span className="text-neutral-400">
              {autosaveState.syncStatus === 'SAVING'
                ? 'Autosaving...'
                : autosaveState.syncStatus === 'OFFLINE_BUFFERED'
                ? `Offline (${autosaveState.pendingCount} in local buffer)`
                : 'All changes saved locally'}
            </span>
          </div>
        </div>

        {/* Right: Auxiliary Tools & Submission */}
        <div className="flex items-center gap-2.5">
          {/* Formula Sheet Trigger */}
          <button
            onClick={() => setIsFormulaOpen(true)}
            className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-neutral-800 hover:bg-neutral-700 border border-neutral-700 text-xs font-medium text-neutral-200 transition-colors"
            title="Open STEM Formula Reference Sheet"
          >
            <BookOpen className="w-4 h-4 text-purple-400" />
            <span className="hidden md:inline">Formulas</span>
          </button>

          {/* Scientific Calculator Trigger */}
          <button
            onClick={() => setIsCalcOpen(true)}
            className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-neutral-800 hover:bg-neutral-700 border border-neutral-700 text-xs font-medium text-neutral-200 transition-colors"
            title="Open Scientific Calculator"
          >
            <CalcIcon className="w-4 h-4 text-blue-400" />
            <span className="hidden md:inline">Calculator</span>
          </button>

          {/* Fullscreen Toggle */}
          <button
            onClick={toggleFullscreen}
            className="p-2 rounded-xl bg-neutral-800 hover:bg-neutral-700 border border-neutral-700 text-neutral-300 transition-colors"
            title={isFullscreen ? 'Exit Fullscreen' : 'Enter Fullscreen Lockdown'}
          >
            {isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
          </button>

          {/* Submit Exam Button */}
          <button
            onClick={() => setIsSubmitModalOpen(true)}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs shadow-md shadow-emerald-900/30 transition-all hover:scale-102"
          >
            <Send className="w-3.5 h-3.5" />
            <span>Finish & Submit</span>
          </button>
        </div>
      </header>

      {/* ── SECURITY / INCIDENT BANNER ───────────────────────────────────── */}
      {warningMessage && (
        <div className="bg-amber-950/90 border-b border-amber-600/60 px-6 py-2 flex items-center justify-between text-xs text-amber-200 animate-in slide-in-from-top duration-200">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
            <span>{warningMessage}</span>
          </div>
          <button
            onClick={() => setWarningMessage(null)}
            className="text-amber-400 hover:text-amber-100 font-bold px-2 py-0.5"
          >
            Acknowledge
          </button>
        </div>
      )}

      {/* ── MAIN EXAM VIEWPORT ────────────────────────────────────────────── */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left: Question Content Area */}
        <main className="flex-1 flex flex-col overflow-y-auto p-6 md:p-8 space-y-6">
          {currentQuestion ? (
            <div className="max-w-4xl mx-auto w-full space-y-6">
              {/* Question Header Card */}
              <div className="flex items-center justify-between bg-neutral-900/80 border border-neutral-800 p-4 rounded-2xl">
                <div className="flex items-center gap-3">
                  <span className="flex items-center justify-center w-8 h-8 rounded-xl bg-blue-600/30 text-blue-300 font-bold text-sm border border-blue-500/40">
                    {currentIndex + 1}
                  </span>
                  <div>
                    <h2 className="font-bold text-base text-neutral-100">
                      Question {currentIndex + 1} of {questions.length}
                    </h2>
                    <p className="text-xs text-neutral-400">
                      {currentQuestion.points} mark{currentQuestion.points === 1 ? '' : 's'} •{' '}
                      {currentQuestion.type === 'MULTIPLE_CHOICE'
                        ? 'Multiple Choice (Select all that apply)'
                        : currentQuestion.type === 'SINGLE_CHOICE'
                        ? 'Single Choice'
                        : 'Free Response / Essay'}
                    </p>
                  </div>
                </div>

                {/* Flag for review & Clear Selection */}
                <div className="flex items-center gap-2">
                  <button
                    onClick={toggleFlagForReview}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold border transition-all ${
                      currentAnswer?.flaggedForReview
                        ? 'bg-amber-600/30 border-amber-500 text-amber-300 shadow-xs'
                        : 'bg-neutral-800 border-neutral-700 text-neutral-400 hover:text-neutral-200'
                    }`}
                  >
                    <Flag className={`w-3.5 h-3.5 ${currentAnswer?.flaggedForReview ? 'fill-amber-400 text-amber-400' : ''}`} />
                    <span>{currentAnswer?.flaggedForReview ? 'Flagged' : 'Flag for Review'}</span>
                  </button>

                  <button
                    onClick={handleClearAnswer}
                    className="p-1.5 text-xs text-neutral-400 hover:text-neutral-200 rounded-lg hover:bg-neutral-800 transition-colors"
                    title="Clear my answer for this question"
                  >
                    <RotateCcw className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {/* Optional Reading Passage */}
              {currentQuestion.passage && (
                <div className="p-5 rounded-2xl bg-neutral-900/50 border border-neutral-800 text-sm text-neutral-300 leading-relaxed max-h-56 overflow-y-auto">
                  <div className="flex items-center gap-2 font-semibold text-xs text-neutral-400 mb-2 uppercase tracking-wider">
                    <BookOpen className="w-3.5 h-3.5 text-blue-400" />
                    Reference Material / Passage
                  </div>
                  {currentQuestion.passage}
                </div>
              )}

              {/* Question Prompt */}
              <div className="p-6 rounded-2xl bg-neutral-900/90 border border-neutral-800 text-neutral-100 text-base md:text-lg font-medium leading-relaxed shadow-sm">
                {currentQuestion.prompt}
              </div>

              {/* Options or Text Response Input */}
              {currentQuestion.options && currentQuestion.options.length > 0 ? (
                <div className="space-y-3">
                  {currentQuestion.options.map((option) => {
                    const isSelected = currentAnswer?.selectedOptionIds.includes(option.id)
                    return (
                      <div
                        key={option.id}
                        onClick={() => handleSelectOption(option.id)}
                        className={`p-4 rounded-xl border flex items-start gap-4 cursor-pointer transition-all ${
                          isSelected
                            ? 'bg-blue-950/40 border-blue-500 text-white shadow-md shadow-blue-950/20'
                            : 'bg-neutral-900/60 border-neutral-800 text-neutral-300 hover:bg-neutral-800/60 hover:border-neutral-700'
                        }`}
                      >
                        <div
                          className={`w-6 h-6 rounded-lg flex items-center justify-center font-semibold text-xs shrink-0 transition-colors ${
                            isSelected
                              ? 'bg-blue-600 text-white'
                              : 'bg-neutral-800 text-neutral-400 border border-neutral-700'
                          }`}
                        >
                          {isSelected ? <Check className="w-4 h-4 stroke-[3]" /> : option.label}
                        </div>
                        <span className="text-sm md:text-base leading-relaxed pt-0.5">{option.text}</span>
                      </div>
                    )
                  })}
                </div>
              ) : (
                <div className="space-y-2">
                  <label className="text-xs font-semibold text-neutral-400 uppercase tracking-wider">
                    Enter your response below:
                  </label>
                  <textarea
                    value={currentAnswer?.textResponse || ''}
                    onChange={(e) => handleTextChange(e.target.value)}
                    placeholder="Type your complete solution or answer here..."
                    rows={8}
                    className="w-full p-4 rounded-xl bg-neutral-900 border border-neutral-800 text-neutral-100 placeholder-neutral-500 focus:outline-hidden focus:border-blue-500 transition-colors text-sm md:text-base leading-relaxed resize-y font-mono"
                  />
                  <div className="flex justify-between items-center text-xs text-neutral-500">
                    <span>Keystrokes buffered and saved automatically</span>
                    <span>{(currentAnswer?.textResponse || '').length} characters</span>
                  </div>
                </div>
              )}

              {/* Bottom Navigation Buttons */}
              <div className="flex items-center justify-between pt-4 border-t border-neutral-800/80">
                <button
                  disabled={currentIndex === 0}
                  onClick={() => setCurrentIndex((prev) => Math.max(0, prev - 1))}
                  className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-neutral-800 hover:bg-neutral-700 disabled:opacity-40 disabled:hover:bg-neutral-800 text-sm font-semibold text-neutral-200 transition-colors"
                >
                  <ChevronLeft className="w-4 h-4" />
                  <span>Previous</span>
                </button>

                <div className="text-xs text-neutral-500 font-mono">
                  {currentIndex + 1} / {questions.length}
                </div>

                <button
                  disabled={currentIndex === questions.length - 1}
                  onClick={() => setCurrentIndex((prev) => Math.min(questions.length - 1, prev + 1))}
                  className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:hover:bg-blue-600 text-sm font-semibold text-white transition-colors"
                >
                  <span>Next</span>
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          ) : (
            <div className="text-center py-20 text-neutral-500">No questions loaded in this exam.</div>
          )}
        </main>

        {/* ── RIGHT: QUESTION PALETTE DRAWER ──────────────────────────────── */}
        <aside
          className={`w-80 bg-neutral-900 border-l border-neutral-800 flex flex-col shrink-0 transition-all duration-300 ${
            isPaletteOpen ? 'translate-x-0' : 'w-0 overflow-hidden border-l-0'
          }`}
        >
          {/* Palette Header */}
          <div className="p-4 border-b border-neutral-800 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Layers className="w-4 h-4 text-blue-400" />
              <h3 className="font-bold text-sm text-neutral-100">Question Palette</h3>
            </div>
            <span className="text-xs font-mono text-neutral-400">
              {paletteStats.answered}/{paletteStats.total} answered
            </span>
          </div>

          {/* Palette Summary Legend */}
          <div className="p-3 bg-neutral-950/60 border-b border-neutral-800/80 grid grid-cols-3 gap-2 text-[11px] text-center">
            <div className="p-1.5 rounded-lg bg-emerald-950/40 border border-emerald-800/50 text-emerald-300 font-medium">
              <div className="font-bold text-sm">{paletteStats.answered}</div>
              <span>Answered</span>
            </div>
            <div className="p-1.5 rounded-lg bg-amber-950/40 border border-amber-800/50 text-amber-300 font-medium">
              <div className="font-bold text-sm">{paletteStats.flagged}</div>
              <span>Flagged</span>
            </div>
            <div className="p-1.5 rounded-lg bg-neutral-800/40 border border-neutral-700/50 text-neutral-400 font-medium">
              <div className="font-bold text-sm">{paletteStats.unanswered}</div>
              <span>Remaining</span>
            </div>
          </div>

          {/* Filter Chips */}
          <div className="px-3 py-2 border-b border-neutral-800 flex items-center gap-1 text-[11px]">
            {(['ALL', 'UNANSWERED', 'FLAGGED', 'ANSWERED'] as const).map((filter) => (
              <button
                key={filter}
                onClick={() => setPaletteFilter(filter)}
                className={`px-2 py-1 rounded-md font-semibold transition-colors flex-1 text-center capitalize ${
                  paletteFilter === filter
                    ? 'bg-blue-600 text-white'
                    : 'bg-neutral-800/60 text-neutral-400 hover:text-neutral-200'
                }`}
              >
                {filter.toLowerCase()}
              </button>
            ))}
          </div>

          {/* Questions Grid */}
          <div className="flex-1 overflow-y-auto p-4 grid grid-cols-4 gap-2.5 content-start">
            {filteredQuestions.map((q) => {
              const status = getQuestionStatus(q.id)
              const isCurrent = questions[currentIndex]?.id === q.id
              const realIndex = q.index || questions.findIndex((item) => item.id === q.id) + 1

              return (
                <button
                  key={q.id}
                  onClick={() => {
                    const targetIdx = questions.findIndex((item) => item.id === q.id)
                    if (targetIdx !== -1) setCurrentIndex(targetIdx)
                  }}
                  className={`h-11 rounded-xl font-bold text-xs flex flex-col items-center justify-center relative transition-all ${
                    isCurrent
                      ? 'ring-2 ring-blue-400 ring-offset-2 ring-offset-neutral-900 font-extrabold scale-105'
                      : ''
                  } ${
                    status === 'FLAGGED'
                      ? 'bg-amber-500 text-neutral-950 shadow-md shadow-amber-900/30'
                      : status === 'ANSWERED'
                      ? 'bg-emerald-600 text-white shadow-md shadow-emerald-900/30'
                      : 'bg-neutral-800 text-neutral-300 hover:bg-neutral-700 border border-neutral-700/60'
                  }`}
                >
                  <span>{realIndex}</span>
                  {status === 'FLAGGED' && (
                    <Flag className="w-2.5 h-2.5 fill-current absolute top-1 right-1" />
                  )}
                </button>
              )
            })}
          </div>

          {/* Palette Footer */}
          <div className="p-3 bg-neutral-950 border-t border-neutral-800 text-[11px] text-neutral-500 text-center">
            Click any question number to navigate directly
          </div>
        </aside>
      </div>

      {/* ── SUBMIT CONFIRMATION MODAL ─────────────────────────────────────── */}
      {isSubmitModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-xs p-4">
          <div className="w-full max-w-md bg-neutral-900 border border-neutral-700 rounded-2xl shadow-2xl p-6 text-neutral-100 space-y-5 animate-in fade-in zoom-in-95 duration-200">
            <div className="flex items-center gap-3">
              <div className="p-3 rounded-xl bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                <Send className="w-6 h-6" />
              </div>
              <div>
                <h3 className="font-bold text-lg text-white">Submit Examination?</h3>
                <p className="text-xs text-neutral-400">Review your test progress before final submission</p>
              </div>
            </div>

            {/* Summary Breakdown */}
            <div className="p-4 rounded-xl bg-neutral-950 border border-neutral-800 space-y-2.5 text-sm">
              <div className="flex justify-between items-center text-emerald-400">
                <span>Answered Questions:</span>
                <span className="font-bold font-mono">{paletteStats.answered} / {paletteStats.total}</span>
              </div>
              <div className="flex justify-between items-center text-amber-400">
                <span>Flagged for Review:</span>
                <span className="font-bold font-mono">{paletteStats.flagged}</span>
              </div>
              <div className="flex justify-between items-center text-neutral-400">
                <span>Unanswered Questions:</span>
                <span className="font-bold font-mono">{paletteStats.unanswered}</span>
              </div>
              <div className="flex justify-between items-center text-blue-400 pt-2 border-t border-neutral-800">
                <span>Time Remaining:</span>
                <span className="font-bold font-mono">{formatTime(secondsRemaining)}</span>
              </div>
            </div>

            {paletteStats.unanswered > 0 && (
              <div className="flex items-center gap-2 p-3 rounded-xl bg-amber-950/40 border border-amber-800/50 text-xs text-amber-300">
                <AlertCircle className="w-4 h-4 shrink-0 text-amber-400" />
                <span>You have {paletteStats.unanswered} unanswered question(s). Are you sure you want to finish?</span>
              </div>
            )}

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                disabled={isSubmitting}
                onClick={() => setIsSubmitModalOpen(false)}
                className="px-4 py-2 rounded-xl bg-neutral-800 hover:bg-neutral-700 text-xs font-semibold text-neutral-300 transition-colors"
              >
                Return to Exam
              </button>
              <button
                disabled={isSubmitting}
                onClick={handleConfirmSubmit}
                className="flex items-center gap-2 px-5 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-xs font-bold text-white shadow-md shadow-emerald-900/30 transition-all"
              >
                {isSubmitting ? (
                  <>Submitting...</>
                ) : (
                  <>
                    <Check className="w-4 h-4" />
                    <span>Confirm & Finalize</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── MODALS: SCIENTIFIC CALCULATOR & FORMULA REFERENCE ─────────────── */}
      <ScientificCalculatorModal isOpen={isCalcOpen} onClose={() => setIsCalcOpen(false)} />
      <FormulaReferenceModal isOpen={isFormulaOpen} onClose={() => setIsFormulaOpen(false)} />
    </div>
  )
}
