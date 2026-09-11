import React from 'react';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { StaffTodayScreen } from '@/screens/staff/TodayScreen';
import { StaffTasksScreen } from '@/screens/staff/TasksScreen';
import { StaffPayrollScreen } from '@/screens/staff/PayrollScreen';
import { StaffDirectoryScreen } from '@/screens/staff/DirectoryScreen';
import { MoreScreen } from '@/screens/shared/MoreScreen';
import { headerScreenOptions } from '../headerOptions';

const TodayStack = createNativeStackNavigator();
export function StaffTodayStackNavigator() {
  return (
    <TodayStack.Navigator screenOptions={headerScreenOptions}>
      <TodayStack.Screen name="TodayMain" component={StaffTodayScreen} options={{ title: 'Today' }} />
    </TodayStack.Navigator>
  );
}

const TasksStack = createNativeStackNavigator();
export function StaffTasksStackNavigator() {
  return (
    <TasksStack.Navigator screenOptions={headerScreenOptions}>
      <TasksStack.Screen name="TasksMain" component={StaffTasksScreen} options={{ title: 'Tasks' }} />
    </TasksStack.Navigator>
  );
}

const PayrollStack = createNativeStackNavigator();
export function StaffPayrollStackNavigator() {
  return (
    <PayrollStack.Navigator screenOptions={headerScreenOptions}>
      <PayrollStack.Screen name="PayrollMain" component={StaffPayrollScreen} options={{ title: 'Payroll' }} />
    </PayrollStack.Navigator>
  );
}

const DirectoryStack = createNativeStackNavigator();
export function StaffDirectoryStackNavigator() {
  return (
    <DirectoryStack.Navigator screenOptions={headerScreenOptions}>
      <DirectoryStack.Screen name="DirectoryMain" component={StaffDirectoryScreen} options={{ title: 'Directory' }} />
    </DirectoryStack.Navigator>
  );
}

const MoreStack = createNativeStackNavigator();
export function StaffMoreStackNavigator() {
  return (
    <MoreStack.Navigator screenOptions={headerScreenOptions}>
      <MoreStack.Screen name="MoreMain" component={MoreScreen} options={{ title: 'More' }} />
    </MoreStack.Navigator>
  );
}
