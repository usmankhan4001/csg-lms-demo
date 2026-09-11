'use client'

import React, { useState, useEffect, useRef } from 'react'
import Link from 'next/link'
import { useParams, useRouter } from 'next/navigation'
import {
  Mic,
  MicOff,
  Video,
  VideoOff,
  ScreenShare,
  Hand,
  Smile,
  PhoneOff,
  MessageSquare,
  Sparkles,
  Users,
  Settings,
  Maximize2,
  Minimize2,
  Volume2,
  Pin,
  MoreVertical,
  Radio,
  Send,
  Bot,
  User,
  CheckCircle2,
  Sparkle,
  Zap,
  HelpCircle,
  Clock,
  Shield,
  Layers,
  ChevronRight,
  Info,
  X,
} from 'lucide-react'
import { cn } from '@/lib/utils'

interface Participant {
  id: string
  name: string
  role: 'teacher' | 'student' | 'ta'
  isSpeaking: boolean
  isMuted: boolean
  isVideoOn: boolean
  isHandRaised: boolean
  avatar: string
  color: string
}

interface ChatMessage {
  id: string
  sender: string
  role: 'teacher' | 'student' | 'ta'
  text: string
  time: string
  isAi?: boolean
}

const PARTICIPANTS: Participant[] = [
  {
    id: 'p-1',
    name: 'Dr. Fatima Noor (Instructor)',
    role: 'teacher',
    isSpeaking: true,
    isMuted: false,
    isVideoOn: true,
    isHandRaised: false,
    avatar: 'FN',
    color: 'from-blue-600 to-indigo-600',
  },
  {
    id: 'p-2',
    name: 'Zaid Usman Khan (You)',
    role: 'student',
    isSpeaking: false,
    isMuted: true,
    isVideoOn: true,
    isHandRaised: false,
    avatar: 'ZK',
    color: 'from-emerald-600 to-teal-600',
  },
  {
    id: 'p-3',
    name: 'Amina Tariq',
    role: 'student',
    isSpeaking: false,
    isMuted: true,
    isVideoOn: true,
    isHandRaised: true,
    avatar: 'AT',
    color: 'from-purple-600 to-pink-600',
  },
  {
    id: 'p-4',
    name: 'Bilal Hashmi',
    role: 'student',
    isSpeaking: false,
    isMuted: true,
    isVideoOn: false,
    isHandRaised: false,
    avatar: 'BH',
    color: 'from-amber-600 to-orange-600',
  },
  {
    id: 'p-5',
    name: 'Maryam Rizvi (TA)',
    role: 'ta',
    isSpeaking: false,
    isMuted: true,
    isVideoOn: true,
    isHandRaised: false,
    avatar: 'MR',
    color: 'from-cyan-600 to-blue-600',
  },
]

export default function LiveClassroomPage() {
  const params = useParams()
  const router = useRouter()
  const roomId = params?.roomId as string || 'phy-401-live'

  // Classroom States
  const [isMicMuted, setIsMicMuted] = useState(true)
  const [isVideoActive, setIsVideoActive] = useState(true)
  const [isScreenSharing, setIsScreenSharing] = useState(false)
  const [isHandRaised, setIsHandRaised] = useState(false)
  const [activeTab, setActiveTab] = useState<'chat' | 'ai' | 'roster'>('ai')
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [leaveModalOpen, setLeaveModalOpen] = useState(false)
  const [reactions, setReactions] = useState<{ id: number; emoji: string; x: number }[]>([])
  const [showReactionsMenu, setShowReactionsMenu] = useState(false)

  // Live Timer
  const [sessionSeconds, setSessionSeconds] = useState(2054) // 34 mins 14 secs
  useEffect(() => {
    const timer = setInterval(() => setSessionSeconds((s) => s + 1), 1000)
    return () => clearInterval(timer)
  }, [])

  const formatTimer = (totalSeconds: number) => {
    const hrs = Math.floor(totalSeconds / 3600)
    const mins = Math.floor((totalSeconds % 3600) / 60)
    const secs = totalSeconds % 60
    return `${hrs > 0 ? `${hrs}:` : ''}${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
  }

  // Session Chat Messages
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([
    {
      id: 'c-1',
      sender: 'Dr. Fatima Noor',
      role: 'teacher',
      text: 'Welcome everyone! Today we will derive the parallel axis theorem and test it on a cylinder.',
      time: '10:30 AM',
    },
    {
      id: 'c-2',
      sender: 'Maryam Rizvi (TA)',
      role: 'ta',
      text: 'Lecture slides and notes have been pinned to the shared resource repository.',
      time: '10:32 AM',
    },
    {
      id: 'c-3',
      sender: 'Amina Tariq',
      role: 'student',
      text: 'Question: Does the distance d in I = I_cm + Md² always have to be measured from the center of mass?',
      time: '10:44 AM',
    },
  ])
  const [chatInput, setChatInput] = useState('')

  // AI Copilot Live Queries & Transcript Insights
  const [aiQueries, setAiQueries] = useState<
    { id: string; query: string; response: string; timestamp: string }[]
  >([
    {
      id: 'ai-1',
      query: 'Summarize the last 5 minutes of lecture',
      response:
        'Dr. Fatima explained the **Parallel Axis Theorem** ($I = I_{cm} + M d^2$). Key point: the moment of inertia around any arbitrary parallel axis is always strictly greater than the moment of inertia through the center of mass.',
      timestamp: '10:45 AM',
    },
  ])
  const [aiCustomPrompt, setAiCustomPrompt] = useState('')
  const [isAiLoading, setIsAiLoading] = useState(false)

  // Floating Emoji Reaction Trigger
  const triggerReaction = (emoji: string) => {
    const newReaction = {
      id: Date.now() + Math.random(),
      emoji,
      x: Math.random() * 60 + 20, // random percentage for animation position
    }
    setReactions((prev) => [...prev, newReaction])
    setTimeout(() => {
      setReactions((prev) => prev.filter((r) => r.id !== newReaction.id))
    }, 2500)
    setShowReactionsMenu(false)
  }

  // Handle Send Chat
  const handleSendChat = (e: React.FormEvent) => {
    e.preventDefault()
    if (!chatInput.trim()) return

    setChatMessages((prev) => [
      ...prev,
      {
        id: `chat-${Date.now()}`,
        sender: 'Zaid Usman Khan',
        role: 'student',
        text: chatInput,
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      },
    ])
    setChatInput('')
  }

  // Handle Ask Live AI Copilot
  const handleAskAiCopilot = (promptText?: string) => {
    const queryToAsk = promptText || aiCustomPrompt
    if (!queryToAsk.trim()) return

    setIsAiLoading(true)
    const newQueryId = `ai-q-${Date.now()}`

    setTimeout(() => {
      let aiResp = `Based on Dr. Fatima's ongoing audio stream: regarding "${queryToAsk}", the key relationship to keep in mind is that rotational inertia depends on the square of the distance from the pivot ($r^2$).`
      if (queryToAsk.toLowerCase().includes('summarize')) {
        aiResp = `**Live Lecture Recap (Last 10 mins):**\n1. Stated Parallel Axis Theorem: $I = I_{cm} + M d^2$\n2. Demonstrated derivation using center of mass coordinate origin.\n3. Addressed Amina's question: Yes, one of the two axes *must* pass strictly through the center of mass.`
      } else if (queryToAsk.toLowerCase().includes('formula') || queryToAsk.toLowerCase().includes('theorem')) {
        aiResp = `**Parallel Axis Theorem Formulation:**\n$$I_{\\text{parallel}} = I_{\\text{cm}} + M d^2$$\nWhere:\n• $I_{\\text{cm}}$: Moment of inertia about the center of mass.\n• $M$: Total mass of rigid body.\n• $d$: Perpendicular distance between the two parallel axes.`
      }

      setAiQueries((prev) => [
        ...prev,
        {
          id: newQueryId,
          query: queryToAsk,
          response: aiResp,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
      ])
      setIsAiLoading(false)
      if (!promptText) setAiCustomPrompt('')
    }, 700)
  }

  return (
    <div className="flex flex-col h-screen bg-neutral-950 text-neutral-100 overflow-hidden select-none">
      {/* Top Header Bar */}
      <header className="h-14 border-b border-neutral-800 px-4 flex items-center justify-between bg-neutral-900/90 backdrop-blur-md shrink-0 z-20">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="flex size-2.5 rounded-full bg-rose-500 animate-pulse" />
            <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-rose-500/20 text-rose-400 border border-rose-500/30 uppercase tracking-wider">
              LIVE REC
            </span>
          </div>

          <div className="h-4 w-px bg-neutral-800" />

          <div>
            <h1 className="text-xs sm:text-sm font-bold text-white flex items-center gap-2 truncate">
              <span>PHY-401: Advanced Physics Mechanics</span>
              <span className="hidden md:inline-block px-1.5 py-0.5 rounded text-[10px] bg-neutral-800 text-neutral-400 font-mono">
                Room #{roomId}
              </span>
            </h1>
          </div>
        </div>

        {/* Header Right: Session Timer & Leave */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-neutral-800/80 border border-neutral-700/60 text-xs font-mono text-neutral-300">
            <Clock className="size-3.5 text-blue-400" />
            <span>{formatTimer(sessionSeconds)}</span>
          </div>

          <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-semibold">
            <Shield className="size-3.5" />
            <span>End-to-End Encrypted</span>
          </div>

          <button
            onClick={() => setLeaveModalOpen(true)}
            className="px-3.5 py-1.5 rounded-xl bg-rose-600/90 hover:bg-rose-600 text-white text-xs font-bold transition-colors shadow-xs flex items-center gap-1.5"
          >
            <PhoneOff className="size-3.5" />
            <span>Leave Class</span>
          </button>
        </div>
      </header>

      {/* Main Classroom Stage Area */}
      <div className="flex-1 flex overflow-hidden relative">
        {/* Left / Center Video Stage */}
        <div className="flex-1 flex flex-col p-3 sm:p-4 overflow-hidden relative">
          {/* Main Speaker Spotlight Container */}
          <div className="flex-1 relative rounded-2xl overflow-hidden bg-neutral-900 border border-neutral-800 shadow-2xl flex flex-col justify-between p-4 group">
            {/* Background Stream Simulation Graphic */}
            <div className="absolute inset-0 bg-gradient-to-br from-neutral-900 via-indigo-950/40 to-neutral-950 pointer-events-none" />

            {/* Simulated Live Teacher Stage Video Content */}
            <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
              <div className="relative size-32 rounded-3xl bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center text-white text-3xl font-extrabold shadow-2xl ring-4 ring-blue-500/30 animate-pulse">
                FN
                {/* Speaking Wave Visualizer */}
                <span className="absolute -bottom-2 px-2.5 py-0.5 rounded-full bg-blue-500 text-[10px] font-bold tracking-wider uppercase text-white shadow-md">
                  Active Speaker
                </span>
              </div>
              <p className="mt-4 text-sm font-semibold text-neutral-200">
                Dr. Fatima Noor is presenting: Parallel Axis Theorem & Moment of Inertia
              </p>
              <div className="mt-2 flex items-center gap-1.5">
                {[40, 75, 55, 90, 60, 80, 45].map((h, idx) => (
                  <div
                    key={idx}
                    className="w-1 bg-blue-400 rounded-full animate-pulse"
                    style={{ height: `${h * 0.25}px`, animationDelay: `${idx * 120}ms` }}
                  />
                ))}
              </div>
            </div>

            {/* Top Stage Badges */}
            <div className="relative z-10 flex items-center justify-between text-xs">
              <div className="flex items-center gap-2 bg-black/60 backdrop-blur-md px-3 py-1.5 rounded-xl border border-white/10">
                <span className="size-2 rounded-full bg-emerald-400" />
                <span className="font-bold text-white">Dr. Fatima Noor</span>
                <span className="text-neutral-400 font-mono text-[10px]">• 1080p 60fps</span>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => alert('Pinning video stream')}
                  className="p-1.5 rounded-lg bg-black/50 hover:bg-black/80 text-white/80 transition-colors border border-white/10"
                  title="Pin Spotlight"
                >
                  <Pin className="size-3.5" />
                </button>
                <button
                  onClick={() => alert('Fullscreen toggled')}
                  className="p-1.5 rounded-lg bg-black/50 hover:bg-black/80 text-white/80 transition-colors border border-white/10"
                  title="Maximize"
                >
                  <Maximize2 className="size-3.5" />
                </button>
              </div>
            </div>

            {/* Floating Live AI Subtitles Bar */}
            <div className="relative z-10 mx-auto max-w-xl bg-black/80 backdrop-blur-md border border-white/15 px-4 py-2 rounded-xl text-center text-xs text-neutral-200 shadow-xl">
              <span className="text-indigo-400 font-bold me-2">AI Realtime Captions:</span>
              <span>&ldquo;...so by substituting the center of mass coordinate into the integral, the cross terms vanish!&rdquo;</span>
            </div>

            {/* Floating Emoji Reactions Layer */}
            <div className="absolute inset-0 pointer-events-none overflow-hidden">
              {reactions.map((r) => (
                <div
                  key={r.id}
                  className="absolute bottom-16 text-3xl animate-bounce transition-all duration-1000"
                  style={{ left: `${r.x}%` }}
                >
                  {r.emoji}
                </div>
              ))}
            </div>
          </div>

          {/* Participant Thumbnail Strip */}
          <div className="mt-3 flex items-center gap-2.5 overflow-x-auto py-1 scrollbar-none">
            {PARTICIPANTS.map((part) => (
              <div
                key={part.id}
                className={cn(
                  'relative h-24 w-36 rounded-xl border shrink-0 bg-neutral-900 overflow-hidden flex flex-col justify-between p-2 transition-all',
                  part.isSpeaking
                    ? 'border-blue-500 ring-2 ring-blue-500/40 shadow-lg'
                    : 'border-neutral-800 hover:border-neutral-700'
                )}
              >
                <div className="flex items-center justify-between text-[10px]">
                  <span className="font-semibold text-neutral-300 truncate max-w-[80px]">
                    {part.name.split(' ')[0]}
                  </span>
                  {part.isHandRaised && (
                    <span className="size-4 rounded-full bg-amber-500 text-black flex items-center justify-center font-bold text-[10px]">
                      ✋
                    </span>
                  )}
                </div>

                <div className="flex items-center justify-center my-auto">
                  <div
                    className={cn(
                      'size-8 rounded-full flex items-center justify-center text-xs font-bold text-white bg-gradient-to-tr',
                      part.color
                    )}
                  >
                    {part.avatar}
                  </div>
                </div>

                <div className="flex items-center justify-between text-[10px] text-neutral-400">
                  <span>{part.role === 'teacher' ? 'Host' : part.role === 'ta' ? 'TA' : 'Student'}</span>
                  {part.isMuted ? (
                    <MicOff className="size-3 text-rose-500" />
                  ) : (
                    <Mic className="size-3 text-emerald-400" />
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Bottom Dock Control Bar */}
          <div className="mt-2 h-16 rounded-2xl bg-neutral-900 border border-neutral-800 px-4 sm:px-6 flex items-center justify-between shrink-0 shadow-xl">
            {/* Audio & Video Controls */}
            <div className="flex items-center gap-2">
              <button
                onClick={() => setIsMicMuted(!isMicMuted)}
                className={cn(
                  'flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold transition-all shadow-xs',
                  isMicMuted
                    ? 'bg-rose-600/20 text-rose-400 border border-rose-500/40 hover:bg-rose-600/30'
                    : 'bg-emerald-600 text-white hover:bg-emerald-700'
                )}
              >
                {isMicMuted ? <MicOff className="size-4" /> : <Mic className="size-4" />}
                <span className="hidden sm:inline">{isMicMuted ? 'Unmute' : 'Mute'}</span>
              </button>

              <button
                onClick={() => setIsVideoActive(!isVideoActive)}
                className={cn(
                  'flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold transition-all shadow-xs',
                  !isVideoActive
                    ? 'bg-rose-600/20 text-rose-400 border border-rose-500/40 hover:bg-rose-600/30'
                    : 'bg-neutral-800 text-neutral-200 hover:bg-neutral-700 border border-neutral-700'
                )}
              >
                {isVideoActive ? <Video className="size-4" /> : <VideoOff className="size-4" />}
                <span className="hidden sm:inline">{isVideoActive ? 'Stop Video' : 'Start Video'}</span>
              </button>
            </div>

            {/* Center Collaboration Controls */}
            <div className="flex items-center gap-1.5 sm:gap-2">
              <button
                onClick={() => setIsScreenSharing(!isScreenSharing)}
                className={cn(
                  'p-2.5 rounded-xl text-xs font-semibold transition-all border',
                  isScreenSharing
                    ? 'bg-blue-600 text-white border-blue-500'
                    : 'bg-neutral-800 text-neutral-300 border-neutral-700 hover:bg-neutral-700'
                )}
                title="Share Screen"
              >
                <ScreenShare className="size-4" />
              </button>

              <button
                onClick={() => {
                  setIsHandRaised(!isHandRaised)
                  if (!isHandRaised) triggerReaction('✋')
                }}
                className={cn(
                  'flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-semibold transition-all border',
                  isHandRaised
                    ? 'bg-amber-500 text-neutral-950 border-amber-400 font-bold ring-2 ring-amber-400/30'
                    : 'bg-neutral-800 text-neutral-300 border-neutral-700 hover:bg-neutral-700'
                )}
              >
                <Hand className="size-4" />
                <span className="hidden md:inline">{isHandRaised ? 'Hand Raised' : 'Raise Hand'}</span>
              </button>

              {/* Reactions Menu Toggle */}
              <div className="relative">
                <button
                  onClick={() => setShowReactionsMenu(!showReactionsMenu)}
                  className="p-2.5 rounded-xl bg-neutral-800 text-neutral-300 border border-neutral-700 hover:bg-neutral-700 transition-colors"
                  title="Emoji Reactions"
                >
                  <Smile className="size-4" />
                </button>

                {showReactionsMenu && (
                  <div className="absolute bottom-14 left-1/2 -translate-x-1/2 bg-neutral-900 border border-neutral-700 p-2 rounded-2xl shadow-2xl flex items-center gap-1.5 animate-in fade-in">
                    {['👍', '👏', '❤️', '💡', '🙋‍♂️', '🔥'].map((emoji) => (
                      <button
                        key={emoji}
                        onClick={() => triggerReaction(emoji)}
                        className="size-8 rounded-xl hover:bg-neutral-800 text-lg flex items-center justify-center transition-transform hover:scale-125"
                      >
                        {emoji}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Right Toggle Sidebar */}
            <div className="flex items-center gap-2">
              <button
                onClick={() => setSidebarOpen(!sidebarOpen)}
                className={cn(
                  'flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-semibold transition-all border',
                  sidebarOpen
                    ? 'bg-indigo-600 text-white border-indigo-500'
                    : 'bg-neutral-800 text-neutral-300 border-neutral-700 hover:bg-neutral-700'
                )}
              >
                <Sparkles className="size-4 text-indigo-300" />
                <span className="hidden sm:inline">AI Copilot & Chat</span>
              </button>
            </div>
          </div>
        </div>

        {/* Right Sidebar: Tabs for Chat, Live AI Copilot & Roster */}
        {sidebarOpen && (
          <aside className="w-80 sm:w-96 border-s border-neutral-800 bg-neutral-900 flex flex-col shrink-0 overflow-hidden shadow-2xl z-20">
            {/* Sidebar Tab Header */}
            <div className="p-2 border-b border-neutral-800 bg-neutral-950 flex items-center justify-between">
              <div className="flex items-center gap-1">
                <button
                  onClick={() => setActiveTab('ai')}
                  className={cn(
                    'flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold transition-all',
                    activeTab === 'ai'
                      ? 'bg-indigo-600 text-white shadow-2xs'
                      : 'text-neutral-400 hover:text-white hover:bg-neutral-800'
                  )}
                >
                  <Sparkles className="size-3.5 text-indigo-300" />
                  <span>AI Copilot</span>
                </button>

                <button
                  onClick={() => setActiveTab('chat')}
                  className={cn(
                    'flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold transition-all',
                    activeTab === 'chat'
                      ? 'bg-blue-600 text-white shadow-2xs'
                      : 'text-neutral-400 hover:text-white hover:bg-neutral-800'
                  )}
                >
                  <MessageSquare className="size-3.5" />
                  <span>Chat</span>
                </button>

                <button
                  onClick={() => setActiveTab('roster')}
                  className={cn(
                    'flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold transition-all',
                    activeTab === 'roster'
                      ? 'bg-neutral-800 text-white shadow-2xs'
                      : 'text-neutral-400 hover:text-white hover:bg-neutral-800'
                  )}
                >
                  <Users className="size-3.5" />
                  <span>Roster (28)</span>
                </button>
              </div>

              <button
                onClick={() => setSidebarOpen(false)}
                className="p-1 rounded-lg text-neutral-400 hover:text-white hover:bg-neutral-800"
              >
                <X className="size-4" />
              </button>
            </div>

            {/* TAB 1: LIVE AI COPILOT */}
            {activeTab === 'ai' && (
              <div className="flex-1 flex flex-col overflow-hidden bg-neutral-900/60">
                {/* AI Copilot Description Banner */}
                <div className="p-3.5 bg-gradient-to-r from-indigo-950 to-neutral-900 border-b border-indigo-900/40">
                  <div className="flex items-center gap-2">
                    <Bot className="size-4 text-indigo-400" />
                    <span className="text-xs font-bold text-white">
                      Live AI Q&A & Lecture Copilot
                    </span>
                  </div>
                  <p className="text-[11px] text-indigo-200/80 mt-1">
                    Ask instant questions about what the instructor is currently explaining without interrupting the class.
                  </p>
                </div>

                {/* Quick AI Prompts */}
                <div className="p-2.5 border-b border-neutral-800 flex items-center gap-1.5 overflow-x-auto text-[11px] scrollbar-none bg-neutral-950">
                  <button
                    onClick={() => handleAskAiCopilot('Summarize the last 5 minutes of lecture')}
                    className="px-2.5 py-1 rounded-full bg-indigo-950 hover:bg-indigo-900 text-indigo-200 border border-indigo-800/60 shrink-0 text-[11px] transition-colors"
                  >
                    ⏱️ Summarize last 5m
                  </button>
                  <button
                    onClick={() => handleAskAiCopilot('Explain the Parallel Axis Theorem formula')}
                    className="px-2.5 py-1 rounded-full bg-indigo-950 hover:bg-indigo-900 text-indigo-200 border border-indigo-800/60 shrink-0 text-[11px] transition-colors"
                  >
                    📐 Explain Formula
                  </button>
                </div>

                {/* AI Query Logs */}
                <div className="flex-1 overflow-y-auto p-3.5 space-y-4">
                  {aiQueries.map((q) => (
                    <div key={q.id} className="space-y-2">
                      <div className="flex items-center justify-between text-[10px] text-neutral-400">
                        <span className="font-semibold text-neutral-300">Q: &ldquo;{q.query}&rdquo;</span>
                        <span>{q.timestamp}</span>
                      </div>
                      <div className="p-3.5 rounded-2xl bg-indigo-950/40 border border-indigo-800/50 text-xs text-indigo-100 leading-relaxed">
                        <div className="flex items-center gap-1.5 text-indigo-300 font-bold mb-1">
                          <Sparkles className="size-3" />
                          <span>AI Answer:</span>
                        </div>
                        <div className="whitespace-pre-wrap">{q.response}</div>
                      </div>
                    </div>
                  ))}

                  {isAiLoading && (
                    <div className="p-3 rounded-2xl bg-indigo-950/30 border border-indigo-800/30 flex items-center gap-2 text-xs text-indigo-300">
                      <span className="size-2 rounded-full bg-indigo-400 animate-ping" />
                      <span>Transcribing audio & analyzing context...</span>
                    </div>
                  )}
                </div>

                {/* AI Query Input */}
                <form
                  onSubmit={(e) => {
                    e.preventDefault()
                    handleAskAiCopilot()
                  }}
                  className="p-3 border-t border-neutral-800 bg-neutral-950 flex items-center gap-2"
                >
                  <input
                    type="text"
                    value={aiCustomPrompt}
                    onChange={(e) => setAiCustomPrompt(e.target.value)}
                    placeholder="Ask AI Copilot about lecture..."
                    className="flex-1 px-3 py-2 rounded-xl border border-neutral-800 bg-neutral-900 text-xs text-white placeholder:text-neutral-500 focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                  />
                  <button
                    type="submit"
                    disabled={!aiCustomPrompt.trim() || isAiLoading}
                    className="p-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white transition-colors"
                  >
                    <Send className="size-4" />
                  </button>
                </form>
              </div>
            )}

            {/* TAB 2: SESSION CHAT */}
            {activeTab === 'chat' && (
              <div className="flex-1 flex flex-col overflow-hidden bg-neutral-900/60">
                <div className="flex-1 overflow-y-auto p-3.5 space-y-3">
                  {chatMessages.map((msg) => (
                    <div key={msg.id} className="space-y-0.5">
                      <div className="flex items-center justify-between text-[11px]">
                        <span
                          className={cn(
                            'font-bold',
                            msg.role === 'teacher'
                              ? 'text-blue-400'
                              : msg.role === 'ta'
                              ? 'text-cyan-400'
                              : 'text-neutral-300'
                          )}
                        >
                          {msg.sender}
                        </span>
                        <span className="text-[10px] text-neutral-500">{msg.time}</span>
                      </div>
                      <p className="p-2.5 rounded-xl bg-neutral-800/80 border border-neutral-700/60 text-xs text-neutral-200 leading-snug">
                        {msg.text}
                      </p>
                    </div>
                  ))}
                </div>

                <form
                  onSubmit={handleSendChat}
                  className="p-3 border-t border-neutral-800 bg-neutral-950 flex items-center gap-2"
                >
                  <input
                    type="text"
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    placeholder="Send a message to class..."
                    className="flex-1 px-3 py-2 rounded-xl border border-neutral-800 bg-neutral-900 text-xs text-white placeholder:text-neutral-500 focus:outline-hidden focus:ring-2 focus:ring-blue-500"
                  />
                  <button
                    type="submit"
                    disabled={!chatInput.trim()}
                    className="p-2 rounded-xl bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white transition-colors"
                  >
                    <Send className="size-4" />
                  </button>
                </form>
              </div>
            )}

            {/* TAB 3: PARTICIPANT ROSTER */}
            {activeTab === 'roster' && (
              <div className="flex-1 flex flex-col overflow-hidden p-3.5 space-y-3 bg-neutral-900/60">
                <div className="text-xs font-bold text-neutral-400 uppercase tracking-wider">
                  In This Session (28)
                </div>
                <div className="space-y-2 overflow-y-auto flex-1">
                  {PARTICIPANTS.map((part) => (
                    <div
                      key={part.id}
                      className="p-2.5 rounded-xl border border-neutral-800 bg-neutral-950 flex items-center justify-between"
                    >
                      <div className="flex items-center gap-2.5">
                        <div
                          className={cn(
                            'size-7 rounded-full flex items-center justify-center text-[10px] font-bold text-white bg-gradient-to-tr',
                            part.color
                          )}
                        >
                          {part.avatar}
                        </div>
                        <div>
                          <div className="text-xs font-bold text-neutral-200">{part.name}</div>
                          <span className="text-[10px] text-neutral-500 capitalize">
                            {part.role}
                          </span>
                        </div>
                      </div>

                      <div className="flex items-center gap-1.5">
                        {part.isMuted ? (
                          <MicOff className="size-3.5 text-rose-500" />
                        ) : (
                          <Mic className="size-3.5 text-emerald-400" />
                        )}
                        {part.isVideoOn ? (
                          <Video className="size-3.5 text-blue-400" />
                        ) : (
                          <VideoOff className="size-3.5 text-neutral-500" />
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </aside>
        )}
      </div>

      {/* Leave Classroom Confirmation Dialog */}
      {leaveModalOpen && (
        <div
          className="fixed inset-0 z-50 bg-black/80 backdrop-blur-xs flex items-center justify-center p-4 animate-in fade-in"
          role="dialog"
          aria-modal="true"
        >
          <div className="w-full max-w-sm bg-neutral-900 border border-neutral-800 rounded-2xl shadow-2xl p-6 text-center space-y-4">
            <div className="size-12 rounded-full bg-rose-500/20 text-rose-400 mx-auto flex items-center justify-center">
              <PhoneOff className="size-6" />
            </div>

            <div>
              <h3 className="text-base font-bold text-white">Leave Virtual Classroom?</h3>
              <p className="text-xs text-neutral-400 mt-1">
                Your attendance for this session (34 mins) will be logged into your academic record.
              </p>
            </div>

            <div className="flex items-center justify-center gap-2 pt-2">
              <button
                onClick={() => setLeaveModalOpen(false)}
                className="px-4 py-2 rounded-xl border border-neutral-700 bg-neutral-800 text-xs font-semibold text-neutral-300 hover:bg-neutral-700 transition-colors"
              >
                Stay in Class
              </button>

              <button
                onClick={() => router.push('/student')}
                className="px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-700 text-xs font-bold text-white transition-colors shadow-xs"
              >
                Confirm Leave
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
