"""Add active and original date

Revision ID: ac84aec426a6
Revises: 2f16c0a586fa
Create Date: 2021-11-03 21:16:38.108400

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.sql import column
from sqlalchemy.sql import table


# revision identifiers, used by Alembic.
revision = "ac84aec426a6"
down_revision = "2f16c0a586fa"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "user_plaid_transaction",
        sa.Column(
            "active", sa.Boolean(), server_default=sa.text("1"), nullable=False
        ),
    )
    UserPlaidTransaction = table(
        "user_plaid_transaction",
        column("date"),
        column("original_date"),
    )
    op.add_column(
        "user_plaid_transaction",
        sa.Column(
            "original_date",
            sa.Date(),
            server_default="1969-01-01",
            nullable=False,
        ),
    )
    op.execute(
        UserPlaidTransaction.update().values(
            original_date=UserPlaidTransaction.c.date
        )
    )


def downgrade():
    op.drop_column("user_plaid_transaction", "original_date")
    op.drop_column("user_plaid_transaction", "active")
