import React from 'react';
import { Pressable, RefreshControl, Text, View } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { ChevronRight, MessageSquare } from 'lucide-react-native';
import { Screen } from '@/components/layout/Screen';
import { SectionCard, StatusChip } from '@/components/ui';
import { useApiResource } from '@/api/useApiResource';
import { listMessageThreads } from '@/modules/sms/messages/api';
import type { ParentMessagesStackParamList } from '@/navigation/stacks/types';

type Props = NativeStackScreenProps<ParentMessagesStackParamList, 'MessagesMain'>;

/**
 * Conversations the school has opened with this family.
 *
 * No "new message" button, deliberately. Starting a thread is refused unless
 * a school relationship permits the pair (notifications.py:218), and the
 * only recipient-picker endpoint, /sms/identity/people, rejects PARENT
 * callers outright -- so a compose button here would be a button that 403s.
 * Replying inside a thread staff opened is permitted and is wired up.
 */
export function ParentMessagesScreen({ navigation }: Props) {
  const threads = useApiResource(() => listMessageThreads(), [], { cacheKey: 'parent-threads' });

  return (
    <Screen refreshControl={<RefreshControl refreshing={threads.status === 'loading'} onRefresh={threads.refetch} />}>
      <SectionCard
        title="Conversations"
        icon={<MessageSquare size={16} color="hsl(215, 28%, 17%)" />}
        state={threads.status}
        error={threads.error}
        sync={threads.sync}
        onRetry={threads.refetch}
        emptyIcon={MessageSquare}
        emptyTitle="No conversations yet"
        emptyDescription="Teachers and the school office can start a conversation with you here."
      >
        <View className="gap-2">
          {(threads.data ?? []).map((thread) => (
            <Pressable
              key={thread.id}
              onPress={() => navigation.navigate('ThreadDetail', { threadId: thread.id, subject: thread.subject })}
              accessibilityRole="button"
              accessibilityLabel={`Open conversation: ${thread.subject}`}
              className="min-h-12 flex-row items-center justify-between gap-3 rounded-md border border-line px-3 py-3 active:opacity-70 dark:border-line-dark"
            >
              <View className="min-w-0 flex-1 gap-1">
                <Text className="text-sm font-semibold text-ink dark:text-ink-dark" numberOfLines={1}>
                  {thread.subject}
                </Text>
                <Text className="text-xs text-ink-muted dark:text-ink-muted-dark">
                  {thread.message_count} message{thread.message_count === 1 ? '' : 's'}
                </Text>
              </View>
              {thread.unread_count > 0 ? <StatusChip label={`${thread.unread_count} new`} tone="info" /> : null}
              <ChevronRight size={18} color="hsla(215, 28%, 17%, 0.65)" />
            </Pressable>
          ))}
        </View>
      </SectionCard>
    </Screen>
  );
}
