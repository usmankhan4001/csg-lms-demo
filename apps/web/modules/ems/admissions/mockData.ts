import {
  AdmissionsLeadCard,
  PipelineStageDefinition,
  NetTuitionYieldModelConfig,
  NetTuitionYieldSummary,
} from './types'

export const PIPELINE_STAGE_DEFINITIONS: PipelineStageDefinition[] = [
  {
    id: 'new_inquiry',
    title: 'New Inquiry',
    shortTitle: 'Inquiry',
    stepNumber: 1,
    colorTheme: 'text-blue-700 dark:text-blue-400',
    borderAccent: 'border-t-blue-500',
    bgAccent: 'bg-blue-50/80 dark:bg-blue-950/20 text-blue-800 dark:text-blue-300',
    badgeClass: 'bg-blue-600 text-white',
    iconName: 'MessageSquare',
    description: 'Fresh inbound inquiries from web forms, WhatsApp AI, and paid ads',
    targetSlaDays: 1,
  },
  {
    id: 'tour_scheduled',
    title: 'Tour Scheduled',
    shortTitle: 'Tour',
    stepNumber: 2,
    colorTheme: 'text-indigo-700 dark:text-indigo-400',
    borderAccent: 'border-t-indigo-500',
    bgAccent: 'bg-indigo-50/80 dark:bg-indigo-950/20 text-indigo-800 dark:text-indigo-300',
    badgeClass: 'bg-indigo-600 text-white',
    iconName: 'Calendar',
    description: 'Campus visit and discovery walkthrough confirmed with admissions desk',
    targetSlaDays: 3,
  },
  {
    id: 'application_submitted',
    title: 'Application Submitted',
    shortTitle: 'Application',
    stepNumber: 3,
    colorTheme: 'text-amber-700 dark:text-amber-400',
    borderAccent: 'border-t-amber-500',
    bgAccent: 'bg-amber-50/80 dark:bg-amber-950/20 text-amber-800 dark:text-amber-300',
    badgeClass: 'bg-amber-600 text-white',
    iconName: 'FileText',
    description: 'Formal application dossier and previous academic transcripts uploaded',
    targetSlaDays: 4,
  },
  {
    id: 'assessment',
    title: 'Assessment',
    shortTitle: 'Assessment',
    stepNumber: 4,
    colorTheme: 'text-purple-700 dark:text-purple-400',
    borderAccent: 'border-t-purple-500',
    bgAccent: 'bg-purple-50/80 dark:bg-purple-950/20 text-purple-800 dark:text-purple-300',
    badgeClass: 'bg-purple-600 text-white',
    iconName: 'GraduationCap',
    description: 'Diagnostic aptitude, cognitive evaluation, and student/parent interview',
    targetSlaDays: 5,
  },
  {
    id: 'offer_issued',
    title: 'Offer Issued',
    shortTitle: 'Offer',
    stepNumber: 5,
    colorTheme: 'text-emerald-700 dark:text-emerald-400',
    borderAccent: 'border-t-emerald-500',
    bgAccent: 'bg-emerald-50/80 dark:bg-emerald-950/20 text-emerald-800 dark:text-emerald-300',
    badgeClass: 'bg-emerald-600 text-white',
    iconName: 'Award',
    description: 'Provisional scholarship & admission letter sent with tuition schedule',
    targetSlaDays: 7,
  },
  {
    id: 'closed_enrolled',
    title: 'Closed-Enrolled',
    shortTitle: 'Enrolled',
    stepNumber: 6,
    colorTheme: 'text-teal-700 dark:text-teal-400',
    borderAccent: 'border-t-teal-500',
    bgAccent: 'bg-teal-50/80 dark:bg-teal-950/20 text-teal-800 dark:text-teal-300',
    badgeClass: 'bg-teal-600 text-white',
    iconName: 'CheckCircle2',
    description: 'Fee deposited, section allocated, and student handshake provisioned',
    targetSlaDays: 0,
  },
]

export const CAMPUS_OPTIONS = [
  'All Campuses',
  'Main Campus (Gulberg)',
  'DHA Campus (Phase 5)',
  'Islamabad Executive Campus',
  'Clifton South Campus',
]

export const FEEDER_SCHOOL_OPTIONS = [
  'All Feeder Schools',
  'Beaconhouse School System',
  'Roots Millennium Schools',
  'Learning Alliance International',
  "Froebel's International School",
  'St. Patrick High School',
  'Aitchison Prep Junior',
  'Bloomfield Hall School',
  'The City School',
  'Lahore Grammar School (LGS)',
  'Direct Inbound / Homeschool',
]

export const GRADE_OPTIONS = [
  'All Grades',
  'Grade 1',
  'Grade 2',
  'Grade 3',
  'Grade 4',
  'Grade 5',
  'Grade 6',
  'Grade 7',
  'Grade 8',
  'Grade 9 (Matric)',
  'Grade 9 (O-Level)',
  'Grade 10 (O-Level)',
  'Grade 11 (A-Level 1)',
  'Grade 12 (A-Level 2)',
]

export const INITIAL_LEADS: AdmissionsLeadCard[] = [
  // 1. New Inquiry
  {
    id: 'lead-101',
    studentName: 'Zainab Fatima',
    parentName: 'Dr. Tariq Mahmood',
    parentPhone: '+92 300 8451290',
    parentEmail: 'tariq.mahmood@cardiohealth.pk',
    targetGrade: 'Grade 9 (O-Level)',
    targetCampus: 'Main Campus (Gulberg)',
    campusId: 1,
    feederSchool: 'Beaconhouse School System',
    feederCategory: 'Private Grammar',
    stage: 'new_inquiry',
    leadScore: 92,
    leadScoreTier: 'HOT',
    grossTuitionPKR: 620000,
    scholarshipDiscountPercent: 10,
    netTuitionYieldPKR: 558000,
    assignedOfficer: 'Sana Malik (Lead SDR)',
    source: 'whatsapp',
    lastContactedDate: 'Today at 10:15 AM',
    createdAt: '2026-09-14',
    notes: 'Father requested urgent campus tour for Cambridge STEM track. Highly motivated.',
    priority: 'URGENT',
    tags: ['STEM Track', 'Cambridge', 'Doctor Family'],
    guardianCnic: '35201-1892837-1',
    emergencyPhone: '+92 321 4455889',
    proposedSection: 'Section 9-Cambridge Alpha',
    recommendedPitch: 'Highlight Robotics Lab & 98% A* Cambridge Distinction Track',
    scoreBreakdown: {
      academicFit: 95,
      budgetReadiness: 90,
      parentEngagement: 92,
      decisionUrgency: 91,
    },
    activities: [
      {
        id: 'act-1',
        type: 'whatsapp',
        title: 'WhatsApp Inquiry Received',
        description: 'Auto-responded with O-Level prospectus & scheduled discovery callback.',
        timestamp: '2026-09-14 10:15',
        officer: 'Admissions AI Bot',
      },
    ],
  },
  {
    id: 'lead-102',
    studentName: 'Hamza Bilal',
    parentName: 'Bilal Farooq',
    parentPhone: '+92 321 9988112',
    parentEmail: 'bilal.farooq@textilegroup.com',
    targetGrade: 'Grade 11 (A-Level 1)',
    targetCampus: 'DHA Campus (Phase 5)',
    campusId: 2,
    feederSchool: 'Lahore Grammar School (LGS)',
    feederCategory: 'Private Grammar',
    stage: 'new_inquiry',
    leadScore: 78,
    leadScoreTier: 'WARM',
    grossTuitionPKR: 780000,
    scholarshipDiscountPercent: 15,
    netTuitionYieldPKR: 663000,
    assignedOfficer: 'Usman Ali (RevOps)',
    source: 'meta_ads',
    lastContactedDate: 'Yesterday at 4:30 PM',
    createdAt: '2026-09-13',
    notes: 'Inquired through Instagram reel campaign. Asking for Economics & Pre-Med subjects.',
    priority: 'HIGH',
    tags: ['A-Level', 'Pre-Med', 'Hostel Query'],
    guardianCnic: '35202-9988771-3',
    emergencyPhone: '+92 300 7711223',
    proposedSection: 'Section 11-A Pre-Med',
    recommendedPitch: 'Focus on Ivy League counseling and pre-medical MCAT prep modules',
    scoreBreakdown: {
      academicFit: 84,
      budgetReadiness: 80,
      parentEngagement: 74,
      decisionUrgency: 74,
    },
  },
  {
    id: 'lead-103',
    studentName: 'Maya Sheryar',
    parentName: 'Ayesha Sheryar',
    parentPhone: '+92 333 4129980',
    parentEmail: 'ayesha.sheryar@gmail.com',
    targetGrade: 'Grade 6',
    targetCampus: 'Clifton South Campus',
    campusId: 4,
    feederSchool: 'Roots Millennium Schools',
    feederCategory: 'International Academy',
    stage: 'new_inquiry',
    leadScore: 45,
    leadScoreTier: 'COLD',
    grossTuitionPKR: 540000,
    scholarshipDiscountPercent: 0,
    netTuitionYieldPKR: 540000,
    assignedOfficer: 'Sana Malik (Lead SDR)',
    source: 'website',
    lastContactedDate: '3 days ago',
    createdAt: '2026-09-11',
    notes: 'Submitted general contact form. Awaiting response to intro email.',
    priority: 'NORMAL',
    tags: ['Middle School'],
    guardianCnic: '42201-6543210-9',
    emergencyPhone: '+92 333 4129981',
    proposedSection: 'Section 6-Emerald',
  },

  // 2. Tour Scheduled
  {
    id: 'lead-104',
    studentName: 'Ibrahim Khurram',
    parentName: 'Khurram Shehzad',
    parentPhone: '+92 301 5566778',
    parentEmail: 'k.shehzad@techlogix.io',
    targetGrade: 'Grade 7',
    targetCampus: 'Main Campus (Gulberg)',
    campusId: 1,
    feederSchool: 'Learning Alliance International',
    feederCategory: 'International Academy',
    stage: 'tour_scheduled',
    leadScore: 89,
    leadScoreTier: 'HOT',
    grossTuitionPKR: 580000,
    scholarshipDiscountPercent: 10,
    netTuitionYieldPKR: 522000,
    assignedOfficer: 'Maria Khan (Campus Host)',
    source: 'referral',
    lastContactedDate: 'Today at 11:45 AM',
    createdAt: '2026-09-12',
    notes: 'Tour scheduled for tomorrow 11:00 AM. Parent interested in AI-Integrated Classrooms.',
    priority: 'HIGH',
    tags: ['Alumni Referral', 'Tech Parent'],
    guardianCnic: '35201-5544332-1',
    emergencyPhone: '+92 302 5566779',
    proposedSection: 'Section 7-Robotics Prime',
    recommendedPitch: 'Demonstrate CSG AI-Tutor and SpeedGrader analytics during lab tour',
  },
  {
    id: 'lead-105',
    studentName: 'Ayla Danial',
    parentName: 'Danial Qasim',
    parentPhone: '+92 345 8899001',
    parentEmail: 'danial.qasim@consulting.ae',
    targetGrade: 'Grade 3',
    targetCampus: 'Islamabad Executive Campus',
    campusId: 3,
    feederSchool: "Froebel's International School",
    feederCategory: 'International Academy',
    stage: 'tour_scheduled',
    leadScore: 74,
    leadScoreTier: 'WARM',
    grossTuitionPKR: 510000,
    scholarshipDiscountPercent: 5,
    netTuitionYieldPKR: 484500,
    assignedOfficer: 'Maria Khan (Campus Host)',
    source: 'google_ads',
    lastContactedDate: 'Yesterday',
    createdAt: '2026-09-10',
    notes: 'Relocating from Dubai next month. Needs primary school briefing.',
    priority: 'HIGH',
    tags: ['Overseas Relocation', 'Primary'],
    guardianCnic: '61101-9988112-5',
    emergencyPhone: '+92 345 8899002',
    proposedSection: 'Section 3-Sapphire',
  },

  // 3. Application Submitted
  {
    id: 'lead-106',
    studentName: 'Rayan Ahmed Raza',
    parentName: 'Ahmed Raza Cheema',
    parentPhone: '+92 322 7788990',
    parentEmail: 'ar.cheema@agritech.pk',
    targetGrade: 'Grade 10 (O-Level)',
    targetCampus: 'Main Campus (Gulberg)',
    campusId: 1,
    feederSchool: 'Aitchison Prep Junior',
    feederCategory: 'Private Grammar',
    stage: 'application_submitted',
    leadScore: 95,
    leadScoreTier: 'HOT',
    grossTuitionPKR: 660000,
    scholarshipDiscountPercent: 20,
    netTuitionYieldPKR: 528000,
    assignedOfficer: 'Farhan Siddiqui (Registrar)',
    source: 'walk_in',
    lastContactedDate: 'Yesterday at 2:15 PM',
    createdAt: '2026-09-08',
    notes: 'Dossier complete. Scored Straight As in Grade 9 term exams. High merit candidate.',
    priority: 'URGENT',
    tags: ['High Merit', 'Debate Champion', 'Sibling in G5'],
    guardianCnic: '35201-1122334-5',
    emergencyPhone: '+92 322 7788991',
    proposedSection: 'Section 10-Honours O-Level',
    recommendedPitch: 'Offer 20% Founder Merit Grant + Parliamentary Debating Captaincy',
    scoreBreakdown: {
      academicFit: 99,
      budgetReadiness: 95,
      parentEngagement: 92,
      decisionUrgency: 94,
    },
  },
  {
    id: 'lead-107',
    studentName: 'Sara Daniyal',
    parentName: 'Daniyal Nisar',
    parentPhone: '+92 300 3344556',
    parentEmail: 'daniyal.nisar@nisarlaw.com',
    targetGrade: 'Grade 8',
    targetCampus: 'DHA Campus (Phase 5)',
    campusId: 2,
    feederSchool: 'Bloomfield Hall School',
    feederCategory: 'Private Grammar',
    stage: 'application_submitted',
    leadScore: 68,
    leadScoreTier: 'WARM',
    grossTuitionPKR: 560000,
    scholarshipDiscountPercent: 10,
    netTuitionYieldPKR: 504000,
    assignedOfficer: 'Farhan Siddiqui (Registrar)',
    source: 'website',
    lastContactedDate: '2 days ago',
    createdAt: '2026-09-09',
    notes: 'Transcripts received. Awaiting diagnostic test date confirmation.',
    priority: 'NORMAL',
    tags: ['Middle School', 'Lawyer Parent'],
    guardianCnic: '35202-3344556-7',
    emergencyPhone: '+92 300 3344557',
    proposedSection: 'Section 8-Falcon',
  },

  // 4. Assessment
  {
    id: 'lead-108',
    studentName: 'Mustafa Jalil',
    parentName: 'Jalil Akhtar',
    parentPhone: '+92 334 1122998',
    parentEmail: 'jalil.akhtar@pakaviation.gov.pk',
    targetGrade: 'Grade 9 (O-Level)',
    targetCampus: 'Islamabad Executive Campus',
    campusId: 3,
    feederSchool: 'St. Patrick High School',
    feederCategory: 'Private Grammar',
    stage: 'assessment',
    leadScore: 86,
    leadScoreTier: 'HOT',
    grossTuitionPKR: 640000,
    scholarshipDiscountPercent: 15,
    netTuitionYieldPKR: 544000,
    assignedOfficer: 'Dr. Noreen Shah (Dean)',
    source: 'referral',
    lastContactedDate: 'Today at 9:00 AM',
    createdAt: '2026-09-05',
    notes: 'Cognitive Test Score: 94th percentile in Logic & Math. Interview scheduled for 2:30 PM.',
    priority: 'HIGH',
    tags: ['Math Olympiad', 'Govt Officer Quota'],
    guardianCnic: '61101-4455667-1',
    emergencyPhone: '+92 334 1122999',
    proposedSection: 'Section 9-STEM Falcon',
    recommendedPitch: 'Fast-track to Advanced Math Syndicate',
  },
  {
    id: 'lead-109',
    studentName: 'Khadija Usman',
    parentName: 'Usman Jamil',
    parentPhone: '+92 312 6677889',
    parentEmail: 'usman.jamil@bankalfalah.com',
    targetGrade: 'Grade 5',
    targetCampus: 'Clifton South Campus',
    campusId: 4,
    feederSchool: 'The City School',
    feederCategory: 'Private Grammar',
    stage: 'assessment',
    leadScore: 71,
    leadScoreTier: 'WARM',
    grossTuitionPKR: 530000,
    scholarshipDiscountPercent: 5,
    netTuitionYieldPKR: 503500,
    assignedOfficer: 'Dr. Noreen Shah (Dean)',
    source: 'meta_ads',
    lastContactedDate: 'Yesterday',
    createdAt: '2026-09-06',
    notes: 'Written assessment scored 78%. Reading fluency assessment satisfactory.',
    priority: 'NORMAL',
    tags: ['Primary Transition'],
    guardianCnic: '42201-7788990-3',
    emergencyPhone: '+92 312 6677880',
    proposedSection: 'Section 5-Garnet',
  },

  // 5. Offer Issued
  {
    id: 'lead-110',
    studentName: 'Eshal Mansoor',
    parentName: 'Mansoor Alam',
    parentPhone: '+92 300 9988223',
    parentEmail: 'mansoor.alam@descon.com',
    targetGrade: 'Grade 12 (A-Level 2)',
    targetCampus: 'Main Campus (Gulberg)',
    campusId: 1,
    feederSchool: 'Lahore Grammar School (LGS)',
    feederCategory: 'Private Grammar',
    stage: 'offer_issued',
    leadScore: 96,
    leadScoreTier: 'HOT',
    grossTuitionPKR: 820000,
    scholarshipDiscountPercent: 25,
    netTuitionYieldPKR: 615000,
    assignedOfficer: 'Admissions Lead Desk',
    source: 'walk_in',
    lastContactedDate: 'Today at 8:30 AM',
    createdAt: '2026-09-01',
    notes: 'Official Offer Letter #OFF-2026-089 issued. 25% Merit Scholarship applied. Valid till Sept 25.',
    priority: 'URGENT',
    tags: ['A* Merit Scholar', 'Engineering Track', 'High Yield'],
    guardianCnic: '35201-9988223-5',
    emergencyPhone: '+92 300 9988224',
    proposedSection: 'Section 12-A Level Advanced',
    recommendedPitch: 'Emphasize guaranteed lab bench allocation and FAST/GIKI prep bootcamp',
  },
  {
    id: 'lead-111',
    studentName: 'Zorain Shah',
    parentName: 'Shahbaz Hassan',
    parentPhone: '+92 321 4400998',
    parentEmail: 'shahbaz.hassan@hassanmills.pk',
    targetGrade: 'Grade 9 (O-Level)',
    targetCampus: 'DHA Campus (Phase 5)',
    campusId: 2,
    feederSchool: 'Beaconhouse School System',
    feederCategory: 'Private Grammar',
    stage: 'offer_issued',
    leadScore: 84,
    leadScoreTier: 'WARM',
    grossTuitionPKR: 650000,
    scholarshipDiscountPercent: 15,
    netTuitionYieldPKR: 552500,
    assignedOfficer: 'Admissions Lead Desk',
    source: 'referral',
    lastContactedDate: 'Yesterday',
    createdAt: '2026-09-02',
    notes: 'Offer letter emailed. Parent reviewing Quarterly Fee installment breakdown.',
    priority: 'HIGH',
    tags: ['O-Level', 'Quarterly Plan Preferred'],
    guardianCnic: '35202-4400998-1',
    emergencyPhone: '+92 321 4400990',
    proposedSection: 'Section 9-Cambridge Beta',
  },

  // 6. Closed-Enrolled
  {
    id: 'lead-112',
    studentName: 'Arham Waseem',
    parentName: 'Waseem Akram Mir',
    parentPhone: '+92 300 1234567',
    parentEmail: 'waseem.mir@nestle.com',
    targetGrade: 'Grade 10 (O-Level)',
    targetCampus: 'Main Campus (Gulberg)',
    campusId: 1,
    feederSchool: 'Aitchison Prep Junior',
    feederCategory: 'Private Grammar',
    stage: 'closed_enrolled',
    leadScore: 98,
    leadScoreTier: 'HOT',
    grossTuitionPKR: 660000,
    scholarshipDiscountPercent: 10,
    netTuitionYieldPKR: 594000,
    assignedOfficer: 'Head of Admissions',
    source: 'referral',
    lastContactedDate: 'Enrolled Today',
    createdAt: '2026-08-28',
    notes: 'Fee deposited (Bank Challan #CH-99218). Section 10-Alpha assigned. LMS account provisioned.',
    priority: 'NORMAL',
    tags: ['Matriculated', 'Fee Paid', 'LMS Active'],
    guardianCnic: '35201-1234567-9',
    emergencyPhone: '+92 300 1234568',
    proposedSection: 'Section 10-Cambridge Alpha',
  },
  {
    id: 'lead-113',
    studentName: 'Noor-ul-Huda',
    parentName: 'Dr. Shahida Parveen',
    parentPhone: '+92 333 8877665',
    parentEmail: 'dr.shahida@shaukatkhanum.org.pk',
    targetGrade: 'Grade 11 (A-Level 1)',
    targetCampus: 'DHA Campus (Phase 5)',
    campusId: 2,
    feederSchool: 'Lahore Grammar School (LGS)',
    feederCategory: 'Private Grammar',
    stage: 'closed_enrolled',
    leadScore: 94,
    leadScoreTier: 'HOT',
    grossTuitionPKR: 790000,
    scholarshipDiscountPercent: 20,
    netTuitionYieldPKR: 632000,
    assignedOfficer: 'Head of Admissions',
    source: 'walk_in',
    lastContactedDate: 'Enrolled Yesterday',
    createdAt: '2026-08-25',
    notes: 'Annual lump-sum payment cleared via 1LINK portal. Student card issued.',
    priority: 'NORMAL',
    tags: ['Matriculated', 'Full Paid', 'Merit 20%'],
    guardianCnic: '35202-8877665-2',
    emergencyPhone: '+92 333 8877660',
    proposedSection: 'Section 11-A Pre-Med Diamond',
  },
]

export const DEFAULT_NTY_CONFIG: NetTuitionYieldModelConfig = {
  cohortGrade: 'Grade 9 (O-Level)',
  targetCohortSize: 120,
  currentEnrolledCount: 88,
  baseAnnualTuitionPKR: 650000,
  meritDiscountPercent: 20,
  meritQuotaPercent: 25, // 25% of students get merit
  needBasedDiscountPercent: 30,
  needQuotaPercent: 15, // 15% of students get need aid
  siblingDiscountPercent: 10,
  siblingQuotaPercent: 20, // 20% of students have siblings
  attritionBufferPercent: 5,
}

export function computeNetTuitionYield(config: NetTuitionYieldModelConfig): NetTuitionYieldSummary {
  const {
    targetCohortSize,
    currentEnrolledCount,
    baseAnnualTuitionPKR,
    meritDiscountPercent,
    meritQuotaPercent,
    needBasedDiscountPercent,
    needQuotaPercent,
    siblingDiscountPercent,
    siblingQuotaPercent,
    attritionBufferPercent,
  } = config

  const activeStudents = currentEnrolledCount || 1
  const grossPotentialTuitionPKR = targetCohortSize * baseAnnualTuitionPKR
  const projectedEnrolledRevenuePKR = activeStudents * baseAnnualTuitionPKR

  // Compute weighted discount per student
  const meritShare = meritQuotaPercent / 100
  const needShare = needQuotaPercent / 100
  const siblingShare = siblingQuotaPercent / 100

  const avgDiscountRate =
    meritShare * (meritDiscountPercent / 100) +
    needShare * (needBasedDiscountPercent / 100) +
    siblingShare * (siblingDiscountPercent / 100)

  const effectiveDiscountRate = Math.min(avgDiscountRate, 0.65) // Cap at 65%

  const totalInstitutionalDiscountsPKR = Math.round(
    projectedEnrolledRevenuePKR * effectiveDiscountRate
  )
  const attritionLoss = Math.round(
    projectedEnrolledRevenuePKR * (attritionBufferPercent / 100)
  )

  const totalNetTuitionYieldPKR = Math.max(
    0,
    projectedEnrolledRevenuePKR - totalInstitutionalDiscountsPKR - attritionLoss
  )

  const netTuitionYieldPerStudentPKR = Math.round(
    totalNetTuitionYieldPKR / activeStudents
  )

  const yieldRealizationRatePercent = Math.round(
    (totalNetTuitionYieldPKR / projectedEnrolledRevenuePKR) * 100
  )

  const fixedCostEstimate = grossPotentialTuitionPKR * 0.45
  const breakevenThresholdStudents = Math.min(
    targetCohortSize,
    Math.ceil(fixedCostEstimate / (netTuitionYieldPerStudentPKR || 1))
  )

  const capacityFillRatePercent = Math.round(
    (activeStudents / (targetCohortSize || 1)) * 100
  )

  return {
    grossPotentialTuitionPKR,
    projectedEnrolledRevenuePKR,
    totalInstitutionalDiscountsPKR,
    totalNetTuitionYieldPKR,
    netTuitionYieldPerStudentPKR,
    yieldRealizationRatePercent,
    breakevenThresholdStudents,
    capacityFillRatePercent,
  }
}

export function formatPKR(val: number): string {
  if (val >= 10000000) {
    return `PKR ${(val / 10000000).toFixed(2)} Cr`
  }
  if (val >= 100000) {
    return `PKR ${(val / 100000).toFixed(2)} Lakh`
  }
  return `PKR ${val.toLocaleString()}`
}

export function formatCompactNumber(val: number): string {
  if (val >= 1000000) {
    return `${(val / 1000000).toFixed(1)}M`
  }
  if (val >= 1000) {
    return `${(val / 1000).toFixed(0)}k`
  }
  return val.toString()
}
