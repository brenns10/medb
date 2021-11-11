# -*- coding: utf-8 -*-
"""Views for speed testing"""
import datetime

import mpld3
import pandas as pd
from flask import Blueprint
from flask import Markup
from flask import render_template
from flask_login import login_required

from .models import SpeedTestResult
from medb.extensions import db


blueprint = Blueprint(
    "speedtest",
    __name__,
    url_prefix="/speedtest",
    static_folder="../static",
)


@blueprint.route("/results/", methods=["GET"])
@login_required
def speedtest_results():
    df = pd.read_sql(SpeedTestResult.query.statement, db.session.bind)
    local_tz = datetime.datetime.now().astimezone().tzinfo
    # This bizarre line is due to the following:
    # 1. We store times in the database as UTC, but want to present them in the
    #    local timezone.
    # 2. Pandas somehow doesn't support timezone aware datetimes
    # So, we convert from UTC to the local time, and then strip the timezone off
    # of it. This results in the timezone "looking" correct in the plot.
    df["time"] = df["time"].dt.tz_convert(local_tz).dt.tz_localize(None)
    df = df.set_index("time")
    df["Upload (Mbps)"] = df["upload_bps"] / 1000000.0
    df["Download (Mbps)"] = df["download_bps"] / 1000000.0
    ax = df[["Upload (Mbps)", "Download (Mbps)"]].plot()
    ax.set_xlabel("Test Date and Time")
    ax.set_ylabel("Speed")
    html = Markup(mpld3.fig_to_html(ax.figure))
    return render_template("speedtest/result.html", result=html)
