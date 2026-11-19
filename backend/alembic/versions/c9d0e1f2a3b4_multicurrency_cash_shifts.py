"""multicurrency_cash_shifts

Revision ID: c9d0e1f2a3b4
Revises: b7c8d9e0f1a2
Create Date: 2026-11-19 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c9d0e1f2a3b4"
down_revision: Union[str, Sequence[str], None] = "b7c8d9e0f1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_cols = [c["name"] for c in inspector.get_columns("cash_shifts")]
    new_columns = [
        ("starting_balance_sar", sa.Column("starting_balance_sar", sa.Numeric(18, 4), nullable=False, server_default="0.0000")),
        ("starting_balance_usd", sa.Column("starting_balance_usd", sa.Numeric(18, 4), nullable=False, server_default="0.0000")),
        ("ending_balance_system_sar", sa.Column("ending_balance_system_sar", sa.Numeric(18, 4), nullable=True)),
        ("ending_balance_system_usd", sa.Column("ending_balance_system_usd", sa.Numeric(18, 4), nullable=True)),
        ("ending_balance_actual_sar", sa.Column("ending_balance_actual_sar", sa.Numeric(18, 4), nullable=True)),
        ("ending_balance_actual_usd", sa.Column("ending_balance_actual_usd", sa.Numeric(18, 4), nullable=True)),
        ("difference_sar", sa.Column("difference_sar", sa.Numeric(18, 4), nullable=True)),
        ("difference_usd", sa.Column("difference_usd", sa.Numeric(18, 4), nullable=True)),
    ]
    with op.batch_alter_table("cash_shifts", schema=None) as batch_op:
        for col_name, col_def in new_columns:
            if col_name not in existing_cols:
                batch_op.add_column(col_def)


def downgrade() -> None:
    with op.batch_alter_table("cash_shifts", schema=None) as batch_op:
        batch_op.drop_column("difference_usd")
        batch_op.drop_column("difference_sar")
        batch_op.drop_column("ending_balance_actual_usd")
        batch_op.drop_column("ending_balance_actual_sar")
        batch_op.drop_column("ending_balance_system_usd")
        batch_op.drop_column("ending_balance_system_sar")
        batch_op.drop_column("starting_balance_usd")
        batch_op.drop_column("starting_balance_sar")
