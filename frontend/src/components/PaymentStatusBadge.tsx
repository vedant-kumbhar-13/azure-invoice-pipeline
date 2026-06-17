import type { PaymentStatus, PaymentDirection } from '../types/payment';

/**
 * Small pill badge for payment status — matches the status-stripe color
 * conventions used in DashboardPage (green/amber/red/blue/gray).
 */
export const PaymentStatusBadge = ({ status }: { status: PaymentStatus }) => {
  const styles: Record<PaymentStatus, string> = {
    PENDING:   'bg-blue-100 text-blue-700',
    PARTIAL:   'bg-amber-100 text-amber-700',
    PAID:      'bg-green-100 text-green-700',
    OVERDUE:   'bg-red-100 text-red-700',
    CANCELLED: 'bg-ink-100 text-ink-500',
  };

  return (
    <span
      className={`inline-flex items-center px-2.5 py-1 rounded-full text-[11px] font-bold uppercase tracking-wider ${styles[status]}`}
    >
      {status}
    </span>
  );
};

/**
 * Direction badge — RECEIVABLE (money in) vs PAYABLE (money out).
 */
export const PaymentDirectionBadge = ({ direction }: { direction: PaymentDirection }) => {
  if (direction === 'RECEIVABLE') {
    return (
      <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-bold uppercase tracking-wider bg-emerald-100 text-emerald-700">
        Receivable
      </span>
    );
  }

  if (direction === 'PAYABLE') {
    return (
      <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-bold uppercase tracking-wider bg-rose-100 text-rose-700">
        Payable
      </span>
    );
  }

  return (
    <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-bold uppercase tracking-wider bg-ink-100 text-ink-500">
      Unknown
    </span>
  );
};