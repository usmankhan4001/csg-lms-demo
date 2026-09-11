import React, { useState } from 'react';
import { Pressable, Text, View } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { ChevronLeft, ChevronRight } from 'lucide-react-native';
import { Screen } from '@/components/layout/Screen';
import { SectionCard, AttendanceStatusChip } from '@/components/ui';
import { useApiResource } from '@/api/useApiResource';
import { useSessionSubject } from '@/auth/useSessionSubject';
import { getMonthlyStudentAttendance } from '@/modules/sms/attendance/api';
import type { StudentHomeStackParamList } from '@/navigation/stacks/types';

type Props = NativeStackScreenProps<StudentHomeStackParamList, 'AttendanceHistory'>;

const MONTH_NAMES = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];

/** M06 mobile screen inventory: "My History" — cached history, per DESIGN-SYSTEM.md §8 shown via useApiResource's offline cache. */
export function MyHistoryScreen({ navigation }: Props) {
  const { subjectId, sectionId } = useSessionSubject();
  const [cursor, setCursor] = useState(() => {
    const now = new Date();
    return { year: now.getFullYear(), month: now.getMonth() + 1 };
  });

  const monthly = useApiResource(
    () => getMonthlyStudentAttendance(subjectId as number, cursor.year, cursor.month, sectionId ?? undefined),
    [subjectId, sectionId, cursor.year, cursor.month],
    {
      skip: !subjectId,
      cacheKey: subjectId ? `student-attendance-monthly-${subjectId}-${cursor.year}-${cursor.month}` : undefined,
    }
  );

  const shiftMonth = (delta: number) => {
    setCursor((prev) => {
      const date = new Date(prev.year, prev.month - 1 + delta, 1);
      return { year: date.getFullYear(), month: date.getMonth() + 1 };
    });
  };

  return (
    <Screen>
      <View className="flex-row items-center justify-between">
        <Pressable onPress={() => shiftMonth(-1)} accessibilityRole="button" accessibilityLabel="Previous month" className="min-h-12 min-w-12 items-center justify-center">
          <ChevronLeft size={20} color="hsl(215, 28%, 17%)" />
        </Pressable>
        <Text className="text-base font-semibold text-ink dark:text-ink-dark">
          {MONTH_NAMES[cursor.month - 1]} {cursor.year}
        </Text>
        <Pressable onPress={() => shiftMonth(1)} accessibilityRole="button" accessibilityLabel="Next month" className="min-h-12 min-w-12 items-center justify-center">
          <ChevronRight size={20} color="hsl(215, 28%, 17%)" />
        </Pressable>
      </View>

      <SectionCard
        title="Daily records"
        state={monthly.status}
        error={monthly.error}
        sync={monthly.sync}
        onRetry={monthly.refetch}
        emptyTitle="No records for this month"
        emptyDescription="Nothing has been marked yet for this period."
      >
        <View className="gap-2">
          {monthly.data?.daily_records.map((record) => (
            <Pressable
              key={record.id}
              onPress={() => navigation.navigate('AttendanceDetail', { record })}
              accessibilityRole="button"
              accessibilityLabel={`Attendance on ${record.date}: ${record.status}`}
              className="min-h-12 flex-row items-center justify-between rounded-md border border-line px-3 py-2.5 active:opacity-70 dark:border-line-dark"
            >
              <Text className="text-sm text-ink dark:text-ink-dark">{record.date}</Text>
              <AttendanceStatusChip status={record.status} />
            </Pressable>
          ))}
        </View>
      </SectionCard>
    </Screen>
  );
}
