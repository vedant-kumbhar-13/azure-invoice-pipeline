import type { LucideIcon } from 'lucide-react';
import { Skeleton } from './ui/skeleton';

interface PaymentStatCardProps {
  label: string;
  value: string;
  subValue?: string;
  icon: LucideIcon;
  iconBg: string;   // e.g. 'bg-green-100'
  iconColor: string; // e.g. 'text-green-600'
  valueColor?: string; // e.g. 'text-green-600'
  isLoading?: boolean;
}

/**
 * Stat card matching the style of DashboardPage's "Total Processed" /
 * "Auto-Approved" cards — white rounded-xl card, icon chip top-right,
 * large bold number.
 */
export const PaymentStatCard = ({
  label,
  value,
  subValue,
  icon: Icon,
  iconBg,
  iconColor,
  valueColor = 'text-ink-900',
  isLoading,
}: PaymentStatCardProps) => {
  if (isLoading) {
    return (
      <div className="bg-white rounded-xl border border-ink-200 shadow-sm p-6 flex flex-col justify-between">
        <Skeleton className="h-20 w-full" />
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl border border-ink-200 shadow-sm p-6 flex flex-col justify-between">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-ink-500 text-xs font-medium uppercase tracking-wide">{label}</h2>
        <div className={`p-2 ${iconBg} rounded-lg`}>
          <Icon className={`h-5 w-5 ${iconColor}`} />
        </div>
      </div>
      <div className={`text-4xl font-bold ${valueColor}`}>{value}</div>
      {subValue && <p className="text-xs text-ink-400 mt-2">{subValue}</p>}
    </div>
  );
};