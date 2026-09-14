import React from 'react';
import { ActivityIndicator, Pressable, Text, View } from 'react-native';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { useAuth } from '@/auth/AuthContext';
import { isMobileRole } from '@/auth/types';
import { LoginScreen } from '@/screens/auth/LoginScreen';
import { PersonaTabNavigator } from './PersonaTabNavigator';

const AuthStack = createNativeStackNavigator();

function HydratingSplash() {
  return (
    <View className="flex-1 items-center justify-center bg-canvas dark:bg-canvas-dark">
      <ActivityIndicator size="large" color="hsl(217, 91%, 60%)" />
    </View>
  );
}

/** Shown when the signed-in user's server-resolved role has no mobile IA (SCHOOL_ADMIN is web-only by design; SUPER_ADMIN/PSYCHOLOGIST have none defined). */
function UnsupportedRoleScreen({ role }: { role: string }) {
  const { logout } = useAuth();
  return (
    <View className="flex-1 items-center justify-center gap-3 bg-canvas px-8 dark:bg-canvas-dark">
      <Text className="text-center text-base font-semibold text-ink dark:text-ink-dark">
        {role} doesn't have a mobile experience
      </Text>
      <Text className="text-center text-sm text-ink-muted dark:text-ink-muted-dark">
        Per the design system, {role === 'SCHOOL_ADMIN' ? 'admin screens are web-only' : 'this role has no mobile navigation defined yet'}
        . Use the web app, or sign in with a STUDENT/TEACHER/PARENT/STAFF token.
      </Text>
      <Pressable
        onPress={() => void logout()}
        accessibilityRole="button"
        accessibilityLabel="Sign out"
        className="mt-2 min-h-12 items-center justify-center rounded-md bg-action px-4 py-3 active:opacity-80"
      >
        <Text className="text-sm font-semibold text-white">Sign out</Text>
      </Pressable>
    </View>
  );
}

export function RootNavigator() {
  const { status, session } = useAuth();

  return (
    <NavigationContainer>
      {status === 'hydrating' && <HydratingSplash />}

      {status === 'signedOut' && (
        <AuthStack.Navigator screenOptions={{ headerShown: false }}>
          <AuthStack.Screen name="Login" component={LoginScreen} />
        </AuthStack.Navigator>
      )}

      {status === 'signedIn' && session && (isMobileRole(session.role) ? <PersonaTabNavigator role={session.role} /> : <UnsupportedRoleScreen role={session.role} />)}
    </NavigationContainer>
  );
}
