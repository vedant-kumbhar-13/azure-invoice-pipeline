/**
 * TypeScript types for the payment tracking feature.
 * Mirrors backend/app/schemas/payment.py
 */

export type PaymentDirection = 'RECEIVABLE' | 'PAYABLE' | 'UNKNOWN';

export type PaymentStatus = 'PENDING' | 'PARTIAL' | 'PAID' | 'OVERDUE' | 'CANCELLED';

export type PaymentMode =
  | 'BANK_TRANSFER'
  | 'UPI'
  | 'CASH'
  | 'CHEQUE'
  | 'NEFT'
  | 'RTGS'
  | 'DD'
  | 'OTHER';

export type ReminderType = 'DUE_SOON' | 'DUE_TODAY' | 'OVERDUE';

export type NotificationChannel = 'IN_APP' | 'EMAIL';

export type ChannelStatus = 'SENT' | 'FAILED' | 'PENDING';

// ── PaymentTransaction ────────────────────────────────────────────────────

export interface PaymentTransaction {
  id: string;
  payment_record_id: string;
  amount: number;
  payment_mode: PaymentMode;
  reference_no: string | null;
  transaction_date: string; // ISO date
  proof_blob_name: string | null;
  notes: string | null;
  recorded_by: string | null;
  created_at: string; // ISO datetime
}

export interface PaymentTransactionCreate {
  amount: number;
  payment_mode: PaymentMode;
  reference_no?: string;
  transaction_date: string; // ISO date
  notes?: string;
}

// ── PaymentRecord ──────────────────────────────────────────────────────────

export interface PaymentRecord {
  id: string;
  invoice_id: string | null;
  user_id: string;
  direction: PaymentDirection;
  status: PaymentStatus;
  total_amount: number;
  paid_amount: number;
  balance: number;
  due_date: string | null; // ISO date
  paid_date: string | null; // ISO date
  counterparty_name: string | null;
  counterparty_gstin: string | null;
  counterparty_email: string | null;
  is_manual: boolean;
  manual_description: string | null;
  manual_invoice_ref: string | null;
  notes: string | null;
  created_by: string | null;
  created_at: string; // ISO datetime
  updated_at: string; // ISO datetime
  transactions: PaymentTransaction[];
}

export interface PaymentRecordListResponse {
  items: PaymentRecord[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface PaymentRecordCreate {
  direction: PaymentDirection;
  total_amount: number;
  due_date?: string;
  counterparty_name?: string;
  counterparty_gstin?: string;
  counterparty_email?: string;
  manual_description?: string;
  manual_invoice_ref?: string;
  notes?: string;
}

export interface PaymentRecordUpdate {
  direction?: PaymentDirection;
  status?: PaymentStatus;
  due_date?: string;
  paid_date?: string;
  counterparty_name?: string;
  counterparty_gstin?: string;
  counterparty_email?: string;
  notes?: string;
  manual_description?: string;
  manual_invoice_ref?: string;
}

// ── Stats (dashboard) ─────────────────────────────────────────────────────

export interface PaymentStats {
  total_receivable: number;
  total_receivable_overdue: number;
  total_received: number;
  total_payable: number;
  total_payable_overdue: number;
  total_paid_out: number;
  pending_count: number;
  overdue_count: number;
  paid_count: number;
  partial_count: number;
  due_next_7_days: number;
  due_next_7_days_count: number;
}

// ── Reminder settings ──────────────────────────────────────────────────────

export interface ReminderSettings {
  id: string;
  user_id: string;
  days_before_due: string; // e.g. "7,3,1"
  email_enabled: boolean;
  in_app_enabled: boolean;
  remind_on_due_date: boolean;
  overdue_reminder_enabled: boolean;
  overdue_reminder_interval_days: number;
  created_at: string;
  updated_at: string;
}

export interface ReminderSettingsUpdate {
  days_before_due?: string;
  email_enabled?: boolean;
  in_app_enabled?: boolean;
  remind_on_due_date?: boolean;
  overdue_reminder_enabled?: boolean;
  overdue_reminder_interval_days?: number;
}

// ── Reminder log ───────────────────────────────────────────────────────────

export interface ReminderLog {
  id: string;
  payment_record_id: string;
  user_id: string;
  reminder_type: ReminderType | 'SNOOZE';
  days_offset: number;
  channel: NotificationChannel;
  channel_status: ChannelStatus;
  error_detail: string | null;
  sent_at: string | null;
  acknowledged_at: string | null;
  snoozed_until: string | null;
  created_at: string;
}

// ── In-app notifications (bell icon) ──────────────────────────────────────

export interface InAppNotification {
  id: string;
  user_id: string;
  reminder_log_id: string | null;
  payment_record_id: string | null;
  title: string;
  body: string;
  icon: string;
  is_read: boolean;
  read_at: string | null;
  created_at: string;
}

export interface NotificationListResponse {
  items: InAppNotification[];
  unread_count: number;
}

// ── Org profile (auth) ────────────────────────────────────────────────────

export interface OrgProfileUpdate {
  org_name?: string;
  org_gstin?: string;
  org_address?: string;
  org_email?: string;
}

export interface UserProfile {
  id: string;
  email: string;
  api_key: string | null;
  org_name: string | null;
  org_gstin: string | null;
  org_address: string | null;
  org_email: string | null;
}