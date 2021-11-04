# -*- coding: utf-8 -*-
"""
Database models for "shiso"
"""
import datetime
import enum
from decimal import Decimal as D

import sqlalchemy.types as types
from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy import Date
from sqlalchemy import Enum
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import Numeric
from sqlalchemy import String
from sqlalchemy.dialects.sqlite.base import SQLiteDialect
from sqlalchemy.sql import expression

from medb.database import Model
from medb.extensions import db


TRANSACTION_CATEGORIES = [
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


def utcnow():
    return datetime.datetime.now(datetime.timezone.utc)


class TZDateTime(types.TypeDecorator):
    impl = types.DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            if not value.tzinfo:
                raise TypeError("tzinfo is required")
            value = value.astimezone(datetime.timezone.utc).replace(tzinfo=None)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            value = value.replace(tzinfo=datetime.timezone.utc)
        return value


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


class SafeNumeric(types.TypeDecorator):

    impl = Numeric

    def __init__(self, precision, scale, *args, **kwargs):
        super().__init__(self, precision, scale, *args, **kwargs)
        self._scale = scale

    def load_dialect_impl(self, dialect):
        if isinstance(dialect, SQLiteDialect):
            return dialect.type_descriptor(types.BigInteger())
        else:
            return self.impl

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if not isinstance(value, D):
            raise TypeError("Numeric literals should be decimal")
        if isinstance(dialect, SQLiteDialect):
            return int(value.shift(self._scale))
        else:
            return value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(dialect, SQLiteDialect):
            return D(value) / (10 ** self._scale)
        else:
            return D(value)


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

    account = db.relationship(
        "UserPlaidAccount",
        backref=db.backref("transactions", lazy="select"),
    )

    def mark_updated(self):
        self.updated = utcnow()

    @property
    def needs_review(self):
        return self.review is None or self.review.updated < self.updated


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


class Balance(Model):
    __tablename__ = "account_balance"
    __table_args__ = (db.UniqueConstraint("account_id", "date"),)

    id = Column(Integer, primary_key=True)
    account_id = Column(
        Integer, ForeignKey("user_plaid_account.id"), nullable=False
    )

    amount = Column(Numeric(16, 3), nullable=False)
    date = Column(Date, nullable=False)
