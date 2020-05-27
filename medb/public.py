# -*- coding: utf-8 -*-
"""Public section, including homepage"""
from flask import (
    Blueprint,
    render_template,
    flash,
)
from flask_login import login_required

blueprint = Blueprint("public", __name__, static_folder="../static")


@blueprint.route("/")
@login_required
def home():
    """Home page."""
    return render_template("home.html")
