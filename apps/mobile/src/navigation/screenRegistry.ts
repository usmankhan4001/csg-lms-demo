import type { ComponentType } from 'react';
import type { MobileRole } from '@/auth/types';
import {
  StudentAiCoachStackNavigator,
  StudentAssignmentsStackNavigator,
  StudentHomeStackNavigator,
  StudentMoreStackNavigator,
  StudentTimetableStackNavigator,
} from './stacks/StudentStacks';
import {
  TeacherAttendanceStackNavigator,
  TeacherClassesStackNavigator,
  TeacherGradebookStackNavigator,
  TeacherMoreStackNavigator,
  TeacherTodayStackNavigator,
} from './stacks/TeacherStacks';
import {
  ParentChildrenStackNavigator,
  ParentFeesStackNavigator,
  ParentHomeStackNavigator,
  ParentMessagesStackNavigator,
  ParentMoreStackNavigator,
} from './stacks/ParentStacks';
import {
  StaffDirectoryStackNavigator,
  StaffPayrollStackNavigator,
  StaffTasksStackNavigator,
  StaffTodayStackNavigator,
  StaffMoreStackNavigator,
} from './stacks/StaffStacks';

/**
 * Maps each `nav-config.ts` item id to the (stack) component that renders
 * it. This is the RN equivalent of the web `NavItem.href` resolving to a
 * Next.js file-route — since bottom tabs navigate by component reference,
 * not URL, the mapping has to be explicit here rather than filesystem-based.
 */
export const TAB_SCREEN_REGISTRY: Record<MobileRole, Record<string, ComponentType>> = {
  STUDENT: {
    home: StudentHomeStackNavigator,
    timetable: StudentTimetableStackNavigator,
    assignments: StudentAssignmentsStackNavigator,
    'ai-coach': StudentAiCoachStackNavigator,
    more: StudentMoreStackNavigator,
  },
  TEACHER: {
    today: TeacherTodayStackNavigator,
    classes: TeacherClassesStackNavigator,
    gradebook: TeacherGradebookStackNavigator,
    attendance: TeacherAttendanceStackNavigator,
    more: TeacherMoreStackNavigator,
  },
  PARENT: {
    home: ParentHomeStackNavigator,
    children: ParentChildrenStackNavigator,
    fees: ParentFeesStackNavigator,
    messages: ParentMessagesStackNavigator,
    more: ParentMoreStackNavigator,
  },
  STAFF: {
    today: StaffTodayStackNavigator,
    tasks: StaffTasksStackNavigator,
    payroll: StaffPayrollStackNavigator,
    directory: StaffDirectoryStackNavigator,
    more: StaffMoreStackNavigator,
  },
};
