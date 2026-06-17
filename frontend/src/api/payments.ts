/**
 * Payment tracking API calls.
 * Mirrors the apiClient pattern from api/client.ts — JWT auth and
 * silent refresh are handled automatically by interceptors.
 */
import { apiClient } from './client';
import type {
  PaymentRecord,
  PaymentRecordListResponse,
  PaymentStats,
  PaymentTransaction,
  PaymentRecordCreate,
  PaymentRecordUpdate,
  PaymentTransactionCreate,
} from '../types/payment';

// ── List / filter ──────────────────────────────────────────────────────────

export interface ListPaymentsParams {
  direction?: 'RECEIVABLE' | 'PAYABLE';
  status?: 'PENDING' | 'PARTIAL' | 'PAID' | 'OVERDUE' | 'CANCELLED';
  due_before?: string; // ISO date
  due_after?: string;  // ISO date
  search?: string;
  page?: number;
  page_size?: number;
}

export const listPayments = async (
  params?: ListPaymentsParams
): Promise<PaymentRecordListResponse> => {
  const response = await apiClient.get('/payments/', { params });
  return response.data;
};

// ── Stats (dashboard cards) ───────────────────────────────────────────────

export const getPaymentStats = async (): Promise<PaymentStats> => {
  const response = await apiClient.get('/payments/stats');
  return response.data;
};

// ── Overdue list ───────────────────────────────────────────────────────────

export const getOverduePayments = async (): Promise<{
  items: PaymentRecord[];
  total: number;
}> => {
  const response = await apiClient.get('/payments/overdue');
  return response.data;
};

// ── Detail ─────────────────────────────────────────────────────────────────

export const getPayment = async (paymentId: string): Promise<PaymentRecord> => {
  const response = await apiClient.get(`/payments/${paymentId}`);
  return response.data;
};

// ── Create manual entry ───────────────────────────────────────────────────

export const createManualPayment = async (
  data: PaymentRecordCreate
): Promise<PaymentRecord> => {
  const response = await apiClient.post('/payments/manual', data);
  return response.data;
};

// ── Update record ─────────────────────────────────────────────────────────

export const updatePayment = async (
  paymentId: string,
  data: PaymentRecordUpdate
): Promise<PaymentRecord> => {
  const response = await apiClient.patch(`/payments/${paymentId}`, data);
  return response.data;
};

// ── Add transaction (partial/full payment) ───────────────────────────────

export const addPaymentTransaction = async (
  paymentId: string,
  data: PaymentTransactionCreate
): Promise<PaymentTransaction> => {
  const response = await apiClient.post(`/payments/${paymentId}/transactions`, data);
  return response.data;
};

// ── Delete transaction (correction) ───────────────────────────────────────

export const deletePaymentTransaction = async (
  paymentId: string,
  transactionId: string
): Promise<void> => {
  await apiClient.delete(`/payments/${paymentId}/transactions/${transactionId}`);
};

// ── Export to Excel ────────────────────────────────────────────────────────

export const exportPaymentsXlsx = async (params?: {
  direction?: string;
  status?: string;
}): Promise<Blob> => {
  const response = await apiClient.get('/payments/export/xlsx', {
    params,
    responseType: 'blob',
  });
  return response.data;
};