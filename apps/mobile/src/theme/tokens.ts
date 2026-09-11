/**
 * JS-side colour constants for places that can't take a NativeWind
 * className (an icon's `color` prop, `ActivityIndicator`, chart libraries,
 * `StatusBar`). Keep these numerically identical to `tailwind.config.js` —
 * that file is the source of truth; this is a mirror for non-style-prop use.
 *
 * See `tailwind.config.js` for the provenance of every value (ported from
 * DESIGN_SYSTEM_CONTRACT.md §1A and DESIGN-SYSTEM.md §1.1/§2.3).
 */

export const colors = {
  light: {
    action: 'hsl(217, 91%, 60%)',
    actionHover: 'hsl(217, 91%, 50%)',
    canvas: 'hsl(210, 40%, 98%)',
    surface: 'hsl(0, 0%, 100%)',
    line: 'hsl(214, 32%, 91%)',
    ink: 'hsl(215, 28%, 17%)',
    inkMuted: 'hsla(215, 28%, 17%, 0.65)',
    positive: 'hsl(142, 76%, 36%)',
    caution: 'hsl(38, 92%, 50%)',
    critical: 'hsl(346, 84%, 61%)',
    info: 'hsl(199, 89%, 48%)',
  },
  dark: {
    action: 'hsl(217, 91%, 68%)',
    actionHover: 'hsl(217, 91%, 58%)',
    canvas: 'hsl(222, 47%, 11%)',
    surface: 'hsl(217, 33%, 17%)',
    line: 'hsl(215, 25%, 27%)',
    ink: 'hsl(210, 40%, 98%)',
    inkMuted: 'hsla(210, 40%, 98%, 0.65)',
    positive: 'hsl(142, 76%, 46%)',
    caution: 'hsl(38, 92%, 60%)',
    critical: 'hsl(346, 84%, 71%)',
    info: 'hsl(199, 89%, 58%)',
  },
} as const;

/** Persona accent colours — identity affordances only, never status (§1.1). */
export const personaAccent = {
  SUPER_ADMIN: '#64748B',
  SCHOOL_ADMIN: '#2563EB',
  TEACHER: '#7C3AED',
  STUDENT: '#059669',
  PARENT: '#D97706',
  STAFF: '#0891B2',
  PSYCHOLOGIST: '#E11D48',
} as const;

export type ColorScheme = 'light' | 'dark';
