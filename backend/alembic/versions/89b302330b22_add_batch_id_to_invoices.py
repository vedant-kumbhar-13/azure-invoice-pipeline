"""add_batch_id_to_invoices

Revision ID: 89b302330b22
Revises: f3a1b2c4d5e6
Create Date: 2026-05-11 10:32:53.895788

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '89b302330b22'
down_revision: Union[str, Sequence[str], None] = 'f3a1b2c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('invoices', sa.Column('batch_id', sa.String(length=36), nullable=True))
    op.create_index(op.f('ix_invoices_batch_id'), 'invoices', ['batch_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_invoices_batch_id'), table_name='invoices')
    op.drop_column('invoices', 'batch_id')
