import type { LucideIcon } from 'lucide-react-native';
import type { MobileRole } from '@/auth/types';

export type { MobileRole };

/**
 * One shared per-persona nav IA definition, conceptually mirroring
 * `apps/web/components/navigation/types.ts`'s `NavItem` / `ROLE_NAV_ITEMS`
 * shape (there `href` points at a Next.js route/anchor; here `id` maps to a
 * registered stack component via `navigation/screenRegistry.ts` — the
 * closest RN equivalent, since bottom tabs don't navigate by URL).
 *
 * Destinations and ordering come from DESIGN-SYSTEM.md §2.3 ("Navigation IA
 * per persona") for the four mobile-relevant personas — SCHOOL_ADMIN is
 * explicitly web-only, SUPER_ADMIN/PSYCHOLOGIST have no mobile IA defined.
 */
export interface PersonaNavItem {
  id: string;
  title: string;
  icon: LucideIcon;
  description?: string;
}
