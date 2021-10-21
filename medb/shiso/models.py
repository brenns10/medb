# -*- coding: utf-8 -*-
"""
Database models for "shiso"
"""
import enum
import datetime
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

from medb.database import Model
from medb.extensions import db
from medb.user.models import User


def utcnow():
    return datetime.datetime.now(datetime.timezone.utc)


class TZDateTime(types.TypeDecorator):
    impl = types.DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            if not value.tzinfo:
                raise TypeError("tzinfo is required")
            value = value.astimezone(datetime.timezone.utc).replace(
                tzinfo=None
            )
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            value = value.replace(tzinfo=datetime.timezone.utc)
        return value


class UserPlaidItem(Model):
    __tablename__ = "user_plaid_item"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('plaid_items', lazy=True))

    access_token = Column(String(100), nullable=False)
    item_id = Column(String(100), nullable=False)
    institution_name = Column(String, nullable=False)


class UserPlaidAccount(Model):
    __tablename__ = "user_plaid_account"

    id = Column(Integer, primary_key=True)
    item_id = Column(Integer, ForeignKey('user_plaid_item.id'), nullable=False)

    account_id = Column(String(100), nullable=False)
    item: UserPlaidItem = db.relationship(
        'UserPlaidItem', backref=db.backref('accounts', lazy=True))

    name = Column(String(), nullable=False)
    kind = Column(String(10), nullable=False)
    sync_start = Column(Date, nullable=True)
    sync_end = Column(Date, nullable=True)
    updated = Column(
        TZDateTime(), nullable=False, default=utcnow, onupdate=utcnow,
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
            raise TypeError('Numeric literals should be decimal')
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
    online = 'online'
    in_store = 'in store'
    other = 'other'


class Transaction(Model):
    __tablename__ = "user_plaid_transaction"

    id = Column(Integer, primary_key=True)
    account_id = Column(
        Integer, ForeignKey('user_plaid_account.id'), nullable=False)

    plaid_txn_id = Column(String(100), nullable=False)
    amount = Column(SafeNumeric(16, 3), nullable=False)
    posted = Column(Boolean, nullable=False)
    name = Column(String, nullable=False)
    date = Column(Date, nullable=False)

    plaid_payment_channel = Column(
        Enum(
            PaymentChannel,
            values_callable=lambda obj: [e.value for e in obj]
        ),
        nullable=False
    )
    plaid_payment_meta = Column(String, nullable=False)  # json
    plaid_merchant_name = Column(String, nullable=True)
    plaid_location = Column(String, nullable=False)  # json
    plaid_authorized_date = Column(Date, nullable=True)
    plaid_category_id = Column(String(100), nullable=False)

    updated = Column(
        TZDateTime(), nullable=False, default=utcnow, onupdate=utcnow,
    )

    account = db.relationship(
        'UserPlaidAccount', backref=db.backref('transactions', lazy=True),
    )


class TransactionReview(Model):
    __tablename__ = "transaction_review"

    id = Column(Integer, primary_key=True)
    transaction_id = Column(
        Integer, ForeignKey("user_plaid_transaction.id"), nullable=False)

    reimbursement_amount = Column(SafeNumeric(16, 3), nullable=False)
    category = Column(String(100), nullable=False)
    notes = Column(String, nullable=True)
    updated = Column(
        TZDateTime(), nullable=False, default=utcnow, onupdate=utcnow,
    )


class Balance(Model):
    __tablename__ = "account_balance"
    __table_args__ = (
        db.UniqueConstraint('account_id', 'date'),
    )

    id = Column(Integer, primary_key=True)
    account_id = Column(
        Integer, ForeignKey('user_plaid_account.id'), nullable=False)

    amount = Column(Numeric(16, 3), nullable=False)
    date = Column(Date, nullable=False)
