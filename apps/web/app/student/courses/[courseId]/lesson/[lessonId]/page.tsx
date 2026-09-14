'use client'

import React, { useState, useRef, useEffect, useTransition } from 'react'
import Link from 'next/link'
import { useParams, useRouter } from 'next/navigation'
import {
  BookOpen,
  CheckCircle2,
  Circle,
  Play,
  Pause,
  Volume2,
  VolumeX,
  Maximize2,
  ChevronLeft,
  ChevronRight,
  Sparkles,
  BrainCircuit,
  Code2,
  FileText,
  HelpCircle,
  Send,
  RotateCcw,
  Check,
  Award,
  Terminal,
  Layers,
  PanelLeftClose,
  PanelLeftOpen,
  PanelRightClose,
  PanelRightOpen,
  Flame,
  ArrowRight,
  ExternalLink,
  Info,
  Lightbulb,
  KeyRound,
  Bot,
  User,
  Zap,
} from 'lucide-react'
import { cn } from '@/lib/utils'

// Types for Curriculum Structure
interface LessonItem {
  id: string
  title: string
  type: 'video' | 'article' | 'code' | 'quiz'
  duration: string
  completed: boolean
  isCurrent?: boolean
  xp: number
}

interface ModuleItem {
  id: string
  title: string
  lessons: LessonItem[]
}

const COURSE_MODULES: ModuleItem[] = [
  {
    id: 'mod-1',
    title: 'Module 1: Foundations of Rotational Dynamics',
    lessons: [
      {
        id: 'les-1',
        title: '1.1 Angular Velocity and Acceleration',
        type: 'video',
        duration: '14 mins',
        completed: true,
        xp: 50,
      },
      {
        id: 'les-2',
        title: '1.2 Moment of Inertia & Mass Distribution',
        type: 'video',
        duration: '18 mins',
        completed: true,
        xp: 75,
      },
      {
        id: 'les-3',
        title: '1.3 Torque and Newton\'s Second Law for Rotation',
        type: 'article',
        duration: '22 mins',
        completed: false,
        isCurrent: true,
        xp: 100,
      },
      {
        id: 'les-4',
        title: '1.4 Python Simulation: Inertia Calculator',
        type: 'code',
        duration: '20 mins',
        completed: false,
        xp: 120,
      },
    ],
  },
  {
    id: 'mod-2',
    title: 'Module 2: Conservation Laws & Gyroscopic Motion',
    lessons: [
      {
        id: 'les-5',
        title: '2.1 Conservation of Angular Momentum',
        type: 'video',
        duration: '16 mins',
        completed: false,
        xp: 80,
      },
      {
        id: 'les-6',
        title: '2.2 Precession and Nutation in Gyroscopes',
        type: 'article',
        duration: '15 mins',
        completed: false,
        xp: 90,
      },
      {
        id: 'les-7',
        title: '2.3 Checkpoint Mastery Assessment',
        type: 'quiz',
        duration: '25 mins',
        completed: false,
        xp: 150,
      },
    ],
  },
]

interface ChatMessage {
  id: string
  sender: 'user' | 'ai' | 'system'
  text: string
  timestamp: string
  hintCategory?: 'concept' | 'formula' | 'example'
}

export default function InteractiveLessonPlayerPage() {
  const params = useParams()
  const router = useRouter()
  const courseId = params?.courseId as string || 'phy-401'
  const lessonId = params?.lessonId as string || 'les-3'

  // Sidebar & Drawer States
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [aiDrawerOpen, setAiDrawerOpen] = useState(true)
  const [completedLessons, setCompletedLessons] = useState<Record<string, boolean>>({
    'les-1': true,
    'les-2': true,
  })

  // Lesson Interactive States
  const [activeTab, setActiveTab] = useState<'content' | 'code' | 'quiz'>('content')
  const [isPlaying, setIsPlaying] = useState(false)
  const [isMuted, setIsMuted] = useState(false)
  const [playbackSpeed, setPlaybackSpeed] = useState('1.0x')
  const [videoProgress, setVideoProgress] = useState(42)

  // Code Sandbox State
  const [sandboxCode, setSandboxCode] = useState<string>(`# CSG Neural Physics Engine - Moment of Inertia Simulation
import math

def calculate_rotational_torque(moment_inertia, angular_accel):
    """Computes Torque using Tau = I * Alpha"""
    torque = moment_inertia * angular_accel
    return round(torque, 3)

# Test parameters
I_cylinder = 0.5 * 4.2 * (0.35 ** 2)  # Mass = 4.2kg, Radius = 0.35m
alpha = 8.75                          # rad/s^2

net_tau = calculate_rotational_torque(I_cylinder, alpha)
print(f"Calculated Moment of Inertia: {I_cylinder:.4f} kg·m²")
print(f"Net Torque generated: {net_tau} N·m")
`)
  const [codeOutput, setCodeOutput] = useState<string>('')
  const [isExecutingCode, setIsExecutingCode] = useState(false)

  // Quiz State
  const [quizSelectedOption, setQuizSelectedOption] = useState<number | null>(null)
  const [quizSubmitted, setQuizSubmitted] = useState(false)

  // Socratic AI State
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'init-1',
      sender: 'ai',
      text: "👋 Welcome Zaid! I'm your CSG Socratic AI Tutor for Rotational Dynamics. I won't just spoil answers — I'll guide your reasoning step-by-step. Select a hint tier or ask any question below!",
      timestamp: '12:00 PM',
    },
  ])
  const [inputPrompt, setInputPrompt] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [conceptMastery, setConceptMastery] = useState(85)
  const chatBottomRef = useRef<HTMLDivElement>(null)

  // Auto-scroll chat to bottom
  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isStreaming])

  // Mark lesson completed toggle
  const toggleLessonCompletion = (id: string) => {
    setCompletedLessons((prev) => ({
      ...prev,
      [id]: !prev[id],
    }))
  }

  // Handle Code Execution Simulation
  const handleRunCode = () => {
    setIsExecutingCode(true)
    setCodeOutput('⚡ Initializing Python WebAssembly Sandbox...\nCompiling AST...')
    setTimeout(() => {
      setCodeOutput(
        `Calculated Moment of Inertia: 0.2573 kg·m²\nNet Torque generated: 2.251 N·m\n\n[Process completed successfully with exit code 0]\nExecution Time: 42ms | Memory: 12.4 MB`
      )
      setIsExecutingCode(false)
    }, 650)
  }

  // Stream message to Socratic AI Tutor API
  const handleSendMessage = async (textToSend?: string, hintType?: 'concept' | 'formula' | 'example') => {
    const messageContent = textToSend || inputPrompt
    if (!messageContent.trim() && !hintType) return

    const userMessageId = `user-${Date.now()}`
    const userMessage: ChatMessage = {
      id: userMessageId,
      sender: 'user',
      text: hintType
        ? `Requesting Tier ${hintType === 'concept' ? '1 (💡 Concept Clue)' : hintType === 'formula' ? '2 (📐 Formula / Rule)' : '3 (🔍 Worked Example)'}`
        : messageContent,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      hintCategory: hintType,
    }

    setMessages((prev) => [...prev, userMessage])
    if (!textToSend) setInputPrompt('')
    setIsStreaming(true)

    const aiMessageId = `ai-${Date.now()}`
    setMessages((prev) => [
      ...prev,
      {
        id: aiMessageId,
        sender: 'ai',
        text: '',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      },
    ])

    try {
      const res = await fetch('/api/v1/ai/tutor/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: messageContent,
          context: 'Lesson 1.3: Torque and Newton\'s Second Law for Rotation',
          hintType: hintType || 'general',
          history: messages.slice(-4),
        }),
      })

      if (!res.body) throw new Error('No readable stream body')

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let accumulatedText = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        const chunk = decoder.decode(value, { stream: true })
        accumulatedText += chunk

        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === aiMessageId ? { ...msg, text: accumulatedText } : msg
          )
        )
      }
    } catch (err) {
      // Fallback offline generator if network unreachable
      let fallback = `Let's analyze this carefully. If torque is defined as $\\vec{\\tau} = \\vec{r} \\times \\vec{F}$, what happens to the rotational leverage when the angle between radius and force vector is 90 degrees?`
      if (hintType === 'concept') {
        fallback = `💡 **Concept Clue:** Think about the rotational equivalent of mass ($m$) and acceleration ($a$). In linear motion, $F = ma$. In angular motion, what opposes rotational acceleration?`
      } else if (hintType === 'formula') {
        fallback = `📐 **Formula / Rule:** The primary governing equation is:\n$$\\tau_{\\text{net}} = I \\alpha$$\nwhere $I = \\sum m_i r_i^2$ and $\\alpha = \\frac{d\\omega}{dt}$.`
      } else if (hintType === 'example') {
        fallback = `🔍 **Example:** Pushing a heavy door at the handle requires less force than pushing near the hinge because the lever arm $r$ is maximized ($F = \\tau / r$).`
      }

      setMessages((prev) =>
        prev.map((msg) => (msg.id === aiMessageId ? { ...msg, text: fallback } : msg))
      )
    } finally {
      setIsStreaming(false)
    }
  }

  // Quick Query Chip Handler
  const handleQuickChipClick = (topicText: string) => {
    handleSendMessage(`Explain this concept in Socratic steps: "${topicText}"`)
  }

  return (
    <div className="flex flex-col h-[calc(100vh-6rem)] overflow-hidden rounded-2xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-950 shadow-lg">
      {/* Top Header Bar */}
      <header className="h-14 border-b border-neutral-200 dark:border-neutral-800 px-4 flex items-center justify-between bg-white dark:bg-neutral-900 shrink-0 z-10">
        <div className="flex items-center gap-3">
          <Link
            href="/student"
            className="p-1.5 rounded-lg text-neutral-500 hover:text-neutral-900 dark:hover:text-white hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-colors"
            title="Back to Dashboard"
          >
            <ChevronLeft className="size-5" />
          </Link>

          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="p-1.5 rounded-lg text-neutral-500 hover:text-neutral-900 dark:hover:text-white hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-colors"
            title={sidebarOpen ? 'Hide Curriculum Tree' : 'Show Curriculum Tree'}
          >
            {sidebarOpen ? <PanelLeftClose className="size-5" /> : <PanelLeftOpen className="size-5" />}
          </button>

          <div className="h-4 w-px bg-neutral-200 dark:border-neutral-700 hidden sm:block" />

          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs font-semibold px-2 py-0.5 rounded bg-blue-500/10 text-blue-600 dark:text-blue-400">
                PHY-401
              </span>
              <h1 className="text-xs sm:text-sm font-bold text-neutral-900 dark:text-white truncate">
                Lesson 1.3: Torque & Newton&apos;s Second Law for Rotation
              </h1>
            </div>
          </div>
        </div>

        {/* Header Right Controls */}
        <div className="flex items-center gap-2 sm:gap-3">
          {/* Progress Indicator */}
          <div className="hidden md:flex items-center gap-2 text-xs text-neutral-500">
            <span>Course Progress:</span>
            <div className="w-24 h-2 rounded-full bg-neutral-100 dark:bg-neutral-800 overflow-hidden">
              <div className="h-full bg-emerald-500 rounded-full w-[65%]" />
            </div>
            <span className="font-bold text-neutral-800 dark:text-neutral-200">65%</span>
          </div>

          <div className="flex items-center gap-1">
            <button
              onClick={() => alert('Navigating to previous lesson')}
              className="p-1.5 rounded-lg border border-neutral-200 dark:border-neutral-700 hover:bg-neutral-100 dark:hover:bg-neutral-800 text-neutral-700 dark:text-neutral-300 text-xs transition-colors flex items-center gap-1"
            >
              <ChevronLeft className="size-4" />
              <span className="hidden sm:inline">Prev</span>
            </button>

            <button
              onClick={() => toggleLessonCompletion('les-3')}
              className={cn(
                'px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors shadow-2xs',
                completedLessons['les-3']
                  ? 'bg-emerald-600 text-white hover:bg-emerald-700'
                  : 'bg-neutral-100 dark:bg-neutral-800 text-neutral-800 dark:text-neutral-200 hover:bg-neutral-200 dark:hover:bg-neutral-700'
              )}
            >
              <Check className="size-3.5" />
              <span>{completedLessons['les-3'] ? 'Completed' : 'Mark Complete'}</span>
            </button>

            <button
              onClick={() => alert('Navigating to next lesson')}
              className="p-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold transition-colors flex items-center gap-1 shadow-2xs"
            >
              <span className="hidden sm:inline">Next</span>
              <ChevronRight className="size-4" />
            </button>
          </div>

          <button
            onClick={() => setAiDrawerOpen(!aiDrawerOpen)}
            className={cn(
              'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-all shadow-xs',
              aiDrawerOpen
                ? 'bg-indigo-600 text-white ring-2 ring-indigo-400/40'
                : 'bg-indigo-50 dark:bg-indigo-950/40 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800 hover:bg-indigo-100'
            )}
            title="Toggle Socratic AI Tutor"
          >
            <Sparkles className="size-4 text-indigo-300" />
            <span className="hidden sm:inline">Socratic AI</span>
            <span className="size-2 rounded-full bg-emerald-400 animate-pulse" />
          </button>
        </div>
      </header>

      {/* Main 3-Column Layout Workspace */}
      <div className="flex-1 flex overflow-hidden relative">
        {/* Left Curriculum Tree Sidebar */}
        {sidebarOpen && (
          <aside className="w-72 sm:w-80 border-e border-neutral-200 dark:border-neutral-800 bg-neutral-50/70 dark:bg-neutral-900/60 flex flex-col shrink-0 overflow-y-auto">
            <div className="p-3.5 border-b border-neutral-200 dark:border-neutral-800 flex items-center justify-between">
              <span className="text-xs font-bold text-neutral-700 dark:text-neutral-300 uppercase tracking-wider flex items-center gap-1.5">
                <Layers className="size-3.5 text-blue-500" />
                Course Curriculum
              </span>
              <span className="text-[11px] font-semibold text-neutral-500">
                2 of 7 Complete
              </span>
            </div>

            {/* Modules Accordion Tree */}
            <div className="p-3 space-y-4">
              {COURSE_MODULES.map((mod) => (
                <div key={mod.id} className="space-y-1.5">
                  <h3 className="text-xs font-bold text-neutral-900 dark:text-white px-2 py-1 flex items-center justify-between">
                    <span className="truncate">{mod.title}</span>
                  </h3>

                  <div className="space-y-1">
                    {mod.lessons.map((les) => {
                      const isDone = completedLessons[les.id]
                      const isCurr = les.id === lessonId || les.isCurrent

                      return (
                        <div
                          key={les.id}
                          className={cn(
                            'group flex items-center justify-between p-2.5 rounded-xl text-xs transition-all cursor-pointer',
                            isCurr
                              ? 'bg-blue-600 text-white font-semibold shadow-sm'
                              : isDone
                              ? 'bg-emerald-500/5 text-neutral-700 dark:text-neutral-300 hover:bg-neutral-200/60 dark:hover:bg-neutral-800'
                              : 'text-neutral-600 dark:text-neutral-400 hover:bg-neutral-200/60 dark:hover:bg-neutral-800'
                          )}
                        >
                          <div className="flex items-center gap-2.5 min-w-0">
                            <button
                              onClick={(e) => {
                                e.stopPropagation()
                                toggleLessonCompletion(les.id)
                              }}
                              className="shrink-0 transition-transform active:scale-90"
                            >
                              {isDone ? (
                                <CheckCircle2
                                  className={cn(
                                    'size-4',
                                    isCurr ? 'text-white' : 'text-emerald-500'
                                  )}
                                />
                              ) : (
                                <Circle
                                  className={cn(
                                    'size-4',
                                    isCurr ? 'text-white/60' : 'text-neutral-400'
                                  )}
                                />
                              )}
                            </button>

                            <div className="min-w-0">
                              <span className="truncate block text-xs">{les.title}</span>
                              <div
                                className={cn(
                                  'flex items-center gap-2 text-[10px] mt-0.5',
                                  isCurr ? 'text-blue-100' : 'text-neutral-400'
                                )}
                              >
                                <span>{les.duration}</span>
                                <span>•</span>
                                <span className="flex items-center gap-0.5">
                                  <Flame className="size-2.5 text-amber-400" />
                                  {les.xp} XP
                                </span>
                              </div>
                            </div>
                          </div>

                          <div className="shrink-0 ms-2">
                            {les.type === 'video' && <Play className="size-3.5 opacity-70" />}
                            {les.type === 'article' && <FileText className="size-3.5 opacity-70" />}
                            {les.type === 'code' && <Code2 className="size-3.5 opacity-70" />}
                            {les.type === 'quiz' && <HelpCircle className="size-3.5 opacity-70" />}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              ))}
            </div>
          </aside>
        )}

        {/* Center Lesson Content & Sandbox Workspace */}
        <main className="flex-1 flex flex-col overflow-y-auto bg-neutral-50/30 dark:bg-neutral-950 p-4 sm:p-6 space-y-6">
          {/* Lesson Hero Header Banner */}
          <div className="p-5 sm:p-6 rounded-2xl bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 shadow-2xs">
            <div className="flex flex-wrap items-center gap-2 mb-2">
              <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border border-indigo-500/20">
                Interactive STEM Module
              </span>
              <span className="text-xs text-neutral-500">22 mins estimated study</span>
              <span className="text-xs text-neutral-500">•</span>
              <span className="text-xs font-semibold text-amber-600 dark:text-amber-400 flex items-center gap-1">
                <Award className="size-3.5" /> +100 XP upon completion
              </span>
            </div>

            <h2 className="text-xl sm:text-2xl font-extrabold text-neutral-900 dark:text-white tracking-tight">
              Torque, Moment of Inertia, and Newton&apos;s 2nd Law for Rotation
            </h2>
            <p className="text-sm text-neutral-600 dark:text-neutral-400 mt-2 leading-relaxed">
              Explore how rotational forces induce angular acceleration and how mass distribution relative to the axis of rotation dictates rotational inertia.
            </p>

            {/* Tab navigation within lesson */}
            <div className="flex items-center gap-2 mt-4 pt-4 border-t border-neutral-100 dark:border-neutral-800">
              <button
                onClick={() => setActiveTab('content')}
                className={cn(
                  'px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all flex items-center gap-1.5',
                  activeTab === 'content'
                    ? 'bg-blue-600 text-white shadow-2xs'
                    : 'bg-neutral-100 dark:bg-neutral-800 text-neutral-600 dark:text-neutral-400 hover:text-neutral-900'
                )}
              >
                <BookOpen className="size-3.5" />
                <span>Lesson Theory & Video</span>
              </button>

              <button
                onClick={() => setActiveTab('code')}
                className={cn(
                  'px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all flex items-center gap-1.5',
                  activeTab === 'code'
                    ? 'bg-blue-600 text-white shadow-2xs'
                    : 'bg-neutral-100 dark:bg-neutral-800 text-neutral-600 dark:text-neutral-400 hover:text-neutral-900'
                )}
              >
                <Code2 className="size-3.5" />
                <span>Python Simulation Sandbox</span>
              </button>

              <button
                onClick={() => setActiveTab('quiz')}
                className={cn(
                  'px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all flex items-center gap-1.5',
                  activeTab === 'quiz'
                    ? 'bg-blue-600 text-white shadow-2xs'
                    : 'bg-neutral-100 dark:bg-neutral-800 text-neutral-600 dark:text-neutral-400 hover:text-neutral-900'
                )}
              >
                <HelpCircle className="size-3.5" />
                <span>Concept Checkpoint</span>
              </button>
            </div>
          </div>

          {/* TAB 1: Theory & Video Lesson View */}
          {activeTab === 'content' && (
            <div className="space-y-6">
              {/* Responsive Video Container Mockup */}
              <div className="relative rounded-2xl overflow-hidden bg-neutral-950 border border-neutral-800 shadow-xl aspect-video flex flex-col justify-between p-4 group">
                <div className="absolute inset-0 bg-radial from-neutral-800/40 via-neutral-950/90 to-neutral-950 pointer-events-none" />

                {/* Video Header Overlay */}
                <div className="relative z-10 flex items-center justify-between text-white/80">
                  <div className="flex items-center gap-2 text-xs font-semibold bg-black/50 backdrop-blur-md px-3 py-1 rounded-full border border-white/10">
                    <span className="size-2 rounded-full bg-rose-500 animate-ping" />
                    <span>CSG Masterclass 4K HDR • Lecture 3</span>
                  </div>
                  <span className="text-xs bg-black/40 px-2 py-0.5 rounded text-neutral-300 font-mono">
                    1080p 60fps
                  </span>
                </div>

                {/* Center Big Play Button */}
                <div className="relative z-10 flex flex-col items-center justify-center my-auto">
                  <button
                    onClick={() => setIsPlaying(!isPlaying)}
                    className="size-16 sm:size-20 rounded-full bg-blue-600/90 hover:bg-blue-600 text-white flex items-center justify-center shadow-2xl hover:scale-105 active:scale-95 transition-all group-hover:ring-8 ring-blue-500/20"
                  >
                    {isPlaying ? <Pause className="size-8 fill-current" /> : <Play className="size-8 fill-current ms-1" />}
                  </button>
                  <p className="text-xs text-neutral-300 font-medium mt-3 bg-black/40 px-3 py-1 rounded-full backdrop-blur-xs">
                    {isPlaying ? 'Playing: Section 2 - Cross Product Torque Analysis' : 'Click to Resume Video'}
                  </p>
                </div>

                {/* Video Control Bar */}
                <div className="relative z-10 bg-black/70 backdrop-blur-md rounded-xl p-2.5 border border-white/10 space-y-2">
                  {/* Scrubber */}
                  <div className="w-full bg-neutral-700 h-1.5 rounded-full cursor-pointer relative overflow-hidden">
                    <div
                      className="bg-gradient-to-r from-blue-500 to-indigo-500 h-full rounded-full"
                      style={{ width: `${videoProgress}%` }}
                    />
                  </div>

                  <div className="flex items-center justify-between text-white text-xs">
                    <div className="flex items-center gap-3">
                      <button onClick={() => setIsPlaying(!isPlaying)} className="hover:text-blue-400">
                        {isPlaying ? <Pause className="size-4" /> : <Play className="size-4" />}
                      </button>
                      <button onClick={() => setIsMuted(!isMuted)} className="hover:text-blue-400">
                        {isMuted ? <VolumeX className="size-4" /> : <Volume2 className="size-4" />}
                      </button>
                      <span className="font-mono text-[11px] text-neutral-300">08:42 / 22:15</span>
                    </div>

                    <div className="flex items-center gap-3">
                      <button
                        onClick={() =>
                          setPlaybackSpeed((prev) =>
                            prev === '1.0x' ? '1.5x' : prev === '1.5x' ? '2.0x' : '1.0x'
                          )
                        }
                        className="px-2 py-0.5 rounded bg-white/10 hover:bg-white/20 font-mono text-[11px] font-semibold transition-colors"
                      >
                        {playbackSpeed}
                      </button>
                      <button className="hover:text-blue-400">
                        <Maximize2 className="size-4" />
                      </button>
                    </div>
                  </div>
                </div>
              </div>

              {/* Rich Markdown / TipTap Formatted Article Blocks */}
              <div className="p-6 sm:p-8 rounded-2xl bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 space-y-6 text-neutral-800 dark:text-neutral-200 leading-relaxed text-sm">
                <div>
                  <h3 className="text-lg font-bold text-neutral-900 dark:text-white flex items-center justify-between">
                    <span>1. Fundamental Definition of Torque</span>
                    <button
                      onClick={() => handleQuickChipClick('Definition of Torque and Cross Product')}
                      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-indigo-50 dark:bg-indigo-950/40 text-indigo-600 dark:text-indigo-400 text-xs font-semibold hover:bg-indigo-100 transition-colors"
                    >
                      <Sparkles className="size-3.5" />
                      <span>Ask AI Tutor about this</span>
                    </button>
                  </h3>
                  <p className="mt-2 text-neutral-600 dark:text-neutral-300">
                    {'Torque is the rotational counterpart of linear force. It measures the effectiveness of a force in causing or modifying rotational motion around a pivot axis. Mathematically, the vector torque $\\vec{\\tau}$ produced by a force $\\vec{F}$ acting at position vector $\\vec{r}$ relative to the pivot is:'}
                  </p>

                  {/* LaTeX / Equation Card */}
                  <div className="my-4 p-4 rounded-xl bg-neutral-100 dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-700 text-center font-mono text-base font-bold text-blue-600 dark:text-blue-400">
                    {'$$\\vec{\\tau} = \\vec{r} \\times \\vec{F} = |\\vec{r}| |\\vec{F}| \\sin(\\theta) \\hat{n}$$'}
                  </div>
                </div>

                {/* Visual Callout Box */}
                <div className="p-4 rounded-xl bg-amber-50 dark:bg-amber-950/30 border border-amber-300/80 dark:border-amber-700/50 flex items-start gap-3">
                  <Lightbulb className="size-5 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
                  <div>
                    <h4 className="text-xs font-bold text-amber-900 dark:text-amber-200 uppercase tracking-wider">
                      Key Principle: The Lever Arm
                    </h4>
                    <p className="text-xs text-amber-800 dark:text-amber-300/90 mt-1">
                      The perpendicular distance from the axis of rotation to the line of action of the force is known as the lever arm ($r_\perp = r \sin\theta$). Maximum torque occurs when the applied force is perpendicular ($\theta = 90^\circ$).
                    </p>
                  </div>
                </div>

                <div>
                  <h3 className="text-lg font-bold text-neutral-900 dark:text-white flex items-center justify-between">
                    <span>2. Newton&apos;s Second Law in Rotational Form</span>
                    <button
                      onClick={() => handleQuickChipClick('Newton 2nd Law for Rotation Tau = I * Alpha')}
                      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-indigo-50 dark:bg-indigo-950/40 text-indigo-600 dark:text-indigo-400 text-xs font-semibold hover:bg-indigo-100 transition-colors"
                    >
                      <Sparkles className="size-3.5" />
                      <span>Ask AI Tutor about this</span>
                    </button>
                  </h3>
                  <p className="mt-2 text-neutral-600 dark:text-neutral-300">
                    {'Just as $\\Sigma \\vec{F} = m \\vec{a}$ governs translational dynamics, the rotational counterpart relates net external torque $\\Sigma \\vec{\\tau}$ to the moment of inertia $I$ and angular acceleration $\\vec{\\alpha}$:'}
                  </p>

                  <div className="my-4 p-4 rounded-xl bg-neutral-100 dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-700 text-center font-mono text-base font-bold text-emerald-600 dark:text-emerald-400">
                    {'$$\\Sigma \\vec{\\tau}_{\\text{ext}} = I \\vec{\\alpha} = \\frac{d\\vec{L}}{dt}$$'}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: Interactive Code Sandbox */}
          {activeTab === 'code' && (
            <div className="space-y-4">
              <div className="p-4 rounded-2xl bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-bold text-neutral-900 dark:text-white flex items-center gap-2">
                    <Terminal className="size-4 text-emerald-500" />
                    Interactive Python Dynamics Simulator
                  </h3>
                  <p className="text-xs text-neutral-500">
                    Modify the rotational parameters and run in browser WebAssembly
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() =>
                      handleSendMessage(
                        'Can you analyze my Python simulation code for moment of inertia calculation and guide me on edge cases?'
                      )
                    }
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-indigo-50 dark:bg-indigo-950/40 text-indigo-600 dark:text-indigo-400 border border-indigo-200 dark:border-indigo-800 text-xs font-semibold hover:bg-indigo-100 transition-colors"
                  >
                    <Sparkles className="size-3.5" />
                    <span>Debug with AI Tutor</span>
                  </button>

                  <button
                    onClick={handleRunCode}
                    disabled={isExecutingCode}
                    className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white font-bold text-xs shadow-md transition-all active:scale-95"
                  >
                    {isExecutingCode ? (
                      <span className="animate-spin">⏳</span>
                    ) : (
                      <Play className="size-3.5 fill-current" />
                    )}
                    <span>Run Simulation</span>
                  </button>
                </div>
              </div>

              {/* Code Editor Area */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {/* Editor Container */}
                <div className="rounded-2xl border border-neutral-800 bg-[#0d1117] text-neutral-100 overflow-hidden flex flex-col h-[400px]">
                  <div className="px-4 py-2.5 bg-[#161b22] border-b border-neutral-800 flex items-center justify-between text-xs text-neutral-400">
                    <span className="font-mono text-neutral-300">inertia_sim.py</span>
                    <span className="text-[11px] font-mono">Python 3.12 (Pyodide)</span>
                  </div>
                  <textarea
                    value={sandboxCode}
                    onChange={(e) => setSandboxCode(e.target.value)}
                    className="flex-1 w-full p-4 bg-transparent font-mono text-xs text-emerald-300/90 leading-relaxed resize-none focus:outline-hidden"
                    spellCheck={false}
                  />
                </div>

                {/* Terminal Output */}
                <div className="rounded-2xl border border-neutral-800 bg-black text-neutral-200 overflow-hidden flex flex-col h-[400px]">
                  <div className="px-4 py-2.5 bg-neutral-900 border-b border-neutral-800 flex items-center justify-between text-xs text-neutral-400">
                    <span className="font-mono flex items-center gap-1.5">
                      <Terminal className="size-3.5 text-blue-400" />
                      Stdout Terminal
                    </span>
                    <button
                      onClick={() => setCodeOutput('')}
                      className="hover:text-white transition-colors text-[11px]"
                    >
                      Clear
                    </button>
                  </div>
                  <pre className="flex-1 p-4 font-mono text-xs text-neutral-300 overflow-y-auto whitespace-pre-wrap">
                    {codeOutput || '// Run the script above to see live simulation stdout...'}
                  </pre>
                </div>
              </div>
            </div>
          )}

          {/* TAB 3: Checkpoint Quiz */}
          {activeTab === 'quiz' && (
            <div className="p-6 rounded-2xl bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 space-y-5">
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-xs font-bold text-indigo-600 dark:text-indigo-400 uppercase tracking-wider">
                    Checkpoint Check #1
                  </span>
                  <h3 className="text-base font-bold text-neutral-900 dark:text-white mt-1">
                    Rotational Inertia of Solid Cylinders
                  </h3>
                </div>
                <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-600">
                  +25 XP
                </span>
              </div>

              <p className="text-sm text-neutral-700 dark:text-neutral-300">
                A solid uniform cylinder and a hollow thin-walled hoop of identical mass $M$ and radius $R$ are released simultaneously from rest down a ramp. Which object reaches the bottom first and why?
              </p>

              <div className="space-y-2.5">
                {[
                  {
                    id: 0,
                    text: 'The solid cylinder, because its moment of inertia (0.5 MR²) is smaller, directing more potential energy into linear acceleration.',
                    isCorrect: true,
                  },
                  {
                    id: 1,
                    text: 'The hollow hoop, because having all mass on the perimeter creates higher rotational inertia that accelerates it faster.',
                    isCorrect: false,
                  },
                  {
                    id: 2,
                    text: 'Both reach the bottom at the exact same time because acceleration due to gravity is independent of mass.',
                    isCorrect: false,
                  },
                ].map((option) => {
                  const isSelected = quizSelectedOption === option.id
                  return (
                    <div
                      key={option.id}
                      onClick={() => !quizSubmitted && setQuizSelectedOption(option.id)}
                      className={cn(
                        'p-3.5 rounded-xl border text-xs cursor-pointer transition-all flex items-start gap-3',
                        isSelected
                          ? 'bg-blue-50 dark:bg-blue-950/40 border-blue-500 ring-2 ring-blue-500/20 text-neutral-900 dark:text-white font-medium'
                          : 'border-neutral-200 dark:border-neutral-800 hover:border-neutral-300 dark:hover:border-neutral-700 text-neutral-700 dark:text-neutral-300'
                      )}
                    >
                      <div
                        className={cn(
                          'size-5 rounded-full border flex items-center justify-center text-[10px] shrink-0 mt-0.5',
                          isSelected ? 'border-blue-600 bg-blue-600 text-white' : 'border-neutral-400'
                        )}
                      >
                        {isSelected ? '✓' : String.fromCharCode(65 + option.id)}
                      </div>
                      <span className="leading-relaxed">{option.text}</span>
                    </div>
                  )
                })}
              </div>

              <div className="flex items-center justify-between pt-3 border-t border-neutral-100 dark:border-neutral-800">
                <button
                  onClick={() =>
                    handleSendMessage(
                      'I am trying to solve the ramp race question with a cylinder and hoop. Can you give me a Socratic hint without spoiling the option?'
                    )
                  }
                  className="inline-flex items-center gap-1.5 text-xs text-indigo-600 dark:text-indigo-400 hover:underline font-semibold"
                >
                  <Sparkles className="size-3.5" />
                  <span>Stuck? Ask Socratic Tutor</span>
                </button>

                <button
                  onClick={() => {
                    if (quizSelectedOption === null) return
                    setQuizSubmitted(true)
                  }}
                  disabled={quizSelectedOption === null}
                  className="px-5 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-xs font-bold transition-all shadow-md"
                >
                  Submit Answer
                </button>
              </div>

              {quizSubmitted && (
                <div
                  className={cn(
                    'p-4 rounded-xl text-xs space-y-1',
                    quizSelectedOption === 0
                      ? 'bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-500/30 text-emerald-800 dark:text-emerald-200'
                      : 'bg-rose-50 dark:bg-rose-950/30 border border-rose-500/30 text-rose-800 dark:text-rose-200'
                  )}
                >
                  <div className="font-bold flex items-center gap-1.5">
                    {quizSelectedOption === 0 ? '🎉 Correct Answer!' : '❌ Incorrect!'}
                  </div>
                  <p>
                    {quizSelectedOption === 0
                      ? 'Solid cylinder has smaller I, meaning less potential energy is converted to rotational kinetic energy and more remains for linear speed!'
                      : 'Remember that higher moment of inertia consumes more kinetic energy just to rotate the object.'}
                  </p>
                </div>
              )}
            </div>
          )}
        </main>

        {/* Right Collapsible Socratic AI Tutor Drawer */}
        {aiDrawerOpen && (
          <aside className="w-80 sm:w-96 border-s border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 flex flex-col shrink-0 overflow-hidden shadow-2xl z-20">
            {/* AI Drawer Header */}
            <div className="p-4 border-b border-neutral-200 dark:border-neutral-800 bg-gradient-to-r from-indigo-900 via-indigo-950 to-neutral-900 text-white">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <div className="size-7 rounded-lg bg-indigo-500/30 border border-indigo-400/30 flex items-center justify-center text-indigo-300 shadow-xs">
                    <BrainCircuit className="size-4" />
                  </div>
                  <div>
                    <h3 className="text-xs sm:text-sm font-bold leading-tight">
                      Socratic AI Tutor
                    </h3>
                    <p className="text-[10px] text-indigo-300/80">
                      Step-by-step Guided Reasoning
                    </p>
                  </div>
                </div>

                <button
                  onClick={() => setAiDrawerOpen(false)}
                  className="p-1 rounded-lg text-white/60 hover:text-white hover:bg-white/10 transition-colors"
                  title="Close Drawer"
                >
                  <PanelRightClose className="size-4" />
                </button>
              </div>

              {/* Concept Mastery Badge */}
              <div className="flex items-center justify-between px-3 py-1.5 rounded-xl bg-white/10 border border-white/15 text-xs">
                <span className="text-[11px] text-indigo-100 flex items-center gap-1">
                  <Zap className="size-3 text-amber-300" />
                  Topic Mastery:
                </span>
                <span className="font-bold text-emerald-300">{conceptMastery}% Complete</span>
              </div>
            </div>

            {/* 3-Tier Hint Toggle Buttons */}
            <div className="p-3 border-b border-neutral-200 dark:border-neutral-800 bg-neutral-50 dark:bg-neutral-900/60">
              <span className="text-[10px] font-bold uppercase tracking-wider text-neutral-500 block mb-2">
                3-Tier Socratic Clues:
              </span>
              <div className="grid grid-cols-3 gap-1.5">
                <button
                  onClick={() => handleSendMessage('', 'concept')}
                  disabled={isStreaming}
                  className="p-2 rounded-xl bg-white dark:bg-neutral-800 hover:bg-indigo-50 dark:hover:bg-indigo-950/40 border border-neutral-200 dark:border-neutral-700 hover:border-indigo-400 text-[11px] font-bold text-neutral-800 dark:text-neutral-200 transition-all text-center flex flex-col items-center gap-1 shadow-2xs group"
                >
                  <span className="text-sm">💡</span>
                  <span className="truncate w-full text-[10px]">Concept</span>
                </button>

                <button
                  onClick={() => handleSendMessage('', 'formula')}
                  disabled={isStreaming}
                  className="p-2 rounded-xl bg-white dark:bg-neutral-800 hover:bg-indigo-50 dark:hover:bg-indigo-950/40 border border-neutral-200 dark:border-neutral-700 hover:border-indigo-400 text-[11px] font-bold text-neutral-800 dark:text-neutral-200 transition-all text-center flex flex-col items-center gap-1 shadow-2xs group"
                >
                  <span className="text-sm">📐</span>
                  <span className="truncate w-full text-[10px]">Formula</span>
                </button>

                <button
                  onClick={() => handleSendMessage('', 'example')}
                  disabled={isStreaming}
                  className="p-2 rounded-xl bg-white dark:bg-neutral-800 hover:bg-indigo-50 dark:hover:bg-indigo-950/40 border border-neutral-200 dark:border-neutral-700 hover:border-indigo-400 text-[11px] font-bold text-neutral-800 dark:text-neutral-200 transition-all text-center flex flex-col items-center gap-1 shadow-2xs group"
                >
                  <span className="text-sm">🔍</span>
                  <span className="truncate w-full text-[10px]">Example</span>
                </button>
              </div>
            </div>

            {/* Quick Socratic Prompt Chips */}
            <div className="px-3 pt-2 pb-1 border-b border-neutral-100 dark:border-neutral-800 flex items-center gap-1.5 overflow-x-auto text-[11px] scrollbar-none">
              <button
                onClick={() => handleQuickChipClick('Explain Tau = I * Alpha')}
                className="px-2.5 py-1 rounded-full bg-neutral-100 dark:bg-neutral-800 hover:bg-neutral-200 text-neutral-700 dark:text-neutral-300 shrink-0 text-[11px] transition-colors"
              >
                Why is I proportional to r²?
              </button>
              <button
                onClick={() => handleQuickChipClick('Give me a practice problem on Torque')}
                className="px-2.5 py-1 rounded-full bg-neutral-100 dark:bg-neutral-800 hover:bg-neutral-200 text-neutral-700 dark:text-neutral-300 shrink-0 text-[11px] transition-colors"
              >
                Give practice problem
              </button>
            </div>

            {/* Chat Messages Stream */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {messages.map((m) => {
                const isUser = m.sender === 'user'
                return (
                  <div
                    key={m.id}
                    className={cn(
                      'flex gap-2.5 max-w-[90%]',
                      isUser ? 'ms-auto flex-row-reverse' : ''
                    )}
                  >
                    <div
                      className={cn(
                        'size-6 rounded-full flex items-center justify-center text-[10px] shrink-0 font-bold',
                        isUser
                          ? 'bg-blue-600 text-white'
                          : 'bg-gradient-to-tr from-indigo-600 to-purple-600 text-white'
                      )}
                    >
                      {isUser ? 'Z' : <Bot className="size-3.5" />}
                    </div>

                    <div className="min-w-0">
                      <div
                        className={cn(
                          'p-3 rounded-2xl text-xs leading-relaxed break-words',
                          isUser
                            ? 'bg-blue-600 text-white rounded-te-xs'
                            : 'bg-neutral-100 dark:bg-neutral-800 text-neutral-900 dark:text-neutral-100 rounded-ts-xs border border-neutral-200 dark:border-neutral-700'
                        )}
                      >
                        {m.text ? (
                          <div className="space-y-1.5 whitespace-pre-wrap">{m.text}</div>
                        ) : (
                          <div className="flex items-center gap-1.5 text-neutral-400 py-1">
                            <span className="size-1.5 rounded-full bg-indigo-500 animate-bounce" />
                            <span className="size-1.5 rounded-full bg-indigo-500 animate-bounce [animation-delay:0.2s]" />
                            <span className="size-1.5 rounded-full bg-indigo-500 animate-bounce [animation-delay:0.4s]" />
                          </div>
                        )}
                      </div>
                      <span className="text-[9px] text-neutral-400 mt-1 inline-block px-1">
                        {m.timestamp}
                      </span>
                    </div>
                  </div>
                )
              })}
              <div ref={chatBottomRef} />
            </div>

            {/* Chat Input Box */}
            <form
              onSubmit={(e) => {
                e.preventDefault()
                handleSendMessage()
              }}
              className="p-3 border-t border-neutral-200 dark:border-neutral-800 bg-neutral-50 dark:bg-neutral-900/80 flex items-center gap-2"
            >
              <input
                type="text"
                value={inputPrompt}
                onChange={(e) => setInputPrompt(e.target.value)}
                placeholder="Ask Socratic tutor a question..."
                className="flex-1 px-3 py-2 rounded-xl border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-800 text-xs text-neutral-900 dark:text-white placeholder:text-neutral-400 focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
              />
              <button
                type="submit"
                disabled={!inputPrompt.trim() || isStreaming}
                className="p-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white transition-colors flex items-center justify-center shrink-0 shadow-2xs"
              >
                <Send className="size-4" />
              </button>
            </form>
          </aside>
        )}
      </div>
    </div>
  )
}
