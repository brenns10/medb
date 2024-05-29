"""Add speedtest

Revision ID: b22150ed0eb0
Revises: 53509453132a
Create Date: 2021-11-09 15:23:09.676556

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "b22150ed0eb0"
down_revision = "53509453132a"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "speedtest_result",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("time", sa.DateTime(), nullable=False),
        sa.Column("download_bps", sa.Integer(), nullable=False),
        sa.Column("upload_bps", sa.Integer(), nullable=False),
        sa.Column(
            "ping_ms",
            sa.Numeric(precision=7, scale=3, asdecimal=False),
            nullable=False,
        ),
        sa.Column("server_name", sa.String(), nullable=False),
        sa.Column("server_id", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("speedtest_result")
    # ### end Alembic commands ###
