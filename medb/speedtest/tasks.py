#!/usr/bin/env python3
"""
Celery tasks for speedtest
"""
import functools
import ipaddress
import json
import logging
import subprocess
from datetime import timedelta
from pathlib import Path

import requests

from .models import FastResult
from .models import IpCheckResult
from .models import PingResult
from .models import SpeedTestResult
from .pinger import Pinger
from medb.extensions import celery
from medb.extensions import db
from medb.model_util import utcnow


IP6CHECK = "https://ip6only.me/api/"
IP4CHECK = "https://ip4only.me/api/"

# Both are cloudflare DNS servers, I don't feel bad about the traffic.
PING_HOST = "1.1.1.1"
PING_V6_HOST = "2606:4700:4700::64"
PING_RETENTION_DAYS = 60


def perform_speedtest_net():
    logging.info("Started speedtest")
    try:
        res = subprocess.run(
            ["speedtest-cli", "--json"],
            check=True,
            capture_output=True,
            timeout=120,
        )
    except subprocess.CalledProcessError as e:
        logging.error('stdout="%s"', e.stdout.decode("utf-8"))
        logging.error('stderr="%s"', e.stderr.decode("utf-8"))
        raise
    except subprocess.TimeoutExpired:
        logging.error("Speed test timed out")
        return
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


def perform_fast_com():
    try:
        res = subprocess.run(
            [Path.home() / "go/bin/fast-cli", "-s"],
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.CalledProcessError as e:
        logging.error('stdout="%s"', e.stdout.decode("utf-8"))
        logging.error('stderr="%s"', e.stderr.decode("utf-8"))
        raise
    except subprocess.TimeoutExpired:
        logging.error("Fast.com test timed out")
        return

    vals = res.stdout.strip().split()
    if vals[1][0].lower() == "m":
        val_mbps = float(vals[0])
    elif vals[1][0].lower() == "g":
        val_mbps = float(vals[0]) * 1000
    elif vals[1][0].lower() == "k":
        val_mbps = float(vals[0]) / 1000
    else:
        logging.error(f"Unsupported unit: '{res.stdout.strip()}'")
    row = FastResult(download_mbps=val_mbps)
    db.session.add(row)
    db.session.commit()


@celery.task
def perform_speedtest():
    perform_speedtest_net()
    perform_fast_com()


@celery.task
def ipcheck():
    logging.info("Starting ip check")
    try:
        resp4 = requests.get(IP4CHECK, timeout=10)
        kind, addr, rest = resp4.text.strip().split(",", 2)
        assert kind == "IPv4"
        ipv4_addr = ipaddress.IPv4Address(addr).exploded
    except TimeoutError:
        logging.warn("IPv4 check timed out!")
        ipv4_addr = None

    try:
        resp6 = requests.get(IP6CHECK, timeout=10)
        kind, addr, rest = resp6.text.strip().split(",", 2)
        assert kind == "IPv6"
        ipv6_addr = ipaddress.IPv6Address(addr).exploded
    except TimeoutError:
        logging.warn("IPv6 check timed out!")
        ipv6_addr = None

    row = IpCheckResult(
        ipv4=ipv4_addr,
        ipv6=ipv6_addr,
    )
    logging.info(
        "IP Check: v4=%s, v6=%s",
        ipv4_addr,
        ipv6_addr,
    )
    db.session.add(row)
    db.session.commit()


@functools.lru_cache(maxsize=1)
def get_pinger():
    return Pinger(PING_HOST)


@functools.lru_cache(maxsize=1)
def get_v6_pinger():
    return Pinger(PING_V6_HOST)


@celery.task
def ping():
    result = get_pinger().ping()
    result_v6 = get_v6_pinger().ping()
    row = PingResult(ping_ms=result.time_ms, v6_ping_ms=result_v6.time_ms)
    db.session.add(row)
    db.session.commit()


@celery.task
def cleanup_ping_history():
    boundary = utcnow() - timedelta(days=PING_RETENTION_DAYS)
    PingResult.query.where(PingResult.time <= boundary).delete()
    db.session.commit()
