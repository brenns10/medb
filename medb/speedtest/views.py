# -*- coding: utf-8 -*-
"""Views for speed testing"""
import datetime
import io
from dataclasses import dataclass
from datetime import timedelta

import matplotlib.pyplot
import matplotlib.style
import pandas as pd
from flask import Blueprint
from flask import make_response
from flask import render_template
from flask_login import login_required
from sqlalchemy.orm import Query
from sqlalchemy.orm import aliased
from sqlalchemy.sql import or_
from sqlalchemy.sql import select

from medb.extensions import db
from medb.model_util import utcnow

from .models import FastResult
from .models import IpCheckResult
from .models import PingResult
from .models import SpeedTestResult

matplotlib.use("agg")
matplotlib.style.use("ggplot")
matplotlib.pyplot.rcParams["figure.figsize"] = (8, 6)

blueprint = Blueprint(
    "speedtest",
    __name__,
    url_prefix="/speedtest",
    static_folder="../static",
)


def sql_to_df(query: Query) -> pd.DataFrame:
    return pd.read_sql(query.statement, db.session.connection())


@dataclass
class SpeedtestSummary:

    recent: SpeedTestResult

    avg_download_1day: float
    avg_upload_1day: float
    avg_ping_1day: float

    avg_download_7day: float
    avg_upload_7day: float
    avg_ping_7day: float

    avg_download_30day: float
    avg_upload_30day: float
    avg_ping_30day: float


def speedtest_stats() -> SpeedtestSummary:
    most_recent = (
        SpeedTestResult.query.order_by(SpeedTestResult.time.desc())
        .limit(1)
        .one()
    )

    kwargs = {"recent": most_recent}

    def agg_days(days):
        res = (
            db.session.query(
                db.func.avg(SpeedTestResult.download_bps).label("avg_download"),
                db.func.avg(SpeedTestResult.upload_bps).label("avg_upload"),
                db.func.avg(SpeedTestResult.ping_ms).label("avg_ping"),
            )
            .filter(SpeedTestResult.time >= utcnow() - timedelta(days=days))
            .one()
        )
        kwargs[f"avg_download_{days}day"] = res.avg_download
        kwargs[f"avg_upload_{days}day"] = res.avg_upload
        kwargs[f"avg_ping_{days}day"] = res.avg_ping

    agg_days(1)
    agg_days(7)
    agg_days(30)

    return SpeedtestSummary(**kwargs)


@dataclass
class FastSummary:

    recent: FastResult
    avg_download_1day: float
    avg_download_7day: float
    avg_download_30day: float


def fast_stats() -> FastSummary:
    most_recent = (
        FastResult.query.order_by(FastResult.time.desc()).limit(1).one()
    )

    kwargs = {"recent": most_recent}

    def agg_days(days):
        res = (
            db.session.query(
                db.func.avg(FastResult.download_mbps).label("avg_download"),
            )
            .filter(FastResult.time >= utcnow() - timedelta(days=days))
            .one()
        )
        kwargs[f"avg_download_{days}day"] = res.avg_download

    agg_days(1)
    agg_days(7)
    agg_days(30)

    return FastSummary(**kwargs)


def ip_history() -> list[IpCheckResult]:
    c1 = aliased(IpCheckResult)
    c2 = aliased(IpCheckResult)
    first = (
        db.session.query(IpCheckResult)
        .order_by(IpCheckResult.id)
        .limit(1)
        .one()
    )
    query = (
        select(c2)
        .where(
            or_(
                c2.ipv4 != c1.ipv4,
                c2.ipv6 != c1.ipv6,
            )
        )
        .join_from(c2, c1, c1.id + 1 == c2.id)
    )
    rows = db.session.execute(query)
    return [first] + [r[0] for r in rows]


@dataclass
class PingSummary:

    recent: PingResult

    avg_v4_1day: float
    lost_v4_1day: int
    avg_v6_1day: float
    lost_v6_1day: int
    count_1day: int

    avg_v4_7day: float
    lost_v4_7day: int
    avg_v6_7day: float
    lost_v6_7day: int
    count_7day: int

    avg_v4_30day: float
    lost_v4_30day: int
    avg_v6_30day: float
    lost_v6_30day: int
    count_30day: int


def ping_results():
    recent = PingResult.query.order_by(PingResult.time.desc()).limit(1).one()
    kwargs = {"recent": recent}

    def agg_days(days):
        start = utcnow()
        since = start - timedelta(days)
        res = (
            db.session.query(
                db.func.avg(PingResult.ping_ms).label("avg_ping_v4"),
                db.func.avg(PingResult.v6_ping_ms).label("avg_ping_v6"),
                db.func.count("*").label("num_pings"),
            )
            .filter(
                PingResult.time >= since,
                PingResult.time < start,
            )
            .one()
        )
        kwargs[f"avg_v4_{days}day"] = res.avg_ping_v4
        kwargs[f"avg_v6_{days}day"] = res.avg_ping_v6
        kwargs[f"count_{days}day"] = res.num_pings
        res = (
            db.session.query(db.func.count("*").label("num"))
            .filter(
                PingResult.time >= since,
                PingResult.time < start,
                PingResult.ping_ms == None,  # noqa
            )
            .one()
        )
        kwargs[f"lost_v4_{days}day"] = res.num
        res = (
            db.session.query(db.func.count("*").label("num"))
            .filter(
                PingResult.time >= since,
                PingResult.time < start,
                PingResult.v6_ping_ms == None,  # noqa
            )
            .one()
        )
        kwargs[f"lost_v6_{days}day"] = res.num

    agg_days(1)
    agg_days(7)
    agg_days(30)
    return PingSummary(**kwargs)


def figure_response(figure):
    bio = io.BytesIO()
    figure.savefig(bio, format="png")
    resp = make_response(bio.getvalue())
    resp.headers.set("Content-Type", "image/png")
    return resp


def fix_tz(df, col="time"):
    local_tz = datetime.datetime.now().astimezone().tzinfo
    # This bizarre line is due to the following:
    # 1. We store times in the database as UTC, but want to present them in the
    #    local timezone.
    # 2. Pandas somehow doesn't support timezone aware datetimes
    # So, we convert from UTC to the local time, and then strip the timezone off
    # of it. This results in the timezone "looking" correct in the plot.
    df[col] = df[col].dt.tz_convert(local_tz).dt.tz_localize(None)


@blueprint.route("/plot/speedtest.png", methods=["GET"])
@login_required
def plot_speedtest_png():
    oldest = utcnow() - datetime.timedelta(days=60)
    query = SpeedTestResult.query.filter(SpeedTestResult.time >= oldest)
    df = sql_to_df(query)
    fix_tz(df)
    df = df.set_index("time")
    df["Upload (Mbps)"] = df["upload_bps"] / 1000000.0
    df["Download (Mbps)"] = df["download_bps"] / 1000000.0
    ax = df[["Upload (Mbps)", "Download (Mbps)"]].plot(style="o")
    ax.set_xlabel("Test Date and Time")
    ax.set_ylabel("Speed")
    return figure_response(ax.figure)


@blueprint.route("/plot/fast.png", methods=["GET"])
@login_required
def plot_fast_png():
    oldest = utcnow() - datetime.timedelta(days=60)
    query = FastResult.query.filter(FastResult.time >= oldest)
    df = sql_to_df(query)
    fix_tz(df)
    df = df.set_index("time")
    df = df.rename(columns={"download_mbps": "Download (Mbps)"})
    ax = df[["Download (Mbps)"]].plot(style="o")
    ax.set_xlabel("Test Date and Time")
    ax.set_ylabel("Speed")
    return figure_response(ax.figure)


def dropped_pings_plot(field, sample="1H"):
    oldest = utcnow() - datetime.timedelta(days=2)
    query = PingResult.query.filter(PingResult.time >= oldest)
    df = sql_to_df(query)
    fix_tz(df)
    df = df.set_index("time")
    fig, ax = matplotlib.pyplot.subplots()
    series = df[field]
    lost = series.isna().resample(sample).sum()
    not_lost = series.resample("1H").count()
    (100 * lost / (lost + not_lost)).plot(ax=ax)
    return figure_response(ax.figure)


@blueprint.route("/plot/ping4.png", methods=["GET"])
@login_required
def plot_ping4():
    return dropped_pings_plot("ping_ms")


@blueprint.route("/plot/ping6.png", methods=["GET"])
@login_required
def plot_ping6():
    return dropped_pings_plot("v6_ping_ms")


@blueprint.route("/results/", methods=["GET"])
@login_required
def speedtest_results():
    return render_template(
        "speedtest/result.html",
        st=speedtest_stats(),
        ping=ping_results(),
        fast=fast_stats(),
        iphist=ip_history(),
    )


@blueprint.app_template_filter("maybe_format")
def maybe_format(fmt, arg):
    if arg:
        return fmt % arg
    else:
        return "None"
