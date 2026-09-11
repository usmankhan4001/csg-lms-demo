import React from 'react';
import { Text, View } from 'react-native';
import { Screen } from '@/components/layout/Screen';
import { SectionCard } from '@/components/ui';
import { useApiResource } from '@/api/useApiResource';
import { useSessionSubject } from '@/auth/useSessionSubject';
import { getTeacherTimetable, slotsForToday } from '@/modules/sms/timetable/api';

export function TeacherTodayScreen() {
  const { subjectId, academicTermId, name } = useSessionSubject();

  const timetable = useApiResource(
    () => getTeacherTimetable(subjectId as number, academicTermId ?? undefined),
    [subjectId, academicTermId],
    { skip: !subjectId, cacheKey: subjectId ? `teacher-timetable-${subjectId}` : undefined }
  );

  const today = timetable.data ? slotsForToday(timetable.data.slots) : [];

  return (
    <Screen>
      <View>
        <Text className="text-xs text-ink-muted dark:text-ink-muted-dark">
          {new Date().toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' })}
        </Text>
        <Text className="text-xl font-semibold text-ink dark:text-ink-dark">{name ?? 'Teacher'}</Text>
      </View>

      <SectionCard
        title="Today's classes"
        state={timetable.status}
        error={timetable.error}
        sync={timetable.sync}
        onRetry={timetable.refetch}
        emptyTitle="No classes scheduled today"
        emptyDescription="Enjoy the free period — nothing on your timetable for today."
      >
        <View className="gap-2">
          {today.map((slot) => (
            <View key={slot.id} className="flex-row items-center justify-between rounded-md border border-line px-3 py-2.5 dark:border-line-dark">
              <View>
                <Text className="text-sm font-medium text-ink dark:text-ink-dark">Course #{slot.course_id} · Section #{slot.section_id}</Text>
                <Text className="text-xs text-ink-muted dark:text-ink-muted-dark">{slot.room_number ? `Room ${slot.room_number}` : 'Room TBD'}</Text>
              </View>
              <Text className="text-xs font-medium text-ink-muted dark:text-ink-muted-dark" style={{ fontVariant: ['tabular-nums'] }}>
                {slot.start_time && slot.end_time ? `${slot.start_time}–${slot.end_time}` : `Period ${slot.period_number ?? slot.period_id}`}
              </Text>
            </View>
          ))}
        </View>
      </SectionCard>
    </Screen>
  );
}
