/**
 * NativeWind (Tailwind-for-RN) config.
 *
 * Colour tokens are ported *verbatim* from the canonical design system so the
 * mobile app and the web app (`apps/web/styles/globals.css` + the shadcn/ui
 * layer) share one visual language rather than inventing new colours here:
 *
 *   - Semantic roles + light values: DESIGN_SYSTEM_CONTRACT.md §1A
 *     (`CSG_Info_Tech_SDM_TechLead_Workspace/.../DESIGN_SYSTEM_CONTRACT.md`)
 *   - Dark-mode counterparts + persona accents: DESIGN-SYSTEM.md §1.1
 *     (`CSG-LMS.wiki/05-UI-UX-Design-System-and-Components/DESIGN-SYSTEM.md`)
 *
 * Usage in components: semantic utility classes only (`bg-canvas`,
 * `text-ink-muted`, `border-line dark:border-line-dark`, ...) — never a raw
 * hex value in feature code, per DESIGN-SYSTEM.md §11 "Do and don't".
 */

/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'media', // follows OS appearance (RN `Appearance`/`useColorScheme`), same default as the web app's `prefers-color-scheme` handling
  content: ['./app/**/*.{js,jsx,ts,tsx}', './src/**/*.{js,jsx,ts,tsx}'],
  presets: [require('nativewind/preset')],
  theme: {
    extend: {
      colors: {
        // --- Brand (DESIGN_SYSTEM_CONTRACT.md §1A) ---
        action: '#2563EB', // brand.primary - hsl(217, 91%, 60%)
        'action-hover': 'hsl(217, 91%, 50%)', // brand.primaryHover
        'action-dark': 'hsl(217, 91%, 68%)', // lighter for contrast on a dark canvas (DESIGN-SYSTEM.md §1.1 rule: invert lightness, keep hue)
        brandSecondary: '#0F172A', // brand.secondary
        brandAccent: '#16A34A', // brand.accent

        // --- Neutral surfaces (light values from the contract; dark
        // counterparts computed per DESIGN-SYSTEM.md §1.1's literal formula) ---
        canvas: 'hsl(210, 40%, 98%)', // neutral.bg
        'canvas-dark': 'hsl(222, 47%, 11%)',
        surface: 'hsl(0, 0%, 100%)', // neutral.card
        'surface-dark': 'hsl(217, 33%, 17%)',
        line: 'hsl(214, 32%, 91%)', // neutral.border
        'line-dark': 'hsl(215, 25%, 27%)',
        ink: 'hsl(215, 28%, 17%)', // neutral.text
        'ink-dark': 'hsl(210, 40%, 98%)',
        // neutral.text @ 65% opacity for secondary/caption text (§1.1)
        'ink-muted': 'hsla(215, 28%, 17%, 0.65)',
        'ink-muted-dark': 'hsla(210, 40%, 98%, 0.65)',

        // --- Status (hue kept identical light/dark per §1.1; dark gains ~10%
        // lightness so contrast holds on a dark canvas) ---
        positive: 'hsl(142, 76%, 36%)',
        'positive-dark': 'hsl(142, 76%, 46%)',
        caution: 'hsl(38, 92%, 50%)',
        'caution-dark': 'hsl(38, 92%, 60%)',
        critical: 'hsl(346, 84%, 61%)',
        'critical-dark': 'hsl(346, 84%, 71%)',
        info: 'hsl(199, 89%, 48%)',
        'info-dark': 'hsl(199, 89%, 58%)',

        // --- Persona accents (identity only — never used for status; §1.1) ---
        persona: {
          superadmin: '#64748B', // slate
          schooladmin: '#2563EB', // royal blue
          teacher: '#7C3AED', // violet
          student: '#059669', // emerald
          parent: '#D97706', // amber
          staff: '#0891B2', // cyan
          psychologist: '#E11D48', // rose
        },
      },
      spacing: {
        // 4px scale per DESIGN-SYSTEM.md §1.2 (Tailwind's default scale
        // already matches 1=4px..16=64px for the values the doc calls out,
        // this just documents that it's deliberate, not incidental)
      },
      borderRadius: {
        sm: '4px',
        md: '8px',
        lg: '12px',
        full: '9999px',
      },
    },
  },
  plugins: [],
};
