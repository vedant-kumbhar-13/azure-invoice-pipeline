import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Bell, AlertTriangle, CheckCheck } from 'lucide-react';
import {
  useNotifications,
  useMarkNotificationRead,
  useMarkAllNotificationsRead,
} from '../hooks/useNotifications';
import { formatDate } from '../utils/formatters';

/**
 * Bell icon with unread count badge + dropdown list.
 * Polls every 60s via useNotifications. Designed to sit in the header
 * next to the user menu.
 */
export const NotificationBell = () => {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  const { data } = useNotifications({ limit: 15 });
  const markRead = useMarkNotificationRead();
  const markAllRead = useMarkAllNotificationsRead();

  const unreadCount = data?.unread_count ?? 0;
  const items = data?.items ?? [];

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const handleItemClick = async (notificationId: string, paymentRecordId: string | null, isRead: boolean) => {
    if (!isRead) {
      await markRead.mutateAsync(notificationId);
    }
    setOpen(false);
    if (paymentRecordId) {
      navigate(`/payments/${paymentRecordId}`);
    }
  };

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="relative p-2 rounded-lg hover:bg-ink-100 transition-colors"
        aria-label="Notifications"
      >
        <Bell className="h-5 w-5 text-ink-600" />
        {unreadCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 flex items-center justify-center min-w-[18px] h-[18px] px-1 rounded-full bg-red-500 text-white text-[10px] font-bold">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 mt-2 w-80 bg-white rounded-xl border border-ink-200 shadow-lg z-50 overflow-hidden">
          {/* Header */}
          <div className="px-4 py-3 border-b border-ink-100 flex items-center justify-between">
            <h3 className="font-semibold text-sm text-ink-900">Notifications</h3>
            {unreadCount > 0 && (
              <button
                onClick={() => markAllRead.mutate()}
                className="inline-flex items-center gap-1 text-xs font-medium text-blue-600 hover:text-blue-800 transition-colors"
              >
                <CheckCheck className="h-3.5 w-3.5" />
                Mark all read
              </button>
            )}
          </div>

          {/* List */}
          <div className="max-h-96 overflow-y-auto divide-y divide-ink-100">
            {items.length === 0 ? (
              <div className="px-4 py-8 text-center text-sm text-ink-400">
                No notifications yet.
              </div>
            ) : (
              items.map((n) => (
                <button
                  key={n.id}
                  onClick={() => handleItemClick(n.id, n.payment_record_id, n.is_read)}
                  className={`w-full text-left px-4 py-3 hover:bg-ink-50 transition-colors flex items-start gap-3 ${
                    !n.is_read ? 'bg-blue-50/50' : ''
                  }`}
                >
                  <div
                    className={`mt-0.5 p-1.5 rounded-lg shrink-0 ${
                      n.icon === 'alert' ? 'bg-red-100' : 'bg-blue-100'
                    }`}
                  >
                    {n.icon === 'alert' ? (
                      <AlertTriangle className="h-3.5 w-3.5 text-red-600" />
                    ) : (
                      <Bell className="h-3.5 w-3.5 text-blue-600" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className={`text-sm ${!n.is_read ? 'font-semibold text-ink-900' : 'font-medium text-ink-700'}`}>
                      {n.title}
                    </p>
                    <p className="text-xs text-ink-500 mt-0.5 line-clamp-2">{n.body}</p>
                    <p className="text-[11px] text-ink-400 mt-1">{formatDate(n.created_at)}</p>
                  </div>
                  {!n.is_read && (
                    <span className="w-2 h-2 rounded-full bg-blue-500 shrink-0 mt-1.5" />
                  )}
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
};