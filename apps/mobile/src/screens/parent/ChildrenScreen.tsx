import React from 'react';
import { Users } from 'lucide-react-native';
import { StubScreen } from '@/screens/shared/StubScreen';

export function ParentChildrenScreen() {
  return (
    <StubScreen
      icon={Users}
      title="My Children"
      description="Would list each child (session claim children_ids) with attendance/grades drill-in, reusing the same sms/attendance + sms/gradebook contracts as the STUDENT screens."
    />
  );
}
