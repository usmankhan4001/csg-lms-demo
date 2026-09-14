import React, { useState } from 'react';
import { Pressable, RefreshControl, Text, View } from 'react-native';
import { BookUser } from 'lucide-react-native';
import { Screen } from '@/components/layout/Screen';
import { SectionCard } from '@/components/ui';
import { useApiResource } from '@/api/useApiResource';
import { listSchoolPeople } from '@/modules/sms/identity/api';
import type { SchoolRoleName } from '@/modules/sms/identity/types';

/**
 * Staff directory from `GET /sms/identity/people?role=` (sms_identity.py:369),
 * which joins `User` so rows carry real names instead of "User #42", and is
 * org-scoped server-side so one tenant never sees another's people.
 */
const DIRECTORY_ROLES: { role: SchoolRoleName; label: string }[] = [
  { role: 'TEACHER', label: 'Teachers' },
  { role: 'STAFF', label: 'Staff' },
  { role: 'SCHOOL_ADMIN', label: 'Admins' },
];

export function StaffDirectoryScreen() {
  const [role, setRole] = useState<SchoolRoleName>('TEACHER');
  const people = useApiResource(() => listSchoolPeople(role), [role], { cacheKey: `directory-${role}` });

  return (
    <Screen refreshControl={<RefreshControl refreshing={people.status === 'loading'} onRefresh={people.refetch} />}>
      <View className="flex-row flex-wrap gap-2">
        {DIRECTORY_ROLES.map((option) => {
          const active = option.role === role;
          return (
            <Pressable
              key={option.role}
              onPress={() => setRole(option.role)}
              accessibilityRole="button"
              accessibilityState={{ selected: active }}
              accessibilityLabel={`Show ${option.label}`}
              className={`min-h-12 justify-center rounded-full px-4 py-2 ${active ? 'bg-action' : 'border border-line dark:border-line-dark'}`}
            >
              <Text className={`text-sm font-semibold ${active ? 'text-white' : 'text-ink-muted dark:text-ink-muted-dark'}`}>
                {option.label}
              </Text>
            </Pressable>
          );
        })}
      </View>

      <SectionCard
        title="Directory"
        icon={<BookUser size={16} color="hsl(215, 28%, 17%)" />}
        state={people.status}
        error={people.error}
        sync={people.sync}
        onRetry={people.refetch}
        requiredRoleLabel="STAFF"
        emptyIcon={BookUser}
        emptyTitle="Nobody holds this role yet"
        emptyDescription="People appear here once the school assigns them this role."
      >
        <View className="gap-2">
          {(people.data ?? []).map((person) => (
            <View key={person.user_id} className="gap-0.5 rounded-md border border-line p-3 dark:border-line-dark">
              <Text className="text-sm font-semibold text-ink dark:text-ink-dark">
                {person.name?.trim() || `User #${person.user_id}`}
              </Text>
              {person.email ? (
                <Text className="text-xs text-ink-muted dark:text-ink-muted-dark">{person.email}</Text>
              ) : null}
            </View>
          ))}
        </View>
      </SectionCard>
    </Screen>
  );
}
