import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  listNotifications,
  markNotificationRead,
  markAllNotificationsRead,
} from '../api/reminders';

/**
 * Powers the notification bell icon.
 * Polls every 60s so the unread count stays reasonably fresh without
 * being aggressive (reminder scans only run every few hours anyway).
 */
export const useNotifications = (params?: { limit?: number; unread_only?: boolean }) => {
  return useQuery({
    queryKey: ['notifications', params],
    queryFn: () => listNotifications(params),
    refetchInterval: 60 * 1000, // 60s polling
    refetchOnWindowFocus: true,
  });
};

// ── Mark one notification as read ─────────────────────────────────────────

export const useMarkNotificationRead = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (notificationId: string) => markNotificationRead(notificationId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications'] });
    },
  });
};

// ── Mark all as read ───────────────────────────────────────────────────────

export const useMarkAllNotificationsRead = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: markAllNotificationsRead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications'] });
    },
  });
};