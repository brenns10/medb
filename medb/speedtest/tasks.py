#!/usr/bin/env python3
"""
Celery tasks for speedtest
"""
import json
import logging
import subprocess

from .models import SpeedTestResult
from medb.extensions import celery
from medb.extensions import db


@celery.task
def perform_speedtest():
    logging.info("Started speedtest")
    res = subprocess.run(
        ["speedtest-cli", "--json"],
        check=True,
        capture_output=True,
    )
    test_result = json.loads(res.stdout.decode("utf-8"))
    server_name = "{} ({})".format(
        test_result["server"]["name"],
        test_result["server"]["sponsor"],
    )
    row = SpeedTestResult(
        upload_bps=int(test_result["upload"]),
        download_bps=int(test_result["download"]),
        ping_ms=float(test_result["ping"]),
        server_name=server_name,
        server_id=test_result["server"]["id"],
    )
    logging.info(
        "Speedtest complete! upload=%d download=%d",
        row.upload_bps,
        row.download_bps,
    )
    db.session.add(row)
    db.session.commit()
