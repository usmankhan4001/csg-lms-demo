import React, { useState } from 'react';
import { Pressable, Text, TextInput, View } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { ArrowRight } from 'lucide-react-native';
import { Screen } from '@/components/layout/Screen';
import { Card } from '@/components/ui';
import { useSessionSubject } from '@/auth/useSessionSubject';
import type { TeacherAttendanceStackParamList } from '@/navigation/stacks/types';

type Props = NativeStackScreenProps<TeacherAttendanceStackParamList, 'CheckInPicker'>;

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

/**
 * M06 mobile screen inventory: "Check-in" entry point — the field-persona
 * flagship (ADR-19): a teacher marking a roll call away from a desk. Section
 * defaults to the section on the teacher's own token claim (see
 * `apps/api/src/core/dev_tokens.py`'s `section_id` convenience claim) but is
 * editable, since a real teacher may teach more than one section.
 */
export function CheckInPickerScreen({ navigation }: Props) {
  const { sectionId } = useSessionSubject();
  const [sectionInput, setSectionInput] = useState(sectionId ? String(sectionId) : '');
  const [dateInput, setDateInput] = useState(todayIso());

  const parsedSectionId = Number(sectionInput);
  const canContinue = Number.isFinite(parsedSectionId) && parsedSectionId > 0 && /^\d{4}-\d{2}-\d{2}$/.test(dateInput);

  return (
    <Screen>
      <Card className="gap-4 p-4">
        <View className="gap-1.5">
          <Text className="text-sm font-medium text-ink dark:text-ink-dark">Section</Text>
          <TextInput
            value={sectionInput}
            onChangeText={setSectionInput}
            keyboardType="number-pad"
            placeholder="e.g. 1"
            placeholderTextColor="hsla(215, 28%, 17%, 0.4)"
            className="min-h-12 rounded-md border border-line px-3 py-2.5 text-sm text-ink dark:border-line-dark dark:text-ink-dark"
          />
        </View>
        <View className="gap-1.5">
          <Text className="text-sm font-medium text-ink dark:text-ink-dark">Date</Text>
          <TextInput
            value={dateInput}
            onChangeText={setDateInput}
            placeholder="YYYY-MM-DD"
            placeholderTextColor="hsla(215, 28%, 17%, 0.4)"
            className="min-h-12 rounded-md border border-line px-3 py-2.5 font-mono text-sm text-ink dark:border-line-dark dark:text-ink-dark"
          />
        </View>
      </Card>

      <Pressable
        onPress={() => navigation.navigate('RollCall', { sectionId: parsedSectionId, date: dateInput })}
        disabled={!canContinue}
        accessibilityRole="button"
        accessibilityLabel="Load roster"
        className="min-h-12 flex-row items-center justify-center gap-2 rounded-md bg-action px-4 py-3 active:opacity-80 disabled:opacity-40"
      >
        <Text className="text-sm font-semibold text-white">Load roster</Text>
        <ArrowRight size={16} color="white" />
      </Pressable>
    </Screen>
  );
}
