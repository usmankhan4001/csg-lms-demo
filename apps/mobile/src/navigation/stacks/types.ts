import type { StudentAttendanceRead } from '@/modules/sms/attendance/types';
import type { StudentEnrollmentRead } from '@/modules/sms/campus/types';
import type { AssessmentPlanRead } from '@/modules/sms/gradebook/types';

export type StudentHomeStackParamList = {
  HomeMain: undefined;
  AttendanceHistory: undefined;
  // The record is passed directly rather than re-fetched — MyHistoryScreen
  // already holds it in memory, and per M06's mobile spec Status Detail is
  // an "offline read of session details", so no extra network round trip.
  AttendanceDetail: { record: StudentAttendanceRead };
};

export type StudentTimetableStackParamList = {
  TimetableMain: undefined;
};

export type StudentAssignmentsStackParamList = {
  AssignmentsMain: undefined;
};

export type StudentAiCoachStackParamList = {
  AiCoachMain: undefined;
};

export type StudentMoreStackParamList = {
  MoreMain: undefined;
};

export type TeacherTodayStackParamList = {
  TodayMain: undefined;
};

export type TeacherClassesStackParamList = {
  ClassesMain: undefined;
};

export type TeacherGradebookStackParamList = {
  GradebookPlans: undefined;
  GradeEntry: { plan: AssessmentPlanRead };
};

export type TeacherAttendanceStackParamList = {
  CheckInPicker: undefined;
  RollCall: { sectionId: number; date: string };
};

export type TeacherMoreStackParamList = {
  MoreMain: undefined;
};

export type EnrollmentWithLabel = StudentEnrollmentRead & { label?: string };

// ── PARENT ──
// `studentId` is only ever taken from the server-resolved children list
// (GET /sms/me -> children_ids); it is a navigation convenience, not a
// trust boundary. Every per-child endpoint re-checks guardianship via
// `require_own_student_or_privileged`, so a wrong id here yields a 403,
// not another family's data.

export type ParentHomeStackParamList = {
  HomeMain: undefined;
  ChildDetail: { studentId: number; name: string };
};

export type ParentChildrenStackParamList = {
  ChildrenMain: undefined;
  ChildDetail: { studentId: number; name: string };
};

export type ParentFeesStackParamList = {
  FeesMain: undefined;
};

export type ParentMessagesStackParamList = {
  MessagesMain: undefined;
  ThreadDetail: { threadId: number; subject: string };
};

export type ParentMoreStackParamList = {
  MoreMain: undefined;
};

export type StaffDirectoryStackParamList = {
  DirectoryMain: undefined;
};
