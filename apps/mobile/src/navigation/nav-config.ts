import {
  Award,
  BookUser,
  CalendarCheck,
  ClipboardList,
  Clock,
  CreditCard,
  Home,
  LayoutGrid,
  Layers,
  ListChecks,
  MessageSquare,
  MoreHorizontal,
  Sparkles,
  Users,
  Wallet,
} from 'lucide-react-native';
import type { MobileRole } from '@/auth/types';
import type { PersonaNavItem } from './types';

/**
 * One nav IA definition per persona, driving the bottom tab bar built in
 * `PersonaTabNavigator.tsx`. Exactly the "Primary destinations" row from
 * DESIGN-SYSTEM.md §2.3 for each mobile-relevant persona (max 5 destinations
 * including "More", per §2.2). Every `id` here must have a matching entry in
 * `screenRegistry.ts`.
 */
export const ROLE_NAV_ITEMS: Record<MobileRole, PersonaNavItem[]> = {
  STUDENT: [
    { id: 'home', title: 'Home', icon: Home, description: 'Overview, today at a glance' },
    { id: 'timetable', title: 'Timetable', icon: Clock },
    { id: 'assignments', title: 'Assignments', icon: ClipboardList },
    { id: 'ai-coach', title: 'AI Coach', icon: Sparkles },
    { id: 'more', title: 'More', icon: MoreHorizontal },
  ],
  TEACHER: [
    { id: 'today', title: 'Today', icon: LayoutGrid, description: "Today's classes at a glance" },
    { id: 'classes', title: 'Classes', icon: Layers },
    { id: 'gradebook', title: 'Gradebook', icon: Award },
    { id: 'attendance', title: 'Attendance', icon: CalendarCheck },
    { id: 'more', title: 'More', icon: MoreHorizontal },
  ],
  PARENT: [
    { id: 'home', title: 'Home', icon: Home, description: "Children's progress at a glance" },
    { id: 'children', title: 'My Children', icon: Users },
    { id: 'fees', title: 'Fees', icon: CreditCard },
    { id: 'messages', title: 'Messages', icon: MessageSquare },
    { id: 'more', title: 'More', icon: MoreHorizontal },
  ],
  STAFF: [
    { id: 'today', title: 'Today', icon: LayoutGrid, description: "Today's tasks at a glance" },
    { id: 'tasks', title: 'Tasks', icon: ListChecks },
    { id: 'payroll', title: 'Payroll', icon: Wallet },
    { id: 'directory', title: 'Directory', icon: BookUser },
    { id: 'more', title: 'More', icon: MoreHorizontal },
  ],
};
