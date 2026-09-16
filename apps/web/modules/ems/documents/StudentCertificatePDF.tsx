'use client'

import React from 'react'
import {
  Award,
  Crown,
  GraduationCap,
  Landmark,
  QrCode,
  ShieldCheck,
  Sparkles,
  Star,
} from 'lucide-react'
import {
  StudentCertificateData,
  SchoolBrandingConfig,
  DEFAULT_SCHOOL_BRANDING,
  SAMPLE_STUDENT_CERTIFICATE_DATA,
  formatDatePretty,
} from '@/lib/sms/document-templates'

interface StudentCertificatePDFProps {
  data?: StudentCertificateData
  branding?: SchoolBrandingConfig
  className?: string
}

export function StudentCertificatePDF({
  data = SAMPLE_STUDENT_CERTIFICATE_DATA,
  branding = DEFAULT_SCHOOL_BRANDING,
  className = '',
}: StudentCertificatePDFProps) {
  return (
    <div
      className={`bg-[#fdfbf7] text-slate-900 font-serif p-6 sm:p-10 md:p-14 print:p-8 w-full max-w-[1020px] mx-auto shadow-xl relative border-[12px] border-double border-amber-700/80 rounded-sm print:border-[10px] print:border-amber-800 ${className}`}
      id="student-certificate-document"
    >
      {/* Inner Decorative Golden Border */}
      <div className="border border-amber-600/50 p-6 sm:p-8 md:p-10 relative flex flex-col justify-between items-center text-center space-y-6">
        {/* Four Corner Rosette Embellishments */}
        <div className="absolute top-2 left-2 text-amber-700 select-none">
          <Star className="w-5 h-5 fill-amber-600/30 text-amber-700" />
        </div>
        <div className="absolute top-2 right-2 text-amber-700 select-none">
          <Star className="w-5 h-5 fill-amber-600/30 text-amber-700" />
        </div>
        <div className="absolute bottom-2 left-2 text-amber-700 select-none">
          <Star className="w-5 h-5 fill-amber-600/30 text-amber-700" />
        </div>
        <div className="absolute bottom-2 right-2 text-amber-700 select-none">
          <Star className="w-5 h-5 fill-amber-600/30 text-amber-700" />
        </div>

        {/* 1. Header: School Crest & Institutional Identity */}
        <div className="space-y-2 flex flex-col items-center">
          <div className="w-16 h-16 rounded-full border-2 border-amber-600 bg-gradient-to-br from-indigo-950 via-slate-900 to-indigo-900 flex items-center justify-center text-amber-400 shadow-md">
            <GraduationCap className="w-8 h-8 text-amber-400" />
          </div>
          <div>
            <h2 className="text-xl sm:text-2xl md:text-3xl font-bold tracking-wider text-slate-900 uppercase">
              {branding.schoolName}
            </h2>
            <p className="font-sans text-[11px] uppercase tracking-widest text-amber-800 font-semibold">
              {branding.campusName || 'Academic District Campus'} • {branding.accreditationBody}
            </p>
          </div>
        </div>

        {/* 2. Certificate Award Title */}
        <div className="space-y-1 my-2">
          <span className="font-sans text-xs uppercase tracking-[0.25em] text-slate-500 font-bold block">
            This Official Credential is Awarded To
          </span>
          <div className="py-2">
            <h1 className="text-3xl sm:text-4xl md:text-5xl font-black italic tracking-wide text-indigo-950 px-4">
              {data.studentName}
            </h1>
            <div className="w-48 h-0.5 bg-gradient-to-r from-transparent via-amber-600 to-transparent mx-auto mt-2"></div>
          </div>
          <span className="font-sans text-xs font-semibold text-amber-700 uppercase tracking-widest block">
            {data.honorsSuffix}
          </span>
        </div>

        {/* 3. Citation & Award Distinction */}
        <div className="max-w-2xl mx-auto space-y-3">
          <div className="inline-block px-4 py-1 rounded-full bg-amber-50 border border-amber-300 text-amber-900 font-sans text-xs font-bold uppercase tracking-wider">
            {data.awardTitle}
          </div>
          <p className="text-sm sm:text-base text-slate-700 leading-relaxed font-serif px-4">
            &ldquo;{data.citationText}&rdquo;
          </p>
          <div className="font-sans text-xs text-slate-500 font-medium">
            <span>Conferred during the <strong>{data.academicYear}</strong> on this <strong>{data.issueDate}</strong></span>
          </div>
        </div>

        {/* 4. Official Signatures, Golden Foil Rosette & Verification QR */}
        <div className="w-full pt-8 grid grid-cols-3 gap-4 items-end text-center font-sans text-xs">
          {/* Principal Signature */}
          <div className="space-y-1">
            <div className="h-12 border-b border-slate-400 flex items-end justify-center pb-1">
              <span className="font-serif italic text-base text-indigo-950 font-bold">
                {branding.principalName || 'Dr. Eleanor Vance'}
              </span>
            </div>
            <span className="font-bold text-slate-900 block text-xs">
              {branding.principalName || 'Dr. Eleanor Vance, Ph.D.'}
            </span>
            <span className="text-[10px] text-slate-500 block">
              {branding.principalTitle || 'Head of School & Principal'}
            </span>
          </div>

          {/* Golden Seal Rosette Badge */}
          <div className="flex flex-col items-center justify-center">
            <div className="w-20 h-20 rounded-full bg-gradient-to-tr from-amber-600 via-amber-400 to-yellow-200 p-1 shadow-lg flex items-center justify-center border-2 border-amber-700">
              <div className="w-full h-full rounded-full border border-dashed border-amber-900 flex flex-col items-center justify-center text-amber-950 text-center p-1 bg-amber-300/40">
                <Crown className="w-4 h-4 text-amber-900" />
                <span className="text-[7px] font-black uppercase tracking-tighter block leading-tight">
                  OFFICIAL SEAL
                </span>
                <span className="text-[6px] font-mono font-bold block">
                  CSG-EMS
                </span>
              </div>
            </div>
            <span className="font-mono text-[8px] text-slate-400 mt-1 block">
              Ref: {data.certificateNo}
            </span>
          </div>

          {/* Academic Registrar Signature */}
          <div className="space-y-1">
            <div className="h-12 border-b border-slate-400 flex items-end justify-center pb-1">
              <span className="font-serif italic text-base text-indigo-950 font-bold">
                {branding.registrarName || 'Patricia Holloway'}
              </span>
            </div>
            <span className="font-bold text-slate-900 block text-xs">
              {branding.registrarName || 'Patricia Holloway, M.Ed.'}
            </span>
            <span className="text-[10px] text-slate-500 block">
              {branding.registrarTitle || 'Academic Registrar'}
            </span>
          </div>
        </div>

        {/* Bottom Tamper-Proof Hash & Verification Badge */}
        <div className="w-full pt-4 border-t border-amber-600/30 flex flex-col sm:flex-row items-center justify-between gap-2 text-[9px] font-sans text-slate-400">
          <div className="flex items-center gap-1.5">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
            <span>Cryptographically Verified Certificate • Blockchain & SHA-256 Anchored</span>
          </div>
          <div className="font-mono text-[8px] text-slate-400">
            HASH: {data.verificationHash.slice(0, 24)}...
          </div>
        </div>
      </div>
    </div>
  )
}
