import React from 'react';
import { RefreshControl, Text, View } from 'react-native';
import { Wallet, UserX } from 'lucide-react-native';
import { Screen } from '@/components/layout/Screen';
import { KpiCard, SectionCard, StatusChip, type ChipTone } from '@/components/ui';
import { useApiResource } from '@/api/useApiResource';
import { useSessionSubject } from '@/auth/useSessionSubject';
import { listMySalarySlips } from '@/modules/sms/payroll/api';
import { formatMoney } from '@/modules/sms/fees/format';
import type { SalaryPaymentStatus, SalarySlipRead } from '@/modules/sms/payroll/types';

/**
 * The staff member's OWN payslips.
 *
 * Only ever requests the signed-in user's `staff_id`. The server enforces
 * this independently -- `_assert_may_read_salary` (sms_payroll.py:57) lets a
 * non-admin read only their own slips, and refuses a bare listing outright.
 * Pay is among the most sensitive data a school holds about an employee, so
 * the client does not get to choose whose slips it asks for.
 *
 * Deductions are itemised rather than rolled into one "total deductions"
 * figure: someone checking a payslip on their phone is usually trying to
 * find out WHY they were paid less, and unpaid-leave days in particular are
 * the answer often enough that the API surfaces them separately.
 */

const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];

function monthLabel(month: number, year: number): string {
  const name = MONTHS[month - 1] ?? `Month ${month}`;
  return `${name} ${year}`;
}

function statusTone(status: SalaryPaymentStatus): ChipTone {
  switch (status) {
    case 'PAID':
      return 'positive';
    case 'APPROVED':
      return 'info';
    case 'REJECTED':
      return 'critical';
    default:
      return 'caution';
  }
}

function DeductionRow({ label, amount }: { label: string; amount: number }) {
  if (!amount) return null;
  return (
    <View className="flex-row items-center justify-between py-1">
      <Text className="text-sm text-ink-muted dark:text-ink-muted-dark">{label}</Text>
      <Text className="text-sm font-medium text-ink dark:text-ink-dark">-{formatMoney(amount)}</Text>
    </View>
  );
}

function SlipCard({ slip }: { slip: SalarySlipRead }) {
  return (
    <View className="gap-2 border-t border-line py-3 dark:border-line-dark">
      <View className="flex-row items-center justify-between">
        <View className="flex-1">
          <Text className="text-base font-semibold text-ink dark:text-ink-dark">
            {monthLabel(slip.month, slip.year)}
          </Text>
          <Text className="text-xs text-ink-muted dark:text-ink-muted-dark">{slip.slip_no}</Text>
        </View>
        <StatusChip label={slip.payment_status} tone={statusTone(slip.payment_status)} />
      </View>

      <View className="flex-row flex-wrap gap-2">
        <KpiCard label="Gross" value={formatMoney(slip.gross_salary)} />
        <KpiCard label="Deductions" value={formatMoney(slip.total_deductions)} tone="critical" />
        <KpiCard label="Net paid" value={formatMoney(slip.net_salary)} tone="positive" />
      </View>

      {slip.total_deductions > 0 ? (
        <View className="rounded-xl bg-line/40 px-3 py-2 dark:bg-line-dark/40">
          <Text className="pb-1 text-xs font-semibold uppercase tracking-wide text-ink-muted dark:text-ink-muted-dark">
            Deductions
          </Text>
          <DeductionRow label="Tax" amount={slip.tax_deduction} />
          <DeductionRow label="Provident fund" amount={slip.provident_fund} />
          <DeductionRow
            label={
              slip.unpaid_leave_days
                ? `Unpaid leave (${slip.unpaid_leave_days} day${slip.unpaid_leave_days === 1 ? '' : 's'})`
                : 'Unpaid leave'
            }
            amount={slip.unpaid_leave_deduction}
          />
          <DeductionRow label="Other" amount={slip.other_deductions} />
        </View>
      ) : null}

      {slip.remarks ? (
        <Text className="text-xs text-ink-muted dark:text-ink-muted-dark">{slip.remarks}</Text>
      ) : null}
    </View>
  );
}

export function StaffPayrollScreen() {
  const { subjectId } = useSessionSubject();

  const slips = useApiResource(() => listMySalarySlips(subjectId as number), [subjectId], {
    skip: subjectId === null,
    cacheKey: subjectId ? `staff-payslips-${subjectId}` : undefined,
    isEmpty: (d) => d.length === 0,
  });

  // No staff record means there is nothing to scope a payslip query to. Say
  // that plainly rather than firing a request that would 403.
  if (subjectId === null) {
    return (
      <Screen>
        <SectionCard
          title="Payroll"
          icon={<Wallet size={16} color="hsl(215, 28%, 17%)" />}
          state="empty"
          emptyIcon={UserX}
          emptyTitle="No staff record linked to your account"
          emptyDescription="Payslips are issued against a staff profile. Ask the school office to link yours."
        />
      </Screen>
    );
  }

  const rows = slips.data ?? [];
  const paid = rows.filter((s) => s.payment_status === 'PAID');
  const latest = rows[0];

  return (
    <Screen refreshControl={<RefreshControl refreshing={slips.status === 'loading'} onRefresh={slips.refetch} />}>
      {latest ? (
        <SectionCard
          title="Latest payslip"
          description={monthLabel(latest.month, latest.year)}
          icon={<Wallet size={16} color="hsl(215, 28%, 17%)" />}
          state={slips.status}
          error={slips.error}
          sync={slips.sync}
          onRetry={slips.refetch}
        >
          <View className="flex-row flex-wrap gap-2">
            <KpiCard label="Net paid" value={formatMoney(latest.net_salary)} tone="positive" />
            <KpiCard label="Status" value={latest.payment_status} />
            <KpiCard label="Slips on record" value={String(rows.length)} />
          </View>
        </SectionCard>
      ) : null}

      <SectionCard
        title="Payslips"
        description={paid.length ? `${paid.length} paid` : undefined}
        icon={<Wallet size={16} color="hsl(215, 28%, 17%)" />}
        state={slips.status}
        error={slips.error}
        sync={slips.sync}
        onRetry={slips.refetch}
        emptyTitle="No payslips yet"
        emptyDescription="Your payslips appear here once payroll has been generated for a month."
      >
        <View>
          {rows.map((slip) => (
            <SlipCard key={slip.id} slip={slip} />
          ))}
        </View>
      </SectionCard>
    </Screen>
  );
}
