import React from 'react';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { StudentHomeScreen } from '@/screens/student/HomeScreen';
import { StudentTimetableScreen } from '@/screens/student/TimetableScreen';
import { StudentAssignmentsScreen } from '@/screens/student/AssignmentsScreen';
import { AiCoachScreen } from '@/screens/student/AiCoachScreen';
import { MyHistoryScreen } from '@/screens/student/attendance/MyHistoryScreen';
import { StatusDetailScreen } from '@/screens/student/attendance/StatusDetailScreen';
import { MoreScreen } from '@/screens/shared/MoreScreen';
import { headerScreenOptions } from '../headerOptions';
import type {
  StudentAiCoachStackParamList,
  StudentAssignmentsStackParamList,
  StudentHomeStackParamList,
  StudentMoreStackParamList,
  StudentTimetableStackParamList,
} from './types';

const HomeStack = createNativeStackNavigator<StudentHomeStackParamList>();
export function StudentHomeStackNavigator() {
  return (
    <HomeStack.Navigator screenOptions={headerScreenOptions}>
      <HomeStack.Screen name="HomeMain" component={StudentHomeScreen} options={{ title: 'Home' }} />
      <HomeStack.Screen name="AttendanceHistory" component={MyHistoryScreen} options={{ title: 'My Attendance' }} />
      <HomeStack.Screen name="AttendanceDetail" component={StatusDetailScreen} options={{ title: 'Attendance Detail' }} />
    </HomeStack.Navigator>
  );
}

const TimetableStack = createNativeStackNavigator<StudentTimetableStackParamList>();
export function StudentTimetableStackNavigator() {
  return (
    <TimetableStack.Navigator screenOptions={headerScreenOptions}>
      <TimetableStack.Screen name="TimetableMain" component={StudentTimetableScreen} options={{ title: 'Timetable' }} />
    </TimetableStack.Navigator>
  );
}

const AssignmentsStack = createNativeStackNavigator<StudentAssignmentsStackParamList>();
export function StudentAssignmentsStackNavigator() {
  return (
    <AssignmentsStack.Navigator screenOptions={headerScreenOptions}>
      <AssignmentsStack.Screen name="AssignmentsMain" component={StudentAssignmentsScreen} options={{ title: 'Assignments' }} />
    </AssignmentsStack.Navigator>
  );
}

const AiCoachStack = createNativeStackNavigator<StudentAiCoachStackParamList>();
export function StudentAiCoachStackNavigator() {
  return (
    <AiCoachStack.Navigator screenOptions={headerScreenOptions}>
      <AiCoachStack.Screen name="AiCoachMain" component={AiCoachScreen} options={{ title: 'AI Coach' }} />
    </AiCoachStack.Navigator>
  );
}

const MoreStack = createNativeStackNavigator<StudentMoreStackParamList>();
export function StudentMoreStackNavigator() {
  return (
    <MoreStack.Navigator screenOptions={headerScreenOptions}>
      <MoreStack.Screen name="MoreMain" component={MoreScreen} options={{ title: 'More' }} />
    </MoreStack.Navigator>
  );
}
