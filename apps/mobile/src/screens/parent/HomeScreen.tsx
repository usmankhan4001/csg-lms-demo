import React from 'react';
import { Home } from 'lucide-react-native';
import { StubScreen } from '@/screens/shared/StubScreen';

export function ParentHomeScreen() {
  return (
    <StubScreen
      icon={Home}
      title="Parent Home"
      description="Per-child progress summary. This pass builds the PARENT tab shell only — real screens (backed by apps/web/modules/sms/attendance + fees) are a follow-up."
    />
  );
}
