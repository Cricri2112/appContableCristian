"""Tabla configuracion (email de destino del resumen diario)

Revision ID: f4514efae956
Revises: e099aa7f38d8
Create Date: 2026-11-13 11:19:41.594559

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f4514efae956'
down_revision: Union[str, None] = 'e099aa7f38d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Etapa 6: ajustes editables desde la app (clave/valor). Hoy guarda el
    # email de destino del resumen diario (F10, Configuración → Notificaciones).
    op.create_table('configuracion',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('clave', sa.Text(), nullable=False),
    sa.Column('valor', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('clave')
    )


def downgrade() -> None:
    op.drop_table('configuracion')
