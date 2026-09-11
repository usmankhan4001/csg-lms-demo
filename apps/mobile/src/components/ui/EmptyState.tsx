import React from 'react';
import { Pressable, Text, View } from 'react-native';
import { Inbox, type LucideIcon } from 'lucide-react-native';

/**
 * Shared placeholder for Empty, Error, Offline and Permission-denied states
 * (DESIGN-SYSTEM.md §4) — icon + one-line explanation + primary action,
 * never a blank panel or a raw status code. Mirrors
 * `apps/web/components/widgets/EmptyState.tsx`.
 */

export interface EmptyStateAction {
  label: string;
  onPress: () => void;
}

export type EmptyStateTone = 'neutral' | 'critical' | 'caution';

export interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description?: string;
  action?: EmptyStateAction;
  secondaryAction?: EmptyStateAction;
  tone?: EmptyStateTone;
  /** Small-print RFC 7807-style code for support, shown under the description on Error states. */
  code?: string;
}

const TONE_CLASSES: Record<EmptyStateTone, { bg: string; fg: string }> = {
  neutral: { bg: 'bg-line dark:bg-line-dark', fg: 'text-ink-muted dark:text-ink-muted-dark' },
  critical: { bg: 'bg-critical/10', fg: 'text-critical dark:text-critical-dark' },
  caution: { bg: 'bg-caution/10', fg: 'text-caution dark:text-caution-dark' },
};

export function EmptyState({
  icon: Icon = Inbox,
  title,
  description,
  action,
  secondaryAction,
  tone = 'neutral',
  code,
}: EmptyStateProps) {
  const toneClasses = TONE_CLASSES[tone];

  return (
    <View className="items-center justify-center gap-3 px-6 py-10">
      <View className={`size-12 items-center justify-center rounded-full ${toneClasses.bg}`}>
        <Icon size={24} strokeWidth={1.5} color={iconColorFor(tone)} />
      </View>
      <View className="max-w-sm items-center gap-1">
        <Text className="text-center text-sm font-semibold text-ink dark:text-ink-dark">{title}</Text>
        {description ? (
          <Text className="text-center text-sm text-ink-muted dark:text-ink-muted-dark">{description}</Text>
        ) : null}
      </View>
      {(action || secondaryAction) && (
        <View className="flex-row items-center gap-3">
          {action && (
            <Pressable
              onPress={action.onPress}
              accessibilityRole="button"
              accessibilityLabel={action.label}
              className="min-h-12 items-center justify-center rounded-md bg-action px-4 py-2.5 active:opacity-80"
            >
              <Text className="text-sm font-semibold text-white">{action.label}</Text>
            </Pressable>
          )}
          {secondaryAction && (
            <Pressable
              onPress={secondaryAction.onPress}
              accessibilityRole="button"
              accessibilityLabel={secondaryAction.label}
              className="min-h-12 items-center justify-center rounded-md px-4 py-2.5 active:opacity-60"
            >
              <Text className="text-sm font-semibold text-ink-muted dark:text-ink-muted-dark">{secondaryAction.label}</Text>
            </Pressable>
          )}
        </View>
      )}
      {code ? <Text className="mt-1 text-[11px] text-ink-muted dark:text-ink-muted-dark">Code: {code}</Text> : null}
    </View>
  );
}

// lucide-react-native icons take a raw colour (no CSS variables), so tone -> icon colour is resolved here directly.
function iconColorFor(tone: EmptyStateTone): string {
  if (tone === 'critical') return 'hsl(346, 84%, 61%)';
  if (tone === 'caution') return 'hsl(38, 92%, 50%)';
  return 'hsl(215, 28%, 17%)';
}
