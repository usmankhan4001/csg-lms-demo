/**
 * CSG-EMS Document Engine & Institutional Branding System
 * =======================================================
 * Core types, branding configuration, sample data generators, and layout schemas
 * for Fee Bank Vouchers, Staff Payslips, Cognia Transcripts, Certificates, and Student ID Cards.
 */

export type DocumentType =
  | 'bank_slip'
  | 'payslip'
  | 'cognia_transcript'
  | 'certificate'
  | 'student_id_card'

export interface SchoolBrandingConfig {
  id?: number
  orgId?: number
  campusId?: number | null
  schoolName: string
  schoolTagline?: string
  campusName?: string
  logoUrl?: string
  crestUrl?: string
  primaryColor: string
  secondaryColor: string
  accentColor: string
  principalName?: string
  principalTitle?: string
  principalSignatureUrl?: string
  controllerName?: string
  controllerTitle?: string
  controllerSignatureUrl?: string
  registrarName?: string
  registrarTitle?: string
  registrarSignatureUrl?: string
  officialStampUrl?: string
  taxId?: string
  registrationNumber?: string
  bankName?: string
  bankBranch?: string
  bankBranchCode?: string
  bankAccountTitle?: string
  bankAccountNumber?: string
  bankIban?: string
  bankSwiftCode?: string
  accreditationBody?: string
  accreditationSealUrl?: string
  accreditationNumber?: string
  contactEmail?: string
  contactPhone?: string
  websiteUrl?: string
  physicalAddress?: string
  customFooterText?: string
}

export const DEFAULT_SCHOOL_BRANDING: SchoolBrandingConfig = {
  schoolName: 'CSG International Academy & College of Sciences',
  schoolTagline: 'Excellence in Global Learning, Leadership & Innovation',
  campusName: 'Main Diplomatic Campus (Sector H-8)',
  primaryColor: '#4F46E5', // Indigo-600
  secondaryColor: '#0EA5E9', // Sky-500
  accentColor: '#D97706', // Amber-600
  principalName: 'Dr. Eleanor Vance, Ph.D.',
  principalTitle: 'Head of School & Principal',
  controllerName: 'Marcus Sterling, CPA',
  controllerTitle: 'Chief Financial Officer',
  registrarName: 'Patricia Holloway, M.Ed.',
  registrarTitle: 'Academic Registrar & Dean of Records',
  taxId: 'NTN: 9842104-7',
  registrationNumber: 'REG-MOE-2018-9412B',
  bankName: 'Habib Bank Limited (HBL) / Standard Chartered',
  bankBranch: 'Diplomatic Enclave Corporate Branch',
  bankBranchCode: '0482',
  bankAccountTitle: 'CSG Educational Ventures Trust',
  bankAccountNumber: '0482-7901234503',
  bankIban: 'PK36HABB0000482790123450',
  bankSwiftCode: 'HABBPKKA',
  accreditationBody: 'Cognia Global Accreditation Commission',
  accreditationNumber: 'COG-INTL-89104-ACC',
  contactEmail: 'admissions@csg-academy.edu',
  contactPhone: '+92 (51) 849-2000 / +1 (555) 019-2834',
  websiteUrl: 'https://academy.csg.edu',
  physicalAddress: 'Sector H-8/4, Diplomatic Avenue, Islamabad, Pakistan',
  customFooterText: 'This is an authentic computer-generated institutional instrument protected by cryptographic seal verification.',
}

// ---------------------------------------------------------------------------
// 1. Fee Bank Slip (3-Part Voucher) Data Model
// ---------------------------------------------------------------------------

export interface FeeItemLine {
  id: string
  title: string
  category: 'tuition' | 'lab' | 'library' | 'sports' | 'admission' | 'security' | 'other'
  amount: number
  discount?: number
  netAmount: number
}

export interface FeeBankSlipData {
  voucherNo: string
  invoiceNo: string
  studentId: number
  studentName: string
  rollNumber: string
  gradeClass: string
  section: string
  academicYear: string
  termName: string
  billingMonth: string
  issueDate: string
  dueDate: string
  validityDate: string
  feeItems: FeeItemLine[]
  subtotal: number
  totalDiscount: number
  netPayableBeforeDueDate: number
  lateFeeSurcharge: number
  netPayableAfterDueDate: number
  paymentStatus: 'UNPAID' | 'PARTIAL' | 'PAID' | 'OVERDUE'
  paymentNotes?: string
  barcodeValue: string
  qrCodeValue: string
}

export const SAMPLE_FEE_BANK_SLIP_DATA: FeeBankSlipData = {
  voucherNo: 'VCH-2026-08914',
  invoiceNo: 'INV-2026-Q1-552',
  studentId: 1042,
  studentName: 'Zainab Fatima Khan',
  rollNumber: 'CSG-2024-G11-042',
  gradeClass: 'Grade 11 (IB Diploma Programme)',
  section: 'Section Alpha (STEM Focus)',
  academicYear: '2025 - 2026',
  termName: 'Spring Term 2026',
  billingMonth: 'March 2026',
  issueDate: '2026-03-01',
  dueDate: '2026-03-15',
  validityDate: '2026-03-31',
  feeItems: [
    { id: '1', title: 'Monthly Tuition & Academic Instruction', category: 'tuition', amount: 48000, discount: 4800, netAmount: 43200 },
    { id: '2', title: 'Science & Robotics Laboratory Facility Fee', category: 'lab', amount: 6500, discount: 0, netAmount: 6500 },
    { id: '3', title: 'Digital Library & Research Database Access', category: 'library', amount: 3500, discount: 0, netAmount: 3500 },
    { id: '4', title: 'Sports Complex & Swimming Gymnasium Fee', category: 'sports', amount: 4000, discount: 0, netAmount: 4000 },
    { id: '5', title: 'Cognia Standardized Assessment & Exam Fee', category: 'other', amount: 5000, discount: 0, netAmount: 5000 },
  ],
  subtotal: 67000,
  totalDiscount: 4800,
  netPayableBeforeDueDate: 62200,
  lateFeeSurcharge: 2500,
  netPayableAfterDueDate: 64700,
  paymentStatus: 'UNPAID',
  paymentNotes: 'Please deposit at any online HBL/SCB branch or pay via 1Link 1Bill ID #048298914.',
  barcodeValue: '048202608914062200',
  qrCodeValue: 'https://academy.csg.edu/pay/vch/VCH-2026-08914',
}

// ---------------------------------------------------------------------------
// 2. Staff Payslip Data Model
// ---------------------------------------------------------------------------

export interface ProgressiveTaxScheduleTier {
  tierName: string
  lowerLimit: number
  upperLimit: number | null
  ratePercent: number
  taxableAmount: number
  taxCharged: number
}

export interface StaffPayslipData {
  slipNo: string
  staffId: number
  employeeCode: string
  staffName: string
  department: string
  designation: string
  gradeBand: string
  nationalTaxNumber: string
  bankAccountTitle: string
  bankAccountNumber: string
  bankIban: string
  payPeriodMonth: string
  payPeriodYear: number
  workingDays: number
  daysPresent: number
  unpaidLeaveDays: number
  basicSalary: number
  housingAllowance: number
  medicalAllowance: number
  conveyanceAllowance: number
  specialDutyAllowance: number
  grossSalary: number
  providentFundPensionDeduction: number
  progressiveIncomeTaxDeduction: number
  unpaidLeaveDeduction: number
  healthInsuranceDeduction: number
  otherDeductions: number
  totalDeductions: number
  netSalary: number
  netSalaryInWords: string
  isClamped: boolean
  taxSchedule: ProgressiveTaxScheduleTier[]
  status: 'PENDING' | 'APPROVED' | 'PAID'
  paymentDate?: string
  paymentMethod: string
  preparerName: string
  preparerTitle: string
  approverName: string
  approverTitle: string
  verificationHash: string
}

export const SAMPLE_STAFF_PAYSLIP_DATA: StaffPayslipData = {
  slipNo: 'PAY-2026-03-088',
  staffId: 504,
  employeeCode: 'FAC-ENG-088',
  staffName: 'Prof. Tariq Mahmud Al-Mansoor',
  department: 'Faculty of Advanced Sciences & Mathematics',
  designation: 'Senior Faculty Lead & IB Physics Examiner',
  gradeBand: 'Band 7 (Senior Academic Specialist)',
  nationalTaxNumber: 'NTN-4109823-1',
  bankAccountTitle: 'Tariq Mahmud Al-Mansoor',
  bankAccountNumber: '0482-8834921004',
  bankIban: 'PK12SCBL0000048288349210',
  payPeriodMonth: 'March 2026',
  payPeriodYear: 2026,
  workingDays: 22,
  daysPresent: 22,
  unpaidLeaveDays: 0,
  basicSalary: 220000,
  housingAllowance: 66000,
  medicalAllowance: 22000,
  conveyanceAllowance: 18000,
  specialDutyAllowance: 15000,
  grossSalary: 341000,
  providentFundPensionDeduction: 17050, // 5% PF
  progressiveIncomeTaxDeduction: 28450, // Progressive bracket calculation
  unpaidLeaveDeduction: 0,
  healthInsuranceDeduction: 4500,
  otherDeductions: 0,
  totalDeductions: 50000,
  netSalary: 291000,
  netSalaryInWords: 'Two Hundred Ninety-One Thousand Rupees Only',
  isClamped: false,
  taxSchedule: [
    { tierName: 'Tier 1 (Up to PKR 50,000)', lowerLimit: 0, upperLimit: 50000, ratePercent: 0, taxableAmount: 50000, taxCharged: 0 },
    { tierName: 'Tier 2 (PKR 50k - 100k)', lowerLimit: 50000, upperLimit: 100000, ratePercent: 5, taxableAmount: 50000, taxCharged: 2500 },
    { tierName: 'Tier 3 (PKR 100k - 200k)', lowerLimit: 100000, upperLimit: 200000, ratePercent: 12.5, taxableAmount: 100000, taxCharged: 12500 },
    { tierName: 'Tier 4 (Above PKR 200k)', lowerLimit: 200000, upperLimit: null, ratePercent: 22.5, taxableAmount: 59700, taxCharged: 13450 },
  ],
  status: 'PAID',
  paymentDate: '2026-03-31',
  paymentMethod: 'Direct Bank Wire Transfer (1Link Raast ID)',
  preparerName: 'Sarah Jenkins, SHRM-CP',
  preparerTitle: 'Head of Human Resources & Payroll',
  approverName: 'Marcus Sterling, CPA',
  approverTitle: 'Chief Financial Officer & Controller',
  verificationHash: '8f92a40c6b12e3d7a84091e0a811c75b31e920d3f829a415b3e201c84f671b90',
}

// ---------------------------------------------------------------------------
// 3. Cognia-Compliant Official Academic Transcript Data Model
// ---------------------------------------------------------------------------

export interface TranscriptCourseEntry {
  courseCode: string
  courseTitle: string
  creditHours: number
  marksObtained: number
  totalMarks: number
  percentage: number
  letterGrade: string
  gpaPoint: number
  isWeighted: boolean
  remarks: string
}

export interface TranscriptTermBlock {
  termName: string
  academicYear: string
  gradeLevel: string
  termGpa: number
  termCredits: number
  courses: TranscriptCourseEntry[]
}

export interface CogniaTranscriptData {
  transcriptNo: string
  studentId: number
  studentName: string
  studentDob: string
  enrollmentNo: string
  candidateNumber?: string
  gender: string
  gradeLevel: string
  graduationYear: string
  issueDate: string
  status: 'OFFICIAL' | 'PROVISIONAL' | 'ARCHIVED'
  terms: TranscriptTermBlock[]
  cumulativeGpa: number
  weightedGpa: number
  unweightedGpa: number
  totalCreditsAttempted: number
  totalCreditsEarned: number
  classRank: string
  totalClassSize: number
  attendanceDaysPresent: number
  attendanceDaysTotal: number
  attendancePercentage: number
  generalRemarks: string
  gradingScaleLegend: {
    letter: string
    range: string
    gpa: number
    description: string
  }[]
  verificationHash: string
  verificationQrUrl: string
}

export const SAMPLE_COGNIA_TRANSCRIPT_DATA: CogniaTranscriptData = {
  transcriptNo: 'TRN-COG-2026-00481',
  studentId: 1042,
  studentName: 'Zainab Fatima Khan',
  studentDob: '2008-07-14',
  enrollmentNo: 'ENR-2023-90812',
  candidateNumber: '003921-0042',
  gender: 'Female',
  gradeLevel: 'Grade 12 (Senior Secondary)',
  graduationYear: 'Class of 2026',
  issueDate: '2026-03-16',
  status: 'OFFICIAL',
  terms: [
    {
      termName: 'Fall Semester 2025',
      academicYear: '2025 - 2026',
      gradeLevel: 'Grade 12',
      termGpa: 3.94,
      termCredits: 4.0,
      courses: [
        { courseCode: 'AP-CALC-BC', courseTitle: 'Advanced Placement Calculus BC', creditHours: 1.0, marksObtained: 96, totalMarks: 100, percentage: 96, letterGrade: 'A+', gpaPoint: 4.0, isWeighted: true, remarks: 'Exemplary analytical performance' },
        { courseCode: 'IB-PHYS-HL', courseTitle: 'IB Physics Higher Level (HL)', creditHours: 1.0, marksObtained: 92, totalMarks: 100, percentage: 92, letterGrade: 'A', gpaPoint: 4.0, isWeighted: true, remarks: 'Outstanding laboratory investigation' },
        { courseCode: 'ENG-LIT-401', courseTitle: 'World Literature & Rhetorical Analysis', creditHours: 1.0, marksObtained: 89, totalMarks: 100, percentage: 89, letterGrade: 'A-', gpaPoint: 3.7, isWeighted: false, remarks: 'Strong critical argumentation' },
        { courseCode: 'CS-AI-301', courseTitle: 'Artificial Intelligence & Data Systems', creditHours: 1.0, marksObtained: 98, totalMarks: 100, percentage: 98, letterGrade: 'A+', gpaPoint: 4.0, isWeighted: true, remarks: 'Top class project capstone' },
      ],
    },
    {
      termName: 'Spring Semester 2026 (Mid-Term Record)',
      academicYear: '2025 - 2026',
      gradeLevel: 'Grade 12',
      termGpa: 4.0,
      termCredits: 4.0,
      courses: [
        { courseCode: 'AP-CHEM-HL', courseTitle: 'Advanced Placement Chemistry', creditHours: 1.0, marksObtained: 94, totalMarks: 100, percentage: 94, letterGrade: 'A', gpaPoint: 4.0, isWeighted: true, remarks: 'Mastery in organic mechanisms' },
        { courseCode: 'ECON-MACRO', courseTitle: 'Macroeconomics & Global Finance', creditHours: 1.0, marksObtained: 95, totalMarks: 100, percentage: 95, letterGrade: 'A', gpaPoint: 4.0, isWeighted: true, remarks: 'Exceptional fiscal policy paper' },
        { courseCode: 'HIST-GLB-202', courseTitle: 'Contemporary Global Diplomatic History', creditHours: 1.0, marksObtained: 91, totalMarks: 100, percentage: 91, letterGrade: 'A', gpaPoint: 4.0, isWeighted: false, remarks: 'Thorough historiographic synthesis' },
        { courseCode: 'STAT-MATH-400', courseTitle: 'Advanced Probability & Multivariable Calculus', creditHours: 1.0, marksObtained: 97, totalMarks: 100, percentage: 97, letterGrade: 'A+', gpaPoint: 4.0, isWeighted: true, remarks: 'Rigorous theorem proofs' },
      ],
    },
  ],
  cumulativeGpa: 3.96,
  weightedGpa: 4.28,
  unweightedGpa: 3.92,
  totalCreditsAttempted: 28.0,
  totalCreditsEarned: 28.0,
  classRank: 'Top 2%',
  totalClassSize: 148,
  attendanceDaysPresent: 174,
  attendanceDaysTotal: 180,
  attendancePercentage: 96.67,
  generalRemarks: 'Student demonstrates exceptional scholastic distinction, high moral character, and extraordinary STEM research aptitude.',
  gradingScaleLegend: [
    { letter: 'A+', range: '95 - 100%', gpa: 4.0, description: 'Superior / High Distinction' },
    { letter: 'A', range: '90 - 94%', gpa: 4.0, description: 'Excellent / Distinction' },
    { letter: 'A-', range: '85 - 89%', gpa: 3.7, description: 'Very Good' },
    { letter: 'B+', range: '80 - 84%', gpa: 3.3, description: 'Good' },
    { letter: 'B', range: '75 - 79%', gpa: 3.0, description: 'Satisfactory' },
    { letter: 'C', range: '70 - 74%', gpa: 2.0, description: 'Average' },
    { letter: 'F', range: 'Below 60%', gpa: 0.0, description: 'Failing' },
  ],
  verificationHash: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
  verificationQrUrl: 'https://academy.csg.edu/verify-doc/TRN-COG-2026-00481',
}

// ---------------------------------------------------------------------------
// 4. Student Certificate of Achievement Data Model
// ---------------------------------------------------------------------------

export interface StudentCertificateData {
  certificateId: number
  certificateNo: string
  studentName: string
  studentId: number
  awardTitle: string
  awardCategory: 'Academic Excellence' | 'High Honors' | 'Graduation' | 'STEM Laureate' | 'Sports Leadership' | 'Distinguished Service'
  citationText: string
  honorsSuffix?: string
  academicYear: string
  issueDate: string
  borderTheme: 'classic_gold' | 'royal_navy' | 'modern_emerald' | 'crimson_prestige'
  verificationHash: string
  verificationQrUrl: string
}

export const SAMPLE_STUDENT_CERTIFICATE_DATA: StudentCertificateData = {
  certificateId: 88,
  certificateNo: 'CRT-2026-VAL-0042',
  studentName: 'Zainab Fatima Khan',
  studentId: 1042,
  awardTitle: 'Grand Laureate of Academic Distinction & Valedictorian',
  awardCategory: 'Academic Excellence',
  citationText: 'For attaining the highest cumulative academic standing with a 4.28 Weighted GPA, demonstrating peerless dedication to rigorous scientific scholarship, pioneering student council leadership, and exemplary ethical citizenship across the 2025-2026 academic tenure.',
  honorsSuffix: 'Summa Cum Laude & Presidential Scholar',
  academicYear: 'Academic Session 2025 – 2026',
  issueDate: 'March 16, 2026',
  borderTheme: 'classic_gold',
  verificationHash: 'd4735e3a265e16eee03f59718b9b5d03019c07d8b6c51f90da3a666eec13ab35',
  verificationQrUrl: 'https://academy.csg.edu/verify-cert/CRT-2026-VAL-0042',
}

// ---------------------------------------------------------------------------
// 5. Printable Student ID Card Data Model (CR80 Standard Dimensions)
// ---------------------------------------------------------------------------

export interface StudentIDCardData {
  cardId: number
  cardNumber: string
  studentName: string
  studentId: number
  rollNumber: string
  gradeClass: string
  section: string
  academicYear: string
  dateOfBirth: string
  bloodGroup: string
  photoUrl?: string
  guardianName: string
  guardianPhone: string
  emergencyContact: string
  residentialAddress: string
  issueDate: string
  expiryDate: string
  barcodeValue: string
  qrCodeValue: string
  cardOrientation: 'portrait' | 'landscape'
}

export const SAMPLE_STUDENT_ID_CARD_DATA: StudentIDCardData = {
  cardId: 902,
  cardNumber: 'CARD-2026-G11-042',
  studentName: 'Zainab Fatima Khan',
  studentId: 1042,
  rollNumber: 'CSG-2024-G11-042',
  gradeClass: 'Grade 11 - IBDP',
  section: 'Section Alpha',
  academicYear: '2025 - 2026',
  dateOfBirth: '14 Jul 2008',
  bloodGroup: 'O Positive (O+)',
  photoUrl: 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=400&auto=format&fit=crop&q=80',
  guardianName: 'Engr. Tariq M. Khan',
  guardianPhone: '+92 300 8594210',
  emergencyContact: '+92 (51) 849-2000 (Ext. 104)',
  residentialAddress: 'House 42-A, Street 18, Sector F-7/2, Islamabad',
  issueDate: '01 Sep 2025',
  expiryDate: '30 Jun 2026',
  barcodeValue: '20240421042',
  qrCodeValue: 'https://academy.csg.edu/id/CSG-2024-G11-042',
  cardOrientation: 'portrait',
}

// ---------------------------------------------------------------------------
// Helper Utilities for Document Formatting & Print Layouts
// ---------------------------------------------------------------------------

export function formatCurrency(amount: number, currency = 'PKR'): string {
  return `${currency} ${amount.toLocaleString(undefined, {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  })}`
}

export function formatDatePretty(dateString: string): string {
  try {
    const date = new Date(dateString)
    if (isNaN(date.getTime())) return dateString
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    })
  } catch {
    return dateString
  }
}
