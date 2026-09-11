import React from 'react';
import { Text, View } from 'react-native';
import { CalendarClock, CheckCircle2, FileCheck2, XCircle, type LucideIcon } from 'lucide-react-native';

/**
 * Colour + icon + text status pill. DESIGN-SYSTEM.md §1.1: "Never encode
 * meaning in colour alone" (WCAG 1.4.1) — every status pairs a colour with
 * an icon and a label. Mirrors `apps/web/components/widgets/StatusChip.tsx`.
 */

export type ChipTone = 'positive' | 'caution' | 'critical' | 'info' | 'neutral';

const TONE_STYLES: Record<ChipTone, { bg: string; text: string; color: string }> = {
  positive: { bg: 'bg-positive/10', text: 'text-positive dark:text-positive-dark', color: 'hsl(142, 76%, 36%)' },
  caution: { bg: 'bg-caution/10', text: 'text-caution dark:text-caution-dark', color: 'hsl(38, 92%, 50%)' },
  critical: { bg: 'bg-critical/10', text: 'text-critical dark:text-critical-dark', color: 'hsl(346, 84%, 61%)' },
  info: { bg: 'bg-info/10', text: 'text-info dark:text-info-dark', color: 'hsl(199, 89%, 48%)' },
  neutral: { bg: 'bg-line dark:bg-line-dark', text: 'text-ink-muted dark:text-ink-muted-dark', color: 'hsl(215, 28%, 17%)' },
};

export function StatusChip({ label, tone, icon: Icon }: { label: string; tone: ChipTone; icon?: LucideIcon }) {
  const style = TONE_STYLES[tone];
  return (
    <View className={`flex-row items-center gap-1 self-start rounded-full px-2.5 py-1 ${style.bg}`}>
      {Icon ? <Icon size={12} color={style.color} /> : null}
      <Text className={`text-[11px] font-semibold ${style.text}`}>{label}</Text>
    </View>
  );
}

/** Attendance-specific convenience wrapper (`AttendanceStatus` from `modules/sms/attendance/types.ts`). */
export function AttendanceStatusChip({ status }: { status: 'PRESENT' | 'ABSENT' | 'LATE' | 'EXCUSED' }) {
  switch (status) {
    case 'PRESENT':
      return <StatusChip label="Present" tone="positive" icon={CheckCircle2} />;
    case 'ABSENT':
      return <StatusChip label="Absent" tone="critical" icon={XCircle} />;
    case 'LATE':
      return <StatusChip label="Late" tone="caution" icon={CalendarClock} />;
    case 'EXCUSED':
      return <StatusChip label="Excused" tone="info" icon={FileCheck2} />;
  }
}
