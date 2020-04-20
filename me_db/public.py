# -*- coding: utf-8 -*-
"""Public section, including homepage"""
from flask import (
    Blueprint,
    render_template,
)

blueprint = Blueprint("public", __name__, static_folder="../static")


@blueprint.route("/")
def home():
    """Home page."""
    return render_template("home.html")
