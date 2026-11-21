"""transport_upgrades_and_infants

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-11-21 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, Sequence[str], None] = "d0e1f2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "transport_booking_details" in tables:
        cols = {c["name"] for c in inspector.get_columns("transport_booking_details")}
        to_add = [
            ("first_middle_name", sa.Column("first_middle_name", sa.String(100), nullable=True)),
            ("last_name", sa.Column("last_name", sa.String(60), nullable=True)),
            ("id_type", sa.Column("id_type", sa.String(30), nullable=False, server_default="national_id")),
        ]
        missing = [col for name, col in to_add if name not in cols]
        if missing:
            with op.batch_alter_table("transport_booking_details", schema=None) as batch_op:
                for col in missing:
                    batch_op.add_column(col)

    if "transport_infants" not in tables and "bookings" in tables:
        op.create_table(
            "transport_infants",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("booking_id", sa.Integer(), sa.ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False),
            sa.Column("full_name", sa.String(150), nullable=False),
            sa.Column("id_type", sa.String(30), nullable=False, server_default="birth_certificate"),
            sa.Column("id_number", sa.String(50), nullable=False, server_default=""),
            sa.Column("birth_date", sa.Date(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_transport_infants_booking_id", "transport_infants", ["booking_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "transport_infants" in tables:
        op.drop_table("transport_infants")
    if "transport_booking_details" in tables:
        cols = {c["name"] for c in inspector.get_columns("transport_booking_details")}
        with op.batch_alter_table("transport_booking_details", schema=None) as batch_op:
            for name in ("id_type", "last_name", "first_middle_name"):
                if name in cols:
                    batch_op.drop_column(name)
