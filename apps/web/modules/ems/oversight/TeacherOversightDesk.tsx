'use client';

import React, { useState } from 'react';
import {
  Users,
  Shield,
  ShieldAlert,
  AlertOctagon,
  Flame,
  Search,
  Filter,
  Eye,
  Power,
  RotateCcw,
  Sparkles,
  TrendingDown,
  TrendingUp,
  BarChart2,
  Lock,
  Layers,
  HelpCircle,
  CheckCircle,
} from 'lucide-react';

export interface StrugglingStudentRecord {
  studentId: string;
  pseudonym: string; // PII-redacted label (e.g. Student #4029)
  gradeLevel: string;
  section: string;
  urgencyScore: number; // 0 to 100
  dominantGapConcept: string;
  gapSeverity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  hintConsumptionRate: number; // Avg hints per session
  aiTutoringBlocked: boolean;
  lastActive: string;
}

export interface ConceptHeatmapNode {
  conceptId: number;
  title: string;
  subject: string;
  topicCode: string;
  struggleRatePct: number; // % of class struggling (<60% mastery)
  avgMasteryPct: number;
  isBottleneck: boolean;
}

export interface RedactedTranscriptItem {
  id: number;
  pseudonym: string;
  section: string;
  redactedPrompt: string;
  outcome: 'answered' | 'blocked_safety' | 'blocked_offtopic' | 'blocked_disabled';
  cognitiveLevel: string;
  timestamp: string;
}

export const TeacherOversightDesk: React.FC = () => {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedSection, setSelectedSection] = useState<string>('ALL');

  // Struggling Student Radar state
  const [students, setStudents] = useState<StrugglingStudentRecord[]>([
    {
      studentId: '1042',
      pseudonym: 'Student-Alpha (ID #1042)',
      gradeLevel: 'Grade 11',
      section: 'Section 11-A',
      urgencyScore: 92,
      dominantGapConcept: 'Rotational Dynamics & Torque',
      gapSeverity: 'CRITICAL',
      hintConsumptionRate: 3.8,
      aiTutoringBlocked: false,
      lastActive: '5 mins ago',
    },
    {
      studentId: '1088',
      pseudonym: 'Student-Beta (ID #1088)',
      gradeLevel: 'Grade 11',
      section: 'Section 11-A',
      urgencyScore: 84,
      dominantGapConcept: 'Integration by Parts',
      gapSeverity: 'HIGH',
      hintConsumptionRate: 3.2,
      aiTutoringBlocked: false,
      lastActive: '18 mins ago',
    },
    {
      studentId: '1015',
      pseudonym: 'Student-Gamma (ID #1015)',
      gradeLevel: 'Grade 11',
      section: 'Section 11-B',
      urgencyScore: 71,
      dominantGapConcept: 'Electromagnetic Induction',
      gapSeverity: 'HIGH',
      hintConsumptionRate: 2.6,
      aiTutoringBlocked: true,
      lastActive: '1 hour ago',
    },
    {
      studentId: '1092',
      pseudonym: 'Student-Delta (ID #1092)',
      gradeLevel: 'Grade 11',
      section: 'Section 11-B',
      urgencyScore: 58,
      dominantGapConcept: 'Vectors & 2D Kinematics',
      gapSeverity: 'MEDIUM',
      hintConsumptionRate: 1.9,
      aiTutoringBlocked: false,
      lastActive: '3 hours ago',
    },
  ]);

  // Concept Gap Heatmap state
  const [concepts, setConcepts] = useState<ConceptHeatmapNode[]>([
    {
      conceptId: 101,
      title: 'Rotational Dynamics & Torque',
      subject: 'Physics',
      topicCode: 'PHY-ROT-01',
      struggleRatePct: 44,
      avgMasteryPct: 52,
      isBottleneck: true,
    },
    {
      conceptId: 102,
      title: 'Integration by Parts',
      subject: 'Calculus',
      topicCode: 'CALC-INT-02',
      struggleRatePct: 38,
      avgMasteryPct: 58,
      isBottleneck: true,
    },
    {
      conceptId: 103,
      title: 'Electromagnetic Induction',
      subject: 'Physics',
      topicCode: 'PHY-EM-03',
      struggleRatePct: 29,
      avgMasteryPct: 68,
      isBottleneck: false,
    },
    {
      conceptId: 104,
      title: 'Conservation of Momentum',
      subject: 'Physics',
      topicCode: 'PHY-MOM-04',
      struggleRatePct: 18,
      avgMasteryPct: 79,
      isBottleneck: false,
    },
    {
      conceptId: 105,
      title: 'Limits & Continuity',
      subject: 'Calculus',
      topicCode: 'CALC-LIM-01',
      struggleRatePct: 12,
      avgMasteryPct: 86,
      isBottleneck: false,
    },
  ]);

  // PII-Redacted AI Tutor Audit Transcripts
  const [transcripts] = useState<RedactedTranscriptItem[]>([
    {
      id: 901,
      pseudonym: 'Student-Alpha (ID #1042)',
      section: 'Section 11-A',
      redactedPrompt: 'Can you solve the rotational inertia equation for a hollow cylinder of mass [REDACTED_NUM] kg?',
      outcome: 'answered',
      cognitiveLevel: 'APPLY',
      timestamp: '14:22:10',
    },
    {
      id: 902,
      pseudonym: 'Student-Beta (ID #1088)',
      section: 'Section 11-A',
      redactedPrompt: 'Just tell me the answer key for question 4 on the assignment worksheet',
      outcome: 'blocked_offtopic',
      cognitiveLevel: 'REMEMBER',
      timestamp: '14:15:30',
    },
    {
      id: 903,
      pseudonym: 'Student-Gamma (ID #1015)',
      section: 'Section 11-B',
      redactedPrompt: 'Explain how Faraday’s law $\\mathcal{E} = -\\frac{d\\Phi_B}{dt}$ relates to Lenz’s law',
      outcome: 'answered',
      cognitiveLevel: 'ANALYZE',
      timestamp: '13:58:05',
    },
  ]);

  // Toggle AI Kill-Switch for a student
  const toggleStudentAiBlock = (studentId: string) => {
    setStudents((prev) =>
      prev.map((s) =>
        s.studentId === studentId ? { ...s, aiTutoringBlocked: !s.aiTutoringBlocked } : s
      )
    );
  };

  const filteredStudents = students.filter((s) => {
    const matchSearch =
      s.pseudonym.toLowerCase().includes(searchTerm.toLowerCase()) ||
      s.dominantGapConcept.toLowerCase().includes(searchTerm.toLowerCase());
    const matchSection = selectedSection === 'ALL' || s.section === selectedSection;
    return matchSearch && matchSection;
  });

  return (
    <div className="flex flex-col max-w-7xl mx-auto p-6 gap-6">
      {/* Dashboard Top Header */}
      <header className="flex flex-wrap items-center justify-between p-6 bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold text-slate-900 dark:text-white">
              Teacher Pedagogic Oversight & Supervisory Radar
            </h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800">
              Contract 3 Active
            </span>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Student 360 Knowledge Gap Heatmaps, Real-Time Urgency Radar & PII-Redacted AI Dialogue Auditing
          </p>
        </div>

        {/* Global Filter Bar */}
        <div className="flex items-center gap-3">
          <div className="relative">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              placeholder="Search student or concept..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-9 pr-3 py-2 text-xs bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <select
            value={selectedSection}
            onChange={(e) => setSelectedSection(e.target.value)}
            className="px-3 py-2 text-xs bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value="ALL">All Sections</option>
            <option value="Section 11-A">Section 11-A</option>
            <option value="Section 11-B">Section 11-B</option>
          </select>
        </div>
      </header>

      {/* Grid: Struggling Student Radar & Concept Bottleneck Heatmap */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Struggling Student Radar (2 Cols) */}
        <div className="lg:col-span-2 bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-5 shadow-sm flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
              <Flame className="w-4 h-4 text-rose-500" />
              Struggling Student Radar (Ranked by Urgency Index)
            </h2>
            <span className="text-xs text-slate-500">
              {filteredStudents.length} Students Monitored
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-200 dark:border-slate-800 text-slate-400 font-semibold uppercase tracking-wider">
                  <th className="pb-3">Student (PII Redacted)</th>
                  <th className="pb-3">Section</th>
                  <th className="pb-3">Urgency Index</th>
                  <th className="pb-3">Primary Knowledge Gap</th>
                  <th className="pb-3">Hint Rate</th>
                  <th className="pb-3 text-right">AI Tutor Kill-Switch</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
                {filteredStudents.map((s) => (
                  <tr key={s.studentId} className="hover:bg-slate-50/60 dark:hover:bg-slate-800/40 transition-colors">
                    <td className="py-3 font-medium text-slate-900 dark:text-white flex items-center gap-2">
                      <div className="w-2 h-2 rounded-full bg-rose-500 animate-pulse" />
                      {s.pseudonym}
                    </td>
                    <td className="py-3 text-slate-500">{s.section}</td>
                    <td className="py-3 font-bold">
                      <span
                        className={`px-2 py-1 rounded-full text-[11px] ${
                          s.urgencyScore >= 85
                            ? 'bg-rose-100 dark:bg-rose-950 text-rose-700 dark:text-rose-300'
                            : s.urgencyScore >= 70
                            ? 'bg-amber-100 dark:bg-amber-950 text-amber-700 dark:text-amber-300'
                            : 'bg-indigo-100 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-300'
                        }`}
                      >
                        {s.urgencyScore}/100
                      </span>
                    </td>
                    <td className="py-3 text-slate-700 dark:text-slate-300 font-medium">
                      {s.dominantGapConcept}
                    </td>
                    <td className="py-3 text-slate-500">{s.hintConsumptionRate} hints/session</td>
                    <td className="py-3 text-right">
                      <button
                        onClick={() => toggleStudentAiBlock(s.studentId)}
                        className={`px-2.5 py-1 rounded-lg text-xs font-semibold inline-flex items-center gap-1 transition-all ${
                          s.aiTutoringBlocked
                            ? 'bg-rose-100 dark:bg-rose-950/70 border border-rose-300 dark:border-rose-800 text-rose-700 dark:text-rose-300 hover:bg-rose-200'
                            : 'bg-slate-100 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-200'
                        }`}
                      >
                        <Power className="w-3.5 h-3.5" />
                        {s.aiTutoringBlocked ? 'Blocked (Disabled)' : 'Active (Enabled)'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Concept Gap Heatmap Matrix (1 Col) */}
        <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-5 shadow-sm flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
              <BarChart2 className="w-4 h-4 text-indigo-500" />
              Class Concept Gap Heatmap
            </h2>
            <span className="text-xs px-2 py-0.5 rounded bg-rose-100 dark:bg-rose-950 text-rose-700 dark:text-rose-300 font-medium">
              Bottlenecks Highlighted
            </span>
          </div>

          <div className="flex flex-col gap-3">
            {concepts.map((c) => (
              <div
                key={c.conceptId}
                className={`p-3 rounded-xl border transition-all ${
                  c.isBottleneck
                    ? 'bg-rose-50/50 dark:bg-rose-950/20 border-rose-300 dark:border-rose-800'
                    : 'bg-slate-50 dark:bg-slate-800/40 border-slate-200 dark:border-slate-700'
                }`}
              >
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-slate-900 dark:text-white truncate max-w-[180px]">
                    {c.title}
                  </span>
                  <span
                    className={`font-bold ${
                      c.struggleRatePct >= 35 ? 'text-rose-600 dark:text-rose-400' : 'text-emerald-600'
                    }`}
                  >
                    {c.struggleRatePct}% Struggling
                  </span>
                </div>
                <div className="flex items-center justify-between text-[11px] text-slate-500 mt-1">
                  <span>{c.topicCode} • {c.subject}</span>
                  <span>Avg Mastery: {c.avgMasteryPct}%</span>
                </div>
                {/* Visual Mastery Bar */}
                <div className="w-full h-1.5 bg-slate-200 dark:bg-slate-700 rounded-full mt-2 overflow-hidden">
                  <div
                    className={`h-full ${
                      c.struggleRatePct >= 35 ? 'bg-rose-500' : 'bg-emerald-500'
                    }`}
                    style={{ width: `${c.avgMasteryPct}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* PII-Redacted AI Tutor Audit Logs */}
      <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-5 shadow-sm flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
              <Shield className="w-4 h-4 text-emerald-500" />
              PII-Redacted AI Tutor Dialogue Audit Stream
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              FERPA/GDPR Compliant: student names and identifiable numeric values are automatically redacted.
            </p>
          </div>
          <span className="text-xs px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 font-medium">
            Live Stream
          </span>
        </div>

        <div className="divide-y divide-slate-100 dark:divide-slate-800">
          {transcripts.map((t) => (
            <div key={t.id} className="py-3 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs">
              <div className="flex items-start gap-3">
                <div
                  className={`p-1.5 rounded-lg shrink-0 ${
                    t.outcome === 'answered'
                      ? 'bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600'
                      : 'bg-amber-50 dark:bg-amber-950/60 text-amber-600'
                  }`}
                >
                  <Layers className="w-4 h-4" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-slate-900 dark:text-white">{t.pseudonym}</span>
                    <span className="text-slate-400">•</span>
                    <span className="text-slate-500">{t.section}</span>
                    <span className="text-slate-400">•</span>
                    <span className="px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 font-mono text-[10px]">
                      {t.cognitiveLevel}
                    </span>
                  </div>
                  <p className="text-slate-700 dark:text-slate-300 mt-1 font-mono text-[11px] bg-slate-50 dark:bg-slate-800/40 p-1.5 rounded border border-slate-200/60 dark:border-slate-700/60">
                    {t.redactedPrompt}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-3 shrink-0 self-end sm:self-center">
                <span
                  className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                    t.outcome === 'answered'
                      ? 'bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300'
                      : 'bg-amber-100 dark:bg-amber-950 text-amber-700 dark:text-amber-300'
                  }`}
                >
                  {t.outcome.toUpperCase()}
                </span>
                <span className="text-slate-400 text-[11px]">{t.timestamp}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
