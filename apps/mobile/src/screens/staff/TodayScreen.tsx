import React from 'react';
import { RefreshControl, Text, View } from 'react-native';
import { CalendarClock, MapPin, UserX } from 'lucide-react-native';
import { Screen } from '@/components/layout/Screen';
import { KpiCard, SectionCard } from '@/components/ui';
import { useApiResource } from '@/api/useApiResource';
import { useSessionSubject } from '@/auth/useSessionSubject';
import { getTeacherTimetable, slotsForToday } from '@/modules/sms/timetable/api';
import type { TimetableSlotDetail } from '@/modules/sms/timetable/types';

/**
 * The staff member's own day, from the real timetable.
 *
 * `slotsForToday` (timetable/api.ts) does the day filtering that the web
 * module already uses, so "today" means the same thing on both clients
 * rather than being re-derived here.
 *
 * Course and section are shown by id where no name is available. That is
 * deliberate: this screen does not have a course/section name lookup, and
 * inventing a label would be worse than showing the real identifier.
 */

function timeRange(slot: TimetableSlotDetail): string {
  if (slot.start_time && slot.end_time) return `${slot.start_time} – ${slot.end_time}`;
  if (slot.start_time) return slot.start_time;
  return slot.period_number ? `Period ${slot.period_number}` : 'Time not set';
}

function SlotRow({ slot }: { slot: TimetableSlotDetail }) {
  return (
    <View className="flex-row items-center gap-3 border-t border-line py-3 dark:border-line-dark">
      <View className="w-24">
        <Text className="text-sm font-semibold text-ink dark:text-ink-dark">{timeRange(slot)}</Text>
        {slot.period_number ? (
          <Text className="text-xs text-ink-muted dark:text-ink-muted-dark">Period {slot.period_number}</Text>
        ) : null}
      </View>
      <View className="flex-1">
        <Text className="text-sm font-medium text-ink dark:text-ink-dark">Course #{slot.course_id}</Text>
        <View className="flex-row items-center gap-1">
          <Text className="text-xs text-ink-muted dark:text-ink-muted-dark">Section #{slot.section_id}</Text>
          {slot.room_number ? (
            <>
              <MapPin size={11} color="hsl(215, 16%, 47%)" />
              <Text className="text-xs text-ink-muted dark:text-ink-muted-dark">{slot.room_number}</Text>
            </>
          ) : null}
        </View>
      </View>
    </View>
  );
}

export function StaffTodayScreen() {
  const { subjectId, academicTermId } = useSessionSubject();

  const timetable = useApiResource(
    () => getTeacherTimetable(subjectId as number, academicTermId ?? undefined),
    [subjectId, academicTermId],
    {
      skip: subjectId === null,
      cacheKey: subjectId ? `staff-today-${subjectId}` : undefined,
      isEmpty: (d) => (d?.slots?.length ?? 0) === 0,
    }
  );

  if (subjectId === null) {
    return (
      <Screen>
        <SectionCard
          title="Today"
          icon={<CalendarClock size={16} color="hsl(215, 28%, 17%)" />}
          state="empty"
          emptyIcon={UserX}
          emptyTitle="No staff record linked to your account"
          emptyDescription="Your timetable is built against a staff profile. Ask the school office to link yours."
        />
      </Screen>
    );
  }

  const allSlots = timetable.data?.slots ?? [];
  const today = slotsForToday(allSlots);

  return (
    <Screen
      refreshControl={<RefreshControl refreshing={timetable.status === 'loading'} onRefresh={timetable.refetch} />}
    >
      <SectionCard
        title="At a glance"
        icon={<CalendarClock size={16} color="hsl(215, 28%, 17%)" />}
        state={timetable.status === 'empty' ? 'success' : timetable.status}
        error={timetable.error}
        sync={timetable.sync}
        onRetry={timetable.refetch}
      >
        <View className="flex-row flex-wrap gap-2">
          <KpiCard label="Classes today" value={String(today.length)} />
          <KpiCard label="Scheduled this week" value={String(allSlots.length)} />
        </View>
      </SectionCard>

      <SectionCard
        title="Today's classes"
        icon={<CalendarClock size={16} color="hsl(215, 28%, 17%)" />}
        state={timetable.status === 'success' && today.length === 0 ? 'empty' : timetable.status}
        error={timetable.error}
        onRetry={timetable.refetch}
        emptyTitle="Nothing scheduled today"
        emptyDescription={
          allSlots.length > 0
            ? 'You have classes on other days this week.'
            : 'No timetable has been published for you yet.'
        }
      >
        <View>
          {today.map((slot) => (
            <SlotRow key={slot.id} slot={slot} />
          ))}
        </View>
      </SectionCard>
    </Screen>
  );
}
