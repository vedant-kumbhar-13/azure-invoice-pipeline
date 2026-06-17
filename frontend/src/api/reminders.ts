/**
 * Reminders + Notifications API calls.
 */
import { apiClient } from './client';
import type {
  ReminderSettings,
  ReminderSettingsUpdate,
  ReminderLog,
  NotificationListResponse,
  InAppNotification,
} from '../types/payment';

// ── Reminder settings ──────────────────────────────────────────────────────

export const getReminderSettings = async (): Promise<ReminderSettings> => {
  const response = await apiClient.get('/reminders/settings');
  return response.data;
};

export const updateReminderSettings = async (
  data: ReminderSettingsUpdate
): Promise<ReminderSettings> => {
  const response = await apiClient.put('/reminders/settings', data);
  return response.data;
};

// ── Reminder log (history) ────────────────────────────────────────────────

export const listReminderLogs = async (params?: {
  payment_record_id?: string;
  limit?: number;
}): Promise<ReminderLog[]> => {
  const response = await apiClient.get('/reminders/', { params });
  return response.data;
};

// ── Snooze ─────────────────────────────────────────────────────────────────

export const snoozeReminders = async (
  paymentRecordId: string,
  snoozeDays: number = 1
): Promise<{ message: string; payment_record_id: string }> => {
  const response = await apiClient.post(`/reminders/${paymentRecordId}/snooze`, {
    snooze_days: snoozeDays,
  });
  return response.data;
};

// ── Acknowledge ────────────────────────────────────────────────────────────

export const acknowledgeReminder = async (reminderLogId: string): Promise<ReminderLog> => {
  const response = await apiClient.post(`/reminders/${reminderLogId}/acknowledge`);
  return response.data;
};

// ── Manual trigger (debug) ────────────────────────────────────────────────

export const runReminderScanNow = async (): Promise<{
  message: string;
  summary: Record<string, unknown>;
}> => {
  const response = await apiClient.post('/reminders/run-now');
  return response.data;
};

// ════════════════════════════════════════════════════════════════════════
// Notifications (bell icon)
// ════════════════════════════════════════════════════════════════════════

export const listNotifications = async (params?: {
  limit?: number;
  unread_only?: boolean;
}): Promise<NotificationListResponse> => {
  const response = await apiClient.get('/notifications/', { params });
  return response.data;
};

export const markNotificationRead = async (
  notificationId: string
): Promise<InAppNotification> => {
  const response = await apiClient.post(`/notifications/${notificationId}/read`);
  return response.data;
};

export const markAllNotificationsRead = async (): Promise<{ message: string }> => {
  const response = await apiClient.post('/notifications/mark-all-read');
  return response.data;
};