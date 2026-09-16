'use client'

import React from 'react'
import {
  AlertCircle,
  Building2,
  Calendar,
  Contact2,
  Droplet,
  GraduationCap,
  Landmark,
  Phone,
  QrCode,
  ShieldAlert,
  ShieldCheck,
  User,
} from 'lucide-react'
import {
  StudentIDCardData,
  SchoolBrandingConfig,
  DEFAULT_SCHOOL_BRANDING,
  SAMPLE_STUDENT_ID_CARD_DATA,
  formatDatePretty,
} from '@/lib/sms/document-templates'

interface StudentIDCardPDFProps {
  data?: StudentIDCardData
  branding?: SchoolBrandingConfig
  className?: string
}

export function StudentIDCardPDF({
  data = SAMPLE_STUDENT_ID_CARD_DATA,
  branding = DEFAULT_SCHOOL_BRANDING,
  className = '',
}: StudentIDCardPDFProps) {
  return (
    <div
      className={`bg-white font-sans p-4 md:p-8 print:p-4 w-full max-w-[800px] mx-auto space-y-6 ${className}`}
      id="student-id-card-document"
    >
      <div className="text-center print:hidden space-y-1">
        <h3 className="text-sm font-bold text-slate-700 uppercase tracking-wider">
          CR80 Standard Academic Identity Card Specification
        </h3>
        <p className="text-xs text-slate-500">
          Double-Sided Printable Layout • Gate Scanner & NFC Turnstile Ready
        </p>
      </div>

      {/* Front & Back Cards Side by Side */}
      <div className="flex flex-col sm:flex-row items-center justify-center gap-6 print:gap-4">
        {/* ================================================================= */}
        {/* FRONT SIDE */}
        {/* ================================================================= */}
        <div className="w-[300px] h-[460px] bg-white border-2 border-slate-300 rounded-2xl shadow-xl overflow-hidden flex flex-col justify-between relative print:shadow-none print:border-slate-400 select-none">
          {/* Top School Header Bar */}
          <div className="bg-gradient-to-r from-indigo-900 via-indigo-800 to-slate-900 text-white p-3 text-center space-y-0.5 relative">
            <div className="flex items-center justify-center gap-1.5">
              <div className="w-5 h-5 rounded-full bg-amber-500 flex items-center justify-center text-slate-950 font-black text-[10px]">
                C
              </div>
              <span className="font-extrabold text-[12px] tracking-tight truncate block">
                {branding.schoolName}
              </span>
            </div>
            <p className="text-[9px] text-indigo-200 tracking-wider uppercase font-semibold">
              Official Student Credential
            </p>
            {/* Color accent strip */}
            <div className="absolute bottom-0 left-0 right-0 h-1 bg-gradient-to-r from-amber-400 via-indigo-400 to-sky-400"></div>
          </div>

          {/* Student Photo & Demographics */}
          <div className="flex-1 flex flex-col items-center justify-center px-4 py-2 text-center space-y-2">
            {/* Portrait Photo with Security Border */}
            <div className="relative">
              <div className="w-24 h-28 rounded-xl border-2 border-indigo-600 overflow-hidden shadow-md bg-slate-100 flex items-center justify-center">
                {data.photoUrl ? (
                  /* eslint-disable-next-line @next/next/no-img-element */
                  <img
                    src={data.photoUrl}
                    alt={data.studentName}
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <User className="w-12 h-12 text-slate-400" />
                )}
              </div>
              <div className="absolute -bottom-1 -right-1 bg-indigo-700 text-white text-[8px] font-black px-1.5 py-0.5 rounded-full shadow-sm">
                VALID
              </div>
            </div>

            {/* Name & Academic Meta */}
            <div className="space-y-0.5">
              <h4 className="text-sm font-black text-slate-900 tracking-tight leading-tight">
                {data.studentName}
              </h4>
              <span className="text-[10px] font-bold text-indigo-700 block uppercase tracking-wider">
                {data.gradeClass} ({data.section})
              </span>
              <span className="font-mono text-[10px] font-bold text-slate-600 block">
                ID: {data.rollNumber}
              </span>
            </div>

            {/* Key Badges */}
            <div className="flex items-center gap-1.5 text-[9px]">
              <span className="px-2 py-0.5 rounded-md bg-slate-100 text-slate-800 font-semibold border border-slate-200">
                Session: {data.academicYear}
              </span>
              <span className="px-2 py-0.5 rounded-md bg-rose-50 text-rose-800 font-bold border border-rose-200 flex items-center gap-0.5">
                <Droplet className="w-2.5 h-2.5 text-rose-600 fill-rose-600" /> {data.bloodGroup}
              </span>
            </div>
          </div>

          {/* Bottom Barcode Strip */}
          <div className="bg-slate-50 border-t border-slate-200 p-2.5 flex flex-col items-center justify-center">
            <div className="font-mono tracking-widest text-[12px] font-bold text-slate-900">
              ||||| ||| |||| || |||||| | ||||
            </div>
            <span className="font-mono text-[8px] text-slate-500">{data.barcodeValue}</span>
          </div>
        </div>

        {/* ================================================================= */}
        {/* BACK SIDE */}
        {/* ================================================================= */}
        <div className="w-[300px] h-[460px] bg-slate-50 border-2 border-slate-300 rounded-2xl shadow-xl overflow-hidden flex flex-col justify-between p-3.5 relative print:shadow-none print:border-slate-400 select-none text-[10px]">
          {/* Back Top: Emergency & Guardian Info */}
          <div className="space-y-2">
            <div className="flex items-center justify-between border-b border-slate-200 pb-1.5">
              <span className="font-bold text-slate-900 uppercase text-[9px] tracking-wider flex items-center gap-1">
                <ShieldAlert className="w-3.5 h-3.5 text-rose-600" /> Emergency Contact
              </span>
              <span className="text-[8px] text-slate-400 font-mono">CR80-NFC</span>
            </div>

            <div className="space-y-1 bg-white p-2 rounded-lg border border-slate-200 text-[9px]">
              <div className="flex justify-between">
                <span className="text-slate-500">Guardian Name:</span>
                <span className="font-bold text-slate-900">{data.guardianName}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Guardian Phone:</span>
                <span className="font-semibold text-slate-900 font-mono">{data.guardianPhone}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Campus Hotline:</span>
                <span className="font-semibold text-indigo-700 font-mono">{data.emergencyContact}</span>
              </div>
              <div className="pt-1 border-t border-slate-100 text-slate-600 leading-tight text-[8px]">
                <strong>Address:</strong> {data.residentialAddress}
              </div>
            </div>
          </div>

          {/* Terms & Instructions */}
          <div className="space-y-1 text-[8px] text-slate-500 leading-tight">
            <p className="font-bold text-slate-700 uppercase">Terms & Conditions:</p>
            <p>
              1. This card is property of {branding.schoolName}. It must be worn on campus at all times.
            </p>
            <p>
              2. If found, please return to the Security Office or call {branding.contactPhone}.
            </p>
          </div>

          {/* Gate Scanning QR Code & Principal Signature */}
          <div className="bg-white p-2.5 rounded-lg border border-slate-200 flex items-center justify-between gap-2">
            <div className="w-14 h-14 bg-slate-100 border border-slate-200 rounded flex items-center justify-center text-slate-800 shrink-0">
              <QrCode className="w-11 h-11" />
            </div>
            <div className="space-y-1 text-right flex-1 min-w-0">
              <span className="text-[8px] text-slate-400 block uppercase">Authorized Signature</span>
              <div className="h-6 border-b border-slate-300 flex items-end justify-end pb-0.5">
                <span className="font-serif italic text-[11px] text-indigo-900 font-bold">
                  {branding.principalName || 'Dr. Eleanor Vance'}
                </span>
              </div>
              <span className="text-[8px] font-bold text-slate-800 block truncate">
                Head of School
              </span>
            </div>
          </div>

          {/* Footer Bar */}
          <div className="flex justify-between items-center text-[8px] text-slate-400 border-t border-slate-200 pt-1">
            <span>Issued: {data.issueDate}</span>
            <span className="font-bold text-rose-600">Expires: {data.expiryDate}</span>
          </div>
        </div>
      </div>
    </div>
  )
}
