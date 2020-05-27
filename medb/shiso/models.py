# -*- coding: utf-8 -*-
"""
Database models for "shiso"
"""
from sqlalchemy import Column
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String

from medb.database import Model
from medb.user.models import User


class UserPlaidItem(Model):
    __tablename__ = "user_plaid_item"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    access_token = Column(String(100), nullable=False)
    item_id = Column(String(100), nullable=False)
