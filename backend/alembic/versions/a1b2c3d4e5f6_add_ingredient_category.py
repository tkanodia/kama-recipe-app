"""add ingredient category column

Revision ID: a1b2c3d4e5f6
Revises: 8d4f50202906
Create Date: 2026-04-25 22:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "8d4f50202906"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("ingredients", sa.Column("category", sa.String(32), nullable=False, server_default="other"))
    op.create_index("ix_ingredients_category", "ingredients", ["category"])


def downgrade() -> None:
    op.drop_index("ix_ingredients_category", table_name="ingredients")
    op.drop_column("ingredients", "category")
