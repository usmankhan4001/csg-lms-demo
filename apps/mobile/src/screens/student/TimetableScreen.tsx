import React from 'react';
import { Text, View } from 'react-native';
import { Screen } from '@/components/layout/Screen';
import { SectionCard } from '@/components/ui';
import { useApiResource } from '@/api/useApiResource';
import { useSessionSubject } from '@/auth/useSessionSubject';
import { getStudentTimetable, slotsByDay } from '@/modules/sms/timetable/api';

const DAY_LABELS: Record<string, string> = {
  MONDAY: 'Monday',
  TUESDAY: 'Tuesday',
  WEDNESDAY: 'Wednesday',
  THURSDAY: 'Thursday',
  FRIDAY: 'Friday',
  SATURDAY: 'Saturday',
  SUNDAY: 'Sunday',
};

export function StudentTimetableScreen() {
  const { subjectId, sectionId, academicTermId } = useSessionSubject();

  const timetable = useApiResource(
    () => getStudentTimetable(subjectId as number, sectionId as number, academicTermId ?? undefined),
    [subjectId, sectionId, academicTermId],
    { skip: !subjectId || !sectionId, cacheKey: subjectId && sectionId ? `student-timetable-full-${subjectId}-${sectionId}` : undefined }
  );

  const grouped = timetable.data ? slotsByDay(timetable.data.slots) : [];

  return (
    <Screen>
      <SectionCard
        title="Weekly timetable"
        description="Your class schedule for this term"
        state={timetable.status}
        error={timetable.error}
        sync={timetable.sync}
        onRetry={timetable.refetch}
        emptyTitle="No schedule published yet"
        emptyDescription="Your section's timetable hasn't been set up for this term."
      >
        <View className="gap-4">
          {grouped.map((group) => (
            <View key={group.day} className="gap-2">
              <Text className="text-xs font-semibold uppercase tracking-wide text-ink-muted dark:text-ink-muted-dark">
                {DAY_LABELS[group.day] ?? group.day}
              </Text>
              {group.slots.map((slot) => (
                <View
                  key={slot.id}
                  className="flex-row items-center justify-between rounded-md border border-line px-3 py-2.5 dark:border-line-dark"
                >
                  <View>
                    <Text className="text-sm font-medium text-ink dark:text-ink-dark">Course #{slot.course_id}</Text>
                    <Text className="text-xs text-ink-muted dark:text-ink-muted-dark">
                      {slot.room_number ? `Room ${slot.room_number}` : 'Room TBD'}
                    </Text>
                  </View>
                  <Text className="text-xs font-medium text-ink-muted dark:text-ink-muted-dark" style={{ fontVariant: ['tabular-nums'] }}>
                    {slot.start_time && slot.end_time ? `${slot.start_time}–${slot.end_time}` : `Period ${slot.period_number ?? slot.period_id}`}
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
