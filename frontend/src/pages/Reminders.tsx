import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Bell, Mail, Settings as SettingsIcon, History, Save, ArrowRight } from 'lucide-react';
import { Skeleton } from '../components/ui/skeleton';
import { useReminderSettings, useUpdateReminderSettings, useReminderLogs } from '../hooks/useReminders';
import { formatDate } from '../utils/formatters';

const STANDARD_PRESETS: { label: string; value: string }[] = [
  { label: '7, 3, 1 days before (default)', value: '7,3,1' },
  { label: '14, 7, 3, 1 days before', value: '14,7,3,1' },
  { label: '3, 1 days before', value: '3,1' },
  { label: '1 day before only', value: '1' },
];

const REMINDER_TYPE_LABELS: Record<string, string> = {
  DUE_SOON: 'Due soon',
  DUE_TODAY: 'Due today',
  OVERDUE: 'Overdue',
  SNOOZE: 'Snoozed',
};

const CHANNEL_LABELS: Record<string, string> = {
  IN_APP: 'In-app',
  EMAIL: 'Email',
};

const STATUS_STYLES: Record<string, string> = {
  SENT: 'bg-green-100 text-green-700',
  FAILED: 'bg-red-100 text-red-700',
  PENDING: 'bg-ink-100 text-ink-500',
};

export const RemindersPage = () => {
  const { data: settings, isLoading: settingsLoading } = useReminderSettings();
  const updateSettings = useUpdateReminderSettings();
  const { data: logs, isLoading: logsLoading } = useReminderLogs({ limit: 30 });

  const [daysBeforeDue, setDaysBeforeDue] = useState('7,3,1');
  const [emailEnabled, setEmailEnabled] = useState(true);
  const [inAppEnabled, setInAppEnabled] = useState(true);
  const [remindOnDueDate, setRemindOnDueDate] = useState(true);
  const [overdueEnabled, setOverdueEnabled] = useState(true);
  const [overdueInterval, setOverdueInterval] = useState(3);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (settings) {
      setDaysBeforeDue(settings.days_before_due);
      setEmailEnabled(settings.email_enabled);
      setInAppEnabled(settings.in_app_enabled);
      setRemindOnDueDate(settings.remind_on_due_date);
      setOverdueEnabled(settings.overdue_reminder_enabled);
      setOverdueInterval(settings.overdue_reminder_interval_days);
    }
  }, [settings]);

  const handleSave = async () => {
    await updateSettings.mutateAsync({
      days_before_due: daysBeforeDue,
      email_enabled: emailEnabled,
      in_app_enabled: inAppEnabled,
      remind_on_due_date: remindOnDueDate,
      overdue_reminder_enabled: overdueEnabled,
      overdue_reminder_interval_days: overdueInterval,
    });
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8 pb-12">
      {/* Header */}
      <header>
        <h1 className="text-2xl font-bold text-ink-900 tracking-tight">Reminders</h1>
        <p className="text-ink-500 text-sm mt-1">
          Configure due-date reminders and view sent notifications
        </p>
      </header>

      {/* Settings card */}
      <div className="bg-white rounded-xl border border-ink-200 shadow-sm p-6">
        <div className="flex items-center gap-2 mb-6">
          <SettingsIcon className="h-5 w-5 text-ink-500" />
          <h2 className="font-semibold text-lg text-ink-900 tracking-tight">
            Reminder Settings
          </h2>
        </div>

        {settingsLoading ? (
          <Skeleton className="h-64 w-full" />
        ) : (
          <div className="space-y-6">
            {/* Days before due */}
            <div>
              <label className="block text-sm font-medium text-ink-700 mb-2">
                Remind me before due date
              </label>
              <select
                value={daysBeforeDue}
                onChange={(e) => setDaysBeforeDue(e.target.value)}
                className="w-full sm:w-80 px-3 py-2 rounded-lg border border-ink-200 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {STANDARD_PRESETS.map((p) => (
                  <option key={p.value} value={p.value}>
                    {p.label}
                  </option>
                ))}
                {!STANDARD_PRESETS.some((p) => p.value === daysBeforeDue) && (
                  <option value={daysBeforeDue}>{daysBeforeDue} (custom)</option>
                )}
              </select>
            </div>

            {/* Channels */}
            <div>
              <label className="block text-sm font-medium text-ink-700 mb-2">
                Notification channels
              </label>
              <div className="space-y-3">
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={inAppEnabled}
                    onChange={(e) => setInAppEnabled(e.target.checked)}
                    className="h-4 w-4 rounded border-ink-300 text-blue-600 focus:ring-blue-500"
                  />
                  <Bell className="h-4 w-4 text-ink-500" />
                  <span className="text-sm text-ink-700">In-app notifications (bell icon)</span>
                </label>
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={emailEnabled}
                    onChange={(e) => setEmailEnabled(e.target.checked)}
                    className="h-4 w-4 rounded border-ink-300 text-blue-600 focus:ring-blue-500"
                  />
                  <Mail className="h-4 w-4 text-ink-500" />
                  <span className="text-sm text-ink-700">Email reminders</span>
                </label>
              </div>
            </div>

            {/* Due date + overdue */}
            <div>
              <label className="block text-sm font-medium text-ink-700 mb-2">
                Additional reminders
              </label>
              <div className="space-y-3">
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={remindOnDueDate}
                    onChange={(e) => setRemindOnDueDate(e.target.checked)}
                    className="h-4 w-4 rounded border-ink-300 text-blue-600 focus:ring-blue-500"
                  />
                  <span className="text-sm text-ink-700">Remind on the due date itself</span>
                </label>
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={overdueEnabled}
                    onChange={(e) => setOverdueEnabled(e.target.checked)}
                    className="h-4 w-4 rounded border-ink-300 text-blue-600 focus:ring-blue-500"
                  />
                  <span className="text-sm text-ink-700">Send recurring overdue reminders</span>
                </label>

                {overdueEnabled && (
                  <div className="ml-7 flex items-center gap-2">
                    <span className="text-sm text-ink-500">Every</span>
                    <input
                      type="number"
                      min={1}
                      max={30}
                      value={overdueInterval}
                      onChange={(e) => setOverdueInterval(parseInt(e.target.value) || 1)}
                      className="w-16 px-2 py-1 rounded-lg border border-ink-200 text-sm text-center focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                    <span className="text-sm text-ink-500">day(s) while overdue</span>
                  </div>
                )}
              </div>
            </div>

            {/* Save button */}
            <div className="flex items-center gap-3 pt-2">
              <button
                onClick={handleSave}
                disabled={updateSettings.isPending}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 transition-colors disabled:opacity-50"
              >
                <Save className="h-4 w-4" />
                {updateSettings.isPending ? 'Saving...' : 'Save Settings'}
              </button>
              {saved && (
                <span className="text-sm text-emerald-600 font-medium">Settings saved</span>
              )}
            </div>

            <p className="text-xs text-ink-400 pt-2 border-t border-ink-100">
              Email reminders require SMTP configuration on the server (.env file).
              In-app notifications work regardless of email setup.
            </p>
          </div>
        )}
      </div>

      {/* Reminder history */}
      <div className="bg-white rounded-xl border border-ink-200 shadow-sm overflow-hidden">
        <div className="px-5 py-4 border-b border-ink-100 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <History className="h-5 w-5 text-ink-500" />
            <h2 className="font-semibold text-lg text-ink-900 tracking-tight">
              Recent Reminders
            </h2>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm whitespace-nowrap">
            <thead className="bg-ink-50/50 text-ink-500 font-medium">
              <tr>
                <th className="px-5 py-3 border-b border-ink-100 font-medium">Type</th>
                <th className="px-5 py-3 border-b border-ink-100 font-medium text-center">Channel</th>
                <th className="px-5 py-3 border-b border-ink-100 font-medium text-center">Status</th>
                <th className="px-5 py-3 border-b border-ink-100 font-medium text-right">Sent At</th>
                <th className="px-5 py-3 border-b border-ink-100 font-medium text-right">Payment</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ink-100 text-ink-900">
              {logsLoading ? (
                Array.from({ length: 4 }).map((_, i) => (
                  <tr key={i}>
                    <td colSpan={5} className="px-5 py-3.5">
                      <Skeleton className="h-6 w-full" />
                    </td>
                  </tr>
                ))
              ) : !logs || logs.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-5 py-12 text-center text-ink-400">
                    No reminders sent yet. Reminders run automatically every few hours.
                  </td>
                </tr>
              ) : (
                logs.map((log) => (
                  <tr key={log.id} className="hover:bg-ink-50 transition-colors">
                    <td className="px-5 py-3.5 font-medium">
                      {REMINDER_TYPE_LABELS[log.reminder_type] || log.reminder_type}
                      {log.days_offset !== 0 && (
                        <span className="text-ink-400 ml-1 font-normal">
                          ({Math.abs(log.days_offset)}d {log.days_offset > 0 ? 'before' : 'after'})
                        </span>
                      )}
                    </td>
                    <td className="px-5 py-3.5 text-center text-ink-600">
                      {CHANNEL_LABELS[log.channel] || log.channel}
                    </td>
                    <td className="px-5 py-3.5 text-center">
                      <span
                        className={`inline-flex px-2.5 py-1 rounded-full text-[11px] font-bold uppercase tracking-wider ${
                          STATUS_STYLES[log.channel_status] || 'bg-ink-100 text-ink-500'
                        }`}
                      >
                        {log.channel_status}
                      </span>
                    </td>
                    <td className="px-5 py-3.5 text-right text-ink-500">
                      {log.sent_at ? formatDate(log.sent_at) : '—'}
                    </td>
                    <td className="px-5 py-3.5 text-right">
                      <Link
                        to={`/payments/${log.payment_record_id}`}
                        className="inline-flex items-center gap-1 text-blue-600 hover:text-blue-800 font-medium"
                      >
                        View <ArrowRight className="h-3.5 w-3.5" />
                      </Link>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};