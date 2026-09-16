'use client'

import React from 'react'
import {
  Award,
  BookOpen,
  Calendar,
  CheckCircle2,
  FileBadge,
  GraduationCap,
  Landmark,
  QrCode,
  ShieldCheck,
  Sparkles,
  UserCheck,
} from 'lucide-react'
import {
  CogniaTranscriptData,
  SchoolBrandingConfig,
  DEFAULT_SCHOOL_BRANDING,
  SAMPLE_COGNIA_TRANSCRIPT_DATA,
  formatDatePretty,
} from '@/lib/sms/document-templates'

interface CogniaTranscriptPDFProps {
  data?: CogniaTranscriptData
  branding?: SchoolBrandingConfig
  className?: string
}

export function CogniaTranscriptPDF({
  data = SAMPLE_COGNIA_TRANSCRIPT_DATA,
  branding = DEFAULT_SCHOOL_BRANDING,
  className = '',
}: CogniaTranscriptPDFProps) {
  return (
    <div
      className={`bg-white text-slate-900 font-serif p-8 md:p-12 print:p-6 w-full max-w-[960px] mx-auto shadow-md border-2 border-slate-300 print:border-none print:shadow-none space-y-6 ${className}`}
      id="cognia-transcript-document"
    >
      {/* 1. Header: School Crest, Institution Name & Cognia Accreditation Badge */}
      <div className="flex flex-col md:flex-row items-center justify-between gap-6 border-b-2 border-slate-800 pb-6 text-center md:text-left">
        <div className="flex items-center gap-4">
          {/* Institutional Crest / Logo */}
          <div className="w-16 h-16 rounded-full border-2 border-amber-600 bg-gradient-to-br from-indigo-900 to-slate-900 flex items-center justify-center text-amber-400 shadow-md shrink-0">
            <GraduationCap className="w-8 h-8" />
          </div>
          <div>
            <span className="text-[10px] font-sans font-black uppercase tracking-widest text-indigo-700 block">
              Official Institutional Academic Record
            </span>
            <h1 className="text-2xl md:text-3xl font-bold tracking-tight text-slate-900">
              {branding.schoolName}
            </h1>
            <p className="text-xs font-sans text-slate-600">
              {branding.campusName} • {branding.physicalAddress}
            </p>
          </div>
        </div>

        {/* Cognia Accreditation Stamp Box */}
        <div className="border-2 border-indigo-900/40 bg-indigo-50/60 rounded-xl p-3 text-center shrink-0 min-w-[200px] shadow-sm font-sans">
          <div className="flex items-center justify-center gap-1.5 text-indigo-900 font-black text-xs uppercase tracking-wider">
            <ShieldCheck className="w-4 h-4 text-indigo-700" />
            <span>Cognia Accredited</span>
          </div>
          <span className="text-[10px] text-slate-600 block mt-0.5">
            Global Commission for Quality Learning
          </span>
          <span className="font-mono text-[9px] font-bold text-indigo-800 block mt-0.5">
            INSTITUTION ID: {branding.accreditationNumber || 'COG-INTL-89104'}
          </span>
        </div>
      </div>

      {/* 2. Document Title Banner */}
      <div className="text-center font-sans space-y-1">
        <h2 className="text-xl font-bold uppercase tracking-widest text-slate-900">
          Official Academic Transcript & Cumulative Term Record
        </h2>
        <div className="flex items-center justify-center gap-3 text-xs text-slate-500 font-medium">
          <span>Transcript Ref: <strong className="text-slate-800 font-mono">{data.transcriptNo}</strong></span>
          <span>•</span>
          <span>Status: <strong className="text-emerald-700 uppercase">{data.status}</strong></span>
          <span>•</span>
          <span>Date of Issue: <strong className="text-slate-800">{formatDatePretty(data.issueDate)}</strong></span>
        </div>
      </div>

      {/* 3. Student Demographics & Academic Profile Block */}
      <div className="font-sans grid grid-cols-2 md:grid-cols-4 gap-3 bg-slate-50 border border-slate-200 rounded-xl p-4 text-xs">
        <div>
          <span className="text-slate-500 block text-[10px] uppercase tracking-wider">Student Full Name</span>
          <span className="font-bold text-slate-900 text-[13px]">{data.studentName}</span>
        </div>
        <div>
          <span className="text-slate-500 block text-[10px] uppercase tracking-wider">Enrollment Number</span>
          <span className="font-mono font-bold text-slate-800">{data.enrollmentNo}</span>
        </div>
        <div>
          <span className="text-slate-500 block text-[10px] uppercase tracking-wider">Date of Birth / Gender</span>
          <span className="font-medium text-slate-800">{formatDatePretty(data.studentDob)} ({data.gender})</span>
        </div>
        <div>
          <span className="text-slate-500 block text-[10px] uppercase tracking-wider">Grade Level / Class</span>
          <span className="font-medium text-slate-800">{data.gradeLevel} ({data.graduationYear})</span>
        </div>
      </div>

      {/* 4. Multi-Term Academic Courses & Grade Schedules */}
      <div className="space-y-6 font-sans">
        {data.terms.map((term, termIdx) => (
          <div key={termIdx} className="border border-slate-300 rounded-xl overflow-hidden shadow-xs">
            {/* Term Header */}
            <div className="bg-slate-900 text-white px-4 py-2 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-1 text-xs">
              <div className="font-bold tracking-wide flex items-center gap-2">
                <BookOpen className="w-3.5 h-3.5 text-amber-400" />
                <span>{term.termName} — {term.academicYear}</span>
                <span className="text-slate-400 font-normal">({term.gradeLevel})</span>
              </div>
              <div className="flex items-center gap-4 text-[11px] font-semibold text-slate-300">
                <span>Term Credits: <strong className="text-white">{term.termCredits.toFixed(1)}</strong></span>
                <span>Term GPA: <strong className="text-amber-400 font-mono text-xs">{term.termGpa.toFixed(2)}</strong></span>
              </div>
            </div>

            {/* Courses Table */}
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="bg-slate-100 border-b border-slate-200 text-slate-600 text-[10px] uppercase tracking-wider font-bold">
                  <th className="py-2 px-3">Course Code</th>
                  <th className="py-2 px-3">Course Title</th>
                  <th className="py-2 px-2 text-center">Credit</th>
                  <th className="py-2 px-2 text-center">Score</th>
                  <th className="py-2 px-2 text-center">Grade</th>
                  <th className="py-2 px-2 text-center">GPA</th>
                  <th className="py-2 px-3">Evaluator Remarks</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {term.courses.map((course, cIdx) => (
                  <tr key={cIdx} className="hover:bg-slate-50/50">
                    <td className="py-2 px-3 font-mono font-semibold text-slate-800 text-[11px]">
                      {course.courseCode}
                    </td>
                    <td className="py-2 px-3 font-medium text-slate-900">
                      {course.courseTitle}
                      {course.isWeighted && (
                        <span className="ml-1.5 px-1 py-0.2 rounded text-[9px] font-bold bg-amber-100 text-amber-800">
                          Weighted +0.5
                        </span>
                      )}
                    </td>
                    <td className="py-2 px-2 text-center font-mono text-slate-700">{course.creditHours.toFixed(1)}</td>
                    <td className="py-2 px-2 text-center font-mono font-semibold text-slate-800">{course.percentage}%</td>
                    <td className="py-2 px-2 text-center font-bold text-indigo-700">{course.letterGrade}</td>
                    <td className="py-2 px-2 text-center font-mono font-bold text-slate-900">{course.gpaPoint.toFixed(2)}</td>
                    <td className="py-2 px-3 text-[11px] text-slate-600 italic">{course.remarks}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
      </div>

      {/* 5. Cumulative Academic Performance & Attendance Dashboard */}
      <div className="font-sans grid grid-cols-2 md:grid-cols-4 gap-3 bg-indigo-50/60 border border-indigo-200 rounded-xl p-4 text-center">
        <div className="space-y-0.5">
          <span className="text-[10px] uppercase font-bold tracking-wider text-indigo-800 block">
            Cumulative GPA (Unweighted)
          </span>
          <span className="font-mono text-2xl font-black text-slate-900 block">
            {data.unweightedGpa.toFixed(2)}
          </span>
          <span className="text-[10px] text-slate-500">4.00 Scale</span>
        </div>

        <div className="space-y-0.5">
          <span className="text-[10px] uppercase font-bold tracking-wider text-indigo-800 block">
            Weighted Honors GPA
          </span>
          <span className="font-mono text-2xl font-black text-amber-700 block">
            {data.weightedGpa.toFixed(2)}
          </span>
          <span className="text-[10px] text-slate-500">AP / IB Honors Boost</span>
        </div>

        <div className="space-y-0.5">
          <span className="text-[10px] uppercase font-bold tracking-wider text-indigo-800 block">
            Total Credits Earned
          </span>
          <span className="font-mono text-2xl font-black text-slate-900 block">
            {data.totalCreditsEarned.toFixed(1)} / {data.totalCreditsAttempted.toFixed(1)}
          </span>
          <span className="text-[10px] text-slate-500">100% Completion</span>
        </div>

        <div className="space-y-0.5">
          <span className="text-[10px] uppercase font-bold tracking-wider text-indigo-800 block">
            Attendance Rate & Rank
          </span>
          <span className="font-mono text-2xl font-black text-emerald-700 block">
            {data.attendancePercentage.toFixed(1)}%
          </span>
          <span className="text-[10px] text-slate-600 font-semibold">Rank: {data.classRank}</span>
        </div>
      </div>

      {/* 6. Grading Scale Legend & Evaluation Policy */}
      <div className="font-sans bg-slate-50 border border-slate-200 rounded-xl p-4 space-y-2 text-[10px]">
        <span className="font-bold text-slate-800 uppercase tracking-wider block">
          Cognia Standard Grading Scale & Credit System:
        </span>
        <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-7 gap-2">
          {data.gradingScaleLegend.map((scale, i) => (
            <div key={i} className="bg-white border border-slate-200 rounded p-1.5 text-center">
              <span className="font-black text-indigo-700 block text-xs">{scale.letter}</span>
              <span className="font-mono text-[9px] text-slate-700 block">{scale.range}</span>
              <span className="text-[9px] text-slate-500 block">GPA: {scale.gpa.toFixed(1)}</span>
            </div>
          ))}
        </div>
        {data.generalRemarks && (
          <p className="pt-2 text-[11px] text-slate-700 font-serif italic border-t border-slate-200">
            <strong>Head of School Assessment Remarks:</strong> &ldquo;{data.generalRemarks}&rdquo;
          </p>
        )}
      </div>

      {/* 7. Official Dual Signatures, School Embossed Seal & Verification QR */}
      <div className="font-sans pt-6 border-t-2 border-slate-800 grid grid-cols-1 md:grid-cols-3 gap-6 items-end text-xs">
        {/* Academic Registrar Signature */}
        <div className="space-y-2 text-center md:text-left">
          <div className="h-12 border-b border-slate-400 flex items-end justify-center md:justify-start pb-1">
            <span className="font-serif italic text-base text-indigo-900 font-bold">
              {branding.registrarName || 'Patricia Holloway'}
            </span>
          </div>
          <div>
            <span className="font-bold text-slate-900 block">{branding.registrarName || 'Patricia Holloway, M.Ed.'}</span>
            <span className="text-[10px] text-slate-500 block">{branding.registrarTitle || 'Academic Registrar & Dean of Records'}</span>
          </div>
        </div>

        {/* Head of School Signature & Seal */}
        <div className="space-y-2 text-center">
          <div className="h-12 border-b border-slate-400 flex items-end justify-center pb-1">
            <span className="font-serif italic text-base text-indigo-900 font-bold">
              {branding.principalName || 'Dr. Eleanor Vance'}
            </span>
          </div>
          <div>
            <span className="font-bold text-slate-900 block">{branding.principalName || 'Dr. Eleanor Vance, Ph.D.'}</span>
            <span className="text-[10px] text-slate-500 block">{branding.principalTitle || 'Head of School & Principal'}</span>
          </div>
        </div>

        {/* Digital Verification QR & Hash */}
        <div className="bg-slate-50 border border-slate-300 rounded-xl p-3 flex items-center gap-3">
          <div className="w-12 h-12 bg-white border border-slate-300 rounded flex items-center justify-center text-slate-800 shrink-0">
            <QrCode className="w-9 h-9" />
          </div>
          <div className="space-y-0.5 text-[9px] text-slate-600 min-w-0">
            <span className="font-bold text-slate-900 block uppercase tracking-wider text-[10px]">
              Scan to Verify
            </span>
            <p className="font-mono text-[8px] text-slate-500 truncate">
              {data.verificationHash}
            </p>
            <span className="text-[8px] text-emerald-700 font-semibold block">
              Cryptographically Stamped Record
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}
