import React from 'react';
import { CreditCard } from 'lucide-react-native';
import { StubScreen } from '@/screens/shared/StubScreen';

export function ParentFeesScreen() {
  return (
    <StubScreen
      icon={CreditCard}
      title="Fees"
      description="Would list vouchers from sms_fees (types already ported conceptually — see apps/web/modules/sms/fees/types.ts) with pay/download actions."
    />
  );
}
