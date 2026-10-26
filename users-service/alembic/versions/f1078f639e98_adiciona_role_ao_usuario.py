"""adiciona role ao usuario

Revision ID: f1078f639e98
Revises: 73656b89186f
Create Date: 2026-09-23 20:24:01.633369

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f1078f639e98'
down_revision: str | Sequence[str] | None = '73656b89186f'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    userrole_enum = sa.Enum('ADMIN', 'USER', name='userrole')
    userrole_enum.create(op.get_bind())

    op.add_column(
        'users',
        sa.Column(
            'role',
            userrole_enum,
            nullable=False,
            server_default='USER',
        ),
    )


def downgrade() -> None:
    op.drop_column('users', 'role')
    op.execute('DROP TYPE userrole')
