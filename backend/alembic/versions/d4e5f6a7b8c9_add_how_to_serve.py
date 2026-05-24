"""add how_to_serve column

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-04-27 10:15:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("canonical_recipes", sa.Column("how_to_serve", sa.Text, nullable=True))
    op.add_column("recipe_candidates", sa.Column("how_to_serve", sa.Text, nullable=True))
    op.add_column("draft_recipes", sa.Column("how_to_serve", sa.Text, nullable=True))


def downgrade() -> None:
    op.drop_column("draft_recipes", "how_to_serve")
    op.drop_column("recipe_candidates", "how_to_serve")
    op.drop_column("canonical_recipes", "how_to_serve")
