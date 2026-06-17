import { useState } from 'react';
import { X } from 'lucide-react';
import { useAddPaymentTransaction } from '../hooks/usePayments';
import type { PaymentMode, PaymentRecord, PaymentTransactionCreate } from '../types/payment';

interface AddTransactionModalProps {
  payment: PaymentRecord;
  onClose: () => void;
}

const PAYMENT_MODES: { label: string; value: PaymentMode }[] = [
  { label: 'Bank Transfer', value: 'BANK_TRANSFER' },
  { label: 'UPI', value: 'UPI' },
  { label: 'NEFT', value: 'NEFT' },
  { label: 'RTGS', value: 'RTGS' },
  { label: 'Cheque', value: 'CHEQUE' },
  { label: 'Cash', value: 'CASH' },
  { label: 'Demand Draft', value: 'DD' },
  { label: 'Other', value: 'OTHER' },
];

const todayIso = () => new Date().toISOString().split('T')[0];

/**
 * Modal for recording a payment transaction (partial or full) against
 * a PaymentRecord. Backend validates amount <= remaining balance.
 */
export const AddTransactionModal = ({ payment, onClose }: AddTransactionModalProps) => {
  const addTransaction = useAddPaymentTransaction();

  const [form, setForm] = useState<PaymentTransactionCreate>({
    amount: payment.balance,
    payment_mode: 'BANK_TRANSFER',
    reference_no: '',
    transaction_date: todayIso(),
    notes: '',
  });
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (form.amount <= 0) {
      setError('Amount must be greater than zero.');
      return;
    }
    if (form.amount > payment.balance) {
      setError(
        `Amount cannot exceed the remaining balance of ₹${payment.balance.toLocaleString('en-IN')}.`
      );
      return;
    }

    try {
      const payload: PaymentTransactionCreate = {
        ...form,
        reference_no: form.reference_no || undefined,
        notes: form.notes || undefined,
      };
      await addTransaction.mutateAsync({ paymentId: payment.id, data: payload });
      onClose();
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail || 'Failed to record transaction.');
    }
  };

  const isFullPayment = form.amount >= payment.balance;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
      <div className="bg-white rounded-xl shadow-lg w-full max-w-md max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="px-6 py-4 border-b border-ink-100 flex items-center justify-between sticky top-0 bg-white">
          <div>
            <h2 className="text-lg font-semibold text-ink-900">Record Payment</h2>
            <p className="text-xs text-ink-500 mt-0.5">
              Remaining balance: ₹{payment.balance.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
            </p>
          </div>
          <button onClick={onClose} className="text-ink-400 hover:text-ink-600 transition-colors">
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">
          {error && (
            <div className="px-4 py-3 rounded-lg bg-red-50 text-red-700 text-sm border border-red-200">
              {error}
            </div>
          )}

          {/* Amount */}
          <div>
            <label className="block text-sm font-medium text-ink-700 mb-1.5">Amount (₹)</label>
            <input
              type="number"
              min="0.01"
              step="0.01"
              max={payment.balance}
              value={form.amount || ''}
              onChange={(e) =>
                setForm((f) => ({ ...f, amount: parseFloat(e.target.value) || 0 }))
              }
              className="w-full px-3 py-2 rounded-lg border border-ink-200 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              required
            />
            <div className="flex items-center gap-2 mt-2">
              <button
                type="button"
                onClick={() => setForm((f) => ({ ...f, amount: payment.balance }))}
                className="text-xs font-medium text-blue-600 hover:text-blue-800"
              >
                Pay full balance (₹{payment.balance.toLocaleString('en-IN')})
              </button>
            </div>
            {isFullPayment && (
              <p className="text-xs text-emerald-600 mt-1 font-medium">
                This will mark the payment as fully PAID.
              </p>
            )}
            {!isFullPayment && form.amount > 0 && (
              <p className="text-xs text-amber-600 mt-1 font-medium">
                This is a partial payment. Remaining after this:{' '}
                ₹{(payment.balance - form.amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
              </p>
            )}
          </div>

          {/* Payment mode */}
          <div>
            <label className="block text-sm font-medium text-ink-700 mb-1.5">Payment Mode</label>
            <select
              value={form.payment_mode}
              onChange={(e) =>
                setForm((f) => ({ ...f, payment_mode: e.target.value as PaymentMode }))
              }
              className="w-full px-3 py-2 rounded-lg border border-ink-200 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {PAYMENT_MODES.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </select>
          </div>

          {/* Transaction date */}
          <div>
            <label className="block text-sm font-medium text-ink-700 mb-1.5">
              Transaction Date
            </label>
            <input
              type="date"
              value={form.transaction_date}
              onChange={(e) => setForm((f) => ({ ...f, transaction_date: e.target.value }))}
              className="w-full px-3 py-2 rounded-lg border border-ink-200 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              required
            />
          </div>

          {/* Reference number */}
          <div>
            <label className="block text-sm font-medium text-ink-700 mb-1.5">
              Reference Number
            </label>
            <input
              type="text"
              value={form.reference_no || ''}
              onChange={(e) => setForm((f) => ({ ...f, reference_no: e.target.value }))}
              placeholder="UTR / Cheque No. / UPI Txn ID"
              className="w-full px-3 py-2 rounded-lg border border-ink-200 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono"
            />
          </div>

          {/* Notes */}
          <div>
            <label className="block text-sm font-medium text-ink-700 mb-1.5">Notes</label>
            <textarea
              value={form.notes || ''}
              onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
              rows={2}
              className="w-full px-3 py-2 rounded-lg border border-ink-200 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
            />
          </div>

          {/* Footer buttons */}
          <div className="flex items-center justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-lg border border-ink-200 text-sm font-medium text-ink-700 hover:bg-ink-50 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={addTransaction.isPending}
              className="px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 transition-colors disabled:opacity-50"
            >
              {addTransaction.isPending ? 'Recording...' : 'Record Payment'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};