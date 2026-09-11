import React, { useState } from 'react';
import { ActivityIndicator, Pressable, Text, TextInput, View } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { CircleCheck } from 'lucide-react-native';
import { Screen } from '@/components/layout/Screen';
import { SectionCard } from '@/components/ui';
import { useApiResource } from '@/api/useApiResource';
import { useSessionSubject } from '@/auth/useSessionSubject';
import { listSectionEnrollments } from '@/modules/sms/campus/api';
import { batchEnterGrades } from '@/modules/sms/gradebook/api';
import { ApiError } from '@/api/client';
import type { TeacherGradebookStackParamList } from '@/navigation/stacks/types';

type Props = NativeStackScreenProps<TeacherGradebookStackParamList, 'GradeEntry'>;

export function GradeEntryScreen({ route }: Props) {
  const { plan } = route.params;
  const { sectionId: mySectionId, subjectId: teacherId } = useSessionSubject();
  const sectionId = plan.section_id ?? mySectionId;

  const roster = useApiResource(
    () => listSectionEnrollments(sectionId as number, 'active'),
    [sectionId],
    { skip: !sectionId, cacheKey: sectionId ? `section-roster-${sectionId}` : undefined }
  );

  const [scores, setScores] = useState<Record<number, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<{ success: true; count: number } | { success: false; message: string } | null>(null);

  const submit = async () => {
    if (!roster.data || roster.data.length === 0) return;
    setSubmitting(true);
    setResult(null);
    try {
      const entries = roster.data
        .filter((enrollment) => scores[enrollment.student_id] !== undefined && scores[enrollment.student_id] !== '')
        .map((enrollment) => ({ student_id: enrollment.student_id, raw_score: Number(scores[enrollment.student_id]) }));

      if (entries.length === 0) {
        setResult({ success: false, message: 'Enter at least one score before submitting.' });
        return;
      }

      const graded = await batchEnterGrades({ assessment_plan_id: plan.id, entries, graded_by: teacherId ?? undefined });
      setResult({ success: true, count: graded.length });
    } catch (err) {
      const apiError = err instanceof ApiError ? err : null;
      setResult({
        success: false,
        message:
          apiError?.kind === 'network'
            ? "You're offline — grades were not submitted. Reconnect and try again (this scaffold does not queue offline writes)."
            : apiError?.message ?? 'Could not submit grades.',
      });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Screen>
      <View>
        <Text className="text-lg font-semibold text-ink dark:text-ink-dark">{plan.assessment_name}</Text>
        <Text className="text-xs text-ink-muted dark:text-ink-muted-dark">Out of {plan.max_score} · {plan.weight_percentage}% weight</Text>
      </View>

      <SectionCard
        title="Roster"
        description="Enter a raw score for each student, then submit"
        state={roster.status}
        error={roster.error}
        sync={roster.sync}
        onRetry={roster.refetch}
        emptyTitle="No students enrolled"
        emptyDescription="This section has no active enrollments yet."
      >
        <View className="gap-2">
          {roster.data?.map((enrollment) => (
            <View key={enrollment.id} className="flex-row items-center justify-between gap-3 rounded-md border border-line px-3 py-2 dark:border-line-dark">
              <Text className="flex-1 text-sm text-ink dark:text-ink-dark">
                Student #{enrollment.student_id}{enrollment.roll_number ? ` · Roll ${enrollment.roll_number}` : ''}
              </Text>
              <TextInput
                value={scores[enrollment.student_id] ?? ''}
                onChangeText={(text) => setScores((prev) => ({ ...prev, [enrollment.student_id]: text.replace(/[^0-9.]/g, '') }))}
                keyboardType="decimal-pad"
                placeholder="—"
                placeholderTextColor="hsla(215, 28%, 17%, 0.4)"
                className="w-16 rounded-md border border-line px-2 py-1.5 text-center text-sm text-ink dark:border-line-dark dark:text-ink-dark"
              />
            </View>
          ))}
        </View>
      </SectionCard>

      {result ? (
        <View className={`rounded-md px-3 py-2.5 ${result.success ? 'bg-positive/10' : 'bg-critical/10'}`}>
          <Text className={`text-sm font-medium ${result.success ? 'text-positive dark:text-positive-dark' : 'text-critical dark:text-critical-dark'}`}>
            {result.success ? `Saved ${result.count} grade(s).` : result.message}
          </Text>
        </View>
      ) : null}

      <Pressable
        onPress={submit}
        disabled={submitting || roster.status !== 'success'}
        accessibilityRole="button"
        accessibilityLabel="Submit grades"
        className="min-h-12 flex-row items-center justify-center gap-2 rounded-md bg-action px-4 py-3 active:opacity-80 disabled:opacity-40"
      >
        {submitting ? <ActivityIndicator color="white" /> : <CircleCheck size={16} color="white" />}
        <Text className="text-sm font-semibold text-white">{submitting ? 'Submitting…' : 'Submit grades'}</Text>
      </Pressable>
    </Screen>
  );
}
