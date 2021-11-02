# -*- coding: utf-8 -*-
"""Create an application instance."""
from medb.app import create_app
from medb.extensions import celery  # noqa

app = create_app()
