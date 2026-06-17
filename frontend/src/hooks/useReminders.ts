import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getReminderSettings,
  updateReminderSettings,
  listReminderLogs,
  snoozeReminders,
  acknowledgeReminder,
  runReminderScanNow,
} from '../api/reminders';
import type { ReminderSettingsUpdate } from '../types/payment';

// ── Reminder settings ──────────────────────────────────────────────────────

export const useReminderSettings = () => {
  return useQuery({
    queryKey: ['reminders', 'settings'],
    queryFn: getReminderSettings,
  });
};

export const useUpdateReminderSettings = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: ReminderSettingsUpdate) => updateReminderSettings(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reminders', 'settings'] });
    },
  });
};

// ── Reminder log (history) ────────────────────────────────────────────────

export const useReminderLogs = (params?: { payment_record_id?: string; limit?: number }) => {
  return useQuery({
    queryKey: ['reminders', 'logs', params],
    queryFn: () => listReminderLogs(params),
  });
};

// ── Snooze ─────────────────────────────────────────────────────────────────

export const useSnoozeReminders = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      paymentRecordId,
      snoozeDays,
    }: {
      paymentRecordId: string;
      snoozeDays?: number;
    }) => snoozeReminders(paymentRecordId, snoozeDays),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reminders'] });
      queryClient.invalidateQueries({ queryKey: ['notifications'] });
    },
  });
};

// ── Acknowledge ────────────────────────────────────────────────────────────

export const useAcknowledgeReminder = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (reminderLogId: string) => acknowledgeReminder(reminderLogId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reminders', 'logs'] });
    },
  });
};

// ── Manual trigger (debug/testing) ────────────────────────────────────────

export const useRunReminderScanNow = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: runReminderScanNow,
    onSuccess: () => {
      // A scan may have created new notifications and flipped statuses
      queryClient.invalidateQueries({ queryKey: ['payments'] });
      queryClient.invalidateQueries({ queryKey: ['notifications'] });
      queryClient.invalidateQueries({ queryKey: ['reminders'] });
    },
  });
};