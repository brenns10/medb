# -*- coding: utf-8 -*-
"""Views for speed testing"""
from flask import Blueprint


blueprint = Blueprint(
    "speedtest",
    __name__,
    url_prefix="/speedtest",
    static_folder="../static",
)
