import React, { useMemo, useState } from 'react';
import { ActivityIndicator, Pressable, Text, View } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { CircleCheck } from 'lucide-react-native';
import { Screen } from '@/components/layout/Screen';
import { SectionCard } from '@/components/ui';
import { useApiResource } from '@/api/useApiResource';
import { useSessionSubject } from '@/auth/useSessionSubject';
import { listSectionEnrollments } from '@/modules/sms/campus/api';
import { submitRollCall } from '@/modules/sms/attendance/api';
import { ApiError } from '@/api/client';
import type { AttendanceStatus } from '@/modules/sms/attendance/types';
import type { TeacherAttendanceStackParamList } from '@/navigation/stacks/types';

type Props = NativeStackScreenProps<TeacherAttendanceStackParamList, 'RollCall'>;

const STATUS_OPTIONS: { value: AttendanceStatus; label: string }[] = [
  { value: 'PRESENT', label: 'P' },
  { value: 'ABSENT', label: 'A' },
  { value: 'LATE', label: 'L' },
  { value: 'EXCUSED', label: 'E' },
];

const STATUS_COLOR: Record<AttendanceStatus, string> = {
  PRESENT: 'hsl(142, 76%, 36%)',
  ABSENT: 'hsl(346, 84%, 61%)',
  LATE: 'hsl(38, 92%, 50%)',
  EXCUSED: 'hsl(199, 89%, 48%)',
};

/**
 * M06 mobile screen inventory: "Check-in" — the field-persona flagship
 * (teachers marking attendance away from a desk). All students default to
 * PRESENT (mark exceptions, the fastest real-world workflow) and the
 * teacher taps to change any student's status before submitting one batch
 * roll call via the real `POST /sms/attendance/roll-call` endpoint.
 *
 * Offline behaviour: per the scope limitation documented in
 * `src/api/cache.ts`, a submission made while offline fails with a clear
 * error rather than being silently queued — there is no write-queue/sync
 * engine in this scaffold.
 */
export function RollCallScreen({ route }: Props) {
  const { sectionId, date } = route.params;
  const { subjectId: teacherId } = useSessionSubject();

  const roster = useApiResource(
    () => listSectionEnrollments(sectionId, 'active'),
    [sectionId],
    { cacheKey: `section-roster-${sectionId}` }
  );

  const [statuses, setStatuses] = useState<Record<number, AttendanceStatus>>({});
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<{ success: true; count: number } | { success: false; message: string } | null>(null);

  const statusFor = (studentId: number): AttendanceStatus => statuses[studentId] ?? 'PRESENT';

  const summary = useMemo(() => {
    if (!roster.data) return null;
    const counts: Record<AttendanceStatus, number> = { PRESENT: 0, ABSENT: 0, LATE: 0, EXCUSED: 0 };
    for (const enrollment of roster.data) counts[statusFor(enrollment.student_id)]++;
    return counts;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [roster.data, statuses]);

  const submit = async () => {
    if (!roster.data || roster.data.length === 0) return;
    setSubmitting(true);
    setResult(null);
    try {
      const response = await submitRollCall({
        section_id: sectionId,
        date,
        entries: roster.data.map((enrollment) => ({ student_id: enrollment.student_id, status: statusFor(enrollment.student_id) })),
        marked_by: teacherId ?? undefined,
      });
      setResult({ success: true, count: response.total_recorded });
    } catch (err) {
      const apiError = err instanceof ApiError ? err : null;
      setResult({
        success: false,
        message:
          apiError?.kind === 'network'
            ? "You're offline — this roll call was NOT submitted or queued. Reconnect and try again."
            : apiError?.message ?? 'Could not submit the roll call.',
      });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Screen>
      <View>
        <Text className="text-lg font-semibold text-ink dark:text-ink-dark">Section #{sectionId}</Text>
        <Text className="text-xs text-ink-muted dark:text-ink-muted-dark">{date}</Text>
      </View>

      {summary ? (
        <View className="flex-row gap-2">
          {STATUS_OPTIONS.map((opt) => (
            <View key={opt.value} className="flex-1 items-center rounded-md border border-line py-2 dark:border-line-dark">
              <Text className="text-base font-semibold" style={{ color: STATUS_COLOR[opt.value] }}>{summary[opt.value]}</Text>
              <Text className="text-[10px] text-ink-muted dark:text-ink-muted-dark">{opt.value}</Text>
            </View>
          ))}
        </View>
      ) : null}

      <SectionCard
        title="Roster"
        description="Tap a status to change it — defaults to Present"
        state={roster.status}
        error={roster.error}
        sync={roster.sync}
        onRetry={roster.refetch}
        emptyTitle="No students enrolled"
        emptyDescription="This section has no active enrollments to check in."
      >
        <View className="gap-2">
          {roster.data?.map((enrollment) => {
            const current = statusFor(enrollment.student_id);
            return (
              <View key={enrollment.id} className="flex-row items-center justify-between gap-3 rounded-md border border-line px-3 py-2 dark:border-line-dark">
                <Text className="flex-1 text-sm text-ink dark:text-ink-dark">
                  Student #{enrollment.student_id}{enrollment.roll_number ? ` · Roll ${enrollment.roll_number}` : ''}
                </Text>
                <View className="flex-row gap-1.5">
                  {STATUS_OPTIONS.map((opt) => {
                    const active = current === opt.value;
                    return (
                      <Pressable
                        key={opt.value}
                        onPress={() => setStatuses((prev) => ({ ...prev, [enrollment.student_id]: opt.value }))}
                        accessibilityRole="button"
                        accessibilityLabel={`Mark ${opt.value.toLowerCase()}`}
                        className="size-9 items-center justify-center rounded-full"
                        style={{ backgroundColor: active ? STATUS_COLOR[opt.value] : 'transparent', borderWidth: active ? 0 : 1, borderColor: 'hsl(214, 32%, 91%)' }}
                      >
                        <Text style={{ color: active ? 'white' : STATUS_COLOR[opt.value], fontSize: 12, fontWeight: '700' }}>{opt.label}</Text>
                      </Pressable>
                    );
                  })}
                </View>
              </View>
            );
          })}
        </View>
      </SectionCard>

      {result ? (
        <View className={`rounded-md px-3 py-2.5 ${result.success ? 'bg-positive/10' : 'bg-critical/10'}`}>
          <Text className={`text-sm font-medium ${result.success ? 'text-positive dark:text-positive-dark' : 'text-critical dark:text-critical-dark'}`}>
            {result.success ? `Roll call submitted for ${result.count} student(s).` : result.message}
          </Text>
        </View>
      ) : null}

      <Pressable
        onPress={submit}
        disabled={submitting || roster.status !== 'success'}
        accessibilityRole="button"
        accessibilityLabel="Submit roll call"
        className="min-h-12 flex-row items-center justify-center gap-2 rounded-md bg-action px-4 py-3 active:opacity-80 disabled:opacity-40"
      >
        {submitting ? <ActivityIndicator color="white" /> : <CircleCheck size={16} color="white" />}
        <Text className="text-sm font-semibold text-white">{submitting ? 'Submitting…' : 'Submit roll call'}</Text>
      </Pressable>
    </Screen>
  );
}
