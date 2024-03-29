# -*- coding: utf-8 -*-
"""
Database models for speedtest
"""
from sqlalchemy import Integer
from sqlalchemy import Numeric
from sqlalchemy import String

from medb.database import Model
from medb.extensions import db
from medb.model_util import TZDateTime
from medb.model_util import utcnow


class SpeedTestResult(Model):
    __tablename__ = "speedtest_result"

    id = db.Column(Integer, primary_key=True)
    time = db.Column(TZDateTime(), nullable=False, default=utcnow)

    download_bps = db.Column(Integer, nullable=False)
    upload_bps = db.Column(Integer, nullable=False)
    ping_ms = db.Column(
        Numeric(precision=7, scale=3, asdecimal=False), nullable=False
    )
    server_name = db.Column(String, nullable=False)
    server_id = db.Column(String, nullable=False)


class FastResult(Model):
    __tablename__ = "fast_result"

    id = db.Column(Integer, primary_key=True)
    time = db.Column(TZDateTime(), nullable=False, default=utcnow)
    download_mbps = db.Column(
        Numeric(precision=10, scale=3, asdecimal=False), nullable=False
    )


class IpCheckResult(Model):
    __tablename__ = "ipcheck_result"

    id = db.Column(Integer, primary_key=True)
    time = db.Column(TZDateTime(), nullable=False, default=utcnow)
    ipv4 = db.Column(String(15), nullable=True)
    ipv6 = db.Column(String(39), nullable=True)


class PingResult(Model):
    __tablename__ = "ping_result"

    id = db.Column(Integer, primary_key=True)
    time = db.Column(TZDateTime(), nullable=False, default=utcnow)
    ping_ms = db.Column(
        Numeric(precision=7, scale=3, asdecimal=False), nullable=True
    )
    v6_ping_ms = db.Column(
        Numeric(precision=7, scale=3, asdecimal=False), nullable=True
    )
