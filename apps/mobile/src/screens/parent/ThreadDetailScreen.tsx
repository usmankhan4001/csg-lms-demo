import React, { useState } from 'react';
import { ActivityIndicator, Pressable, Text, TextInput, View } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { Send } from 'lucide-react-native';
import { Screen } from '@/components/layout/Screen';
import { SectionCard } from '@/components/ui';
import { useApiResource } from '@/api/useApiResource';
import { ApiError } from '@/api/client';
import { getThreadMessages, postThreadMessage } from '@/modules/sms/messages/api';
import { useSchoolIdentity } from '@/auth/useSchoolIdentity';
import type { ParentMessagesStackParamList } from '@/navigation/stacks/types';

type Props = NativeStackScreenProps<ParentMessagesStackParamList, 'ThreadDetail'>;

/**
 * One conversation, oldest-first, with a reply box.
 *
 * The server re-checks the access rule on every reply, not just at thread
 * creation, so a reply can start failing mid-year (a teacher stops teaching
 * the child). That 403 is surfaced verbatim rather than swallowed: the
 * parent needs to know the route closed, not watch a message vanish.
 */
export function ParentThreadDetailScreen({ route }: Props) {
  const { threadId } = route.params;
  const { identity } = useSchoolIdentity();
  const [draft, setDraft] = useState('');
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);

  const messages = useApiResource(() => getThreadMessages(threadId), [threadId], {
    cacheKey: `thread-${threadId}`,
  });

  // `lh_user_id` is not exposed on /sms/me; a parent's own id surfaces as
  // student_id/staff_id only for those roles. Rather than guess which side of
  // the conversation a message is on, messages are labelled by whether the
  // sender matches nothing we can confirm -- so we show "You" only when the
  // backend gave us an id to compare against.
  const ownId = identity?.staff_id ?? identity?.student_id ?? null;

  async function handleSend() {
    const body = draft.trim();
    if (!body) return;
    setSending(true);
    setSendError(null);
    try {
      await postThreadMessage(threadId, body);
      setDraft('');
      messages.refetch();
    } catch (err) {
      setSendError(
        err instanceof ApiError
          ? err.kind === 'permission_denied'
            ? 'You can no longer reply to this conversation. The school relationship that allowed it has changed.'
            : err.message
          : 'Could not send. Try again.'
      );
    } finally {
      setSending(false);
    }
  }

  return (
    <Screen>
      <SectionCard
        title={route.params.subject}
        state={messages.status}
        error={messages.error}
        sync={messages.sync}
        onRetry={messages.refetch}
        emptyTitle="No messages yet"
      >
        <View className="gap-2">
          {(messages.data ?? []).map((message) => {
            const isOwn = ownId !== null && message.sender_user_id === ownId;
            return (
              <View
                key={message.id}
                className={`max-w-[85%] gap-1 rounded-lg px-3 py-2.5 ${
                  isOwn ? 'self-end bg-action' : 'self-start border border-line dark:border-line-dark'
                }`}
              >
                <Text className={`text-sm ${isOwn ? 'text-white' : 'text-ink dark:text-ink-dark'}`}>{message.body}</Text>
                <Text className={`text-[11px] ${isOwn ? 'text-white/70' : 'text-ink-muted dark:text-ink-muted-dark'}`}>
                  {new Date(message.created_at).toLocaleString()}
                </Text>
              </View>
            );
          })}
        </View>
      </SectionCard>

      <View className="gap-2">
        <View className="flex-row items-end gap-2">
          <TextInput
            value={draft}
            onChangeText={setDraft}
            placeholder="Write a reply…"
            placeholderTextColor="hsla(215, 28%, 17%, 0.5)"
            multiline
            accessibilityLabel="Reply message"
            className="min-h-12 flex-1 rounded-md border border-line bg-surface px-3 py-2.5 text-sm text-ink dark:border-line-dark dark:bg-surface-dark dark:text-ink-dark"
          />
          <Pressable
            onPress={handleSend}
            disabled={sending || draft.trim().length === 0}
            accessibilityRole="button"
            accessibilityLabel="Send reply"
            className={`size-12 items-center justify-center rounded-md ${
              sending || draft.trim().length === 0 ? 'bg-line dark:bg-line-dark' : 'bg-action active:opacity-80'
            }`}
          >
            {sending ? <ActivityIndicator color="#fff" /> : <Send size={18} color="#fff" />}
          </Pressable>
        </View>
        {sendError ? <Text className="text-xs text-critical dark:text-critical-dark">{sendError}</Text> : null}
      </View>
    </Screen>
  );
}
