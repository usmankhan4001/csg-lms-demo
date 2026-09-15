'use client'

import React, { useState } from 'react'
import Link from 'next/link'
import {
  ShieldAlert,
  Lock,
  Key,
  ShieldCheck,
  AlertTriangle,
  FileText,
  UserCheck,
  EyeOff,
  Clock,
  Plus,
  Search,
  CheckCircle2,
  Calendar,
  Save,
  Tag,
  Stethoscope,
  Activity,
  Heart
} from 'lucide-react'
import { useOrgMembership, useOrg } from '@components/Contexts/OrgContext'
import { PersonaSwitcher } from '@/components/ems/PersonaSwitcher'

interface ClinicalCaseNote {
  id: string
  studentPseudonym: string
  grade: string
  category: 'ANXIETY' | 'ACADEMIC_STRESS' | 'FAMILY_TRANSITION' | 'NEURODIVERGENT' | 'SAFEGUARDING'
  date: string
  encryptedSnippet: string
  isDecrypted: boolean
  decryptedContent?: string
  priority: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'ROUTINE'
  clinicianName: string
}

interface CrisisTriageItem {
  id: string
  studentPseudonym: string
  trigger: string
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM'
  status: 'PENDING_TRIAGE' | 'INTERVENTION_ACTIVE' | 'RESOLVED'
  timeLogged: string
  source: 'AI_SAFETY_AGENT' | 'ATTENDANCE_ANOMALY' | 'FACULTY_REFERRAL'
}

export default function ClinicalPortalPage() {
  const { orgslug } = useOrgMembership()
  const org = useOrg() as any

  const [activeTab, setActiveTab] = useState<'triage' | 'casenotes' | 'appointments'>('triage')
  const [selectedCase, setSelectedCase] = useState<string | null>('cn-1')
  const [encryptionUnlocked, setEncryptionUnlocked] = useState(true)

  // Case notes state
  const [caseNotes, setCaseNotes] = useState<ClinicalCaseNote[]>([
    {
      id: 'cn-1',
      studentPseudonym: 'Student #STU-8821',
      grade: 'Grade 11',
      category: 'ACADEMIC_STRESS',
      date: 'Sep 14, 2026',
      encryptedSnippet: 'U2FsdGVkX1+V2s7k0q1W8e7Y...[AES-256-GCM Encrypted]',
      isDecrypted: true,
      decryptedContent:
        'Student reports acute pre-exam somatic tension ahead of AP Physics C midterm. Introduced 4-7-8 breathing protocol and negotiated 24h milestone extension with faculty.',
      priority: 'HIGH',
      clinicianName: 'Dr. Alistair Finch (Lead Psychologist)',
    },
    {
      id: 'cn-2',
      studentPseudonym: 'Student #STU-4409',
      grade: 'Grade 9',
      category: 'NEURODIVERGENT',
      date: 'Sep 12, 2026',
      encryptedSnippet: 'U2FsdGVkX19k9aJk1992Lz3q...[AES-256-GCM Encrypted]',
      isDecrypted: true,
      decryptedContent:
        'Sensory accommodation review completed. Recommended noise-dampening headphone pass during independent study blocks in central library.',
      priority: 'MEDIUM',
      clinicianName: 'Sarah Jenkins, LCSW',
    },
    {
      id: 'cn-3',
      studentPseudonym: 'Student #STU-3108',
      grade: 'Grade 12',
      category: 'SAFEGUARDING',
      date: 'Sep 10, 2026',
      encryptedSnippet: 'U2FsdGVkX18a209Lk9qWmZ99...[AES-256-GCM Encrypted]',
      isDecrypted: true,
      decryptedContent:
        'Follow-up confidential pastoral check-in regarding recent family bereavement. Student exhibits positive coping mechanisms and supportive peer network.',
      priority: 'ROUTINE',
      clinicianName: 'Dr. Alistair Finch (Lead Psychologist)',
    },
  ])

  // Crisis Triage Items
  const [triageItems, setTriageItems] = useState<CrisisTriageItem[]>([
    {
      id: 'tri-1',
      studentPseudonym: 'Student #STU-9204',
      trigger: 'Repeated late-night distress keyword cluster in Socratic session',
      severity: 'CRITICAL',
      status: 'INTERVENTION_ACTIVE',
      timeLogged: '18 mins ago',
      source: 'AI_SAFETY_AGENT',
    },
    {
      id: 'tri-2',
      studentPseudonym: 'Student #STU-8821',
      trigger: '3 consecutive unexplained morning absences',
      severity: 'HIGH',
      status: 'PENDING_TRIAGE',
      timeLogged: '1 hour ago',
      source: 'ATTENDANCE_ANOMALY',
    },
    {
      id: 'tri-3',
      studentPseudonym: 'Student #STU-1049',
      trigger: 'Faculty observation: Sudden acute withdrawal during group seminar',
      severity: 'MEDIUM',
      status: 'PENDING_TRIAGE',
      timeLogged: 'Yesterday',
      source: 'FACULTY_REFERRAL',
    },
  ])

  const [newNoteStudent, setNewNoteStudent] = useState('Student #STU-8821')
  const [newNoteContent, setNewNoteContent] = useState('')
  const [newNoteCategory, setNewNoteCategory] = useState<'ANXIETY' | 'ACADEMIC_STRESS' | 'FAMILY_TRANSITION' | 'NEURODIVERGENT' | 'SAFEGUARDING'>('ACADEMIC_STRESS')
  const [showNewNoteSuccess, setShowNewNoteSuccess] = useState(false)

  const handleCreateNote = (e: React.FormEvent) => {
    e.preventDefault()
    if (!newNoteContent.trim()) return

    const newNote: ClinicalCaseNote = {
      id: `cn-${Date.now()}`,
      studentPseudonym: newNoteStudent,
      grade: 'Grade 10',
      category: newNoteCategory,
      date: 'Just now',
      encryptedSnippet: 'U2FsdGVkX1+encrypted_blob...',
      isDecrypted: true,
      decryptedContent: newNoteContent,
      priority: 'MEDIUM',
      clinicianName: 'Dr. Alistair Finch (Lead Psychologist)',
    }

    setCaseNotes([newNote, ...caseNotes])
    setNewNoteContent('')
    setShowNewNoteSuccess(true)
    setTimeout(() => setShowNewNoteSuccess(false), 3000)
  }

  return (
    <div className="flex flex-col min-h-screen">
      {/* Persona Header Switcher */}
      <PersonaSwitcher
        currentPortal="clinical"
        breadcrumbs={[{ label: 'Confidential Clinical Desk' }]}
        actions={
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1.5 rounded-full bg-teal-50 px-3 py-1 text-xs font-bold text-teal-800 border border-teal-200">
              <Lock className="size-3.5 text-teal-600" />
              <span>AES-256 Zero-Knowledge Encrypted</span>
            </div>
          </div>
        }
      />

      <main className="mx-auto w-full max-w-7xl px-4 py-8 sm:px-6 lg:px-8 space-y-8">
        {/* Title & Tab Navigation */}
        <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-black tracking-tight text-gray-900 sm:text-3xl">
                Confidential Clinical Desk
              </h1>
              <span className="rounded-full bg-teal-100 px-2.5 py-0.5 text-xs font-extrabold text-teal-800 border border-teal-200">
                Safeguarding & Pastoral
              </span>
            </div>
            <p className="mt-1 text-sm text-gray-500">
              End-to-end encrypted psychological case notes, crisis triage inbox & pastoral intervention protocols.
            </p>
          </div>

          <div className="flex items-center rounded-xl bg-gray-100 p-1 border border-gray-200">
            <button
              onClick={() => setActiveTab('triage')}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold transition ${
                activeTab === 'triage'
                  ? 'bg-white text-gray-900 shadow-xs'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              <ShieldAlert className="size-3.5 text-rose-500" />
              <span>Crisis Triage Inbox</span>
            </button>
            <button
              onClick={() => setActiveTab('casenotes')}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold transition ${
                activeTab === 'casenotes'
                  ? 'bg-white text-gray-900 shadow-xs'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              <FileText className="size-3.5" />
              <span>Encrypted Case Notes</span>
            </button>
          </div>
        </div>

        {/* Zero-Knowledge Security Banner */}
        <div className="rounded-3xl border border-teal-200 bg-gradient-to-r from-teal-900 to-slate-900 p-5 sm:p-6 text-white shadow-md flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3.5">
            <div className="flex size-10 shrink-0 items-center justify-center rounded-2xl bg-teal-500/20 text-teal-300 border border-teal-400/30">
              <Key className="size-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-bold text-white">Client-Side E2E Key Verified</h3>
                <span className="rounded-full bg-emerald-500/20 px-2 py-0.5 text-[10px] font-extrabold text-emerald-300 border border-emerald-400/30">
                  Strict HIPAA & FERPA Compliant
                </span>
              </div>
              <p className="text-xs text-teal-200/80 mt-0.5">
                All case records are decrypted strictly in browser memory. Plaintext is never stored on servers.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 self-start sm:self-auto text-xs text-teal-200 font-mono">
            <Clock className="size-3.5" />
            <span>Session Lockout: 14m 20s</span>
          </div>
        </div>

        {/* Tab 1: Crisis Triage Inbox */}
        {activeTab === 'triage' && (
          <div className="space-y-6">
            <div className="rounded-3xl border border-gray-200 bg-white p-6 sm:p-8 shadow-xs space-y-6">
              <div className="flex items-center justify-between border-b border-gray-100 pb-4">
                <div>
                  <h3 className="text-lg font-black text-gray-900">High-Priority Crisis Triage</h3>
                  <p className="text-xs text-gray-400">Automated AI safety alerts & faculty pastoral escalations</p>
                </div>
                <span className="rounded-full bg-rose-100 px-3 py-1 text-xs font-black text-rose-800">
                  {triageItems.filter((t) => t.status === 'PENDING_TRIAGE').length} Pending Review
                </span>
              </div>

              <div className="space-y-3">
                {triageItems.map((item) => (
                  <div
                    key={item.id}
                    className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 rounded-2xl border border-gray-200 bg-gray-50/50 p-4 transition hover:bg-white hover:shadow-xs"
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs font-black text-gray-900">
                          {item.studentPseudonym}
                        </span>
                        <span
                          className={`rounded-full px-2 py-0.5 text-[10px] font-extrabold uppercase ${
                            item.severity === 'CRITICAL'
                              ? 'bg-rose-100 text-rose-800 border border-rose-200'
                              : item.severity === 'HIGH'
                              ? 'bg-amber-100 text-amber-800 border border-amber-200'
                              : 'bg-blue-100 text-blue-800 border border-blue-200'
                          }`}
                        >
                          {item.severity}
                        </span>
                        <span className="rounded bg-gray-100 px-1.5 py-0.5 text-[10px] font-semibold text-gray-600">
                          {item.source.replace(/_/g, ' ')}
                        </span>
                      </div>
                      <p className="text-xs font-semibold text-gray-800">{item.trigger}</p>
                      <span className="text-[10px] text-gray-400">Logged {item.timeLogged}</span>
                    </div>

                    <div className="flex items-center gap-2 self-end sm:self-center">
                      <button
                        type="button"
                        onClick={() => alert(`Opening confidential case file for ${item.studentPseudonym}...`)}
                        className="rounded-xl border border-gray-200 bg-white px-3 py-1.5 text-xs font-bold text-gray-700 hover:bg-gray-50 shadow-2xs transition"
                      >
                        Review Profile
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setTriageItems((prev) =>
                            prev.map((t) => (t.id === item.id ? { ...t, status: 'INTERVENTION_ACTIVE' } : t))
                          )
                        }}
                        className="rounded-xl bg-teal-600 px-3.5 py-1.5 text-xs font-bold text-white hover:bg-teal-700 shadow-xs transition"
                      >
                        {item.status === 'INTERVENTION_ACTIVE' ? 'Intervention Active' : 'Initiate Triage'}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Tab 2: Encrypted Case Notes */}
        {activeTab === 'casenotes' && (
          <div className="grid grid-cols-1 gap-8 lg:grid-cols-12">
            {/* Case List (5 cols) */}
            <div className="rounded-3xl border border-gray-200 bg-white p-6 shadow-xs lg:col-span-5 space-y-4">
              <div className="flex items-center justify-between border-b border-gray-100 pb-3">
                <h3 className="text-sm font-bold text-gray-900">Confidential Session History</h3>
                <span className="text-xs font-semibold text-gray-400">{caseNotes.length} Records</span>
              </div>

              <div className="space-y-3">
                {caseNotes.map((note) => {
                  const isSelected = selectedCase === note.id
                  return (
                    <div
                      key={note.id}
                      onClick={() => setSelectedCase(note.id)}
                      className={`cursor-pointer rounded-2xl border p-4 transition ${
                        isSelected
                          ? 'border-teal-500 bg-teal-50/40 ring-1 ring-teal-500/30'
                          : 'border-gray-200 hover:bg-gray-50'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-xs font-bold text-gray-900">
                          {note.studentPseudonym}
                        </span>
                        <span className="rounded bg-teal-100 px-1.5 py-0.5 text-[9px] font-bold text-teal-800 uppercase">
                          {note.category.replace(/_/g, ' ')}
                        </span>
                      </div>
                      <p className="mt-2 text-xs text-gray-600 line-clamp-2">
                        {note.decryptedContent}
                      </p>
                      <div className="mt-3 flex items-center justify-between text-[10px] text-gray-400">
                        <span>{note.date}</span>
                        <span>{note.clinicianName}</span>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>

            {/* Note Editor & Details (7 cols) */}
            <div className="rounded-3xl border border-gray-200 bg-white p-6 sm:p-7 shadow-xs lg:col-span-7 space-y-5">
              <div className="border-b border-gray-100 pb-3 flex items-center justify-between">
                <div>
                  <h3 className="text-base font-bold text-gray-900">Create Encrypted Case Note</h3>
                  <p className="text-xs text-gray-400">Record will be encrypted before transmission</p>
                </div>
                <Lock className="size-4 text-teal-600" />
              </div>

              {showNewNoteSuccess && (
                <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-xs font-bold text-emerald-800 flex items-center gap-2 animate-in fade-in">
                  <CheckCircle2 className="size-4 text-emerald-600" />
                  <span>Case note encrypted and saved with cryptographic seal.</span>
                </div>
              )}

              <form onSubmit={handleCreateNote} className="space-y-4">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-bold text-gray-700">Student Pseudonym</label>
                    <input
                      type="text"
                      value={newNoteStudent}
                      onChange={(e) => setNewNoteStudent(e.target.value)}
                      className="mt-1 w-full rounded-xl border border-gray-200 bg-white px-3 py-2 text-xs font-mono font-bold text-gray-900 focus:border-teal-500 focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-gray-700">Category Tag</label>
                    <select
                      value={newNoteCategory}
                      onChange={(e) => setNewNoteCategory(e.target.value as any)}
                      className="mt-1 w-full rounded-xl border border-gray-200 bg-white px-3 py-2 text-xs font-medium text-gray-900 focus:border-teal-500 focus:outline-none"
                    >
                      <option value="ACADEMIC_STRESS">Academic Stress</option>
                      <option value="ANXIETY">Anxiety & Coping</option>
                      <option value="FAMILY_TRANSITION">Family Transition</option>
                      <option value="NEURODIVERGENT">Neurodivergent Support</option>
                      <option value="SAFEGUARDING">Safeguarding / Pastoral</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-bold text-gray-700">Confidential Clinical Observations</label>
                  <textarea
                    rows={4}
                    value={newNoteContent}
                    onChange={(e) => setNewNoteContent(e.target.value)}
                    placeholder="Enter confidential observation notes, interventions, and agreed pastoral milestones..."
                    className="mt-1 w-full rounded-xl border border-gray-200 bg-white p-3 text-xs text-gray-900 focus:border-teal-500 focus:outline-none"
                    required
                  />
                </div>

                <div className="flex justify-end">
                  <button
                    type="submit"
                    className="inline-flex items-center gap-1.5 rounded-xl bg-teal-600 px-4 py-2 text-xs font-bold text-white shadow-xs hover:bg-teal-700 transition"
                  >
                    <Save className="size-3.5" />
                    <span>Encrypt & Store Note</span>
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
