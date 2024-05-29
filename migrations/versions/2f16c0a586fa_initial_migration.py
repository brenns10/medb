"""Initial migration: add unique constraiont to transaction_id

Revision ID: 2f16c0a586fa Initial migration
Revises: transaction_review.transaction_id
Create Date: 2021-11-03 20:15:44.345622

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "2f16c0a586fa"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("transaction_review", schema=None) as batch_op:
        batch_op.create_unique_constraint(
            "transaction_review__transaction_id__unique",
            ["transaction_id"],
        )


def downgrade():
    with op.batch_alter_table("transaction_review", schema=None) as batch_op:
        batch_op.drop_constraint(
            "transaction_review__transaction_id__unique",
            type_="unique",
        )
