"""add_email_unique_constraint_to_users

Revision ID: f3a1b2c4d5e6
Revises: 46d447a247c0
Create Date: 2026-05-10 12:26:00.000000

BUG-D4: The application-level email uniqueness check (db.query(...).first())
has a race condition — two concurrent registrations with the same email can
both pass the check before either commits. This migration adds a database-level
UNIQUE constraint on users.email so the DB enforces uniqueness atomically.

The ORM already declares unique=True on the email column; this migration
ensures that constraint physically exists in the database for deployments
that were created before this fix or that use SQLite in dev (where
create_all may not have added the constraint).

The auth.py register endpoint is updated separately to catch IntegrityError
and return a clean HTTP 400 instead of a 500.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3a1b2c4d5e6'
down_revision: Union[str, Sequence[str], None] = '46d447a247c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add DB-level UNIQUE constraint on users.email (BUG-D4)."""
    # Use batch_alter_table for SQLite compatibility (SQLite doesn't support
    # ALTER TABLE ADD CONSTRAINT directly).
    with op.batch_alter_table('users', schema=None) as batch_op:
        # The index may already exist if the table was created via create_all()
        # with unique=True on the column. create_unique_constraint is idempotent
        # on PostgreSQL; on SQLite, batch mode recreates the table.
        batch_op.create_unique_constraint('uq_users_email', ['email'])


def downgrade() -> None:
    """Remove DB-level UNIQUE constraint on users.email."""
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_constraint('uq_users_email', type_='unique')
