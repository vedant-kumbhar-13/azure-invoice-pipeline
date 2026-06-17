"""add payment tracking tables

Revision ID: 001_add_payment_tracking
Revises: (set this to your latest existing revision ID)
Create Date: 2024-01-01 00:00:00.000000

INSTRUCTIONS BEFORE RUNNING:
  1. Open this file and find the `down_revision` variable below.
  2. Run: alembic heads
     This prints your current latest revision ID (e.g. "a1b2c3d4e5f6").
  3. Replace the placeholder string in down_revision with that ID.
     If you have no existing migrations yet, set down_revision = None.
  4. Then run: alembic upgrade head
"""

from alembic import op
import sqlalchemy as sa


# ── Revision identifiers ─────────────────────────────────────────────────────
revision = "001_add_payment_tracking"

# IMPORTANT: Replace the string below with your actual latest revision ID.
# Run `alembic heads` to find it. If no prior migrations exist, set to None.
down_revision = "89b302330b22"

branch_labels = None
depends_on = None


def upgrade() -> None:

    # ── 1. Add new columns to existing `users` table ─────────────────────────
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("org_name",    sa.String(255), nullable=True))
        batch_op.add_column(sa.Column("org_gstin",   sa.String(15),  nullable=True))
        batch_op.add_column(sa.Column("org_address", sa.String(500), nullable=True))
        batch_op.add_column(sa.Column("org_email",   sa.String(255), nullable=True))

    # Index on org_gstin for fast direction detection lookups
    op.create_index("ix_users_org_gstin", "users", ["org_gstin"], unique=False)

    # ── 2. Add new columns to existing `invoices` table ──────────────────────
    with op.batch_alter_table("invoices") as batch_op:
        batch_op.add_column(sa.Column("payment_direction",  sa.String(12),  nullable=True))
        batch_op.add_column(sa.Column("payment_due_date",   sa.Date(),      nullable=True))
        batch_op.add_column(sa.Column("counterparty_name",  sa.String(255), nullable=True))
        batch_op.add_column(sa.Column("counterparty_gstin", sa.String(15),  nullable=True))

    op.create_index("ix_invoices_payment_direction",  "invoices", ["payment_direction"],  unique=False)
    op.create_index("ix_invoices_payment_due_date",   "invoices", ["payment_due_date"],   unique=False)
    op.create_index("ix_invoices_counterparty_gstin", "invoices", ["counterparty_gstin"], unique=False)

    # ── 3. Create `payment_records` table ────────────────────────────────────
    op.create_table(
        "payment_records",
        sa.Column("id",           sa.String(36),  primary_key=True),
        sa.Column("invoice_id",   sa.String(36),  sa.ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True),
        sa.Column("user_id",      sa.String(36),  sa.ForeignKey("users.id",    ondelete="CASCADE"),  nullable=False),
        sa.Column("direction",    sa.String(12),  nullable=False),
        sa.Column("status",       sa.String(12),  nullable=False, server_default="PENDING"),
        sa.Column("total_amount", sa.Float(),     nullable=False),
        sa.Column("paid_amount",  sa.Float(),     nullable=False, server_default="0"),
        sa.Column("balance",      sa.Float(),     nullable=False),
        sa.Column("due_date",     sa.Date(),      nullable=True),
        sa.Column("paid_date",    sa.Date(),      nullable=True),
        sa.Column("counterparty_name",  sa.String(255), nullable=True),
        sa.Column("counterparty_gstin", sa.String(15),  nullable=True),
        sa.Column("is_manual",          sa.Boolean(),   nullable=False, server_default="0"),
        sa.Column("manual_description", sa.String(500), nullable=True),
        sa.Column("manual_invoice_ref", sa.String(100), nullable=True),
        sa.Column("notes",     sa.Text(),      nullable=True),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_payment_records_invoice_id",  "payment_records", ["invoice_id"],  unique=False)
    op.create_index("ix_payment_records_user_id",     "payment_records", ["user_id"],     unique=False)
    op.create_index("ix_payment_records_direction",   "payment_records", ["direction"],   unique=False)
    op.create_index("ix_payment_records_status",      "payment_records", ["status"],      unique=False)
    op.create_index("ix_payment_records_due_date",    "payment_records", ["due_date"],    unique=False)

    # ── 4. Create `payment_transactions` table ───────────────────────────────
    op.create_table(
        "payment_transactions",
        sa.Column("id",                sa.String(36), primary_key=True),
        sa.Column("payment_record_id", sa.String(36), sa.ForeignKey("payment_records.id", ondelete="CASCADE"), nullable=False),
        sa.Column("amount",            sa.Float(),    nullable=False),
        sa.Column("payment_mode",      sa.String(20), nullable=False, server_default="BANK_TRANSFER"),
        sa.Column("reference_no",      sa.String(100), nullable=True),
        sa.Column("transaction_date",  sa.Date(),     nullable=False),
        sa.Column("proof_blob_name",   sa.String(255), nullable=True),
        sa.Column("notes",             sa.Text(),     nullable=True),
        sa.Column("recorded_by",       sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at",        sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_payment_transactions_record_id", "payment_transactions", ["payment_record_id"], unique=False)

    # ── 5. Create `reminder_settings` table ──────────────────────────────────
    op.create_table(
        "reminder_settings",
        sa.Column("id",      sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("days_before_due",              sa.String(50), nullable=False, server_default="7,3,1"),
        sa.Column("email_enabled",                sa.Boolean(),  nullable=False, server_default="1"),
        sa.Column("in_app_enabled",               sa.Boolean(),  nullable=False, server_default="1"),
        sa.Column("remind_on_due_date",           sa.Boolean(),  nullable=False, server_default="1"),
        sa.Column("overdue_reminder_enabled",     sa.Boolean(),  nullable=False, server_default="1"),
        sa.Column("overdue_reminder_interval_days", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_reminder_settings_user_id", "reminder_settings", ["user_id"], unique=True)

    # ── 6. Create `reminder_logs` table ──────────────────────────────────────
    op.create_table(
        "reminder_logs",
        sa.Column("id",                sa.String(36), primary_key=True),
        sa.Column("payment_record_id", sa.String(36), sa.ForeignKey("payment_records.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id",           sa.String(36), sa.ForeignKey("users.id",           ondelete="CASCADE"), nullable=False),
        sa.Column("reminder_type",     sa.String(20), nullable=False),
        sa.Column("days_offset",       sa.Integer(),  nullable=False),
        sa.Column("channel",           sa.String(10), nullable=False),
        sa.Column("channel_status",    sa.String(10), nullable=False, server_default="PENDING"),
        sa.Column("error_detail",      sa.String(500), nullable=True),
        sa.Column("sent_at",           sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_at",   sa.DateTime(timezone=True), nullable=True),
        sa.Column("snoozed_until",     sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at",        sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_reminder_logs_payment_record_id", "reminder_logs", ["payment_record_id"], unique=False)
    op.create_index("ix_reminder_logs_user_id",           "reminder_logs", ["user_id"],           unique=False)

    # ── 7. Create `in_app_notifications` table ───────────────────────────────
    op.create_table(
        "in_app_notifications",
        sa.Column("id",                sa.String(36), primary_key=True),
        sa.Column("user_id",           sa.String(36), sa.ForeignKey("users.id",           ondelete="CASCADE"), nullable=False),
        sa.Column("reminder_log_id",   sa.String(36), sa.ForeignKey("reminder_logs.id",   ondelete="CASCADE"), nullable=True),
        sa.Column("payment_record_id", sa.String(36), sa.ForeignKey("payment_records.id", ondelete="CASCADE"), nullable=True),
        sa.Column("title",    sa.String(255), nullable=False),
        sa.Column("body",     sa.String(500), nullable=False),
        sa.Column("icon",     sa.String(20),  nullable=False, server_default="bell"),
        sa.Column("is_read",  sa.Boolean(),   nullable=False, server_default="0"),
        sa.Column("read_at",  sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_in_app_notifications_user_id",  "in_app_notifications", ["user_id"],  unique=False)
    op.create_index("ix_in_app_notifications_is_read",  "in_app_notifications", ["is_read"],  unique=False)
    op.create_index("ix_in_app_notifications_created_at", "in_app_notifications", ["created_at"], unique=False)


def downgrade() -> None:
    # Drop in reverse order of creation (respect FK dependencies)
    op.drop_table("in_app_notifications")
    op.drop_table("reminder_logs")
    op.drop_table("reminder_settings")
    op.drop_table("payment_transactions")
    op.drop_table("payment_records")

    # Remove added columns from invoices
    with op.batch_alter_table("invoices") as batch_op:
        batch_op.drop_column("counterparty_gstin")
        batch_op.drop_column("counterparty_name")
        batch_op.drop_column("payment_due_date")
        batch_op.drop_column("payment_direction")

    # Remove added columns from users
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("org_email")
        batch_op.drop_column("org_address")
        batch_op.drop_column("org_gstin")
        batch_op.drop_column("org_name")