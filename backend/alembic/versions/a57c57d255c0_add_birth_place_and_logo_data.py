"""add_birth_place_and_logo_data

Revision ID: a57c57d255c0
Revises: 0dbfa8a9c1fc
Create Date: 2026-09-17 23:19:57.450695

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a57c57d255c0'
down_revision: Union[str, Sequence[str], None] = '0dbfa8a9c1fc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("transport_booking_details") as batch_op:
        batch_op.add_column(sa.Column("birth_place", sa.String(length=100), nullable=False, server_default=""))
    with op.batch_alter_table("settings") as batch_op:
        batch_op.add_column(sa.Column("logo_data", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("settings") as batch_op:
        batch_op.drop_column("logo_data")
    with op.batch_alter_table("transport_booking_details") as batch_op:
        batch_op.drop_column("birth_place")

