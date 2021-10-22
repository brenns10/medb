# -*- coding: utf-8 -*-
"""Public section, including homepage"""
import getpass

from flask import Blueprint
from flask import render_template
from flask_login import login_required

from medb.extensions import db
from medb.user.models import User

blueprint = Blueprint("public", __name__, static_folder="../static")


@blueprint.route("/")
@login_required
def home():
    """Home page."""
    return render_template("home.html")


@blueprint.cli.command("init")
def cmd_init():
    print("Create database...")
    db.create_all()
    print("done.")
    print("Create initial user")
    username = input("username: ")
    email = input("email: ")
    password = getpass.getpass("password: ")
    user = User(username=username, email=email, password=password)
    db.session.add(user)
    db.session.commit()
