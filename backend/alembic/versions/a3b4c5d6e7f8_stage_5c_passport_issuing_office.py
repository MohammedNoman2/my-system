"""Stage 5-C: add issuing_office to passport_booking_details

Revision ID: a3b4c5d6e7f8
Revises: f2a3b4c5d6e7
Create Date: 2026-11-26 01:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "a3b4c5d6e7f8"
down_revision: Union[str, None] = "f2a3b4c5d6e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("passport_booking_details"):
        return
    cols = {c["name"] for c in inspector.get_columns("passport_booking_details")}
    if "issuing_office" not in cols:
        with op.batch_alter_table("passport_booking_details") as batch_op:
            batch_op.add_column(sa.Column("issuing_office", sa.String(length=100), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("passport_booking_details"):
        return
    cols = {c["name"] for c in inspector.get_columns("passport_booking_details")}
    if "issuing_office" in cols:
        with op.batch_alter_table("passport_booking_details") as batch_op:
            batch_op.drop_column("issuing_office")
