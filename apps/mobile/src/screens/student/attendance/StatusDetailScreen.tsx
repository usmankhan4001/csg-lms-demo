import React from 'react';
import { Text, View } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { Screen } from '@/components/layout/Screen';
import { Card, AttendanceStatusChip } from '@/components/ui';
import type { StudentHomeStackParamList } from '@/navigation/stacks/types';

type Props = NativeStackScreenProps<StudentHomeStackParamList, 'AttendanceDetail'>;

/**
 * M06 mobile screen inventory: "Status Detail" — offline read of session
 * details. The record is passed via navigation params (see
 * `navigation/stacks/types.ts`), so this screen never issues a network
 * request and works fully offline by construction, not just "on retry".
 */
export function StatusDetailScreen({ route }: Props) {
  const { record } = route.params;

  return (
    <Screen>
      <Card className="gap-4 p-4">
        <View className="flex-row items-center justify-between">
          <Text className="text-lg font-semibold text-ink dark:text-ink-dark">{record.date}</Text>
          <AttendanceStatusChip status={record.status} />
        </View>

        <View className="gap-3 border-t border-line pt-3 dark:border-line-dark">
          <Row label="Section" value={String(record.section_id)} />
          <Row label="Marked by" value={record.marked_by ? `Staff #${record.marked_by}` : 'Automated'} />
          <Row label="Recorded at" value={new Date(record.timestamp).toLocaleString()} />
          {record.remarks ? <Row label="Remarks" value={record.remarks} /> : null}
        </View>
      </Card>
    </Screen>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <View className="flex-row items-start justify-between gap-4">
      <Text className="text-sm text-ink-muted dark:text-ink-muted-dark">{label}</Text>
      <Text className="flex-1 text-right text-sm font-medium text-ink dark:text-ink-dark">{value}</Text>
    </View>
  );
}
