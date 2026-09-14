import React from 'react';
import { Pressable, RefreshControl, Text, View } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { ChevronRight, Users } from 'lucide-react-native';
import { Screen } from '@/components/layout/Screen';
import { SectionCard, StatusChip } from '@/components/ui';
import { useChildren, childLabel } from '@/modules/sms/identity/useChildren';
import type { ParentChildrenStackParamList } from '@/navigation/stacks/types';

type Props = NativeStackScreenProps<ParentChildrenStackParamList, 'ChildrenMain'>;

/**
 * The guardian's children, from the server-resolved `StudentGuardian` link
 * (GET /sms/me -> children_ids), never from a client-supplied id.
 */
export function ParentChildrenScreen({ navigation }: Props) {
  const { children, status, error, sync, refetch } = useChildren();

  return (
    <Screen refreshControl={<RefreshControl refreshing={status === 'loading'} onRefresh={refetch} />}>
      <SectionCard
        title="My children"
        description="Tap a child to see their attendance and fees."
        icon={<Users size={16} color="hsl(215, 28%, 17%)" />}
        state={status}
        error={error}
        sync={sync}
        onRetry={refetch}
        emptyIcon={Users}
        emptyTitle="No children linked to your account"
        emptyDescription="The school links a guardian to each child. Ask the school office to connect your account if this looks wrong."
      >
        <View className="gap-2">
          {children.map((entry) => (
            <Pressable
              key={entry.studentId}
              onPress={() => navigation.navigate('ChildDetail', { studentId: entry.studentId, name: childLabel(entry) })}
              accessibilityRole="button"
              accessibilityLabel={`Open ${childLabel(entry)}`}
              className="min-h-12 flex-row items-center justify-between gap-3 rounded-md border border-line px-3 py-3 active:opacity-70 dark:border-line-dark"
            >
              <View className="min-w-0 flex-1 gap-1">
                <Text className="text-sm font-semibold text-ink dark:text-ink-dark">{childLabel(entry)}</Text>
                {entry.context === null ? (
                  <StatusChip label="Details unavailable" tone="caution" />
                ) : entry.context.section_id ? (
                  <Text className="text-xs text-ink-muted dark:text-ink-muted-dark">Section #{entry.context.section_id}</Text>
                ) : (
                  <Text className="text-xs text-ink-muted dark:text-ink-muted-dark">Not enrolled in an active section</Text>
                )}
              </View>
              <ChevronRight size={18} color="hsla(215, 28%, 17%, 0.65)" />
            </Pressable>
          ))}
        </View>
      </SectionCard>
    </Screen>
  );
}
