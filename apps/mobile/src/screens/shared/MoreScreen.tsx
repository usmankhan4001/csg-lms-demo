import React from 'react';
import { Pressable, Text, View } from 'react-native';
import { LogOut, ShieldQuestion } from 'lucide-react-native';
import { Screen } from '@/components/layout/Screen';
import { Card } from '@/components/ui';
import { useAuth } from '@/auth/AuthContext';
import { useSessionSubject } from '@/auth/useSessionSubject';

/** Shared "More" landing for every persona's 5th tab — profile summary + sign out. */
export function MoreScreen({ extra }: { extra?: React.ReactNode }) {
  const { session, logout } = useAuth();
  const { name, email, campusId, orgId } = useSessionSubject();

  return (
    <Screen>
      <Card className="gap-3 p-4">
        <View className="flex-row items-center gap-3">
          <View className="size-11 items-center justify-center rounded-full bg-action">
            <Text className="text-base font-semibold text-white">{(name ?? '?').charAt(0).toUpperCase()}</Text>
          </View>
          <View className="flex-1">
            <Text className="text-sm font-semibold text-ink dark:text-ink-dark">{name ?? 'Unknown user'}</Text>
            <Text className="text-xs text-ink-muted dark:text-ink-muted-dark">{email ?? session?.claims.sub}</Text>
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
          Dev build — signed in with a locally-minted token, not a real Keycloak session.
        </Text>
      </View>
    </Screen>
  );
}
