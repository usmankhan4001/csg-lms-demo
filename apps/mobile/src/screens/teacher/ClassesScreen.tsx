import React from 'react';
import { Text, View } from 'react-native';
import { Screen } from '@/components/layout/Screen';
import { SectionCard } from '@/components/ui';
import { useApiResource } from '@/api/useApiResource';
import { useSessionSubject } from '@/auth/useSessionSubject';
import { getTeacherTimetable, slotsByDay } from '@/modules/sms/timetable/api';

const DAY_LABELS: Record<string, string> = {
  MONDAY: 'Monday', TUESDAY: 'Tuesday', WEDNESDAY: 'Wednesday', THURSDAY: 'Thursday',
  FRIDAY: 'Friday', SATURDAY: 'Saturday', SUNDAY: 'Sunday',
};

export function TeacherClassesScreen() {
  const { subjectId, academicTermId } = useSessionSubject();

  const timetable = useApiResource(
    () => getTeacherTimetable(subjectId as number, academicTermId ?? undefined),
    [subjectId, academicTermId],
    { skip: !subjectId, cacheKey: subjectId ? `teacher-timetable-full-${subjectId}` : undefined }
  );

  const grouped = timetable.data ? slotsByDay(timetable.data.slots) : [];

  return (
    <Screen>
      <SectionCard
        title="Weekly load"
        description="Every section and course you teach this term"
        state={timetable.status}
        error={timetable.error}
        sync={timetable.sync}
        onRetry={timetable.refetch}
        emptyTitle="No classes assigned"
        emptyDescription="You have no sections on the timetable for this term yet."
      >
        <View className="gap-4">
          {grouped.map((group) => (
            <View key={group.day} className="gap-2">
              <Text className="text-xs font-semibold uppercase tracking-wide text-ink-muted dark:text-ink-muted-dark">
                {DAY_LABELS[group.day] ?? group.day}
              </Text>
              {group.slots.map((slot) => (
                <View key={slot.id} className="rounded-md border border-line px-3 py-2.5 dark:border-line-dark">
                  <Text className="text-sm font-medium text-ink dark:text-ink-dark">
                    Course #{slot.course_id} · Section #{slot.section_id}
                  </Text>
                  <Text className="text-xs text-ink-muted dark:text-ink-muted-dark">
                    {slot.start_time && slot.end_time ? `${slot.start_time}–${slot.end_time}` : `Period ${slot.period_number ?? slot.period_id}`}
                    {slot.room_number ? ` · Room ${slot.room_number}` : ''}
                  </Text>
                </View>
              ))}
            </View>
          ))}
        </View>
      </SectionCard>
    </Screen>
  );
}
