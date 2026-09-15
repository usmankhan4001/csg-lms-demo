'use client';

import React, { useState } from 'react';
import {
  Lock,
  Unlock,
  ShieldCheck,
  ShieldAlert,
  AlertTriangle,
  UserCheck,
  Search,
  Plus,
  FileText,
  Key,
  Eye,
  EyeOff,
  Send,
  CheckCircle2,
  RefreshCw,
  Clock,
  Sparkles,
  Zap,
  Activity,
  Layers,
  ChevronRight,
  Info,
} from 'lucide-react';

export interface ClinicalCaseNote {
  id: string;
  studentId: string;
  pseudonym: string;
  category: 'therapeutic_note' | 'diagnostic_assessment' | 'risk_evaluation';
  riskLevel: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  diagnosticTool?: string;
  encryptedEnvelope: {
    algorithm: string;
    version: string;
    iv: string;
    tag: string;
    keyId: string;
    ciphertext: string;
  };
  plaintextNote?: string;
  isDecrypted: boolean;
  createdAt: string;
}

export interface CrisisTriageItem {
  id: string;
  studentId: string;
  pseudonym: string;
  triageLevel: 'ELEVATED' | 'HIGH' | 'CRITICAL';
  triggerReason: string;
  flaggedAt: string;
  status: 'ACTIVE' | 'RESOLVED' | 'ESCALATED';
}

export interface PastoralEscalation {
  id: string;
  studentAnonToken: string;
  riskLevel: string;
  category: string;
  actionRequired: string;
  timestamp: string;
  status: string;
}

export const ClinicalDeskStudio: React.FC = () => {
  const [selectedTab, setSelectedTab] = useState<'notes' | 'triage' | 'escalations'>('notes');
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedStudentId, setSelectedStudentId] = useState<string>('501');
  const [clientKey, setClientKey] = useState<string>('k-aes256gcm-clinician-session-9842');
  const [isKeyUnlocked, setIsKeyUnlocked] = useState<boolean>(true);

  // Note editor form
  const [newNoteCategory, setNewNoteCategory] = useState<'therapeutic_note' | 'diagnostic_assessment' | 'risk_evaluation'>('therapeutic_note');
  const [newNoteRisk, setNewNoteRisk] = useState<'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'>('MEDIUM');
  const [newNoteText, setNewNoteText] = useState('');
  const [diagnosticTool, setDiagnosticTool] = useState('PHQ-9');

  // Escalation Modal
  const [isEscalating, setIsEscalating] = useState(false);
  const [escalateCategory, setEscalateCategory] = useState('pastoral_risk');
  const [escalateAction, setEscalateAction] = useState('Initiate immediate pastoral welfare check and notify head of house.');
  const [escalateSuccess, setEscalateSuccess] = useState(false);

  // Case notes state
  const [caseNotes, setCaseNotes] = useState<ClinicalCaseNote[]>([
    {
      id: 'cn-8841',
      studentId: '501',
      pseudonym: 'Student #501 (Class 11-A)',
      category: 'therapeutic_note',
      riskLevel: 'MEDIUM',
      encryptedEnvelope: {
        algorithm: 'AES-256-GCM',
        version: 'v1',
        iv: 'v9Kj31Nq8LmP==',
        tag: '7tY49wQw08LzKx==',
        keyId: 'vault-clin-key-501',
        ciphertext: 'U2FsdGVkX19x8+7ZzJkL83KmPq0O82/4nO1b+2Lp+0Z3Q==',
      },
      plaintextNote: 'Session 4: Student expressed anxiety surrounding upcoming AP Calculus exams. Recommended cognitive reframing exercises and scheduled weekly follow-up.',
      isDecrypted: true,
      createdAt: '2026-09-14 14:30',
    },
    {
      id: 'cn-8842',
      studentId: '501',
      pseudonym: 'Student #501 (Class 11-A)',
      category: 'diagnostic_assessment',
      diagnosticTool: 'PHQ-9',
      riskLevel: 'LOW',
      encryptedEnvelope: {
        algorithm: 'AES-256-GCM',
        version: 'v1',
        iv: 'm8Kp42Zq1LmX==',
        tag: '9uX51wPw19MzLy==',
        keyId: 'vault-clin-key-501',
        ciphertext: 'U2FsdGVkX1+z99P0qJmL14LnQr1P93/5oP2c+3Mq+1A4R==',
      },
      plaintextNote: 'PHQ-9 Standardized Evaluation: Score 6 (Mild depressive symptoms). Somatic symptoms absent; mood stability confirmed.',
      isDecrypted: true,
      createdAt: '2026-09-08 10:15',
    },
    {
      id: 'cn-8843',
      studentId: '604',
      pseudonym: 'Student #604 (Class 10-B)',
      category: 'risk_evaluation',
      riskLevel: 'CRITICAL',
      encryptedEnvelope: {
        algorithm: 'AES-256-GCM',
        version: 'v1',
        iv: 'w1Nm88Qp7KzR==',
        tag: '4vR12xTy77NyKw==',
        keyId: 'vault-clin-key-604',
        ciphertext: 'U2FsdGVkX18m55LmN78Vq21LoP99/1aQ48Vz90Xm==',
      },
      plaintextNote: 'Urgent crisis evaluation: Social withdrawal observed over 3 weeks with sudden attendance drop. Protective safety protocol initiated.',
      isDecrypted: true,
      createdAt: '2026-09-15 09:00',
    },
  ]);

  // Crisis triage queue
  const [triageQueue, setTriageQueue] = useState<CrisisTriageItem[]>([
    {
      id: 'tr-101',
      studentId: '604',
      pseudonym: 'Student #604 (Class 10-B)',
      triageLevel: 'CRITICAL',
      triggerReason: 'Sudden attendance drop (3 consecutive unexcused absences) & peer withdrawal signal',
      flaggedAt: '15 mins ago',
      status: 'ACTIVE',
    },
    {
      id: 'tr-102',
      studentId: '722',
      pseudonym: 'Student #722 (Class 12-C)',
      triageLevel: 'HIGH',
      triggerReason: 'Self-reported severe burnout ahead of IB Extended Essay deadline',
      flaggedAt: '2 hours ago',
      status: 'ACTIVE',
    },
    {
      id: 'tr-103',
      studentId: '501',
      pseudonym: 'Student #501 (Class 11-A)',
      triageLevel: 'ELEVATED',
      triggerReason: 'Routine counseling check-in follow-up',
      flaggedAt: '1 day ago',
      status: 'RESOLVED',
    },
  ]);

  // Pastoral escalations emitted
  const [escalations, setEscalations] = useState<PastoralEscalation[]>([
    {
      id: 'esc-901',
      studentAnonToken: 'STU-ANON-E7B92A4C',
      riskLevel: 'high',
      category: 'crisis_triage',
      actionRequired: 'Initiate immediate pastoral welfare check and notify head of house.',
      timestamp: '2026-09-15 09:20',
      status: 'ACKNOWLEDGED_BY_PRINCIPAL',
    },
    {
      id: 'esc-902',
      studentAnonToken: 'STU-ANON-41A88F10',
      riskLevel: 'medium',
      category: 'attendance_decline',
      actionRequired: 'Contact guardian regarding unexplained morning absences.',
      timestamp: '2026-09-12 16:45',
      status: 'RESOLVED',
    },
  ]);

  const handleSaveNote = () => {
    if (!newNoteText.trim()) return;

    const newNote: ClinicalCaseNote = {
      id: `cn-${Date.now()}`,
      studentId: selectedStudentId,
      pseudonym: `Student #${selectedStudentId}`,
      category: newNoteCategory,
      diagnosticTool: newNoteCategory === 'diagnostic_assessment' ? diagnosticTool : undefined,
      riskLevel: newNoteRisk,
      encryptedEnvelope: {
        algorithm: 'AES-256-GCM',
        version: 'v1',
        iv: 'b64_' + Math.random().toString(36).substring(2, 10),
        tag: 'b64_tag_' + Math.random().toString(36).substring(2, 10),
        keyId: `vault-clin-key-${selectedStudentId}`,
        ciphertext: 'ENC_AES256GCM_' + btoa(newNoteText).substring(0, 32) + '==',
      },
      plaintextNote: newNoteText,
      isDecrypted: isKeyUnlocked,
      createdAt: new Date().toISOString().replace('T', ' ').substring(0, 16),
    };

    setCaseNotes([newNote, ...caseNotes]);
    setNewNoteText('');
  };

  const handleEmitEscalation = () => {
    const newEsc: PastoralEscalation = {
      id: `esc-${Date.now()}`,
      studentAnonToken: `STU-ANON-${Math.random().toString(16).substring(2, 10).toUpperCase()}`,
      riskLevel: newNoteRisk.toLowerCase(),
      category: escalateCategory,
      actionRequired: escalateAction,
      timestamp: new Date().toISOString().replace('T', ' ').substring(0, 16),
      status: 'PENDING_LEADERSHIP_ACTION',
    };

    setEscalations([newEsc, ...escalations]);
    setEscalateSuccess(true);
    setTimeout(() => {
      setEscalateSuccess(false);
      setIsEscalating(false);
    }, 1200);
  };

  const handleTriageAction = (id: string, newStatus: 'ACTIVE' | 'RESOLVED' | 'ESCALATED') => {
    setTriageQueue(
      triageQueue.map((item) => (item.id === id ? { ...item, status: newStatus } : item))
    );
  };

  const filteredNotes = caseNotes.filter(
    (n) =>
      n.studentId === selectedStudentId &&
      (searchTerm === '' ||
        n.plaintextNote?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        n.category.includes(searchTerm.toLowerCase()))
  );

  return (
    <div className="flex flex-col h-full bg-slate-950 text-slate-100 p-6 space-y-6">
      {/* Top Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div className="flex items-center space-x-3">
          <div className="p-3 bg-purple-600/20 border border-purple-500/40 rounded-xl text-purple-400">
            <Lock className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold tracking-tight text-white">
                Psychological Clinical Desk
              </h1>
              <span className="px-2 py-0.5 text-xs font-semibold bg-purple-500/20 text-purple-300 border border-purple-500/30 rounded-full">
                AES-256-GCM Zero-Knowledge
              </span>
            </div>
            <p className="text-sm text-slate-400">
              Confidential clinical case notes, diagnostic assessments, and protective pastoral triage
            </p>
          </div>
        </div>

        {/* 404-Never-403 Assurance Badge & Key status */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-xs">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            <span className="text-slate-300">404-Never-403 Rule Active</span>
          </div>

          <button
            onClick={() => setIsKeyUnlocked(!isKeyUnlocked)}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
              isKeyUnlocked
                ? 'bg-emerald-950/40 border-emerald-600/50 text-emerald-300 hover:bg-emerald-900/50'
                : 'bg-rose-950/40 border-rose-600/50 text-rose-300 hover:bg-rose-900/50'
            }`}
          >
            {isKeyUnlocked ? <Unlock className="w-4 h-4" /> : <Lock className="w-4 h-4" />}
            <span>{isKeyUnlocked ? 'DEK Unlocked (AES-256-GCM)' : 'DEK Sealed'}</span>
          </button>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="flex items-center gap-2 border-b border-slate-800">
        <button
          onClick={() => setSelectedTab('notes')}
          className={`flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            selectedTab === 'notes'
              ? 'border-purple-500 text-purple-400 bg-purple-500/10'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <FileText className="w-4 h-4" />
          <span>Encrypted Case Notes & Diagnostics</span>
        </button>

        <button
          onClick={() => setSelectedTab('triage')}
          className={`flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            selectedTab === 'triage'
              ? 'border-rose-500 text-rose-400 bg-rose-500/10'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <AlertTriangle className="w-4 h-4" />
          <span>Emergency Crisis Triage</span>
          <span className="px-1.5 py-0.2 bg-rose-600/30 text-rose-300 rounded text-xs">
            {triageQueue.filter((t) => t.status === 'ACTIVE').length}
          </span>
        </button>

        <button
          onClick={() => setSelectedTab('escalations')}
          className={`flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            selectedTab === 'escalations'
              ? 'border-blue-500 text-blue-400 bg-blue-500/10'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <Send className="w-4 h-4" />
          <span>Anonymized Institutional Escalations</span>
        </button>
      </div>

      {/* Main Studio Views */}
      {selectedTab === 'notes' && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left Column: Student Selector & Case Files */}
          <div className="lg:col-span-4 bg-slate-900 border border-slate-800 rounded-xl p-4 flex flex-col space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
                Confidential Case Files
              </h2>
              <span className="text-xs text-purple-400 bg-purple-950/60 px-2 py-0.5 rounded border border-purple-800/40">
                Psychologist Scoped
              </span>
            </div>

            {/* Student Search & Quick Select */}
            <div className="relative">
              <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-500" />
              <input
                type="text"
                placeholder="Search student case or pseudonym..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-9 pr-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm text-slate-200 focus:outline-none focus:border-purple-500"
              />
            </div>

            <div className="space-y-2 overflow-y-auto max-h-[520px]">
              {[
                { id: '501', label: 'Student #501', grade: 'Class 11-A', risk: 'MEDIUM', notesCount: 2 },
                { id: '604', label: 'Student #604', grade: 'Class 10-B', risk: 'CRITICAL', notesCount: 1 },
                { id: '722', label: 'Student #722', grade: 'Class 12-C', risk: 'HIGH', notesCount: 0 },
              ].map((student) => (
                <div
                  key={student.id}
                  onClick={() => setSelectedStudentId(student.id)}
                  className={`p-3 rounded-lg border cursor-pointer transition-all ${
                    selectedStudentId === student.id
                      ? 'bg-purple-950/40 border-purple-500/60'
                      : 'bg-slate-950/60 border-slate-800 hover:border-slate-700'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-slate-200 text-sm">{student.label}</span>
                    <span
                      className={`text-xs px-2 py-0.5 rounded font-semibold border ${
                        student.risk === 'CRITICAL'
                          ? 'bg-rose-950/80 text-rose-400 border-rose-700'
                          : student.risk === 'HIGH'
                          ? 'bg-amber-950/80 text-amber-400 border-amber-700'
                          : 'bg-blue-950/80 text-blue-400 border-blue-700'
                      }`}
                    >
                      {student.risk}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-xs text-slate-400 mt-2">
                    <span>{student.grade}</span>
                    <span>{student.notesCount} Encrypted Records</span>
                  </div>
                </div>
              ))}
            </div>

            {/* Zero Knowledge Privacy Notice */}
            <div className="mt-auto p-3 bg-slate-950 border border-slate-800/80 rounded-lg text-xs text-slate-400 space-y-1">
              <div className="flex items-center gap-1.5 text-purple-400 font-medium">
                <Info className="w-3.5 h-3.5" />
                <span>Zero-Knowledge Guarantee</span>
              </div>
              <p>
                Clinical narratives are encrypted with AES-256-GCM in the browser before transmission.
                Zero unencrypted therapeutic notes are visible to teachers or general administrators.
              </p>
            </div>
          </div>

          {/* Right Column: Encrypted Note Editor & Records */}
          <div className="lg:col-span-8 flex flex-col space-y-6">
            {/* Encrypted Note Creator */}
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Key className="w-4 h-4 text-purple-400" />
                  <h3 className="text-sm font-semibold text-white">
                    New Encrypted Clinical Entry for Student #{selectedStudentId}
                  </h3>
                </div>
                <button
                  onClick={() => setIsEscalating(true)}
                  className="flex items-center gap-1.5 px-3 py-1 bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 border border-amber-500/40 rounded-lg text-xs font-medium"
                >
                  <AlertTriangle className="w-3.5 h-3.5" />
                  <span>Escalate to Principal (Anonymized)</span>
                </button>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div>
                  <label className="text-xs text-slate-400 mb-1 block">Entry Category</label>
                  <select
                    value={newNoteCategory}
                    onChange={(e) => setNewNoteCategory(e.target.value as any)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-purple-500"
                  >
                    <option value="therapeutic_note">Therapeutic Case Note</option>
                    <option value="diagnostic_assessment">Diagnostic Assessment</option>
                    <option value="risk_evaluation">Psychological Risk Evaluation</option>
                  </select>
                </div>

                {newNoteCategory === 'diagnostic_assessment' ? (
                  <div>
                    <label className="text-xs text-slate-400 mb-1 block">Assessment Battery</label>
                    <select
                      value={diagnosticTool}
                      onChange={(e) => setDiagnosticTool(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-purple-500"
                    >
                      <option value="PHQ-9">PHQ-9 (Depression Inventory)</option>
                      <option value="GAD-7">GAD-7 (Anxiety Scale)</option>
                      <option value="BASC-3">BASC-3 (Behavioral Assessment)</option>
                      <option value="WISC-V">WISC-V (Cognitive Index)</option>
                    </select>
                  </div>
                ) : (
                  <div>
                    <label className="text-xs text-slate-400 mb-1 block">Clinical Risk Level</label>
                    <select
                      value={newNoteRisk}
                      onChange={(e) => setNewNoteRisk(e.target.value as any)}
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-purple-500"
                    >
                      <option value="LOW">LOW</option>
                      <option value="MEDIUM">MEDIUM</option>
                      <option value="HIGH">HIGH</option>
                      <option value="CRITICAL">CRITICAL</option>
                    </select>
                  </div>
                )}

                <div>
                  <label className="text-xs text-slate-400 mb-1 block">Envelope Cipher</label>
                  <div className="px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-purple-300 font-mono flex items-center justify-between">
                    <span>AES-256-GCM / IV+TAG</span>
                    <Lock className="w-3.5 h-3.5 text-purple-400" />
                  </div>
                </div>
              </div>

              <div>
                <label className="text-xs text-slate-400 mb-1 block">
                  Therapeutic Narrative & Observations (Client-Side Encrypted)
                </label>
                <textarea
                  rows={4}
                  placeholder="Record structured therapeutic notes, clinical impressions, and intervention plan..."
                  value={newNoteText}
                  onChange={(e) => setNewNoteText(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-3 text-sm text-slate-200 focus:outline-none focus:border-purple-500"
                />
              </div>

              <div className="flex items-center justify-between pt-2">
                <div className="flex items-center gap-2 text-xs text-slate-400 font-mono">
                  <ShieldCheck className="w-4 h-4 text-emerald-400" />
                  <span>Payload will be sealed into AES-256-GCM Envelope before API transit</span>
                </div>
                <button
                  onClick={handleSaveNote}
                  disabled={!newNoteText.trim()}
                  className="px-4 py-2 bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white text-sm font-medium rounded-lg flex items-center gap-2"
                >
                  <Lock className="w-4 h-4" />
                  <span>Seal & Store Encrypted Note</span>
                </button>
              </div>
            </div>

            {/* Note Records List */}
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold text-slate-300">
                  Encrypted Records for Student #{selectedStudentId} ({filteredNotes.length})
                </h3>
              </div>

              {filteredNotes.length === 0 ? (
                <div className="p-8 text-center bg-slate-900 border border-slate-800 rounded-xl text-slate-400 text-sm">
                  No encrypted case notes found for this student.
                </div>
              ) : (
                filteredNotes.map((note) => (
                  <div
                    key={note.id}
                    className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-3"
                  >
                    <div className="flex items-center justify-between border-b border-slate-800 pb-2.5">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-semibold text-purple-400 bg-purple-950/60 px-2 py-0.5 rounded border border-purple-800/40">
                          {note.category.replace('_', ' ').toUpperCase()}
                          {note.diagnosticTool ? ` (${note.diagnosticTool})` : ''}
                        </span>
                        <span
                          className={`text-xs px-2 py-0.5 rounded font-semibold border ${
                            note.riskLevel === 'CRITICAL'
                              ? 'bg-rose-950/80 text-rose-400 border-rose-700'
                              : note.riskLevel === 'HIGH'
                              ? 'bg-amber-950/80 text-amber-400 border-amber-700'
                              : 'bg-blue-950/80 text-blue-400 border-blue-700'
                          }`}
                        >
                          Risk: {note.riskLevel}
                        </span>
                      </div>
                      <div className="flex items-center gap-2 text-xs text-slate-400">
                        <Clock className="w-3.5 h-3.5" />
                        <span>{note.createdAt}</span>
                      </div>
                    </div>

                    {/* Decrypted / Ciphertext Display */}
                    {isKeyUnlocked ? (
                      <div className="p-3 bg-slate-950 border border-slate-800/80 rounded-lg text-sm text-slate-200 leading-relaxed font-sans">
                        {note.plaintextNote}
                      </div>
                    ) : (
                      <div className="p-3 bg-slate-950/80 border border-slate-800 rounded-lg font-mono text-xs text-purple-300/80 break-all space-y-1">
                        <div className="flex items-center gap-1.5 text-rose-400 text-[11px] font-semibold">
                          <Lock className="w-3.5 h-3.5" />
                          <span>ENVELOPE CIPHERTEXT (DEK LOCKED)</span>
                        </div>
                        <p>{note.encryptedEnvelope.ciphertext}</p>
                      </div>
                    )}

                    <div className="flex items-center justify-between text-xs text-slate-500 font-mono">
                      <span>Algorithm: {note.encryptedEnvelope.algorithm}</span>
                      <span>IV: {note.encryptedEnvelope.iv} | Tag: {note.encryptedEnvelope.tag}</span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}

      {/* Emergency Crisis Triage View */}
      {selectedTab === 'triage' && (
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-semibold text-white">Emergency Crisis Triage Queue</h2>
              <p className="text-xs text-slate-400">
                Real-time psychiatric triage alerts with direct anonymized pastoral escalation
              </p>
            </div>
            <button
              onClick={() => {
                const newTriage: CrisisTriageItem = {
                  id: `tr-${Date.now()}`,
                  studentId: '902',
                  pseudonym: 'Student #902 (Class 10-A)',
                  triageLevel: 'CRITICAL',
                  triggerReason: 'Severe affective distress signal during academic exam',
                  flaggedAt: 'Just now',
                  status: 'ACTIVE',
                };
                setTriageQueue([newTriage, ...triageQueue]);
              }}
              className="px-3 py-1.5 bg-rose-600/20 hover:bg-rose-600/30 text-rose-300 border border-rose-500/40 rounded-lg text-xs font-medium flex items-center gap-1.5"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Flag Crisis Case</span>
            </button>
          </div>

          <div className="space-y-3">
            {triageQueue.map((item) => (
              <div
                key={item.id}
                className="bg-slate-950 border border-slate-800 rounded-xl p-4 flex flex-col md:flex-row md:items-center justify-between gap-4"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-sm text-slate-200">{item.pseudonym}</span>
                    <span
                      className={`text-xs px-2 py-0.5 rounded font-bold border ${
                        item.triageLevel === 'CRITICAL'
                          ? 'bg-rose-950 text-rose-400 border-rose-600'
                          : 'bg-amber-950 text-amber-400 border-amber-600'
                      }`}
                    >
                      {item.triageLevel}
                    </span>
                    <span className="text-xs text-slate-400">Flagged {item.flaggedAt}</span>
                  </div>
                  <p className="text-sm text-slate-300">{item.triggerReason}</p>
                </div>

                <div className="flex items-center gap-2">
                  {item.status === 'ACTIVE' ? (
                    <>
                      <button
                        onClick={() => {
                          setIsEscalating(true);
                          setEscalateAction(`Immediate crisis triage welfare check for ${item.pseudonym}.`);
                        }}
                        className="px-3 py-1.5 bg-amber-600 hover:bg-amber-500 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5"
                      >
                        <AlertTriangle className="w-3.5 h-3.5" />
                        <span>Escalate to Principal</span>
                      </button>
                      <button
                        onClick={() => handleTriageAction(item.id, 'RESOLVED')}
                        className="px-3 py-1.5 bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-300 border border-emerald-500/40 rounded-lg text-xs font-semibold flex items-center gap-1.5"
                      >
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        <span>Mark Triaged</span>
                      </button>
                    </>
                  ) : (
                    <span className="px-3 py-1 bg-slate-800 text-slate-400 rounded-lg text-xs font-medium">
                      Status: {item.status}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Pastoral Escalations View */}
      {selectedTab === 'escalations' && (
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-semibold text-white">
                Anonymized Institutional Escalation Audit Trail
              </h2>
              <p className="text-xs text-slate-400">
                Protective pastoral alerts emitted to School Leadership. Zero clinical case notes or diagnostic narratives are leaked.
              </p>
            </div>
            <div className="flex items-center gap-2 px-3 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-xs text-emerald-400">
              <ShieldCheck className="w-4 h-4" />
              <span>PII & Notes Redacted</span>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-300">
              <thead className="bg-slate-950 text-xs text-slate-400 uppercase tracking-wider border-b border-slate-800">
                <tr>
                  <th className="py-3 px-4">Anonymized Token</th>
                  <th className="py-3 px-4">Risk Level</th>
                  <th className="py-3 px-4">Category</th>
                  <th className="py-3 px-4">Mandated Action</th>
                  <th className="py-3 px-4">Timestamp</th>
                  <th className="py-3 px-4">Leadership Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/80">
                {escalations.map((esc) => (
                  <tr key={esc.id} className="hover:bg-slate-950/40 font-mono text-xs">
                    <td className="py-3 px-4 text-purple-400 font-bold">{esc.studentAnonToken}</td>
                    <td className="py-3 px-4">
                      <span
                        className={`px-2 py-0.5 rounded font-bold border ${
                          esc.riskLevel === 'high' || esc.riskLevel === 'critical'
                            ? 'bg-rose-950 text-rose-400 border-rose-600'
                            : 'bg-amber-950 text-amber-400 border-amber-600'
                        }`}
                      >
                        {esc.riskLevel.toUpperCase()}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-slate-200">{esc.category}</td>
                    <td className="py-3 px-4 font-sans text-slate-300">{esc.actionRequired}</td>
                    <td className="py-3 px-4 text-slate-400">{esc.timestamp}</td>
                    <td className="py-3 px-4">
                      <span className="px-2 py-0.5 bg-blue-950 text-blue-300 border border-blue-700 rounded font-sans">
                        {esc.status.replace(/_/g, ' ')}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Anonymized Escalation Modal */}
      {isEscalating && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-lg w-full p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2 text-amber-400">
                <AlertTriangle className="w-5 h-5" />
                <h3 className="font-bold text-white text-base">
                  Emit Anonymized Institutional Escalation
                </h3>
              </div>
              <button
                onClick={() => setIsEscalating(false)}
                className="text-slate-400 hover:text-white text-sm"
              >
                ✕
              </button>
            </div>

            <div className="p-3 bg-amber-950/40 border border-amber-600/40 rounded-xl text-xs text-amber-200 space-y-1">
              <div className="font-semibold flex items-center gap-1.5">
                <ShieldAlert className="w-4 h-4 text-amber-400" />
                <span>Statutory Confidentiality Boundary</span>
              </div>
              <p>
                This will dispatch a high-priority pastoral alert to the School Principal with an
                anonymized token (e.g. <code>STU-ANON-XXXX</code>). Your clinical case notes and
                diagnostic narratives will <strong>NEVER</strong> be shared.
              </p>
            </div>

            <div className="space-y-3 text-sm">
              <div>
                <label className="text-xs text-slate-400 mb-1 block">Trigger Category</label>
                <select
                  value={escalateCategory}
                  onChange={(e) => setEscalateCategory(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 text-sm focus:outline-none focus:border-amber-500"
                >
                  <option value="pastoral_risk">Pastoral Risk / Wellbeing Flag</option>
                  <option value="attendance_decline">Unexplained Attendance Decline</option>
                  <option value="crisis_triage">Immediate Crisis Triage Required</option>
                  <option value="safety_alert">Campus Safety Alert</option>
                </select>
              </div>

              <div>
                <label className="text-xs text-slate-400 mb-1 block">
                  Mandated Non-Clinical Protective Action
                </label>
                <textarea
                  rows={3}
                  value={escalateAction}
                  onChange={(e) => setEscalateAction(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-3 text-slate-200 text-sm focus:outline-none focus:border-amber-500"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-800">
              <button
                onClick={() => setIsEscalating(false)}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm rounded-lg"
              >
                Cancel
              </button>
              <button
                onClick={handleEmitEscalation}
                className="px-4 py-2 bg-amber-600 hover:bg-amber-500 text-white font-medium text-sm rounded-lg flex items-center gap-2"
              >
                {escalateSuccess ? <CheckCircle2 className="w-4 h-4" /> : <Send className="w-4 h-4" />}
                <span>{escalateSuccess ? 'Alert Dispatched!' : 'Dispatch Pastoral Alert'}</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
