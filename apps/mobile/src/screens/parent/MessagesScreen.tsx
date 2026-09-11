import React from 'react';
import { MessageSquare } from 'lucide-react-native';
import { StubScreen } from '@/screens/shared/StubScreen';

export function ParentMessagesScreen() {
  return (
    <StubScreen
      icon={MessageSquare}
      title="Messages"
      description="M13 Communication module has no sms_* module ported to this app yet."
    />
  );
}
