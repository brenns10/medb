#!/usr/bin/env python3
"""
Celery tasks
"""
from medb.extensions import celery

from .logic import scheduled_sync


@celery.task
def hello():
    print("Hello world")


@celery.task
def run_scheduled_sync():
    scheduled_sync()
