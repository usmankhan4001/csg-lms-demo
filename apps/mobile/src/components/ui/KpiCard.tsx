import React from 'react';
import { Text, View } from 'react-native';
import type { LucideIcon } from 'lucide-react-native';

/** Small stat tile for dashboard screens (Home/Today). Mirrors the intent of `apps/web/components/widgets/KpiCard.tsx`. */
export function KpiCard({ label, value, icon: Icon, tone = 'neutral' }: { label: string; value: string; icon?: LucideIcon; tone?: 'neutral' | 'positive' | 'caution' | 'critical' }) {
  const toneColor = {
    neutral: 'hsl(215, 28%, 17%)',
    positive: 'hsl(142, 76%, 36%)',
    caution: 'hsl(38, 92%, 50%)',
    critical: 'hsl(346, 84%, 61%)',
  }[tone];

  return (
    <View className="min-w-[140px] flex-1 gap-1.5 rounded-lg border border-line bg-surface p-4 dark:border-line-dark dark:bg-surface-dark">
      <View className="flex-row items-center gap-1.5">
        {Icon ? <Icon size={14} color={toneColor} /> : null}
        <Text className="text-xs text-ink-muted dark:text-ink-muted-dark">{label}</Text>
      </View>
      <Text className="text-xl font-semibold text-ink dark:text-ink-dark" style={{ fontVariant: ['tabular-nums'] }}>
        {value}
      </Text>
    </View>
  );
}
