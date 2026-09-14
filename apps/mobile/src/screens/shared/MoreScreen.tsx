import React from 'react';
import { Pressable, Text, View } from 'react-native';
import { Bell, LogOut, ShieldQuestion } from 'lucide-react-native';
import { Screen } from '@/components/layout/Screen';
import { Card, SectionCard, StatusChip } from '@/components/ui';
import { useAuth } from '@/auth/AuthContext';
import { useSessionSubject } from '@/auth/useSessionSubject';
import { useApiResource } from '@/api/useApiResource';
import { listNotifications } from '@/modules/sms/messages/api';

/** Shared "More" landing for every persona's 5th tab — profile summary + sign out. */
export function MoreScreen({ extra }: { extra?: React.ReactNode }) {
  const { session, logout } = useAuth();
  const { name, email, campusId, orgId } = useSessionSubject();
  const notifications = useApiResource(() => listNotifications(), [], { cacheKey: 'my-notifications' });

  return (
    <Screen>
      <Card className="gap-3 p-4">
        <View className="flex-row items-center gap-3">
          <View className="size-11 items-center justify-center rounded-full bg-action">
            <Text className="text-base font-semibold text-white">{(name ?? '?').charAt(0).toUpperCase()}</Text>
          </View>
          <View className="flex-1">
            <Text className="text-sm font-semibold text-ink dark:text-ink-dark">{name ?? 'Unknown user'}</Text>
            <Text className="text-xs text-ink-muted dark:text-ink-muted-dark">{email ?? session?.identity.email ?? session?.role}</Text>
          </View>
        </View>
        <View className="flex-row gap-2">
          <View className="rounded-full bg-line px-2.5 py-1 dark:bg-line-dark">
            <Text className="text-[11px] font-medium text-ink-muted dark:text-ink-muted-dark">{session?.role}</Text>
          </View>
          {orgId ? (
            <View className="rounded-full bg-line px-2.5 py-1 dark:bg-line-dark">
              <Text className="text-[11px] font-medium text-ink-muted dark:text-ink-muted-dark">Org #{orgId}</Text>
            </View>
          ) : null}
          {campusId ? (
            <View className="rounded-full bg-line px-2.5 py-1 dark:bg-line-dark">
              <Text className="text-[11px] font-medium text-ink-muted dark:text-ink-muted-dark">Campus #{campusId}</Text>
            </View>
          ) : null}
        </View>
      </Card>

      {/* Notifications are per-person and role-agnostic (M35), so they belong
          on every persona's More tab rather than in one persona's tab bar --
          the 5-destination cap in DESIGN-SYSTEM.md §2.2 leaves no room for
          another primary tab. */}
      <SectionCard
        title="Notifications"
        icon={<Bell size={16} color="hsl(215, 28%, 17%)" />}
        state={notifications.status}
        error={notifications.error}
        sync={notifications.sync}
        onRetry={notifications.refetch}
        emptyIcon={Bell}
        emptyTitle="Nothing new"
        emptyDescription="Alerts from the school appear here."
      >
        <View className="gap-2">
          {(notifications.data ?? []).slice(0, 10).map((item) => (
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

      {extra}

      <Pressable
        onPress={() => void logout()}
        accessibilityRole="button"
        accessibilityLabel="Sign out"
        className="min-h-12 flex-row items-center justify-center gap-2 rounded-md border border-critical/30 px-4 py-3 active:opacity-70"
      >
        <LogOut size={16} color="hsl(346, 84%, 61%)" />
        <Text className="text-sm font-semibold text-critical dark:text-critical-dark">Sign out</Text>
      </Pressable>

      <View className="flex-row items-center gap-2 px-1">
        <ShieldQuestion size={14} color="hsla(215, 28%, 17%, 0.65)" />
        <Text className="text-[11px] text-ink-muted dark:text-ink-muted-dark">
          Dev build — this app still signs in with a pasted, locally-minted
          Keycloak-shaped token. The backend no longer accepts one: it resolves
          the caller from a real Learnhouse session (see the note in
          src/auth/token.ts).
        </Text>
      </View>
    </Screen>
  );
}
