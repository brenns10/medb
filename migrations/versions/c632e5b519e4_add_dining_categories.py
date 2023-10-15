"""Add and rename dining categories

Revision ID: c632e5b519e4
Revises: d383714f967b
Create Date: 2023-10-15 15:50:48.433864

"""
import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "c632e5b519e4"
down_revision = "d383714f967b"
branch_labels = None
depends_on = None


new_categories = [
    "Dinner Takeout",
    "Social Dining",
    "Fancy Dinner",
]

misc_category = "Other Dining"


def upgrade():
    pass


def downgrade():
    # Now, we can go ahead and migrate the category values themselves.
    text = sa.text(
        "UPDATE transaction_review SET category = :new WHERE category = :old"
    )
    for old in new_categories:
        print(f"Downgrade {old!r} back to {misc_category!r}")
        op.execute(text.bindparams(new=misc_category, old=old))
