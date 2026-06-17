"""add counterparty email to payment records

Revision ID: 002_add_counterparty_email
Revises: 001_add_payment_tracking
Create Date: 2026-06-17 00:00:00.000000

This migration adds a single column: counterparty_email on payment_records.
Used as the reminder recipient for RECEIVABLE payments (the counterparty
owes us, so they receive the reminder to pay). For PAYABLE payments this
field is informational only — reminders always go to the org's own email.
"""

from alembic import op
import sqlalchemy as sa


revision = "002_add_counterparty_email"
down_revision = "001_add_payment_tracking"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("payment_records") as batch_op:
        batch_op.add_column(
            sa.Column("counterparty_email", sa.String(255), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("payment_records") as batch_op:
        batch_op.drop_column("counterparty_email")