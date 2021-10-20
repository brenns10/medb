#!/usr/bin/env python3
from flask import Blueprint


blueprint = Blueprint(
    "user", __name__, url_prefix="/users", static_folder="../static")
