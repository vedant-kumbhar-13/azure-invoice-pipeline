import { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  ArrowDownCircle,
  ArrowUpCircle,
  AlertTriangle,
  Clock,
  Plus,
  Download,
  Search,
} from 'lucide-react';
import { Skeleton } from '../components/ui/skeleton';
import { PaymentStatCard } from '../components/PaymentStatCard';
import { PaymentStatusBadge, PaymentDirectionBadge } from '../components/PaymentStatusBadge';
import { AddManualPaymentModal } from '../components/AddManualPaymentModal';
import { usePayments, usePaymentStats } from '../hooks/usePayments';
import { exportPaymentsXlsx } from '../api/payments';
import { formatCurrency, formatDate } from '../utils/formatters';
import type { PaymentDirection, PaymentStatus } from '../types/payment';

const DIRECTION_FILTERS: { label: string; value: PaymentDirection | 'All' }[] = [
  { label: 'All', value: 'All' },
  { label: 'Receivable', value: 'RECEIVABLE' },
  { label: 'Payable', value: 'PAYABLE' },
];

const STATUS_FILTERS: { label: string; value: PaymentStatus | 'All' }[] = [
  { label: 'All', value: 'All' },
  { label: 'Pending', value: 'PENDING' },
  { label: 'Partial', value: 'PARTIAL' },
  { label: 'Paid', value: 'PAID' },
  { label: 'Overdue', value: 'OVERDUE' },
  { label: 'Cancelled', value: 'CANCELLED' },
];

export const PaymentsPage = () => {
  const [direction, setDirection] = useState<PaymentDirection | 'All'>('All');
  const [status, setStatus] = useState<PaymentStatus | 'All'>('All');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [showManualModal, setShowManualModal] = useState(false);
  const [exporting, setExporting] = useState(false);

  const { data: stats, isLoading: statsLoading } = usePaymentStats();

  const { data: paymentsData, isLoading: listLoading } = usePayments({
    direction: direction === 'All' ? undefined : direction,
    status: status === 'All' ? undefined : status,
    search: search.trim() || undefined,
    page,
    page_size: 20,
  });

  const items = paymentsData?.items || [];
  const totalPages = paymentsData?.total_pages || 1;

  const handleExport = async () => {
    setExporting(true);
    try {
      const blob = await exportPaymentsXlsx({
        direction: direction === 'All' ? undefined : direction,
        status: status === 'All' ? undefined : status,
      });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'payments.xlsx';
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } finally {
      setExporting(false);
    }
  };

  const getRowStyling = (s: PaymentStatus) => {
    if (s === 'PAID') return 'status-stripe-green bg-green-50/30 hover:bg-ink-50';
    if (s === 'PARTIAL') return 'status-stripe-amber bg-amber-50/30 hover:bg-ink-50';
    if (s === 'OVERDUE') return 'status-stripe-red bg-red-50/30 hover:bg-ink-50';
    if (s === 'PENDING') return 'status-stripe-blue bg-blue-50/20 hover:bg-ink-50';
    return 'status-stripe-gray bg-white hover:bg-ink-50';
  };

  return (
    <div className="max-w-7xl mx-auto space-y-8 pb-12">
      {/* Page Header */}
      <header className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-ink-900 tracking-tight">Payments</h1>
          <p className="text-ink-500 text-sm mt-1">
            Track receivables, payables, and due dates
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleExport}
            disabled={exporting}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-ink-200 bg-white text-ink-700 text-sm font-medium hover:bg-ink-50 transition-colors disabled:opacity-50"
          >
            <Download className="h-4 w-4" />
            {exporting ? 'Exporting...' : 'Export'}
          </button>
          <button
            onClick={() => setShowManualModal(true)}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 transition-colors"
          >
            <Plus className="h-4 w-4" />
            Add Manual Entry
          </button>
        </div>
      </header>

      {/* Stats Strip */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
        <PaymentStatCard
          label="Receivable"
          value={formatCurrency(stats?.total_receivable ?? 0)}
          subValue={stats ? `${stats.due_next_7_days_count} due in 7 days (combined)` : undefined}
          icon={ArrowDownCircle}
          iconBg="bg-emerald-100"
          iconColor="text-emerald-600"
          valueColor="text-emerald-600"
          isLoading={statsLoading}
        />
        <PaymentStatCard
          label="Payable"
          value={formatCurrency(stats?.total_payable ?? 0)}
          subValue={stats ? `${stats.pending_count + stats.partial_count} pending records` : undefined}
          icon={ArrowUpCircle}
          iconBg="bg-rose-100"
          iconColor="text-rose-600"
          valueColor="text-rose-600"
          isLoading={statsLoading}
        />
        <PaymentStatCard
          label="Overdue"
          value={formatCurrency(
            (stats?.total_receivable_overdue ?? 0) + (stats?.total_payable_overdue ?? 0)
          )}
          subValue={stats ? `${stats.overdue_count} overdue record(s)` : undefined}
          icon={AlertTriangle}
          iconBg="bg-red-100"
          iconColor="text-red-600"
          valueColor="text-red-600"
          isLoading={statsLoading}
        />
        <PaymentStatCard
          label="Due Next 7 Days"
          value={formatCurrency(stats?.due_next_7_days ?? 0)}
          subValue={stats ? `${stats.due_next_7_days_count} payment(s)` : undefined}
          icon={Clock}
          iconBg="bg-amber-100"
          iconColor="text-amber-600"
          valueColor="text-amber-600"
          isLoading={statsLoading}
        />
      </div>

      {/* Filters + List */}
      <div className="bg-white rounded-xl border border-ink-200 shadow-sm overflow-hidden flex flex-col">
        {/* Filter bar */}
        <div className="px-5 py-4 border-b border-ink-100 flex flex-wrap items-center gap-3 bg-white shrink-0">
          {/* Direction tabs */}
          <div className="flex items-center gap-1 bg-ink-50 rounded-lg p-1">
            {DIRECTION_FILTERS.map((f) => (
              <button
                key={f.value}
                onClick={() => {
                  setDirection(f.value);
                  setPage(1);
                }}
                className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                  direction === f.value
                    ? 'bg-white text-ink-900 shadow-sm'
                    : 'text-ink-500 hover:text-ink-700'
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>

          {/* Status dropdown */}
          <select
            value={status}
            onChange={(e) => {
              setStatus(e.target.value as PaymentStatus | 'All');
              setPage(1);
            }}
            className="px-3 py-1.5 rounded-lg border border-ink-200 text-sm text-ink-700 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {STATUS_FILTERS.map((f) => (
              <option key={f.value} value={f.value}>
                {f.label}
              </option>
            ))}
          </select>

          {/* Search */}
          <div className="relative flex-1 min-w-[200px] max-w-xs">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-ink-400" />
            <input
              type="text"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              placeholder="Search counterparty..."
              className="w-full pl-9 pr-3 py-1.5 rounded-lg border border-ink-200 text-sm text-ink-700 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>

        {/* Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm whitespace-nowrap">
            <thead className="bg-ink-50/50 text-ink-500 font-medium">
              <tr>
                <th className="px-5 py-3 border-b border-ink-100 font-medium">Counterparty</th>
                <th className="px-5 py-3 border-b border-ink-100 font-medium text-center">Direction</th>
                <th className="px-5 py-3 border-b border-ink-100 font-medium text-right">Total</th>
                <th className="px-5 py-3 border-b border-ink-100 font-medium text-right">Balance</th>
                <th className="px-5 py-3 border-b border-ink-100 font-medium text-center">Status</th>
                <th className="px-5 py-3 border-b border-ink-100 font-medium text-right">Due Date</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ink-100 text-ink-900">
              {listLoading ? (
                Array.from({ length: 5 }).map((_, i) => (
                  <tr key={i}>
                    <td colSpan={6} className="px-5 py-3.5">
                      <Skeleton className="h-6 w-full" />
                    </td>
                  </tr>
                ))
              ) : items.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-5 py-12 text-center text-ink-400">
                    No payment records found. They are created automatically when
                    invoices are approved, or add a manual entry above.
                  </td>
                </tr>
              ) : (
                items.map((p) => (
                  <tr
                    key={p.id}
                    className={`transition-colors cursor-pointer ${getRowStyling(p.status)}`}
                  >
                    <td className="px-5 py-3.5">
                      <Link to={`/payments/${p.id}`} className="font-medium hover:text-blue-600">
                        {p.counterparty_name || 'Unknown'}
                      </Link>
                      {p.is_manual && (
                        <span className="ml-2 text-[10px] uppercase tracking-wide text-ink-400 font-semibold">
                          Manual
                        </span>
                      )}
                    </td>
                    <td className="px-5 py-3.5 text-center">
                      <PaymentDirectionBadge direction={p.direction} />
                    </td>
                    <td className="px-5 py-3.5 text-right font-mono font-medium">
                      {formatCurrency(p.total_amount)}
                    </td>
                    <td className="px-5 py-3.5 text-right font-mono font-medium">
                      {formatCurrency(p.balance)}
                    </td>
                    <td className="px-5 py-3.5 text-center">
                      <PaymentStatusBadge status={p.status} />
                    </td>
                    <td className="px-5 py-3.5 text-right text-ink-500">
                      {p.due_date ? formatDate(p.due_date) : '—'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="px-5 py-4 border-t border-ink-100 flex items-center justify-between">
            <span className="text-sm text-ink-500">
              Page {page} of {totalPages} · {paymentsData?.total} total
            </span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="px-3 py-1.5 rounded-lg border border-ink-200 text-sm font-medium text-ink-700 hover:bg-ink-50 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                Previous
              </button>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className="px-3 py-1.5 rounded-lg border border-ink-200 text-sm font-medium text-ink-700 hover:bg-ink-50 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Manual entry modal */}
      {showManualModal && (
        <AddManualPaymentModal onClose={() => setShowManualModal(false)} />
      )}
    </div>
  );
};