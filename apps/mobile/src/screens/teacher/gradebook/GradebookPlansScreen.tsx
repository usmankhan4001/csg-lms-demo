import React from 'react';
import { Pressable, Text, View } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { ChevronRight } from 'lucide-react-native';
import { Screen } from '@/components/layout/Screen';
import { SectionCard } from '@/components/ui';
import { useApiResource } from '@/api/useApiResource';
import { useSessionSubject } from '@/auth/useSessionSubject';
import { listAssessmentPlans } from '@/modules/sms/gradebook/api';
import type { TeacherGradebookStackParamList } from '@/navigation/stacks/types';

type Props = NativeStackScreenProps<TeacherGradebookStackParamList, 'GradebookPlans'>;

export function GradebookPlansScreen({ navigation }: Props) {
  const { academicTermId } = useSessionSubject();

  const plans = useApiResource(
    () => listAssessmentPlans({ academicTermId: academicTermId ?? undefined }),
    [academicTermId],
    { cacheKey: `gradebook-plans-${academicTermId ?? 'all'}` }
  );

  return (
    <Screen>
      <SectionCard
        title="Assessment plans"
        description="Tap a plan to enter scores for its roster"
        state={plans.status}
        error={plans.error}
        sync={plans.sync}
        onRetry={plans.refetch}
        emptyTitle="No assessment plans yet"
        emptyDescription="Create one from the web admin console, or ask your school admin to set one up."
        requiredRoleLabel="TEACHER"
      >
        <View className="gap-2">
          {plans.data?.map((plan) => (
            <Pressable
              key={plan.id}
              onPress={() => navigation.navigate('GradeEntry', { plan })}
              accessibilityRole="button"
              accessibilityLabel={`Enter grades for ${plan.assessment_name}`}
              className="min-h-12 flex-row items-center justify-between rounded-md border border-line px-3 py-3 active:opacity-70 dark:border-line-dark"
            >
              <View className="flex-1">
                <Text className="text-sm font-medium text-ink dark:text-ink-dark">{plan.assessment_name}</Text>
                <Text className="text-xs text-ink-muted dark:text-ink-muted-dark">
                  Course #{plan.course_id} · {plan.weight_percentage}% weight · out of {plan.max_score}
                </Text>
              </View>
              <ChevronRight size={16} color="hsl(215, 28%, 17%)" />
            </Pressable>
          ))}
        </View>
      </SectionCard>
    </Screen>
  );
}
