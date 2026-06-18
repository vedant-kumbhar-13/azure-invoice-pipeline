import { useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  ArrowLeft,
  Plus,
  Receipt,
  Building2,
  Calendar,
  Hash,
  StickyNote,
  BellOff,
  Trash2,
  FileText,
  Mail,
  Pencil,
  Check,
  X,
} from 'lucide-react';
import { Skeleton } from '../components/ui/skeleton';
import { PaymentStatusBadge, PaymentDirectionBadge } from '../components/PaymentStatusBadge';
import { AddTransactionModal } from '../components/AddTransactionModal';
import {
  usePaymentDetail,
  useUpdatePayment,
  useDeletePaymentTransaction,
} from '../hooks/usePayments';
import { useSnoozeReminders } from '../hooks/useReminders';
import { formatCurrency, formatDate } from '../utils/formatters';
import type { PaymentStatus } from '../types/payment';

const STATUS_OPTIONS: PaymentStatus[] = ['PENDING', 'PARTIAL', 'PAID', 'OVERDUE', 'CANCELLED'];

const MODE_LABELS: Record<string, string> = {
  BANK_TRANSFER: 'Bank Transfer',
  UPI: 'UPI',
  NEFT: 'NEFT',
  RTGS: 'RTGS',
  CHEQUE: 'Cheque',
  CASH: 'Cash',
  DD: 'Demand Draft',
  OTHER: 'Other',
};

export const PaymentDetailPage = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: payment, isLoading } = usePaymentDetail(id);
  const updatePayment = useUpdatePayment();
  const deleteTransaction = useDeletePaymentTransaction();
  const snoozeReminders = useSnoozeReminders();

  const [showAddTxn, setShowAddTxn] = useState(false);
  const [editingEmail, setEditingEmail] = useState(false);
  const [emailInput, setEmailInput] = useState('');
  const [emailError, setEmailError] = useState<string | null>(null);

  if (isLoading) {
    return (
      <div className="max-w-4xl mx-auto space-y-6 pb-12">
        <Skeleton className="h-10 w-48" />
        <Skeleton className="h-48 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (!payment) {
    return (
      <div className="max-w-4xl mx-auto text-center py-20">
        <p className="text-ink-500">Payment record not found.</p>
        <Link to="/payments" className="text-blue-600 font-medium hover:text-blue-800 mt-2 inline-block">
          Back to Payments
        </Link>
      </div>
    );
  }

  const progressPct =
    payment.total_amount > 0
      ? Math.min(100, Math.round((payment.paid_amount / payment.total_amount) * 100))
      : 0;

  const handleStatusChange = async (newStatus: PaymentStatus) => {
    await updatePayment.mutateAsync({
      paymentId: payment.id,
      data: { status: newStatus },
    });
  };

  const handleDeleteTransaction = async (transactionId: string) => {
    if (!confirm('Delete this transaction? This will recalculate the balance.')) return;
    await deleteTransaction.mutateAsync({ paymentId: payment.id, transactionId });
  };

  const handleSnooze = async (days: number) => {
    await snoozeReminders.mutateAsync({ paymentRecordId: payment.id, snoozeDays: days });
  };

  const startEditEmail = () => {
    setEmailInput(payment.counterparty_email || '');
    setEmailError(null);
    setEditingEmail(true);
  };

  const cancelEditEmail = () => {
    setEditingEmail(false);
    setEmailError(null);
  };

  const saveEmail = async () => {
    const trimmed = emailInput.trim();
    if (trimmed && (!trimmed.includes('@') || !trimmed.split('@')[1]?.includes('.'))) {
      setEmailError('Enter a valid email address.');
      return;
    }
    try {
      await updatePayment.mutateAsync({
        paymentId: payment.id,
        data: { counterparty_email: trimmed || undefined } as any,
      });
      setEditingEmail(false);
      setEmailError(null);
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setEmailError(detail || 'Failed to save email.');
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6 pb-12">
      {/* Back link */}
      <button
        onClick={() => navigate('/payments')}
        className="inline-flex items-center gap-1.5 text-sm font-medium text-ink-500 hover:text-ink-900 transition-colors"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Payments
      </button>

      {/* Header card */}
      <div className="bg-white rounded-xl border border-ink-200 shadow-sm p-6">
        <div className="flex items-start justify-between flex-wrap gap-4">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <PaymentDirectionBadge direction={payment.direction} />
              <PaymentStatusBadge status={payment.status} />
              {payment.is_manual && (
                <span className="text-[10px] uppercase tracking-wide text-ink-400 font-semibold">
                  Manual Entry
                </span>
              )}
            </div>
            <h1 className="text-2xl font-bold text-ink-900 tracking-tight">
              {payment.counterparty_name || 'Unknown Counterparty'}
            </h1>
            {payment.counterparty_gstin && (
              <p className="text-sm text-ink-500 font-mono mt-1">{payment.counterparty_gstin}</p>
            )}
          </div>

          {payment.invoice_id && (
            <Link
              to={`/invoices/${payment.invoice_id}`}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-ink-200 text-sm font-medium text-ink-700 hover:bg-ink-50 transition-colors"
            >
              <FileText className="h-4 w-4" />
              View Invoice
            </Link>
          )}
        </div>

        {/* Amount summary */}
        <div className="grid grid-cols-3 gap-4 mt-6">
          <div>
            <p className="text-xs text-ink-500 uppercase tracking-wide font-medium mb-1">
              Total Amount
            </p>
            <p className="text-2xl font-bold text-ink-900 font-mono">
              {formatCurrency(payment.total_amount)}
            </p>
          </div>
          <div>
            <p className="text-xs text-ink-500 uppercase tracking-wide font-medium mb-1">
              Paid
            </p>
            <p className="text-2xl font-bold text-emerald-600 font-mono">
              {formatCurrency(payment.paid_amount)}
            </p>
          </div>
          <div>
            <p className="text-xs text-ink-500 uppercase tracking-wide font-medium mb-1">
              Balance
            </p>
            <p className="text-2xl font-bold text-rose-600 font-mono">
              {formatCurrency(payment.balance)}
            </p>
          </div>
        </div>

        {/* Progress bar */}
        <div className="mt-4">
          <div className="w-full bg-ink-100 rounded-full h-2 overflow-hidden">
            <div
              className="bg-emerald-500 h-2 rounded-full transition-all duration-700"
              style={{ width: `${progressPct}%` }}
            />
          </div>
          <p className="text-xs text-ink-400 mt-1.5">{progressPct}% paid</p>
        </div>

        {/* Meta info */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-6 pt-6 border-t border-ink-100">
          <div className="flex items-start gap-3">
            <Calendar className="h-4 w-4 text-ink-400 mt-0.5" />
            <div>
              <p className="text-xs text-ink-500 uppercase tracking-wide font-medium">Due Date</p>
              <p className="text-sm text-ink-900 mt-0.5">
                {payment.due_date ? formatDate(payment.due_date) : 'Not set'}
              </p>
            </div>
          </div>
          {payment.paid_date && (
            <div className="flex items-start gap-3">
              <Calendar className="h-4 w-4 text-ink-400 mt-0.5" />
              <div>
                <p className="text-xs text-ink-500 uppercase tracking-wide font-medium">
                  Paid Date
                </p>
                <p className="text-sm text-ink-900 mt-0.5">{formatDate(payment.paid_date)}</p>
              </div>
            </div>
          )}

          {/* Counterparty email — editable. Used as the reminder recipient
              for RECEIVABLE payments; informational only for PAYABLE. */}
          <div className="flex items-start gap-3 sm:col-span-2">
            <Mail className="h-4 w-4 text-ink-400 mt-0.5" />
            <div className="flex-1">
              <p className="text-xs text-ink-500 uppercase tracking-wide font-medium">
                Counterparty Email
              </p>

              {!editingEmail ? (
                <div className="flex items-center gap-2 mt-0.5">
                  <p className="text-sm text-ink-900">
                    {payment.counterparty_email || (
                      <span className="text-ink-400 italic">Not set</span>
                    )}
                  </p>
                  <button
                    onClick={startEditEmail}
                    className="text-ink-400 hover:text-blue-600 transition-colors"
                    title="Edit counterparty email"
                  >
                    <Pencil className="h-3.5 w-3.5" />
                  </button>
                </div>
              ) : (
                <div className="mt-1">
                  <div className="flex items-center gap-2">
                    <input
                      type="email"
                      value={emailInput}
                      onChange={(e) => setEmailInput(e.target.value)}
                      placeholder="counterparty@example.com"
                      autoFocus
                      className="flex-1 max-w-xs px-2.5 py-1.5 rounded-lg border border-ink-200 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                    <button
                      onClick={saveEmail}
                      disabled={updatePayment.isPending}
                      className="p-1.5 rounded-lg bg-emerald-100 text-emerald-700 hover:bg-emerald-200 transition-colors disabled:opacity-50"
                      title="Save"
                    >
                      <Check className="h-4 w-4" />
                    </button>
                    <button
                      onClick={cancelEditEmail}
                      className="p-1.5 rounded-lg bg-ink-100 text-ink-600 hover:bg-ink-200 transition-colors"
                      title="Cancel"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                  {emailError && (
                    <p className="text-xs text-red-600 mt-1.5">{emailError}</p>
                  )}
                </div>
              )}

              <p className="text-[11px] text-ink-400 mt-1.5">
                {payment.direction === 'RECEIVABLE'
                  ? 'Reminder emails are sent here (falls back to your org email if blank).'
                  : 'Informational only — reminders for payables always go to your org email.'}
              </p>
            </div>
          </div>

          {payment.manual_invoice_ref && (
            <div className="flex items-start gap-3">
              <Hash className="h-4 w-4 text-ink-400 mt-0.5" />
              <div>
                <p className="text-xs text-ink-500 uppercase tracking-wide font-medium">
                  Reference
                </p>
                <p className="text-sm text-ink-900 mt-0.5">{payment.manual_invoice_ref}</p>
              </div>
            </div>
          )}
          {payment.manual_description && (
            <div className="flex items-start gap-3 sm:col-span-2">
              <Building2 className="h-4 w-4 text-ink-400 mt-0.5" />
              <div>
                <p className="text-xs text-ink-500 uppercase tracking-wide font-medium">
                  Description
                </p>
                <p className="text-sm text-ink-900 mt-0.5">{payment.manual_description}</p>
              </div>
            </div>
          )}
          {payment.notes && (
            <div className="flex items-start gap-3 sm:col-span-2">
              <StickyNote className="h-4 w-4 text-ink-400 mt-0.5" />
              <div>
                <p className="text-xs text-ink-500 uppercase tracking-wide font-medium">Notes</p>
                <p className="text-sm text-ink-900 mt-0.5">{payment.notes}</p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Actions bar */}
      <div className="bg-white rounded-xl border border-ink-200 shadow-sm p-4 flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-ink-700">Status:</span>
          <select
            value={payment.status}
            onChange={(e) => handleStatusChange(e.target.value as PaymentStatus)}
            disabled={updatePayment.isPending}
            className="px-3 py-1.5 rounded-lg border border-ink-200 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {STATUS_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-2">
          {payment.status !== 'PAID' && payment.status !== 'CANCELLED' && (
            <>
              <button
                onClick={() => handleSnooze(3)}
                disabled={snoozeReminders.isPending}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-ink-200 text-sm font-medium text-ink-700 hover:bg-ink-50 transition-colors disabled:opacity-50"
              >
                <BellOff className="h-4 w-4" />
                Snooze 3 days
              </button>
              <button
                onClick={() => setShowAddTxn(true)}
                className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 transition-colors"
              >
                <Plus className="h-4 w-4" />
                Record Payment
              </button>
            </>
          )}
        </div>
      </div>

      {/* Transaction timeline */}
      <div className="bg-white rounded-xl border border-ink-200 shadow-sm overflow-hidden">
        <div className="px-5 py-4 border-b border-ink-100 flex items-center gap-2">
          <Receipt className="h-5 w-5 text-ink-500" />
          <h3 className="font-semibold text-lg text-ink-900 tracking-tight">
            Transaction History
          </h3>
        </div>

        {payment.transactions.length === 0 ? (
          <div className="px-5 py-12 text-center text-ink-400 text-sm">
            No transactions recorded yet.
          </div>
        ) : (
          <div className="divide-y divide-ink-100">
            {payment.transactions.map((txn) => (
              <div key={txn.id} className="px-5 py-4 flex items-start justify-between gap-4">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-bold text-ink-900 text-lg">
                      {formatCurrency(txn.amount)}
                    </span>
                    <span className="px-2 py-0.5 rounded-full bg-ink-100 text-ink-600 text-[11px] font-semibold uppercase tracking-wide">
                      {MODE_LABELS[txn.payment_mode] || txn.payment_mode}
                    </span>
                  </div>
                  <p className="text-sm text-ink-500 mt-1">
                    {formatDate(txn.transaction_date)}
                    {txn.reference_no && (
                      <span className="font-mono ml-2">· Ref: {txn.reference_no}</span>
                    )}
                  </p>
                  {txn.notes && <p className="text-sm text-ink-600 mt-1">{txn.notes}</p>}
                </div>
                <button
                  onClick={() => handleDeleteTransaction(txn.id)}
                  className="text-ink-300 hover:text-red-600 transition-colors p-1"
                  title="Delete transaction"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Add transaction modal */}
      {showAddTxn && (
        <AddTransactionModal payment={payment} onClose={() => setShowAddTxn(false)} />
      )}
    </div>
  );
};