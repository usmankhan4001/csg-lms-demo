import React from 'react';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { ParentHomeScreen } from '@/screens/parent/HomeScreen';
import { ParentChildrenScreen } from '@/screens/parent/ChildrenScreen';
import { ParentFeesScreen } from '@/screens/parent/FeesScreen';
import { ParentMessagesScreen } from '@/screens/parent/MessagesScreen';
import { MoreScreen } from '@/screens/shared/MoreScreen';
import { headerScreenOptions } from '../headerOptions';

const HomeStack = createNativeStackNavigator();
export function ParentHomeStackNavigator() {
  return (
    <HomeStack.Navigator screenOptions={headerScreenOptions}>
      <HomeStack.Screen name="HomeMain" component={ParentHomeScreen} options={{ title: 'Home' }} />
    </HomeStack.Navigator>
  );
}

const ChildrenStack = createNativeStackNavigator();
export function ParentChildrenStackNavigator() {
  return (
    <ChildrenStack.Navigator screenOptions={headerScreenOptions}>
      <ChildrenStack.Screen name="ChildrenMain" component={ParentChildrenScreen} options={{ title: 'My Children' }} />
    </ChildrenStack.Navigator>
  );
}

const FeesStack = createNativeStackNavigator();
export function ParentFeesStackNavigator() {
  return (
    <FeesStack.Navigator screenOptions={headerScreenOptions}>
      <FeesStack.Screen name="FeesMain" component={ParentFeesScreen} options={{ title: 'Fees' }} />
    </FeesStack.Navigator>
  );
}

const MessagesStack = createNativeStackNavigator();
export function ParentMessagesStackNavigator() {
  return (
    <MessagesStack.Navigator screenOptions={headerScreenOptions}>
      <MessagesStack.Screen name="MessagesMain" component={ParentMessagesScreen} options={{ title: 'Messages' }} />
    </MessagesStack.Navigator>
  );
}

const MoreStack = createNativeStackNavigator();
export function ParentMoreStackNavigator() {
  return (
    <MoreStack.Navigator screenOptions={headerScreenOptions}>
      <MoreStack.Screen name="MoreMain" component={MoreScreen} options={{ title: 'More' }} />
    </MoreStack.Navigator>
  );
}
