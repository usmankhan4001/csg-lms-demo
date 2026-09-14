import React from 'react';
import { RefreshControl, Text, View } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { CalendarCheck, CreditCard } from 'lucide-react-native';
import { Screen } from '@/components/layout/Screen';
import { AttendanceStatusChip, KpiCard, SectionCard } from '@/components/ui';
import { useApiResource } from '@/api/useApiResource';
import { getMonthlyStudentAttendance } from '@/modules/sms/attendance/api';
import { getStudentFeeLedger } from '@/modules/sms/fees/api';
import { getChildContext } from '@/modules/sms/identity/api';
import { formatMoney } from '@/modules/sms/fees/format';
import type { ParentChildrenStackParamList } from '@/navigation/stacks/types';

type Props = NativeStackScreenProps<ParentChildrenStackParamList, 'ChildDetail'>;

/**
 * One child's current month attendance plus their fee position. Both
 * endpoints are gated server-side by `require_own_student_or_privileged`, so
 * a guardian reaching for a child that is not theirs gets a 403 rendered as
 * the Restricted state rather than data.
 */
export function ParentChildDetailScreen({ route }: Props) {
  const { studentId } = route.params;
  const now = new Date();
  const year = now.getFullYear();
  const month = now.getMonth() + 1;

  const context = useApiResource(() => getChildContext(studentId), [studentId], {
    cacheKey: `child-context-${studentId}`,
    isEmpty: () => false,
  });

  const attendance = useApiResource(
    () => getMonthlyStudentAttendance(studentId, year, month, context.data?.section_id ?? undefined),
    [studentId, year, month, context.data?.section_id],
    { cacheKey: `child-attendance-${studentId}-${year}-${month}`, isEmpty: () => false }
  );

  const ledger = useApiResource(() => getStudentFeeLedger(studentId), [studentId], {
    cacheKey: `child-ledger-${studentId}`,
    isEmpty: () => false,
  });

  const refetchAll = () => {
    context.refetch();
    attendance.refetch();
    ledger.refetch();
  };

  const stats = attendance.data?.stats;
  const records = attendance.data?.daily_records ?? [];

  return (
    <Screen refreshControl={<RefreshControl refreshing={attendance.status === 'loading'} onRefresh={refetchAll} />}>
      <SectionCard
        title="This month"
        description={`${MONTH_NAMES[month - 1]} ${year}`}
        icon={<CalendarCheck size={16} color="hsl(215, 28%, 17%)" />}
        state={attendance.status}
        error={attendance.error}
        sync={attendance.sync}
        onRetry={attendance.refetch}
      >
        {/* `total_days` is the number of days actually marked. With none
            marked there is no attendance percentage to show -- a school that
            has not taken register yet is not a 0% or a 100% child. */}
        {stats && stats.total_days > 0 ? (
          <View className="gap-3">
            <View className="flex-row flex-wrap gap-2">
              <KpiCard label="Attendance" value={`${stats.attendance_percentage}%`} tone={stats.attendance_percentage >= 90 ? 'positive' : 'caution'} />
              <KpiCard label="Present" value={String(stats.present_days)} tone="positive" />
              <KpiCard label="Absent" value={String(stats.absent_days)} tone={stats.absent_days > 0 ? 'critical' : 'neutral'} />
              <KpiCard label="Late" value={String(stats.late_days)} tone={stats.late_days > 0 ? 'caution' : 'neutral'} />
            </View>
            <View className="gap-2">
              {records.map((record) => (
                <View key={record.id} className="flex-row items-center justify-between rounded-md border border-line px-3 py-2.5 dark:border-line-dark">
                  <Text className="text-sm text-ink dark:text-ink-dark">{record.date}</Text>
                  <AttendanceStatusChip status={record.status} />
                </View>
              ))}
            </View>
          </View>
        ) : (
          <Text className="py-4 text-center text-sm text-ink-muted dark:text-ink-muted-dark">
            No attendance has been marked for this month yet.
          </Text>
        )}
      </SectionCard>

      <SectionCard
        title="Fees"
        icon={<CreditCard size={16} color="hsl(215, 28%, 17%)" />}
        state={ledger.status}
        error={ledger.error}
        sync={ledger.sync}
        onRetry={ledger.refetch}
      >
        {ledger.data ? (
          <View className="flex-row flex-wrap gap-2">
            <KpiCard label="Invoiced" value={formatMoney(ledger.data.total_invoiced)} />
            <KpiCard label="Paid" value={formatMoney(ledger.data.total_paid)} tone="positive" />
            <KpiCard
              label="Outstanding"
              value={formatMoney(ledger.data.total_outstanding)}
              tone={ledger.data.total_outstanding > 0 ? 'critical' : 'positive'}
            />
          </View>
        ) : null}
      </SectionCard>
    </Screen>
  );
}

const MONTH_NAMES = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];
