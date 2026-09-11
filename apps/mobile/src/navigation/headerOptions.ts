import type { NativeStackNavigationOptions } from '@react-navigation/native-stack';

/**
 * Shared native-stack header styling — DESIGN-SYSTEM.md §2.2: "stack
 * navigation per tab, header 56px with contextual actions".
 *
 * NOTE: this is a static (light-mode) style object, not dark-mode-reactive —
 * making native-stack header options respond live to `useColorScheme()`
 * needs a small per-navigator wrapper hook. Out of scope for this scaffold;
 * screen bodies (built with NativeWind `dark:` classes) already are.
 */
export const headerScreenOptions: NativeStackNavigationOptions = {
  headerStyle: { backgroundColor: 'hsl(0, 0%, 100%)' },
  headerTitleStyle: { color: 'hsl(215, 28%, 17%)', fontSize: 17, fontWeight: '600' },
  headerTintColor: 'hsl(217, 91%, 60%)',
  headerShadowVisible: false,
};
