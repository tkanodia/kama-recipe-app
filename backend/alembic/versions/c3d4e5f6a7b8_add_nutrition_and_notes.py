"""add nutrition and notes columns

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-04-27 10:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("canonical_recipes", sa.Column("nutrition", JSONB, nullable=True))
    op.add_column("canonical_recipes", sa.Column("notes", JSONB, server_default="[]", nullable=False))

    op.add_column("recipe_candidates", sa.Column("nutrition", JSONB, nullable=True))
    op.add_column("recipe_candidates", sa.Column("notes", JSONB, server_default="[]", nullable=False))

    op.add_column("draft_recipes", sa.Column("nutrition", JSONB, nullable=True))
    op.add_column("draft_recipes", sa.Column("notes", JSONB, server_default="[]", nullable=False))


def downgrade() -> None:
    op.drop_column("draft_recipes", "notes")
    op.drop_column("draft_recipes", "nutrition")
    op.drop_column("recipe_candidates", "notes")
    op.drop_column("recipe_candidates", "nutrition")
    op.drop_column("canonical_recipes", "notes")
    op.drop_column("canonical_recipes", "nutrition")
