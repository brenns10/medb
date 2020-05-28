# -*- coding: utf-8 -*-
"""
Database models for "shiso"
"""
from sqlalchemy import Column
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String

from medb.database import Model
from medb.extensions import db
from medb.user.models import User


class UserPlaidItem(Model):
    __tablename__ = "user_plaid_item"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    user = db.relationship('User',
        backref=db.backref('plaid_items', lazy=True))

    access_token = Column(String(100), nullable=False)
    item_id = Column(String(100), nullable=False)


class UserPlaidAccount(Model):
    __tablename__ = "user_plaid_account"

    id = Column(Integer, primary_key=True)
    item_id = Column(Integer, ForeignKey('user_plaid_item.id'), nullable=False)

    account_id = Column(String(100), nullable=False)
    account = db.relationship('UserPlaidItem',
        backref=db.backref('accounts', lazy=True))

    name = Column(String(), nullable=False)
    kind = Column(String(10), nullable=False)
