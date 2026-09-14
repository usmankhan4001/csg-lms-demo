import React from 'react';
import { Pressable, RefreshControl, Text, View } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { Bell, ChevronRight, Users } from 'lucide-react-native';
import { Screen } from '@/components/layout/Screen';
import { SectionCard, StatusChip } from '@/components/ui';
import { useApiResource } from '@/api/useApiResource';
import { listNotifications } from '@/modules/sms/messages/api';
import { getStudentFeeLedger } from '@/modules/sms/fees/api';
import { formatMoney } from '@/modules/sms/fees/format';
import { useChildren, childLabel, type ChildEntry } from '@/modules/sms/identity/useChildren';
import type { ParentHomeStackParamList } from '@/navigation/stacks/types';

type Props = NativeStackScreenProps<ParentHomeStackParamList, 'HomeMain'>;

/** The guardian's children at a glance, plus anything the school has sent. */
export function ParentHomeScreen({ navigation }: Props) {
  const { children, status, error, sync, refetch } = useChildren();
  const notifications = useApiResource(() => listNotifications(), [], { cacheKey: 'parent-notifications' });

  return (
    <Screen refreshControl={<RefreshControl refreshing={status === 'loading'} onRefresh={refetch} />}>
      <SectionCard
        title="My children"
        icon={<Users size={16} color="hsl(215, 28%, 17%)" />}
        state={status}
        error={error}
        sync={sync}
        onRetry={refetch}
        emptyIcon={Users}
        emptyTitle="No children linked to your account"
        emptyDescription="Ask the school office to connect your account to your child's record."
      >
        <View className="gap-2">
          {children.map((entry) => (
            <ChildRow
              key={entry.studentId}
              entry={entry}
              onPress={() => navigation.navigate('ChildDetail', { studentId: entry.studentId, name: childLabel(entry) })}
            />
          ))}
        </View>
      </SectionCard>

      <SectionCard
        title="Recent notifications"
        icon={<Bell size={16} color="hsl(215, 28%, 17%)" />}
        state={notifications.status}
        error={notifications.error}
        sync={notifications.sync}
        onRetry={notifications.refetch}
        emptyIcon={Bell}
        emptyTitle="Nothing new"
        emptyDescription="Alerts from the school will appear here."
      >
        <View className="gap-2">
          {(notifications.data ?? []).slice(0, 8).map((item) => (
            <View key={item.id} className="gap-1 rounded-md border border-line p-3 dark:border-line-dark">
              <View className="flex-row items-start justify-between gap-2">
                <Text className="min-w-0 flex-1 text-sm font-semibold text-ink dark:text-ink-dark">{item.title}</Text>
                {!item.is_read ? <StatusChip label="New" tone="info" /> : null}
              </View>
              <Text className="text-xs text-ink-muted dark:text-ink-muted-dark">{item.body}</Text>
            </View>
          ))}
        </View>
      </SectionCard>
    </Screen>
  );
}

/**
 * One child's headline figure. The fee ledger is fetched per child; a child
 * whose ledger fails or has never been invoiced shows no amount at all
 * rather than a reassuring Rs. 0.00 -- "nothing owed" and "we could not read
 * your balance" must not look identical.
 */
function ChildRow({ entry, onPress }: { entry: ChildEntry; onPress: () => void }) {
  const ledger = useApiResource(() => getStudentFeeLedger(entry.studentId), [entry.studentId], {
    cacheKey: `parent-home-ledger-${entry.studentId}`,
    isEmpty: () => false,
  });

  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={`Open ${childLabel(entry)}`}
      className="min-h-12 flex-row items-center justify-between gap-3 rounded-md border border-line px-3 py-3 active:opacity-70 dark:border-line-dark"
    >
      <View className="min-w-0 flex-1 gap-1">
        <Text className="text-sm font-semibold text-ink dark:text-ink-dark">{childLabel(entry)}</Text>
        {ledger.status === 'success' && ledger.data ? (
          ledger.data.total_outstanding > 0 ? (
            <Text className="text-xs text-critical dark:text-critical-dark">
              {formatMoney(ledger.data.total_outstanding)} outstanding
            </Text>
          ) : (
            <Text className="text-xs text-positive dark:text-positive-dark">Fees up to date</Text>
          )
        ) : ledger.status === 'loading' ? (
          <Text className="text-xs text-ink-muted dark:text-ink-muted-dark">Loading fees…</Text>
        ) : (
          <Text className="text-xs text-ink-muted dark:text-ink-muted-dark">Fee balance unavailable</Text>
        )}
      </View>
      <ChevronRight size={18} color="hsla(215, 28%, 17%, 0.65)" />
    </Pressable>
  );
}
