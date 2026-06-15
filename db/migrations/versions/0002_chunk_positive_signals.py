"""chunks.positive_signals reinforcement counter (phase 7)

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-15

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # FR-13 reinforcement signal: bumped when a cited answer is marked helpful.
    op.add_column(
        "chunks",
        sa.Column(
            "positive_signals", sa.Integer, nullable=False, server_default=sa.text("0")
        ),
    )


def downgrade() -> None:
    op.drop_column("chunks", "positive_signals")
