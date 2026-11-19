"""accounting_period_lock

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-11-20 03:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d0e1f2a3b4c5"
down_revision: Union[str, Sequence[str], None] = "c9d0e1f2a3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "settings" not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns("settings")}
    if "accounting_lock_date" not in cols:
        with op.batch_alter_table("settings", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column("accounting_lock_date", sa.Date(), nullable=True)
            )


def downgrade() -> None:
    with op.batch_alter_table("settings", schema=None) as batch_op:
        batch_op.drop_column("accounting_lock_date")
