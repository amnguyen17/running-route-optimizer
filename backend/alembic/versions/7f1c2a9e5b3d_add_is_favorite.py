"""add is_favorite to route_records

Revision ID: 7f1c2a9e5b3d
Revises: 3cda899c9a6b
Create Date: 2026-08-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7f1c2a9e5b3d'
down_revision: Union[str, None] = '3cda899c9a6b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'route_records',
        sa.Column('is_favorite', sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column('route_records', 'is_favorite')
