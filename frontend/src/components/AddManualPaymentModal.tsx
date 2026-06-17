import { useState } from 'react';
import { X } from 'lucide-react';
import { useCreateManualPayment } from '../hooks/usePayments';
import type { PaymentDirection, PaymentRecordCreate } from '../types/payment';

interface AddManualPaymentModalProps {
  onClose: () => void;
}

/**
 * Modal for creating a standalone payment entry not linked to any invoice.
 * e.g. advances, retainers, manual reconciliation entries.
 */
export const AddManualPaymentModal = ({ onClose }: AddManualPaymentModalProps) => {
  const createManual = useCreateManualPayment();

  const [form, setForm] = useState<PaymentRecordCreate>({
    direction: 'PAYABLE',
    total_amount: 0,
    due_date: '',
    counterparty_name: '',
    counterparty_gstin: '',
    counterparty_email: '',
    manual_description: '',
    manual_invoice_ref: '',
    notes: '',
  });
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (form.total_amount <= 0) {
      setError('Total amount must be greater than zero.');
      return;
    }

    try {
      // Strip empty optional strings so backend validators don't choke
      const payload: PaymentRecordCreate = {
        ...form,
        due_date: form.due_date || undefined,
        counterparty_name: form.counterparty_name || undefined,
        counterparty_gstin: form.counterparty_gstin || undefined,
        counterparty_email: form.counterparty_email || undefined,
        manual_description: form.manual_description || undefined,
        manual_invoice_ref: form.manual_invoice_ref || undefined,
        notes: form.notes || undefined,
      };
      await createManual.mutateAsync(payload);
      onClose();
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail || 'Failed to create payment entry. Please check the form.');
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
      <div className="bg-white rounded-xl shadow-lg w-full max-w-lg max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="px-6 py-4 border-b border-ink-100 flex items-center justify-between sticky top-0 bg-white">
          <h2 className="text-lg font-semibold text-ink-900">Add Manual Payment Entry</h2>
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

          {/* Direction */}
          <div>
            <label className="block text-sm font-medium text-ink-700 mb-1.5">Direction</label>
            <div className="flex items-center gap-2">
              {(['PAYABLE', 'RECEIVABLE'] as PaymentDirection[]).map((d) => (
                <button
                  key={d}
                  type="button"
                  onClick={() => setForm((f) => ({ ...f, direction: d }))}
                  className={`flex-1 px-3 py-2 rounded-lg text-sm font-medium border transition-colors ${
                    form.direction === d
                      ? d === 'PAYABLE'
                        ? 'bg-rose-50 border-rose-300 text-rose-700'
                        : 'bg-emerald-50 border-emerald-300 text-emerald-700'
                      : 'border-ink-200 text-ink-500 hover:bg-ink-50'
                  }`}
                >
                  {d === 'PAYABLE' ? 'Payable (money out)' : 'Receivable (money in)'}
                </button>
              ))}
            </div>
          </div>

          {/* Total amount */}
          <div>
            <label className="block text-sm font-medium text-ink-700 mb-1.5">
              Total Amount (₹)
            </label>
            <input
              type="number"
              min="0.01"
              step="0.01"
              value={form.total_amount || ''}
              onChange={(e) =>
                setForm((f) => ({ ...f, total_amount: parseFloat(e.target.value) || 0 }))
              }
              className="w-full px-3 py-2 rounded-lg border border-ink-200 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              required
            />
          </div>

          {/* Due date */}
          <div>
            <label className="block text-sm font-medium text-ink-700 mb-1.5">Due Date</label>
            <input
              type="date"
              value={form.due_date || ''}
              onChange={(e) => setForm((f) => ({ ...f, due_date: e.target.value }))}
              className="w-full px-3 py-2 rounded-lg border border-ink-200 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {/* Counterparty name */}
          <div>
            <label className="block text-sm font-medium text-ink-700 mb-1.5">
              Counterparty Name
            </label>
            <input
              type="text"
              value={form.counterparty_name || ''}
              onChange={(e) => setForm((f) => ({ ...f, counterparty_name: e.target.value }))}
              placeholder="e.g. ABC Suppliers Pvt Ltd"
              className="w-full px-3 py-2 rounded-lg border border-ink-200 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {/* Counterparty GSTIN */}
          <div>
            <label className="block text-sm font-medium text-ink-700 mb-1.5">
              Counterparty GSTIN (optional)
            </label>
            <input
              type="text"
              value={form.counterparty_gstin || ''}
              onChange={(e) =>
                setForm((f) => ({ ...f, counterparty_gstin: e.target.value.toUpperCase() }))
              }
              placeholder="15-character GSTIN"
              maxLength={15}
              className="w-full px-3 py-2 rounded-lg border border-ink-200 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono"
            />
          </div>

          {/* Counterparty email */}
          <div>
            <label className="block text-sm font-medium text-ink-700 mb-1.5">
              Counterparty Email (optional)
            </label>
            <input
              type="email"
              value={form.counterparty_email || ''}
              onChange={(e) => setForm((f) => ({ ...f, counterparty_email: e.target.value }))}
              placeholder="vendor@example.com"
              className="w-full px-3 py-2 rounded-lg border border-ink-200 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            {form.direction === 'RECEIVABLE' && (
              <p className="text-[11px] text-ink-400 mt-1.5">
                For receivables, reminder emails go to this address (the counterparty owes you).
                If left blank, reminders go to your own organisation email instead.
              </p>
            )}
            {form.direction === 'PAYABLE' && (
              <p className="text-[11px] text-ink-400 mt-1.5">
                For payables, reminder emails always go to your own organisation email —
                this is stored for reference only.
              </p>
            )}
          </div>

          {/* Description */}
          <div>
            <label className="block text-sm font-medium text-ink-700 mb-1.5">
              Description
            </label>
            <input
              type="text"
              value={form.manual_description || ''}
              onChange={(e) => setForm((f) => ({ ...f, manual_description: e.target.value }))}
              placeholder="e.g. Advance payment for Q2 order"
              className="w-full px-3 py-2 rounded-lg border border-ink-200 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {/* Reference number */}
          <div>
            <label className="block text-sm font-medium text-ink-700 mb-1.5">
              Reference Number (optional)
            </label>
            <input
              type="text"
              value={form.manual_invoice_ref || ''}
              onChange={(e) => setForm((f) => ({ ...f, manual_invoice_ref: e.target.value }))}
              placeholder="e.g. PO-1234"
              className="w-full px-3 py-2 rounded-lg border border-ink-200 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
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
              disabled={createManual.isPending}
              className="px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 transition-colors disabled:opacity-50"
            >
              {createManual.isPending ? 'Creating...' : 'Create Entry'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};