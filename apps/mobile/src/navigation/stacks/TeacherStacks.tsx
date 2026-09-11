import React from 'react';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { TeacherTodayScreen } from '@/screens/teacher/TodayScreen';
import { TeacherClassesScreen } from '@/screens/teacher/ClassesScreen';
import { GradebookPlansScreen } from '@/screens/teacher/gradebook/GradebookPlansScreen';
import { GradeEntryScreen } from '@/screens/teacher/gradebook/GradeEntryScreen';
import { CheckInPickerScreen } from '@/screens/teacher/attendance/CheckInPickerScreen';
import { RollCallScreen } from '@/screens/teacher/attendance/RollCallScreen';
import { MoreScreen } from '@/screens/shared/MoreScreen';
import { headerScreenOptions } from '../headerOptions';
import type {
  TeacherAttendanceStackParamList,
  TeacherClassesStackParamList,
  TeacherGradebookStackParamList,
  TeacherMoreStackParamList,
  TeacherTodayStackParamList,
} from './types';

const TodayStack = createNativeStackNavigator<TeacherTodayStackParamList>();
export function TeacherTodayStackNavigator() {
  return (
    <TodayStack.Navigator screenOptions={headerScreenOptions}>
      <TodayStack.Screen name="TodayMain" component={TeacherTodayScreen} options={{ title: 'Today' }} />
    </TodayStack.Navigator>
  );
}

const ClassesStack = createNativeStackNavigator<TeacherClassesStackParamList>();
export function TeacherClassesStackNavigator() {
  return (
    <ClassesStack.Navigator screenOptions={headerScreenOptions}>
      <ClassesStack.Screen name="ClassesMain" component={TeacherClassesScreen} options={{ title: 'Classes' }} />
    </ClassesStack.Navigator>
  );
}

const GradebookStack = createNativeStackNavigator<TeacherGradebookStackParamList>();
export function TeacherGradebookStackNavigator() {
  return (
    <GradebookStack.Navigator screenOptions={headerScreenOptions}>
      <GradebookStack.Screen name="GradebookPlans" component={GradebookPlansScreen} options={{ title: 'Gradebook' }} />
      <GradebookStack.Screen name="GradeEntry" component={GradeEntryScreen} options={{ title: 'Enter Grades' }} />
    </GradebookStack.Navigator>
  );
}

const AttendanceStack = createNativeStackNavigator<TeacherAttendanceStackParamList>();
export function TeacherAttendanceStackNavigator() {
  return (
    <AttendanceStack.Navigator screenOptions={headerScreenOptions}>
      <AttendanceStack.Screen name="CheckInPicker" component={CheckInPickerScreen} options={{ title: 'Check-in' }} />
      <AttendanceStack.Screen name="RollCall" component={RollCallScreen} options={{ title: 'Roll Call' }} />
    </AttendanceStack.Navigator>
  );
}

const MoreStack = createNativeStackNavigator<TeacherMoreStackParamList>();
export function TeacherMoreStackNavigator() {
  return (
    <MoreStack.Navigator screenOptions={headerScreenOptions}>
      <MoreStack.Screen name="MoreMain" component={MoreScreen} options={{ title: 'More' }} />
    </MoreStack.Navigator>
  );
}
