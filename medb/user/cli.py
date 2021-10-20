#!/usr/bin/env python3
import click
import getpass

from medb.user.blueprint import blueprint
from medb.user.models import User
from medb.database import db


@blueprint.cli.command("setup")
@click.option("--username", default="admin")
@click.option("--email", default="example@example.com")
def user_setup(username, email):
    db.create_all()
    password = getpass.getpass()
    user = User(username, email, password)
    db.session.add(user)
    db.session.commit()
