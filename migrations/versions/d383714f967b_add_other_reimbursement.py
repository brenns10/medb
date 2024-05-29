"""Add other reimbursement

Revision ID: d383714f967b
Revises: 095a817a8431
Create Date: 2022-11-12 19:38:01.533172

"""

import sqlalchemy as sa
from alembic import op

from medb.model_util import SafeNumeric

# revision identifiers, used by Alembic.
revision = "d383714f967b"
down_revision = "095a817a8431"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("transaction_review", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "other_reimbursement",
                SafeNumeric(16, 3),
                server_default="0",
                nullable=False,
            )
        )


def downgrade():
    with op.batch_alter_table("transaction_review", schema=None) as batch_op:
        batch_op.drop_column("other_reimbursement")
