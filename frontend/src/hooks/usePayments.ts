import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  listPayments,
  getPaymentStats,
  getOverduePayments,
  getPayment,
  createManualPayment,
  updatePayment,
  addPaymentTransaction,
  deletePaymentTransaction,
  type ListPaymentsParams,
} from '../api/payments';
import type {
  PaymentRecordCreate,
  PaymentRecordUpdate,
  PaymentTransactionCreate,
} from '../types/payment';

// ── List payments (with filters) ──────────────────────────────────────────

export const usePayments = (params?: ListPaymentsParams) => {
  return useQuery({
    queryKey: ['payments', params],
    queryFn: () => listPayments(params),
    placeholderData: (prev) => prev, // keep showing old page while refetching
  });
};

// ── Dashboard stats ────────────────────────────────────────────────────────

export const usePaymentStats = () => {
  return useQuery({
    queryKey: ['payments', 'stats'],
    queryFn: getPaymentStats,
    // Stats change as transactions are added — keep reasonably fresh
    staleTime: 30 * 1000,
  });
};

// ── Overdue list ───────────────────────────────────────────────────────────

export const useOverduePayments = () => {
  return useQuery({
    queryKey: ['payments', 'overdue'],
    queryFn: getOverduePayments,
  });
};

// ── Single payment detail ─────────────────────────────────────────────────

export const usePaymentDetail = (paymentId: string | undefined) => {
  return useQuery({
    queryKey: ['payment', paymentId],
    queryFn: () => getPayment(paymentId as string),
    enabled: !!paymentId,
  });
};

// ── Create manual payment entry ───────────────────────────────────────────

export const useCreateManualPayment = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: PaymentRecordCreate) => createManualPayment(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['payments'] });
    },
  });
};

// ── Update payment record ─────────────────────────────────────────────────

export const useUpdatePayment = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ paymentId, data }: { paymentId: string; data: PaymentRecordUpdate }) =>
      updatePayment(paymentId, data),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['payments'] });
      queryClient.invalidateQueries({ queryKey: ['payment', variables.paymentId] });
    },
  });
};

// ── Add transaction (partial / full payment) ──────────────────────────────

export const useAddPaymentTransaction = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      paymentId,
      data,
    }: {
      paymentId: string;
      data: PaymentTransactionCreate;
    }) => addPaymentTransaction(paymentId, data),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['payments'] });
      queryClient.invalidateQueries({ queryKey: ['payment', variables.paymentId] });
    },
  });
};

// ── Delete transaction (correction) ───────────────────────────────────────

export const useDeletePaymentTransaction = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      paymentId,
      transactionId,
    }: {
      paymentId: string;
      transactionId: string;
    }) => deletePaymentTransaction(paymentId, transactionId),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['payments'] });
      queryClient.invalidateQueries({ queryKey: ['payment', variables.paymentId] });
    },
  });
};