"""generalize_names_and_flight_categories

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-11-22 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f2a3b4c5d6e7"
down_revision: Union[str, Sequence[str], None] = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add_missing_columns(table_name: str, columns_spec: list) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name not in inspector.get_table_names():
        return
    existing = {c["name"] for c in inspector.get_columns(table_name)}
    missing = [col for col_name, col in columns_spec if col_name not in existing]
    if missing:
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            for col in missing:
                batch_op.add_column(col)


def upgrade() -> None:
    _add_missing_columns(
        "flight_booking_details",
        [
            ("first_middle_name", sa.Column("first_middle_name", sa.String(100), nullable=True)),
            ("last_name", sa.Column("last_name", sa.String(60), nullable=True)),
            ("passenger_category", sa.Column("passenger_category", sa.String(20), nullable=False, server_default="adult")),
        ],
    )
    _add_missing_columns(
        "visa_booking_details",
        [
            ("first_middle_name", sa.Column("first_middle_name", sa.String(100), nullable=True)),
            ("last_name", sa.Column("last_name", sa.String(60), nullable=True)),
        ],
    )
    _add_missing_columns(
        "passport_booking_details",
        [
            ("first_middle_name", sa.Column("first_middle_name", sa.String(100), nullable=True)),
            ("last_name", sa.Column("last_name", sa.String(60), nullable=True)),
        ],
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    for tbl, cols_to_drop in (
        ("flight_booking_details", ("passenger_category", "last_name", "first_middle_name")),
        ("visa_booking_details", ("last_name", "first_middle_name")),
        ("passport_booking_details", ("last_name", "first_middle_name")),
    ):
        if tbl in tables:
            existing = {c["name"] for c in inspector.get_columns(tbl)}
            with op.batch_alter_table(tbl, schema=None) as batch_op:
                for col_name in cols_to_drop:
                    if col_name in existing:
                        batch_op.drop_column(col_name)
