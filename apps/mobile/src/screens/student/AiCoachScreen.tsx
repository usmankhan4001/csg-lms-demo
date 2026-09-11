import React, { useEffect, useRef, useState } from 'react';
import { ActivityIndicator, FlatList, KeyboardAvoidingView, Platform, Pressable, Text, TextInput, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Send, Sparkles } from 'lucide-react-native';
import { streamTutorChat } from '@/modules/ai/tutor/api';
import type { ChatMessage } from '@/modules/ai/tutor/types';

function randomId(): string {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

/**
 * "Simple chat screen" against the real `POST /api/v1/ai/tutor/chat`
 * Socratic tutor endpoint (`apps/api/src/routers/ai_tutor.py`) — see
 * `src/modules/ai/tutor/api.ts` for the SSE-over-XHR streaming client and
 * its documented platform caveats.
 */
export function AiCoachScreen() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState('');
  const [sending, setSending] = useState(false);
  const sessionUuid = useRef(randomId());
  const listRef = useRef<FlatList<ChatMessage>>(null);
  const abortRef = useRef<{ abort: () => void } | null>(null);

  useEffect(() => () => abortRef.current?.abort(), []);

  const send = () => {
    const query = draft.trim();
    if (!query || sending) return;

    const userMessage: ChatMessage = { id: randomId(), role: 'user', content: query };
    const assistantId = randomId();
    const assistantMessage: ChatMessage = { id: assistantId, role: 'assistant', content: '', streaming: true };

    setMessages((prev) => [...prev, userMessage, assistantMessage]);
    setDraft('');
    setSending(true);

    abortRef.current = streamTutorChat(
      {
        query,
        session_uuid: sessionUuid.current,
        history: messages.map((m) => ({ role: m.role, content: m.content })),
      },
      {
        onChunk: (chunk) => {
          setMessages((prev) => prev.map((m) => (m.id === assistantId ? { ...m, content: m.content + chunk } : m)));
        },
        onDone: (fullResponse) => {
          setMessages((prev) => prev.map((m) => (m.id === assistantId ? { ...m, content: fullResponse, streaming: false } : m)));
          setSending(false);
        },
        onError: (message) => {
          setMessages((prev) =>
            prev.map((m) => (m.id === assistantId ? { ...m, content: m.content || `⚠️ ${message}`, streaming: false } : m))
          );
          setSending(false);
        },
      }
    );
  };

  return (
    <SafeAreaView edges={['bottom', 'left', 'right']} className="flex-1 bg-canvas dark:bg-canvas-dark">
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={{ flex: 1 }}>
        {messages.length === 0 ? (
          <View className="flex-1 items-center justify-center gap-3 px-8">
            <View className="size-14 items-center justify-center rounded-full bg-action/10">
              <Sparkles size={28} color="hsl(217, 91%, 60%)" />
            </View>
            <Text className="text-center text-base font-semibold text-ink dark:text-ink-dark">AI Coach</Text>
            <Text className="text-center text-sm text-ink-muted dark:text-ink-muted-dark">
              Ask a question about your coursework. Your coach asks guiding questions rather than giving the
              answer outright — that's by design (Socratic tutoring).
            </Text>
          </View>
        ) : (
          <FlatList
            ref={listRef}
            data={messages}
            keyExtractor={(m) => m.id}
            contentContainerStyle={{ padding: 16, gap: 10 }}
            onContentSizeChange={() => listRef.current?.scrollToEnd({ animated: true })}
            renderItem={({ item }) => (
              <View
                className={`max-w-[85%] rounded-lg px-3.5 py-2.5 ${
                  item.role === 'user' ? 'self-end bg-action' : 'self-start bg-surface dark:bg-surface-dark border border-line dark:border-line-dark'
                }`}
              >
                <Text className={`text-sm ${item.role === 'user' ? 'text-white' : 'text-ink dark:text-ink-dark'}`}>
                  {item.content || (item.streaming ? '…' : '')}
                </Text>
              </View>
            )}
          />
        )}

        <View className="flex-row items-end gap-2 border-t border-line p-3 dark:border-line-dark">
          <TextInput
            value={draft}
            onChangeText={setDraft}
            placeholder="Ask your AI coach…"
            placeholderTextColor="hsla(215, 28%, 17%, 0.4)"
            multiline
            className="max-h-28 min-h-12 flex-1 rounded-md border border-line px-3 py-2.5 text-sm text-ink dark:border-line-dark dark:text-ink-dark"
          />
          <Pressable
            onPress={send}
            disabled={sending || !draft.trim()}
            accessibilityRole="button"
            accessibilityLabel="Send message"
            className="size-12 items-center justify-center rounded-full bg-action active:opacity-80 disabled:opacity-40"
          >
            {sending ? <ActivityIndicator color="white" /> : <Send size={18} color="white" />}
          </Pressable>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
