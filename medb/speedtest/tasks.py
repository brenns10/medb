#!/usr/bin/env python3
"""
Celery tasks for speedtest
"""
import ipaddress
import json
import logging
import subprocess

import requests

from .models import IpCheckResult
from .models import SpeedTestResult
from medb.extensions import celery
from medb.extensions import db


IP6CHECK = "https://ip6only.me/api/"
IP4CHECK = "https://ip4only.me/api/"


@celery.task
def perform_speedtest():
    logging.info("Started speedtest")
    try:
        res = subprocess.run(
            ["speedtest-cli", "--json"],
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as e:
        logging.error('stdout="%s"', e.stdout.decode("utf-8"))
        logging.error('stderr="%s"', e.stderr.decode("utf-8"))
        raise
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


@celery.task
def ipcheck():
    logging.info("Starting ip check")
    resp4 = requests.get(IP4CHECK)
    kind, addr, rest = resp4.text.strip().split(",", 2)
    assert kind == "IPv4"
    ipv4_addr = ipaddress.IPv4Address(addr)
    resp6 = requests.get(IP6CHECK)
    kind, addr, rest = resp6.text.strip().split(",", 2)
    assert kind == "IPv6"
    ipv6_addr = ipaddress.IPv6Address(addr)
    row = IpCheckResult(
        ipv4=ipv4_addr.exploded,
        ipv6=ipv6_addr.exploded,
    )
    logging.info(
        "IP Check: v4=%s, v6=%s",
        ipv4_addr.compressed,
        ipv6_addr.compressed,
    )
    db.session.add(row)
    db.session.commit()
