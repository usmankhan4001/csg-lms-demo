import React from 'react';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { ParentHomeScreen } from '@/screens/parent/HomeScreen';
import { ParentChildrenScreen } from '@/screens/parent/ChildrenScreen';
import { ParentChildDetailScreen } from '@/screens/parent/ChildDetailScreen';
import { ParentFeesScreen } from '@/screens/parent/FeesScreen';
import { ParentMessagesScreen } from '@/screens/parent/MessagesScreen';
import { ParentThreadDetailScreen } from '@/screens/parent/ThreadDetailScreen';
import { MoreScreen } from '@/screens/shared/MoreScreen';
import { headerScreenOptions } from '../headerOptions';
import type {
  ParentChildrenStackParamList,
  ParentFeesStackParamList,
  ParentHomeStackParamList,
  ParentMessagesStackParamList,
  ParentMoreStackParamList,
} from './types';

const HomeStack = createNativeStackNavigator<ParentHomeStackParamList>();
export function ParentHomeStackNavigator() {
  return (
    <HomeStack.Navigator screenOptions={headerScreenOptions}>
      <HomeStack.Screen name="HomeMain" component={ParentHomeScreen} options={{ title: 'Home' }} />
      <HomeStack.Screen
        name="ChildDetail"
        component={ParentChildDetailScreen}
        options={({ route }) => ({ title: route.params.name })}
      />
    </HomeStack.Navigator>
  );
}

const ChildrenStack = createNativeStackNavigator<ParentChildrenStackParamList>();
export function ParentChildrenStackNavigator() {
  return (
    <ChildrenStack.Navigator screenOptions={headerScreenOptions}>
      <ChildrenStack.Screen name="ChildrenMain" component={ParentChildrenScreen} options={{ title: 'My Children' }} />
      <ChildrenStack.Screen
        name="ChildDetail"
        component={ParentChildDetailScreen}
        options={({ route }) => ({ title: route.params.name })}
      />
    </ChildrenStack.Navigator>
  );
}

const FeesStack = createNativeStackNavigator<ParentFeesStackParamList>();
export function ParentFeesStackNavigator() {
  return (
    <FeesStack.Navigator screenOptions={headerScreenOptions}>
      <FeesStack.Screen name="FeesMain" component={ParentFeesScreen} options={{ title: 'Fees' }} />
    </FeesStack.Navigator>
  );
}

const MessagesStack = createNativeStackNavigator<ParentMessagesStackParamList>();
export function ParentMessagesStackNavigator() {
  return (
    <MessagesStack.Navigator screenOptions={headerScreenOptions}>
      <MessagesStack.Screen name="MessagesMain" component={ParentMessagesScreen} options={{ title: 'Messages' }} />
      <MessagesStack.Screen
        name="ThreadDetail"
        component={ParentThreadDetailScreen}
        options={({ route }) => ({ title: route.params.subject })}
      />
    </MessagesStack.Navigator>
  );
}

const MoreStack = createNativeStackNavigator<ParentMoreStackParamList>();
export function ParentMoreStackNavigator() {
  return (
    <MoreStack.Navigator screenOptions={headerScreenOptions}>
      <MoreStack.Screen name="MoreMain" component={MoreScreen} options={{ title: 'More' }} />
    </MoreStack.Navigator>
  );
}
