"""Add reviewed copies of fields

Revision ID: 53509453132a
Revises: ac84aec426a6
Create Date: 2021-11-04 00:20:25.132214

"""

import sqlalchemy as sa
from alembic import op

import medb.shiso.models

# revision identifiers, used by Alembic.
revision = "53509453132a"
down_revision = "ac84aec426a6"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "transaction_review",
        sa.Column(
            "reviewed_amount",
            medb.shiso.models.SafeNumeric(16, 3),
            nullable=True,
        ),
    )
    op.add_column(
        "transaction_review",
        sa.Column("reviewed_posted", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "transaction_review",
        sa.Column("reviewed_name", sa.String(), nullable=True),
    )
    op.add_column(
        "transaction_review",
        sa.Column("reviewed_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "transaction_review",
        sa.Column("reviewed_plaid_merchant_name", sa.String(), nullable=True),
    )


def downgrade():
    op.drop_column("transaction_review", "reviewed_plaid_merchant_name")
    op.drop_column("transaction_review", "reviewed_date")
    op.drop_column("transaction_review", "reviewed_name")
    op.drop_column("transaction_review", "reviewed_posted")
    op.drop_column("transaction_review", "reviewed_amount")
