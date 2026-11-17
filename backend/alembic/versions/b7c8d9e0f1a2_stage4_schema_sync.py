"""stage4_schema_sync

Revision ID: b7c8d9e0f1a2
Revises: 655210f0992f
Create Date: 2026-11-17 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b7c8d9e0f1a2"
down_revision: Union[str, Sequence[str], None] = "655210f0992f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """مزامنة مخطط قاعدة البيانات مع تعديلات المرحلة الرابعة (Stage 4-A إلى 4-D) بأمان على SQLite وPostgreSQL."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "bookings" in tables:
        booking_cols = {c["name"] for c in inspector.get_columns("bookings")}
        if "credit_applied" not in booking_cols:
            with op.batch_alter_table("bookings") as batch_op:
                batch_op.add_column(
                    sa.Column(
                        "credit_applied",
                        sa.Numeric(precision=10, scale=2),
                        nullable=False,
                        server_default="0.00",
                    )
                )

    if "customers" in tables:
        indexes = inspector.get_indexes("customers")
        has_non_unique_phone_idx = False
        for idx in indexes:
            cols = idx.get("column_names") or []
            if cols == ["phone_number"]:
                if idx.get("unique"):
                    op.drop_index(idx["name"], table_name="customers")
                else:
                    has_non_unique_phone_idx = True
        if not has_non_unique_phone_idx:
            op.create_index(
                "ix_customers_phone_number",
                "customers",
                ["phone_number"],
                unique=False,
            )


def downgrade() -> None:
    """التراجع الآمن عن عمود credit_applied."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "bookings" in tables:
        booking_cols = {c["name"] for c in inspector.get_columns("bookings")}
        if "credit_applied" in booking_cols:
            with op.batch_alter_table("bookings") as batch_op:
                batch_op.drop_column("credit_applied")
