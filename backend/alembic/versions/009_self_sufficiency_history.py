"""add self_sufficiency_history table

Revision ID: 009
Revises: 008
Create Date: 2026-04-11
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "self_sufficiency_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rate_pct", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_self_sufficiency_history_timestamp", "self_sufficiency_history", ["timestamp"])


def downgrade() -> None:
    op.drop_index("ix_self_sufficiency_history_timestamp", table_name="self_sufficiency_history")
    op.drop_table("self_sufficiency_history")
