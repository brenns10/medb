"""Migrate to new Transaction tree

Revision ID: 095a817a8431
Revises: 2204b9aa0cfe
Create Date: 2022-11-12 11:31:52.791006

"""
import typing as t

import sqlalchemy as sa
from alembic import op

from medb.shiso.models import CATEGORIES_V1
from medb.shiso.models import CATEGORIES_V2
from medb.shiso.models import LEAF_CATEGORIES_V2


def get_v2_to_v1_map() -> t.Dict[str, str]:
    """
    Mapping v2 to v1 is not impossible, but there is info loss. Most parent
    categories were originally a category in v1. To make the mapping, default to
    selecting the parent category, but ignore that if we have a hardcoded
    alternative.
    """
    mappings = {
        "Reimbursement": "Income",
        "Rent": "Rent",
        "Donation": "Gifts",
        "Bars": "Dining",
        "Alcohol Store": "Groceries",
        "Other Alcohol": "Groceries",
        "Charity": "Gifts",
        "Wedding": "Shopping",
        "Visiting Home": "Vacation",
        "Conference Travel": "Vacation",
        "Vacation": "Vacation",
        "": "",
    }
    for top_level, leaves in CATEGORIES_V2.items():
        for leaf in leaves:
            if leaf not in mappings:
                assert top_level in CATEGORIES_V1, top_level
                mappings[leaf] = top_level
    return mappings


def get_v1_to_v2_map() -> t.Dict[str, str]:
    """
    Every category in v1 exists in v2, but some are now inner categories with
    multiple children. To migrate them, use the last child, which is always the
    "catch-all" for the category.
    """
    # Unfortunately, empty-string got used as a null value, only in the case
    # where a pending transaction got deleted and we review the deletion. It
    # would be nicer to use a real SQL NULL, but I don't want to rock the boat
    # here.
    mappings = {"": ""}
    for category in CATEGORIES_V1:
        if category in LEAF_CATEGORIES_V2:
            mappings[category] = category
        else:
            mappings[category] = CATEGORIES_V2[category][-1]
    return mappings


# revision identifiers, used by Alembic.
revision = "095a817a8431"
down_revision = "2204b9aa0cfe"
branch_labels = None
depends_on = None


def upgrade():
    # First, we alter the table using a batch operation.
    with op.batch_alter_table("transaction_review", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "category_v2",
                sa.String(length=100),
                nullable=False,
                server_default="NONE",
            )
        )

    # Now, we can go ahead and migrate the category values themselves.
    text = sa.text(
        "UPDATE transaction_review SET category_v2 = :new WHERE category = :old"
    )
    for old, new in get_v1_to_v2_map().items():
        print(f"Migrate {old!r} to {new!r}")
        op.execute(text.bindparams(new=new, old=old))

    # Now we drop the old column and rename the new one.
    with op.batch_alter_table("transaction_review", schema=None) as batch_op:
        batch_op.drop_column("category")
    with op.batch_alter_table("transaction_review", schema=None) as batch_op:
        batch_op.alter_column("category_v2", new_column_name="category")


def downgrade():
    # Do the reverse of upgrade: create a category_v1 column, set it
    # appropriately, and then cleanup.
    with op.batch_alter_table("transaction_review", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "category_v1",
                sa.String(length=100),
                nullable=False,
                server_default="NONE",
            )
        )

    # Now, we can go ahead and migrate the category values themselves.
    text = sa.text(
        "UPDATE transaction_review SET category_v1 = :new WHERE category = :old"
    )
    for old, new in get_v2_to_v1_map().items():
        print(f"Migrate {old!r} to {new!r}")
        op.execute(text.bindparams(new=new, old=old))

    # Now we drop the old column and rename the new one.
    with op.batch_alter_table("transaction_review", schema=None) as batch_op:
        batch_op.drop_column("category")
    with op.batch_alter_table("transaction_review", schema=None) as batch_op:
        batch_op.alter_column("category_v1", new_column_name="category")
