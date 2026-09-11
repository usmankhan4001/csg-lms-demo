import React from 'react';
import { Wallet } from 'lucide-react-native';
import { StubScreen } from '@/screens/shared/StubScreen';

export function StaffPayrollScreen() {
  return (
    <StubScreen
      icon={Wallet}
      title="Payroll"
      description="Would read apps/api/src/routers/sms_payroll.py via a ported sms/payroll module, mirroring the STUDENT/TEACHER screens' pattern."
    />
  );
}
