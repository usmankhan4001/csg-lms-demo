import React from 'react';
import { Text, View } from 'react-native';
import { Construction, type LucideIcon } from 'lucide-react-native';
import { Screen } from '@/components/layout/Screen';

/**
 * Explicit "not built in this pass" placeholder — used for PARENT/STAFF
 * screens beyond their nav shell, and for STUDENT's Assignments tab (no
 * `apps/web/modules/sms/assignments` module exists yet to port a real
 * contract from; M03 Assignments is a separate, not-yet-built SMS module).
 *
 * Deliberately NOT styled to look "broken" or omitted — it's an honest,
 * labelled stub so this is never mistaken for a finished, working screen.
 */
export function StubScreen({
  title,
  description,
  icon: Icon = Construction,
}: {
  title: string;
  description: string;
  icon?: LucideIcon;
}) {
  return (
    <Screen scroll={false}>
      <View className="flex-1 items-center justify-center gap-3 px-6">
        <View className="size-14 items-center justify-center rounded-full bg-line dark:bg-line-dark">
          <Icon size={28} strokeWidth={1.5} color="hsl(215, 28%, 17%)" />
        </View>
        <Text className="text-center text-base font-semibold text-ink dark:text-ink-dark">{title}</Text>
        <Text className="max-w-xs text-center text-sm text-ink-muted dark:text-ink-muted-dark">{description}</Text>
        <View className="mt-2 rounded-md bg-caution/10 px-3 py-1.5">
          <Text className="text-[11px] font-semibold text-caution dark:text-caution-dark">NOT IMPLEMENTED IN THIS SCAFFOLD</Text>
        </View>
      </View>
    </Screen>
  );
}
