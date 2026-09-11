import React from 'react';
import { ClipboardList } from 'lucide-react-native';
import { StubScreen } from '@/screens/shared/StubScreen';

/**
 * DESIGN-SYSTEM.md §2.3 lists "Assignments" as one of STUDENT's 5 primary
 * destinations, but no `apps/web/modules/sms/assignments` module exists to
 * port a real contract from (M03 Assignments is a separate, not-yet-built
 * SMS module — the ported modules are attendance/campus/fees/financials/
 * gradebook/hr_payroll/library/timetable only). Kept as an honest stub
 * rather than inventing an API contract.
 */
export function StudentAssignmentsScreen() {
  return (
    <StubScreen
      icon={ClipboardList}
      title="Assignments"
      description="No sms_assignments backend module/contract exists yet (M03 is a separate, not-yet-built module) — nothing real to wire up here in this pass."
    />
  );
}
