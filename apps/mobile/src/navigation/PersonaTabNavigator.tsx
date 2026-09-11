import React from 'react';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { ROLE_NAV_ITEMS } from './nav-config';
import { TAB_SCREEN_REGISTRY } from './screenRegistry';
import type { MobileRole } from '@/auth/types';

const Tab = createBottomTabNavigator();

/**
 * Builds a persona's bottom tab bar entirely from `ROLE_NAV_ITEMS` (one
 * shared per-persona nav config — see `nav-config.ts`'s doc comment) rather
 * than one hand-written navigator per role. DESIGN-SYSTEM.md §2.2: max 5
 * destinations including "More", which `nav-config.ts` already enforces by
 * construction (every persona array is exactly 5 items long).
 */
export function PersonaTabNavigator({ role }: { role: MobileRole }) {
  const items = ROLE_NAV_ITEMS[role];
  const registry = TAB_SCREEN_REGISTRY[role];

  return (
    <Tab.Navigator
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: 'hsl(217, 91%, 60%)',
        tabBarInactiveTintColor: 'hsl(215, 28%, 17%)',
        tabBarStyle: { backgroundColor: 'hsl(0, 0%, 100%)', borderTopColor: 'hsl(214, 32%, 91%)' },
      }}
    >
      {items.map((item) => {
        const ScreenComponent = registry[item.id];
        return (
          <Tab.Screen
            key={item.id}
            name={item.id}
            component={ScreenComponent}
            options={{
              title: item.title,
              tabBarLabel: item.title,
              tabBarIcon: ({ color, size }) => <item.icon color={color} size={size} />,
              tabBarAccessibilityLabel: item.title,
            }}
          />
        );
      })}
    </Tab.Navigator>
  );
}
