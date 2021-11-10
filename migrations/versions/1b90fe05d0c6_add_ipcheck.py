"""Add ipcheck

Revision ID: 1b90fe05d0c6
Revises: b22150ed0eb0
Create Date: 2021-11-10 13:54:46.094003

"""
import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "1b90fe05d0c6"
down_revision = "b22150ed0eb0"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "ipcheck_result",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("time", sa.DateTime(), nullable=False),
        sa.Column("ipv4", sa.String(length=15), nullable=False),
        sa.Column("ipv6", sa.String(length=39), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("ipcheck_result")
    # ### end Alembic commands ###
