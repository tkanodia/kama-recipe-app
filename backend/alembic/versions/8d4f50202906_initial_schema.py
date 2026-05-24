"""initial_schema

Revision ID: 8d4f50202906
Revises:
Create Date: 2026-04-11 22:20:17.770756

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8d4f50202906"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from app.core.database import Base
    import app.models.tables  # noqa: F401

    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    from app.core.database import Base
    import app.models.tables  # noqa: F401

    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
