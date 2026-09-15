'use client';

import React, { useState, useEffect, useRef } from 'react';
import {
  Send,
  Sparkles,
  HelpCircle,
  Lightbulb,
  BookOpen,
  Clock,
  ShieldAlert,
  AlertTriangle,
  ArrowRight,
  RefreshCw,
  PhoneCall,
  ExternalLink,
  GraduationCap,
  Layers,
  ChevronRight,
  CheckCircle2,
  Lock,
} from 'lucide-react';
import 'katex/dist/katex.min.css';
import { InlineMath, BlockMath } from 'react-katex';

export type BloomLevel = 'REMEMBER' | 'UNDERSTAND' | 'APPLY' | 'ANALYZE' | 'EVALUATE' | 'CREATE';
export type HintTier = 1 | 2 | 3;

export interface ChatMessage {
  id: string;
  sender: 'student' | 'tutor' | 'system';
  content: string;
  timestamp: string;
  bloomLevel?: BloomLevel;
  hintTier?: HintTier;
  isCrisisAlert?: boolean;
  crisisData?: {
    category: string;
    severity: string;
    hotlines: Array<{ name: string; contact: string; action_type?: string }>;
  };
}

export interface SocraticLearnerStudioProps {
  studentId?: string;
  courseId?: string;
  subjectTitle?: string;
  dailyMinutesBudget?: number;
  initialMinutesUsed?: number;
  onSessionTimeout?: () => void;
}

const BLOOM_STAGES: Array<{ level: BloomLevel; label: string; desc: string }> = [
  { level: 'REMEMBER', label: 'Remember', desc: 'Recall definitions & core terms' },
  { level: 'UNDERSTAND', label: 'Understand', desc: 'Explain concepts in own words' },
  { level: 'APPLY', label: 'Apply', desc: 'Solve scenarios with formulas' },
  { level: 'ANALYZE', label: 'Analyze', desc: 'Break down structures & patterns' },
  { level: 'EVALUATE', label: 'Evaluate', desc: 'Critique & justify solution methods' },
];

export const SocraticLearnerStudio: React.FC<SocraticLearnerStudioProps> = ({
  studentId = 'student-current',
  courseId = 'course-101',
  subjectTitle = 'Advanced Physics & Calculus',
  dailyMinutesBudget = 45,
  initialMinutesUsed = 12,
  onSessionTimeout,
}) => {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome-1',
      sender: 'tutor',
      content:
        'Hello! I am your Socratic AI Academic Tutor. I am here to help you reason through tough problems step-by-step.\n\nWhat concept or assignment problem are we exploring today?',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      bloomLevel: 'REMEMBER',
    },
  ]);

  const [inputQuery, setInputQuery] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [selectedHintTier, setSelectedHintTier] = useState<HintTier | null>(null);
  const [currentBloom, setCurrentBloom] = useState<BloomLevel>('REMEMBER');
  const [minutesUsed, setMinutesUsed] = useState(initialMinutesUsed);
  const [crisisIntercepted, setCrisisIntercepted] = useState(false);
  const [activeCrisisCard, setActiveCrisisCard] = useState<any | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll chat to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isGenerating]);

  // Screen-time countdown timer simulation (updates every minute)
  useEffect(() => {
    const timer = setInterval(() => {
      setMinutesUsed((prev) => {
        const next = prev + 1;
        if (next >= dailyMinutesBudget && onSessionTimeout) {
          onSessionTimeout();
        }
        return next;
      });
    }, 60000);
    return () => clearInterval(timer);
  }, [dailyMinutesBudget, onSessionTimeout]);

  const remainingMinutes = Math.max(0, dailyMinutesBudget - minutesUsed);
  const screenTimePercent = Math.min(100, Math.round((minutesUsed / dailyMinutesBudget) * 100));

  // Render text containing inline or block LaTeX formulas safely
  const renderFormattedContent = (text: string) => {
    // Regex matches $$block math$$ or $inline math$
    const parts = text.split(/(\$\$[\s\S]+?\$\$|\$[^\$\n]+?\$)/g);

    return (
      <div className="space-y-2 text-sm leading-relaxed text-slate-800 dark:text-slate-100">
        {parts.map((part, idx) => {
          if (part.startsWith('$$') && part.endsWith('$$')) {
            const math = part.slice(2, -2).trim();
            try {
              return <BlockMath key={idx} math={math} />;
            } catch (err) {
              return <code key={idx} className="block p-2 text-xs bg-slate-100 dark:bg-slate-800 rounded font-mono">{part}</code>;
            }
          } else if (part.startsWith('$') && part.endsWith('$')) {
            const math = part.slice(1, -1).trim();
            try {
              return <InlineMath key={idx} math={math} />;
            } catch (err) {
              return <code key={idx} className="px-1 text-xs bg-slate-100 dark:bg-slate-800 rounded font-mono">{part}</code>;
            }
          }
          return <span key={idx}>{part}</span>;
        })}
      </div>
    );
  };

  const handleSendMessage = async (customTier?: HintTier) => {
    const query = inputQuery.trim();
    if (!query && !customTier) return;

    const activeTier = customTier || selectedHintTier;
    const studentMsgId = `msg-${Date.now()}`;
    const timestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    // Append student message
    const newStudentMsg: ChatMessage = {
      id: studentMsgId,
      sender: 'student',
      content: query || `[Requested Tier ${activeTier} Hint]`,
      timestamp,
      hintTier: activeTier || undefined,
    };

    setMessages((prev) => [...prev, newStudentMsg]);
    setInputQuery('');
    setSelectedHintTier(null);
    setIsGenerating(true);

    // Crisis screening regex (client-side pre-screen preview)
    const crisisMatch = query.match(/(suicide|kill myself|want to die|self[-\s]?harm|end my life|shoot up|can'?t take this anymore)/i);
    if (crisisMatch) {
      setCrisisIntercepted(true);
      const crisisPayload = {
        category: 'SELF_HARM',
        severity: 'CRITICAL',
        hotlines: [
          { name: 'On-Call Campus Psychologist', contact: '+1 (800) 555-CARE', action_type: 'phone' },
          { name: 'Crisis Lifeline', contact: '988 (USA/CAN) or findahelpline.com', action_type: 'url' },
        ],
      };
      setActiveCrisisCard(crisisPayload);

      const crisisAlertMsg: ChatMessage = {
        id: `tutor-${Date.now()}`,
        sender: 'tutor',
        content:
          'It sounds like you are going through a very difficult time right now, and your wellbeing is our highest priority. The AI tutor has paused this session. Our on-call school counselor has been alerted to provide immediate confidential support.',
        timestamp,
        isCrisisAlert: true,
        crisisData: crisisPayload,
      };

      setMessages((prev) => [...prev, crisisAlertMsg]);
      setIsGenerating(false);
      return;
    }

    // Direct answer refusal check
    const cheatingMatch = query.match(/(give me the answer|do my homework|tell me the answer key|solve this test)/i);
    if (cheatingMatch) {
      setTimeout(() => {
        const refusalMsg: ChatMessage = {
          id: `tutor-${Date.now()}`,
          sender: 'tutor',
          content:
            'I cannot provide the direct answer or complete homework for you, as my goal is to guide you to understand it thoroughly.\n\nLet us break down the problem together: what fundamental formula or law applies here? For example, is Newton\'s Second Law $F = m \\cdot a$ or energy conservation relevant?',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          bloomLevel: currentBloom,
        };
        setMessages((prev) => [...prev, refusalMsg]);
        setIsGenerating(false);
      }, 700);
      return;
    }

    // Standard progressive Socratic response
    setTimeout(() => {
      let nextBloom = currentBloom;
      let replyContent = '';

      if (activeTier === 1) {
        replyContent =
          '💡 **Tier 1 (Conceptual Clue):** Think about how kinetic energy $E_k = \\frac{1}{2}mv^2$ relates to gravitational potential energy $U = mgh$. When a projectile reaches peak height, what is its vertical velocity component?';
        nextBloom = 'UNDERSTAND';
      } else if (activeTier === 2) {
        replyContent =
          '📐 **Tier 2 (Process & Strategy):** Set up the work-energy theorem:\n\n$$W_{\\text{net}} = \\Delta E_k = E_{k,\\text{final}} - E_{k,\\text{initial}}$$\n\nIdentify which forces do non-conservative work (e.g., friction or air resistance) versus conservative work.';
        nextBloom = 'APPLY';
      } else if (activeTier === 3) {
        replyContent =
          '🧩 **Tier 3 (Guided Analogous Sub-step):** Let\'s look at an analogous problem with simpler numbers: Suppose a $2\\text{ kg}$ object is dropped from $10\\text{ m}$.\n\n1. Initial potential energy: $U = 2 \\times 9.8 \\times 10 = 196\\text{ J}$.\n2. At ground level, all $U$ converts to $E_k$: $\\frac{1}{2}(2)v^2 = 196 \\implies v = 14\\text{ m/s}$.\n\nNow, apply this exact conservation step to your object with mass $m$ and height $h$. What is your initial total energy?';
        nextBloom = 'ANALYZE';
      } else {
        replyContent =
          'Great question! Let\'s analyze this systematically. What variables are given in the problem statement, and what target quantity are we solving for?';
      }

      setCurrentBloom(nextBloom);
      const tutorReply: ChatMessage = {
        id: `tutor-${Date.now()}`,
        sender: 'tutor',
        content: replyContent,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        bloomLevel: nextBloom,
      };

      setMessages((prev) => [...prev, tutorReply]);
      setIsGenerating(false);
    }, 900);
  };

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] max-w-6xl mx-auto p-4 gap-4">
      {/* Top Header & Screen-time Meter */}
      <header className="flex flex-wrap items-center justify-between p-4 bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-indigo-50 dark:bg-indigo-950/50 rounded-lg text-indigo-600 dark:text-indigo-400">
            <GraduationCap className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-lg font-semibold text-slate-900 dark:text-white flex items-center gap-2">
              Socratic AI Learner Studio
              <span className="text-xs px-2 py-0.5 rounded-full bg-indigo-100 dark:bg-indigo-900 text-indigo-700 dark:text-indigo-300 font-medium">
                Phase 4
              </span>
            </h1>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              {subjectTitle} • Student ID: {studentId}
            </p>
          </div>
        </div>

        {/* 45-Min Screen Time Gauge */}
        <div className="flex items-center gap-4 bg-slate-50 dark:bg-slate-800/60 px-4 py-2 rounded-lg border border-slate-200 dark:border-slate-700">
          <Clock className={`w-5 h-5 ${remainingMinutes <= 5 ? 'text-rose-500 animate-pulse' : 'text-emerald-500'}`} />
          <div className="flex flex-col">
            <div className="flex items-center justify-between gap-4 text-xs font-medium">
              <span className="text-slate-600 dark:text-slate-300">Daily Session Limit</span>
              <span className={remainingMinutes <= 5 ? 'text-rose-600 font-bold' : 'text-slate-900 dark:text-white'}>
                {remainingMinutes}m left ({minutesUsed}/{dailyMinutesBudget}m)
              </span>
            </div>
            <div className="w-36 h-2 bg-slate-200 dark:bg-slate-700 rounded-full mt-1 overflow-hidden">
              <div
                className={`h-full transition-all duration-500 ${
                  screenTimePercent > 85 ? 'bg-rose-500' : screenTimePercent > 60 ? 'bg-amber-500' : 'bg-indigo-600'
                }`}
                style={{ width: `${screenTimePercent}%` }}
              />
            </div>
          </div>
        </div>
      </header>

      {/* Bloom's Taxonomy Progression Tracker */}
      <div className="bg-white dark:bg-slate-900 p-3 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
            <Layers className="w-3.5 h-3.5" />
            Bloom's Taxonomy Cognitive Progression
          </span>
          <span className="text-xs font-medium text-indigo-600 dark:text-indigo-400">
            Active Level: {currentBloom}
          </span>
        </div>
        <div className="grid grid-cols-5 gap-2">
          {BLOOM_STAGES.map((stage, idx) => {
            const isCurrent = stage.level === currentBloom;
            const currentIdx = BLOOM_STAGES.findIndex((s) => s.level === currentBloom);
            const isCompleted = idx < currentIdx;

            return (
              <div
                key={stage.level}
                className={`p-2 rounded-lg border text-center transition-all ${
                  isCurrent
                    ? 'bg-indigo-50 dark:bg-indigo-950/60 border-indigo-500 text-indigo-900 dark:text-indigo-200 shadow-sm'
                    : isCompleted
                    ? 'bg-emerald-50 dark:bg-emerald-950/30 border-emerald-300 dark:border-emerald-800 text-emerald-800 dark:text-emerald-300'
                    : 'bg-slate-50 dark:bg-slate-800/40 border-slate-200 dark:border-slate-700 text-slate-400 opacity-70'
                }`}
              >
                <div className="text-xs font-semibold flex items-center justify-center gap-1">
                  {isCompleted && <CheckCircle2 className="w-3 h-3 text-emerald-600 dark:text-emerald-400" />}
                  {stage.label}
                </div>
                <div className="text-[10px] text-slate-500 dark:text-slate-400 truncate mt-0.5">{stage.desc}</div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Crisis Intercept Banner Modal (if triggered) */}
      {crisisIntercepted && activeCrisisCard && (
        <div className="bg-rose-50 dark:bg-rose-950/70 border-2 border-rose-500 rounded-xl p-4 shadow-md flex flex-col gap-3 animate-in fade-in slide-in-from-top-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-rose-700 dark:text-rose-300 font-bold text-base">
              <ShieldAlert className="w-6 h-6 text-rose-600 animate-pulse" />
              Emergency Safety & Crisis Support Intercept
            </div>
            <span className="text-xs font-semibold px-2 py-1 rounded bg-rose-200 dark:bg-rose-900 text-rose-800 dark:text-rose-200">
              SLA ≤ 120s Counselor Notified
            </span>
          </div>
          <p className="text-sm text-rose-900 dark:text-rose-100 leading-normal">
            Your safety and wellbeing are our top priority. We have paused the tutoring dialogue. Please reach out to one of the confidential resources below or speak directly with a trusted teacher or counselor.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-1">
            {activeCrisisCard.hotlines.map((h: any, i: number) => (
              <a
                key={i}
                href={h.contact.startsWith('http') ? h.contact : `tel:${h.contact}`}
                target="_blank"
                rel="noreferrer"
                className="flex items-center justify-between p-3 bg-white dark:bg-slate-900 rounded-lg border border-rose-300 dark:border-rose-800 hover:border-rose-500 transition-colors shadow-sm"
              >
                <div>
                  <div className="text-xs font-semibold text-slate-900 dark:text-white">{h.name}</div>
                  <div className="text-xs text-rose-600 dark:text-rose-400 font-medium">{h.contact}</div>
                </div>
                <div className="p-1.5 bg-rose-100 dark:bg-rose-900/50 rounded text-rose-700 dark:text-rose-300">
                  {h.action_type === 'phone' ? <PhoneCall className="w-4 h-4" /> : <ExternalLink className="w-4 h-4" />}
                </div>
              </a>
            ))}
          </div>
        </div>
      )}

      {/* Main Chat Conversation Stream */}
      <div className="flex-1 bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm p-4 overflow-y-auto flex flex-col gap-4">
        {messages.map((msg) => {
          const isStudent = msg.sender === 'student';
          const isSystem = msg.sender === 'system';

          return (
            <div key={msg.id} className={`flex flex-col ${isStudent ? 'items-end' : 'items-start'} max-w-full`}>
              <div
                className={`max-w-[85%] rounded-2xl p-4 shadow-sm ${
                  isStudent
                    ? 'bg-indigo-600 text-white rounded-br-none'
                    : msg.isCrisisAlert
                    ? 'bg-rose-50 dark:bg-rose-950/60 border border-rose-400 rounded-bl-none'
                    : 'bg-slate-100 dark:bg-slate-800 text-slate-900 dark:text-slate-100 rounded-bl-none'
                }`}
              >
                {!isStudent && (
                  <div className="flex items-center gap-2 mb-1.5 text-xs font-semibold text-indigo-600 dark:text-indigo-400">
                    <Sparkles className="w-3.5 h-3.5" />
                    Socratic AI Guide
                    {msg.bloomLevel && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-indigo-100 dark:bg-indigo-900 text-indigo-700 dark:text-indigo-300 font-normal">
                        {msg.bloomLevel}
                      </span>
                    )}
                  </div>
                )}
                {isStudent && msg.hintTier && (
                  <div className="text-[11px] text-indigo-200 mb-1 font-medium">
                    Requested Hint Tier {msg.hintTier}
                  </div>
                )}

                {renderFormattedContent(msg.content)}

                <div className={`text-[10px] mt-2 text-right ${isStudent ? 'text-indigo-200' : 'text-slate-400'}`}>
                  {msg.timestamp}
                </div>
              </div>
            </div>
          );
        })}

        {isGenerating && (
          <div className="flex items-center gap-2 text-slate-500 text-xs p-3">
            <RefreshCw className="w-4 h-4 animate-spin text-indigo-600" />
            Socratic AI is formulating a guiding question...
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Progressive 3-Tier Hint Selector & Message Input Bar */}
      <div className="flex flex-col gap-2 bg-white dark:bg-slate-900 p-3 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
        {/* 3-Tier Progressive Hint Buttons */}
        <div className="flex items-center gap-2 overflow-x-auto pb-1">
          <span className="text-xs font-semibold text-slate-500 flex items-center gap-1 shrink-0">
            <Lightbulb className="w-3.5 h-3.5 text-amber-500" />
            Hint Ladder:
          </span>
          <button
            type="button"
            onClick={() => handleSendMessage(1)}
            disabled={isGenerating || crisisIntercepted}
            className="text-xs px-3 py-1.5 rounded-lg border border-amber-300 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/40 text-amber-900 dark:text-amber-200 hover:bg-amber-100 transition-colors flex items-center gap-1 shrink-0 disabled:opacity-50"
          >
            Tier 1: Conceptual Clue
          </button>
          <button
            type="button"
            onClick={() => handleSendMessage(2)}
            disabled={isGenerating || crisisIntercepted}
            className="text-xs px-3 py-1.5 rounded-lg border border-indigo-300 dark:border-indigo-800 bg-indigo-50 dark:bg-indigo-950/40 text-indigo-900 dark:text-indigo-200 hover:bg-indigo-100 transition-colors flex items-center gap-1 shrink-0 disabled:opacity-50"
          >
            Tier 2: Process & Formulas
          </button>
          <button
            type="button"
            onClick={() => handleSendMessage(3)}
            disabled={isGenerating || crisisIntercepted}
            className="text-xs px-3 py-1.5 rounded-lg border border-purple-300 dark:border-purple-800 bg-purple-50 dark:bg-purple-950/40 text-purple-900 dark:text-purple-200 hover:bg-purple-100 transition-colors flex items-center gap-1 shrink-0 disabled:opacity-50"
          >
            Tier 3: Guided Sub-step
          </button>
        </div>

        {/* Input Bar */}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSendMessage();
          }}
          className="flex items-center gap-2 mt-1"
        >
          <input
            type="text"
            value={inputQuery}
            onChange={(e) => setInputQuery(e.target.value)}
            disabled={isGenerating || crisisIntercepted || remainingMinutes <= 0}
            placeholder={
              remainingMinutes <= 0
                ? 'Daily 45-minute tutoring limit reached. Resume tomorrow!'
                : crisisIntercepted
                ? 'Chat session paused for safety protocols.'
                : 'Type your explanation, question, or math equation (e.g. $F = ma$)...'
            }
            className="flex-1 px-4 py-2.5 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 text-slate-900 dark:text-white disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={!inputQuery.trim() || isGenerating || crisisIntercepted || remainingMinutes <= 0}
            className="p-2.5 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-lg transition-colors shadow-sm flex items-center justify-center shrink-0"
          >
            <Send className="w-4 h-4" />
          </button>
        </form>
      </div>
    </div>
  );
};
