#!/usr/bin/env python3
"""
Celery tasks
"""
from medb.extensions import celery


@celery.task
def hello():
    print("Hello world")
