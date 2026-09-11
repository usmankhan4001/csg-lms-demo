import React from 'react';
import { Pressable, Text, View } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { CalendarCheck, ChevronRight, Clock } from 'lucide-react-native';
import { Screen } from '@/components/layout/Screen';
import { SectionCard, KpiCard } from '@/components/ui';
import { useApiResource } from '@/api/useApiResource';
import { useSessionSubject } from '@/auth/useSessionSubject';
import { getStudentTimetable, slotsForToday } from '@/modules/sms/timetable/api';
import { getMonthlyStudentAttendance } from '@/modules/sms/attendance/api';
import type { StudentHomeStackParamList } from '@/navigation/stacks/types';

type Props = NativeStackScreenProps<StudentHomeStackParamList, 'HomeMain'>;

export function StudentHomeScreen({ navigation }: Props) {
  const { subjectId, sectionId, academicTermId, name } = useSessionSubject();
  const now = new Date();

  const timetable = useApiResource(
    () => getStudentTimetable(subjectId as number, sectionId as number, academicTermId ?? undefined),
    [subjectId, sectionId, academicTermId],
    { skip: !subjectId || !sectionId, cacheKey: subjectId && sectionId ? `student-timetable-${subjectId}-${sectionId}` : undefined }
  );

  const attendance = useApiResource(
    () => getMonthlyStudentAttendance(subjectId as number, now.getFullYear(), now.getMonth() + 1, sectionId ?? undefined),
    [subjectId, sectionId, now.getFullYear(), now.getMonth()],
    {
      skip: !subjectId,
      cacheKey: subjectId ? `student-attendance-monthly-${subjectId}-${now.getFullYear()}-${now.getMonth() + 1}` : undefined,
    }
  );

  const todayCount = timetable.data ? slotsForToday(timetable.data.slots).length : null;
  const attendancePct = attendance.data ? Math.round(attendance.data.stats.attendance_percentage) : null;

  return (
    <Screen>
      <View>
        <Text className="text-xs text-ink-muted dark:text-ink-muted-dark">Welcome back</Text>
        <Text className="text-xl font-semibold text-ink dark:text-ink-dark">{name ?? 'Student'}</Text>
      </View>

      <View className="flex-row gap-3">
        <KpiCard
          label="Classes today"
          value={timetable.status === 'success' && todayCount !== null ? String(todayCount) : '—'}
          icon={Clock}
        />
        <KpiCard
          label="Attendance (month)"
          value={attendance.status === 'success' && attendancePct !== null ? `${attendancePct}%` : '—'}
          icon={CalendarCheck}
          tone={attendancePct !== null && attendancePct < 75 ? 'critical' : 'positive'}
        />
      </View>

      <SectionCard
        title="Attendance"
        description="This month's summary"
        state={attendance.status}
        error={attendance.error}
        sync={attendance.sync}
        onRetry={attendance.refetch}
        emptyTitle="No attendance recorded yet"
        emptyDescription="Once your teacher marks a roll call, it will show up here."
      >
        {attendance.data ? (
          <View className="gap-3">
            <View className="flex-row justify-between">
              <Text className="text-sm text-ink-muted dark:text-ink-muted-dark">Present days</Text>
              <Text className="text-sm font-semibold text-ink dark:text-ink-dark">{attendance.data.stats.present_days}</Text>
            </View>
            <View className="flex-row justify-between">
              <Text className="text-sm text-ink-muted dark:text-ink-muted-dark">Absent days</Text>
              <Text className="text-sm font-semibold text-ink dark:text-ink-dark">{attendance.data.stats.absent_days}</Text>
            </View>
            <Pressable
              onPress={() => navigation.navigate('AttendanceHistory')}
              accessibilityRole="button"
              accessibilityLabel="View full attendance history"
              className="mt-1 min-h-12 flex-row items-center justify-between rounded-md border border-line px-3 py-3 active:opacity-70 dark:border-line-dark"
            >
              <Text className="text-sm font-medium text-action">View full history</Text>
              <ChevronRight size={16} color="hsl(217, 91%, 60%)" />
            </Pressable>
          </View>
        ) : null}
      </SectionCard>
    </Screen>
  );
}
