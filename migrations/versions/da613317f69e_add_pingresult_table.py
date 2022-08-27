"""Add PingResult table

Revision ID: da613317f69e
Revises: e3745a3d757f
Create Date: 2022-08-25 14:45:19.547121

"""
import sqlalchemy as sa
from alembic import op

import medb.model_util


# revision identifiers, used by Alembic.
revision = "da613317f69e"
down_revision = "e3745a3d757f"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "ping_result",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("time", medb.model_util.TZDateTime(), nullable=False),
        sa.Column(
            "ping_ms",
            sa.Numeric(precision=7, scale=3, asdecimal=False),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("ping_result")
    # ### end Alembic commands ###