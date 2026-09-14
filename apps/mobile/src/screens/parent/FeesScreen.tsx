import React, { useState } from 'react';
import { Pressable, RefreshControl, Text, View } from 'react-native';
import { CreditCard, Users } from 'lucide-react-native';
import { Screen } from '@/components/layout/Screen';
import { KpiCard, SectionCard, StatusChip, type ChipTone } from '@/components/ui';
import { useApiResource } from '@/api/useApiResource';
import { getStudentFeeLedger } from '@/modules/sms/fees/api';
import { formatMoney, isOverdue } from '@/modules/sms/fees/format';
import { useChildren, childLabel } from '@/modules/sms/identity/useChildren';
import type { VoucherStatus } from '@/modules/sms/fees/types';

/**
 * Fee vouchers and balances for the guardian's own children. Read-only by
 * design: there is no payment gateway in this deployment, and the one
 * write endpoint (POST /sms/fees/payments) records a payment the office has
 * already taken rather than collecting one.
 *
 * That endpoint is deliberately NOT called from here. Flagged to the owner:
 * it is gated only by `get_current_user_principal` (sms_fees.py:146) and
 * `process_fee_payment` looks the voucher up by id with no ownership or role
 * check (services/sms/fees.py:91), so any signed-in user can currently mark
 * any voucher paid. Wiring a parent-facing button to it would turn that into
 * a one-tap way for a family to clear their own balance.
 */
export function ParentFeesScreen() {
  const { children, status: childrenStatus, error: childrenError, refetch: refetchChildren } = useChildren();
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const activeChildId = selectedId ?? children[0]?.studentId ?? null;

  const ledger = useApiResource(() => getStudentFeeLedger(activeChildId as number), [activeChildId], {
    skip: activeChildId === null,
    cacheKey: activeChildId ? `parent-fees-${activeChildId}` : undefined,
    isEmpty: () => false,
  });

  if (childrenStatus === 'empty' || childrenStatus === 'error' || childrenStatus === 'loading') {
    return (
      <Screen>
        <SectionCard
          title="Fees"
          icon={<CreditCard size={16} color="hsl(215, 28%, 17%)" />}
          state={childrenStatus}
          error={childrenError}
          onRetry={refetchChildren}
          emptyIcon={Users}
          emptyTitle="No children linked to your account"
          emptyDescription="Fees are shown per child. Ask the school office to link your account."
        />
      </Screen>
    );
  }

  const vouchers = ledger.data?.vouchers ?? [];

  return (
    <Screen refreshControl={<RefreshControl refreshing={ledger.status === 'loading'} onRefresh={ledger.refetch} />}>
      {children.length > 1 ? (
        <View className="flex-row flex-wrap gap-2">
          {children.map((entry) => {
            const active = entry.studentId === activeChildId;
            return (
              <Pressable
                key={entry.studentId}
                onPress={() => setSelectedId(entry.studentId)}
                accessibilityRole="button"
                accessibilityState={{ selected: active }}
                accessibilityLabel={`Show fees for ${childLabel(entry)}`}
                className={`min-h-12 justify-center rounded-full px-4 py-2 ${active ? 'bg-action' : 'border border-line dark:border-line-dark'}`}
              >
                <Text className={`text-sm font-semibold ${active ? 'text-white' : 'text-ink-muted dark:text-ink-muted-dark'}`}>
                  {childLabel(entry)}
                </Text>
              </Pressable>
            );
          })}
        </View>
      ) : null}

      <SectionCard
        title="Balance"
        description={children.length === 1 ? childLabel(children[0]) : undefined}
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

      <SectionCard
        title="Vouchers"
        icon={<CreditCard size={16} color="hsl(215, 28%, 17%)" />}
        state={ledger.status === 'success' && vouchers.length === 0 ? 'empty' : ledger.status}
        error={ledger.error}
        onRetry={ledger.refetch}
        emptyTitle="No vouchers issued yet"
        emptyDescription="Fee vouchers appear here once the school issues them."
      >
        <View className="gap-2">
          {vouchers.map((voucher) => (
            <View key={voucher.id} className="gap-2 rounded-md border border-line p-3 dark:border-line-dark">
              <View className="flex-row items-start justify-between gap-3">
                <View className="min-w-0 flex-1">
                  <Text className="text-sm font-semibold text-ink dark:text-ink-dark">{voucher.voucher_no}</Text>
                  <Text className="text-xs text-ink-muted dark:text-ink-muted-dark">Due {voucher.due_date}</Text>
                </View>
                <View className="items-end gap-1">
                  <StatusChip label={VOUCHER_LABELS[voucher.status]} tone={VOUCHER_TONES[voucher.status]} />
                  {isOverdue(voucher.due_date, voucher.balance_amount) ? (
                    <StatusChip label="Overdue" tone="critical" />
                  ) : null}
                </View>
              </View>
              <View className="flex-row justify-between">
                <Text className="text-xs text-ink-muted dark:text-ink-muted-dark">Total {formatMoney(voucher.total_amount)}</Text>
                <Text className="text-xs font-semibold text-ink dark:text-ink-dark">
                  Balance {formatMoney(voucher.balance_amount)}
                </Text>
              </View>
              {voucher.late_fee_applied > 0 ? (
                <Text className="text-[11px] text-caution dark:text-caution-dark">
                  Includes {formatMoney(voucher.late_fee_applied)} automatic late fee
                </Text>
              ) : null}
            </View>
          ))}
        </View>
      </SectionCard>
    </Screen>
  );
}

// Exactly the four members of VoucherStatus (db/sms_fees.py:20).
const VOUCHER_LABELS: Record<VoucherStatus, string> = {
  UNPAID: 'Unpaid',
  PARTIAL: 'Part paid',
  PAID: 'Paid',
  CANCELLED: 'Cancelled',
};

const VOUCHER_TONES: Record<VoucherStatus, ChipTone> = {
  UNPAID: 'caution',
  PARTIAL: 'info',
  PAID: 'positive',
  CANCELLED: 'neutral',
};
