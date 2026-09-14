/**
 * Learnhouse dash design tokens, as class strings.
 *
 * The school (SMS) modules originally shipped with shadcn defaults
 * (`border border-border bg-card`, `rounded-xl`, shadcn `<Button>`), which
 * read as a different product sitting inside Learnhouse's own dashboard.
 * These constants are the literal classes Learnhouse uses on its own dash
 * pages -- see `app/orgs/[orgslug]/dash/{courses,podcasts,playgrounds}/client.tsx`
 * and `components/Dashboard/Analytics/*` -- so the two surfaces match rather
 * than merely resemble each other.
 *
 * Learnhouse's dash is a LIGHT surface (`#f8f8f8`) with no dark variant, so
 * these deliberately use plain light-ground colours instead of shadcn's
 * theme tokens.
 */

/** Page background + horizontal gutters. Wraps a whole dash route. */
export const LH_PAGE = 'h-full w-full bg-[#f8f8f8] ps-4 pe-4 sm:ps-10 sm:pe-10'

/** Header block sitting at the top of a dash page. */
export const LH_HEADER = 'mb-6 pt-6'

/** Page title. Learnhouse uses 3xl here, not the xl the SMS modules had. */
export const LH_TITLE = 'text-3xl font-bold mb-4 sm:mb-0'

/** White surface used for every card/panel. No border -- `nice-shadow` carries the edge. */
export const LH_CARD = 'bg-white rounded-xl nice-shadow'

/** Primary action. Black pill, scales slightly on hover. */
export const LH_PRIMARY_BUTTON =
  'rounded-lg bg-black hover:scale-105 transition-all duration-100 ease-linear antialiased ' +
  'p-2 px-5 my-auto text-xs font-bold text-white nice-shadow inline-flex space-x-2 items-center ' +
  'disabled:opacity-50 disabled:hover:scale-100 disabled:cursor-not-allowed'

/** Secondary action. White pill on the light ground. */
export const LH_SECONDARY_BUTTON =
  'rounded-lg bg-white hover:scale-105 transition-all duration-100 ease-linear antialiased ' +
  'p-2 px-5 my-auto text-xs font-bold text-gray-700 nice-shadow inline-flex space-x-2 items-center ' +
  'disabled:opacity-50 disabled:hover:scale-100 disabled:cursor-not-allowed'

/** Low-emphasis action, no chrome until hover. */
export const LH_GHOST_BUTTON =
  'inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium ' +
  'text-gray-600 hover:bg-gray-100 transition-colors disabled:opacity-50'

/** Text/select/date input. Borderless; `nice-shadow` provides definition. */
export const LH_INPUT =
  'w-full px-3 py-2.5 bg-white nice-shadow rounded-lg text-sm ' +
  'focus:outline-none focus:ring-2 focus:ring-black focus:ring-offset-2 border-0 ' +
  'disabled:opacity-50 disabled:cursor-not-allowed'

/** Field label above an input. */
export const LH_LABEL = 'text-xs font-semibold text-gray-600'
