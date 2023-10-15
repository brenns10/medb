# -*- coding: utf-8 -*-
"""
Database models for "shiso"
"""
import enum
import itertools

from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy import Date
from sqlalchemy import Enum
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.sql import expression

from medb.database import Model
from medb.extensions import db
from medb.model_util import SafeNumeric
from medb.model_util import TZDateTime
from medb.model_util import utcnow


CATEGORIES_V1 = [
    "Transport",
    "Entertainment",
    "Vacation",
    "Dining",
    "Groceries",
    "Rent",
    "Bills & Utilities",
    "Medical",
    "Shopping",
    "Gifts",
    "Income",
    "Transfer",
    "Pet",
]

CATEGORIES_V2 = {
    "Transport": [
        "Car Expenses",
        "Bike Expenses",
        "Public Transit",
        "Ride Share",
        "Bike Share",
        "Other Transport",
    ],
    "Entertainment": [
        "Streaming Subscription",
        "Other Entertainment",
    ],
    "Dining": [
        "Coffee & Boba",
        "Lunch",
        "Dinner Takeout",
        "Social Dining",
        "Fancy Dinner",
        "Other Dining",
    ],
    "Alcohol": [
        "Bars",
        "Alcohol Store",
        "Other Alcohol",
    ],
    "Bills & Utilities": [
        "Rent",
        "Internet",
        "Cell Phone",
        "Cloud Service",
        "Donation",
        "Other Bill or Utility",
    ],
    "Shopping": [
        "Household Staples",
        "Plants & Plant Stuff",
        "Hobby Purchases",
        "Clothing",
        "Gifts",
        "Other Shopping",
    ],
    "Medical": [
        "Medical",
    ],
    "Travel Expenses": [
        "Visiting Home",
        "Conference Travel",
        "Vacation",
    ],
    "Wedding": [
        "Wedding",
    ],
    "Groceries": [
        "Groceries",
    ],
    "Charity": [
        "Charity",
    ],
    "Pet": [
        "Pet",
    ],
    "Income": [
        "Income",
    ],
    "Reimbursement": [
        "Reimbursement",
    ],
    "Transfer": [
        "Transfer",
    ],
}

# List of leaf categories
LEAF_CATEGORIES_V2 = list(itertools.chain.from_iterable(CATEGORIES_V2.values()))

# List of inner categories
INNER_CATEGORIES_V2 = list(CATEGORIES_V2.keys())

# All categories: inner/outer
ALL_CATEGORIES_V2 = list(set(LEAF_CATEGORIES_V2 + INNER_CATEGORIES_V2))

# Map leaf categories to their parents
CATEGORY_PARENT_V2 = {}
for parent, leaves in CATEGORIES_V2.items():
    for leaf in leaves:
        CATEGORY_PARENT_V2[leaf] = parent


class UserPlaidItem(Model):
    __tablename__ = "user_plaid_item"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    user = db.relationship("User", backref=db.backref("plaid_items", lazy=True))

    access_token = Column(String(100), nullable=False)
    item_id = Column(String(100), nullable=False)
    institution_name = Column(String, nullable=False)


class UserPlaidAccount(Model):
    __tablename__ = "user_plaid_account"

    id = Column(Integer, primary_key=True)
    item_id = Column(Integer, ForeignKey("user_plaid_item.id"), nullable=False)

    account_id = Column(String(100), nullable=False)
    item: UserPlaidItem = db.relationship(
        "UserPlaidItem", backref=db.backref("accounts", lazy=True)
    )

    name = Column(String(), nullable=False)
    kind = Column(String(10), nullable=False)
    sync_start = Column(Date, nullable=True)
    sync_end = Column(Date, nullable=True)
    updated = Column(
        TZDateTime(),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )


class PaymentChannel(enum.Enum):
    online = "online"
    in_store = "in store"
    other = "other"


class Transaction(Model):
    __tablename__ = "user_plaid_transaction"

    id = Column(Integer, primary_key=True)
    account_id = Column(
        Integer, ForeignKey("user_plaid_account.id"), nullable=False
    )

    active = Column(Boolean, nullable=False, server_default=expression.true())
    """Does this transaction row still exist in Plaid?

    If active=false, the transaction is hidden from the reports and transaction
    views. However, inactive rows retain their review row. Setting active=false
    should be accompanied by a mark_updated(), which will show the transaction
    once more for review, so the user can acknowledge its deletion.
    """

    plaid_txn_id = Column(String(100), nullable=False)
    amount = Column(SafeNumeric(16, 3), nullable=False)
    posted = Column(Boolean, nullable=False)
    name = Column(String, nullable=False)
    date = Column(Date, nullable=False)
    """The date field which Plaid reports.

    The date field may change over time - it starts as the transaction date, and
    then becomes the "posted" date. This means transactions "move around" in the
    table, which is not really good for the user, so we also store original_date.
    We use date whenever we need to synchronize with Plaid. We use original_date
    when fetching and displaying data for users.
    """

    original_date = Column(Date, nullable=False)
    """The first date associated with this transaction.

    Since the date column can change, this field holds the original value of the
    date column. Since it's more likely to be the actual day that the user
    swiped (or inserted (or tapped)) their card, we use this for user-facing
    reporting.
    """

    plaid_payment_channel = Column(
        Enum(
            PaymentChannel, values_callable=lambda obj: [e.value for e in obj]
        ),
        nullable=False,
    )
    plaid_payment_meta = Column(String, nullable=False)  # json
    plaid_merchant_name = Column(String, nullable=True)
    plaid_location = Column(String, nullable=False)  # json
    plaid_authorized_date = Column(Date, nullable=True)
    plaid_category_id = Column(String(100), nullable=False)

    updated = Column(
        TZDateTime(),
        nullable=False,
        default=utcnow,
    )

    subscription_id = Column(Integer, nullable=True)
    subscription = db.relationship(
        "Subscription",
        backref=db.backref("transactions", lazy="select"),
    )

    account = db.relationship(
        "UserPlaidAccount",
        backref=db.backref("transactions", lazy="select"),
    )

    def mark_updated(self):
        self.updated = utcnow()

    @property
    def needs_review(self):
        return self.review is None or self.review.updated < self.updated

    __table_args__ = (
        db.ForeignKeyConstraint(
            ["subscription_id"],
            ["subscription.id"],
            name="transaction__fk_subscription_id",
        ),
    )


class TransactionReview(Model):
    __tablename__ = "transaction_review"

    id = Column(Integer, primary_key=True)
    transaction_id = Column(
        Integer,
        ForeignKey("user_plaid_transaction.id"),
        nullable=False,
        unique=True,
    )
    transaction = db.relationship(
        "Transaction",
        backref=db.backref("review", uselist=False),
        lazy="select",
    )

    reimbursement_amount = Column(SafeNumeric(16, 3), nullable=False)
    other_reimbursement = Column(
        SafeNumeric(16, 3), nullable=False, server_default="0"
    )
    category = Column(String(100), nullable=False)
    notes = Column(String, nullable=True)
    updated = Column(
        TZDateTime(),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    reviewed_amount = Column(SafeNumeric(16, 3), nullable=True)
    reviewed_posted = Column(Boolean, nullable=True)
    reviewed_name = Column(String, nullable=True)
    reviewed_date = Column(Date, nullable=True)
    reviewed_plaid_merchant_name = Column(String, nullable=True)

    def mark_updated(self):
        self.updated = utcnow()

    # Newly added constraints should be named, so that they can be migrated
    # properly.
    __table_args__ = (
        db.UniqueConstraint(
            "transaction_id",
            name="transaction_review__transaction_id__unique",
        ),
    )


class Subscription(Model):
    """
    Represents a monthly subscription which is automatically tracked

    Most of the "metadata" of a subscription is determined simply by looking at
    the most recent transaction in it. (e.g. subscription price, day of month).
    """

    __tablename__ = "subscription"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)

    # Subscriptions are associated with an account to reduce false positives
    account_id = Column(
        Integer, ForeignKey("user_plaid_account.id"), nullable=False
    )

    # Subscriptions are tracked via regular expression match.
    regex = Column(String, nullable=False)

    # Auto-detected transactions are flagged as new.
    is_new = Column(Boolean, nullable=False)

    # All name patterns which "look like" subscriptions to the detector will
    # appear in the database. However, only "tracked" ones (i.e. those confirmed
    # by the user) will show on the UI.
    is_tracked = Column(Boolean, nullable=False)

    # Active subscriptions - should still charge every month. Inactive
    # subscriptions should not - if they do, it's a warning.
    is_active = Column(Boolean, nullable=False)

    account = db.relationship(
        "UserPlaidAccount",
        backref=db.backref("subscriptions", lazy="select"),
    )
