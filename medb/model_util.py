#!/usr/bin/env python3
import datetime
from decimal import Decimal

import sqlalchemy.types as types
from sqlalchemy.dialects.sqlite.base import SQLiteDialect


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


class SafeNumeric(types.TypeDecorator):

    impl = types.Numeric

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
        if not isinstance(value, Decimal):
            raise TypeError("Numeric literals should be decimal")
        if isinstance(dialect, SQLiteDialect):
            return int(value.shift(self._scale))
        else:
            return value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(dialect, SQLiteDialect):
            return Decimal(value) / (10**self._scale)
        else:
            return Decimal(value)
