'use client'

import React, { useState, useRef } from 'react'
import {
  Download,
  Printer,
  X,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  Maximize2,
  Copy,
  Check,
  FileText,
  CreditCard,
  GraduationCap,
  Award,
  IdCard,
  Settings2,
  Share2,
  Eye,
  SlidersHorizontal,
} from 'lucide-react'
import {
  DocumentType,
  SchoolBrandingConfig,
  DEFAULT_SCHOOL_BRANDING,
  SAMPLE_FEE_BANK_SLIP_DATA,
  SAMPLE_STAFF_PAYSLIP_DATA,
  SAMPLE_COGNIA_TRANSCRIPT_DATA,
  SAMPLE_STUDENT_CERTIFICATE_DATA,
  SAMPLE_STUDENT_ID_CARD_DATA,
  FeeBankSlipData,
  StaffPayslipData,
  CogniaTranscriptData,
  StudentCertificateData,
  StudentIDCardData,
} from '@/lib/sms/document-templates'
import { FeeBankSlipPDF } from './FeeBankSlipPDF'
import { StaffPayslipPDF } from './StaffPayslipPDF'
import { CogniaTranscriptPDF } from './CogniaTranscriptPDF'
import { StudentCertificatePDF } from './StudentCertificatePDF'
import { StudentIDCardPDF } from './StudentIDCardPDF'

interface PrintableDocumentViewerProps {
  isOpen?: boolean
  onClose?: () => void
  initialDocType?: DocumentType
  branding?: SchoolBrandingConfig
  feeData?: FeeBankSlipData
  payslipData?: StaffPayslipData
  transcriptData?: CogniaTranscriptData
  certificateData?: StudentCertificateData
  idCardData?: StudentIDCardData
}

export function PrintableDocumentViewer({
  isOpen = true,
  onClose,
  initialDocType = 'bank_slip',
  branding: initialBranding = DEFAULT_SCHOOL_BRANDING,
  feeData = SAMPLE_FEE_BANK_SLIP_DATA,
  payslipData = SAMPLE_STAFF_PAYSLIP_DATA,
  transcriptData = SAMPLE_COGNIA_TRANSCRIPT_DATA,
  certificateData = SAMPLE_STUDENT_CERTIFICATE_DATA,
  idCardData = SAMPLE_STUDENT_ID_CARD_DATA,
}: PrintableDocumentViewerProps) {
  const [currentDocType, setCurrentDocType] = useState<DocumentType>(initialDocType)
  const [zoomLevel, setZoomLevel] = useState<number>(100)
  const [isExporting, setIsExporting] = useState<boolean>(false)
  const [isCopied, setIsCopied] = useState<boolean>(false)
  const [showBrandingEditor, setShowBrandingEditor] = useState<boolean>(false)
  const [activeBranding, setActiveBranding] = useState<SchoolBrandingConfig>(initialBranding)

  const documentRef = useRef<HTMLDivElement>(null)

  if (!isOpen) return null

  const handleZoomIn = () => setZoomLevel((prev) => Math.min(prev + 15, 200))
  const handleZoomOut = () => setZoomLevel((prev) => Math.max(prev - 15, 50))
  const handleZoomReset = () => setZoomLevel(100)

  const handlePrint = () => {
    window.print()
  }

  const handleDownloadPDF = async () => {
    try {
      setIsExporting(true)
      const html2canvas = (await import('html2canvas')).default
      const { jsPDF } = await import('jspdf')

      if (!documentRef.current) return

      const element = documentRef.current
      const canvas = await html2canvas(element, {
        scale: 2,
        useCORS: true,
        logging: false,
        backgroundColor: '#ffffff',
      })

      const imgData = canvas.toDataURL('image/png')
      const isLandscape = currentDocType === 'certificate' || currentDocType === 'bank_slip'
      const pdf = new jsPDF({
        orientation: isLandscape ? 'landscape' : 'portrait',
        unit: 'mm',
        format: 'a4',
      })

      const imgProps = pdf.getImageProperties(imgData)
      const pdfWidth = pdf.internal.pageSize.getWidth()
      const pdfHeight = (imgProps.height * pdfWidth) / imgProps.width

      pdf.addImage(imgData, 'PNG', 0, 0, pdfWidth, pdfHeight)
      pdf.save(`CSG-Document-${currentDocType}-${Date.now()}.pdf`)
    } catch (err) {
      console.error('Error generating PDF download:', err)
      // Fallback to print
      window.print()
    } finally {
      setIsExporting(false)
    }
  }

  const handleCopyVerificationLink = () => {
    const hash =
      transcriptData.verificationHash ||
      certificateData.verificationHash ||
      payslipData.verificationHash ||
      'VERIFIED-DOC-0482'
    const url = `${window.location.origin}/verify-doc/${hash}`
    navigator.clipboard.writeText(url)
    setIsCopied(true)
    setTimeout(() => setIsCopied(false), 2000)
  }

  const docNavItems: Array<{ type: DocumentType; label: string; icon: React.ElementType }> = [
    { type: 'bank_slip', label: 'Fee Bank Voucher', icon: CreditCard },
    { type: 'payslip', label: 'Staff Payslip', icon: FileText },
    { type: 'cognia_transcript', label: 'Cognia Transcript', icon: GraduationCap },
    { type: 'certificate', label: 'Award Certificate', icon: Award },
    { type: 'student_id_card', label: 'Student ID Card', icon: IdCard },
  ]

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-slate-950/90 backdrop-blur-md overflow-hidden animate-in fade-in duration-200">
      {/* 1. Header Toolbar (Hidden during print) */}
      <header className="h-16 px-4 md:px-6 bg-slate-900 border-b border-slate-800 flex items-center justify-between gap-4 shrink-0 print:hidden text-white">
        {/* Left: Branding & Doc Type Switcher */}
        <div className="flex items-center gap-3 overflow-x-auto py-1">
          <div className="flex items-center gap-2 pr-3 border-r border-slate-800 shrink-0">
            <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center font-black text-white text-xs">
              CSG
            </div>
            <div className="hidden sm:block">
              <h2 className="text-xs font-bold leading-tight truncate max-w-[160px]">
                Document Engine
              </h2>
              <p className="text-[10px] text-slate-400">High-Res Print Studio</p>
            </div>
          </div>

          <div className="flex items-center gap-1 bg-slate-950/60 p-1 rounded-xl border border-slate-800 shrink-0">
            {docNavItems.map((item) => {
              const Icon = item.icon
              const isActive = currentDocType === item.type
              return (
                <button
                  key={item.type}
                  onClick={() => setCurrentDocType(item.type)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                    isActive
                      ? 'bg-indigo-600 text-white shadow-sm'
                      : 'text-slate-400 hover:text-white hover:bg-slate-800/50'
                  }`}
                >
                  <Icon className="w-3.5 h-3.5" />
                  <span className="hidden md:inline">{item.label}</span>
                </button>
              )
            })}
          </div>
        </div>

        {/* Right: Actions & Zoom Controls */}
        <div className="flex items-center gap-2 shrink-0">
          {/* Zoom Toolbar */}
          <div className="hidden lg:flex items-center gap-1 bg-slate-950/60 p-1 rounded-xl border border-slate-800">
            <button
              onClick={handleZoomOut}
              className="p-1.5 hover:bg-slate-800 text-slate-400 hover:text-white rounded-lg transition-colors"
              title="Zoom Out"
            >
              <ZoomOut className="w-4 h-4" />
            </button>
            <span className="text-[11px] font-mono px-1.5 text-slate-300 min-w-[42px] text-center">
              {zoomLevel}%
            </span>
            <button
              onClick={handleZoomIn}
              className="p-1.5 hover:bg-slate-800 text-slate-400 hover:text-white rounded-lg transition-colors"
              title="Zoom In"
            >
              <ZoomIn className="w-4 h-4" />
            </button>
            <button
              onClick={handleZoomReset}
              className="p-1.5 hover:bg-slate-800 text-slate-400 hover:text-white rounded-lg transition-colors ml-0.5 border-l border-slate-800"
              title="Reset Zoom"
            >
              <RotateCcw className="w-3.5 h-3.5" />
            </button>
          </div>

          {/* Verification Link Copy */}
          <button
            onClick={handleCopyVerificationLink}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition-colors"
            title="Copy Public Verification Link"
          >
            {isCopied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
            <span className="hidden sm:inline">{isCopied ? 'Copied!' : 'Verify Link'}</span>
          </button>

          {/* Quick Branding Customizer Toggle */}
          <button
            onClick={() => setShowBrandingEditor(!showBrandingEditor)}
            className={`p-2 rounded-xl text-xs font-semibold border transition-colors ${
              showBrandingEditor
                ? 'bg-amber-500/20 border-amber-500/40 text-amber-300'
                : 'bg-slate-800 hover:bg-slate-700 text-slate-300 border-slate-700'
            }`}
            title="Institutional Branding & Signatory Settings"
          >
            <SlidersHorizontal className="w-4 h-4" />
          </button>

          {/* Direct Print Button */}
          <button
            onClick={handlePrint}
            className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-bold bg-white text-slate-900 hover:bg-slate-100 shadow-sm transition-all"
          >
            <Printer className="w-4 h-4" />
            <span>Print</span>
          </button>

          {/* Direct Download Button */}
          <button
            onClick={handleDownloadPDF}
            disabled={isExporting}
            className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-bold bg-indigo-600 hover:bg-indigo-500 text-white shadow-sm transition-all disabled:opacity-50"
          >
            <Download className="w-4 h-4" />
            <span>{isExporting ? 'Exporting...' : 'PDF'}</span>
          </button>

          {/* Close Modal */}
          {onClose && (
            <button
              onClick={onClose}
              className="p-1.5 text-slate-400 hover:text-white hover:bg-slate-800 rounded-xl transition-colors ml-1"
            >
              <X className="w-5 h-5" />
            </button>
          )}
        </div>
      </header>

      {/* 2. Main Workspace / Paper Canvas */}
      <main className="flex-1 overflow-auto p-4 md:p-8 flex justify-center items-start relative bg-slate-950/60 print:bg-white print:p-0 print:overflow-visible">
        {/* Quick Branding Editor Drawer Sidebar (Overlay) */}
        {showBrandingEditor && (
          <div className="absolute top-4 right-4 z-40 w-80 bg-slate-900 border border-slate-800 rounded-2xl p-4 shadow-2xl text-xs text-white space-y-3 print:hidden animate-in slide-in-from-right-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-2">
              <span className="font-bold flex items-center gap-1.5 text-amber-400">
                <SlidersHorizontal className="w-3.5 h-3.5" /> School Branding Settings
              </span>
              <button
                onClick={() => setShowBrandingEditor(false)}
                className="text-slate-400 hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-2">
              <div>
                <label className="text-[10px] text-slate-400 block">School Legal Name</label>
                <input
                  type="text"
                  value={activeBranding.schoolName}
                  onChange={(e) =>
                    setActiveBranding({ ...activeBranding, schoolName: e.target.value })
                  }
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-white"
                />
              </div>

              <div>
                <label className="text-[10px] text-slate-400 block">Campus Name / Sector</label>
                <input
                  type="text"
                  value={activeBranding.campusName || ''}
                  onChange={(e) =>
                    setActiveBranding({ ...activeBranding, campusName: e.target.value })
                  }
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-white"
                />
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-[10px] text-slate-400 block">Principal Name</label>
                  <input
                    type="text"
                    value={activeBranding.principalName || ''}
                    onChange={(e) =>
                      setActiveBranding({ ...activeBranding, principalName: e.target.value })
                    }
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2 py-1 text-xs text-white"
                  />
                </div>
                <div>
                  <label className="text-[10px] text-slate-400 block">Registrar Name</label>
                  <input
                    type="text"
                    value={activeBranding.registrarName || ''}
                    onChange={(e) =>
                      setActiveBranding({ ...activeBranding, registrarName: e.target.value })
                    }
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2 py-1 text-xs text-white"
                  />
                </div>
              </div>

              <div>
                <label className="text-[10px] text-slate-400 block">Tax / Registration No</label>
                <input
                  type="text"
                  value={activeBranding.registrationNumber || ''}
                  onChange={(e) =>
                    setActiveBranding({ ...activeBranding, registrationNumber: e.target.value })
                  }
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-white font-mono"
                />
              </div>

              <div>
                <label className="text-[10px] text-slate-400 block">Bank Account & IBAN</label>
                <input
                  type="text"
                  value={activeBranding.bankIban || ''}
                  onChange={(e) =>
                    setActiveBranding({ ...activeBranding, bankIban: e.target.value })
                  }
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-white font-mono"
                />
              </div>
            </div>
          </div>
        )}

        {/* Scaled Printable Document Paper */}
        <div
          ref={documentRef}
          style={{
            transform: `scale(${zoomLevel / 100})`,
            transformOrigin: 'top center',
          }}
          className="transition-transform duration-100 ease-out print:transform-none print:m-0 print:p-0 print:w-full"
        >
          {currentDocType === 'bank_slip' && (
            <FeeBankSlipPDF data={feeData} branding={activeBranding} />
          )}
          {currentDocType === 'payslip' && (
            <StaffPayslipPDF data={payslipData} branding={activeBranding} />
          )}
          {currentDocType === 'cognia_transcript' && (
            <CogniaTranscriptPDF data={transcriptData} branding={activeBranding} />
          )}
          {currentDocType === 'certificate' && (
            <StudentCertificatePDF data={certificateData} branding={activeBranding} />
          )}
          {currentDocType === 'student_id_card' && (
            <StudentIDCardPDF data={idCardData} branding={activeBranding} />
          )}
        </div>
      </main>
    </div>
  )
}
