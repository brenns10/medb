# -*- coding: utf-8 -*-
"""Public section, including homepage and signup."""
from flask import Blueprint
from flask import current_app
from flask import flash
from flask import redirect
from flask import render_template
from flask import request
from flask import url_for
from flask_login import current_user
from flask_login import login_required
from flask_login import login_user
from flask_login import logout_user

from me_db.extensions import login_manager
from me_db.user.forms import LoginForm
from me_db.user.models import User
from me_db.utils import flash_errors

blueprint = Blueprint(
    "user", __name__, url_prefix="/users", static_folder="../static")


@login_manager.user_loader
def load_user(user_id):
    """Load user by ID."""
    return User.query.get(int(user_id))


@blueprint.route("/login/", methods=["GET", "POST"])
def login():
    form = LoginForm(request.form)
    current_app.logger.info("Hello from the home page!")
    # Handle logging in
    if request.method == "POST":
        if form.validate_on_submit():
            login_user(form.user)
            flash("You are logged in.", "success")
            # NOTE: could accept a "next" for redirect, but for simplicity
            # (and security, ish) omitted this
            return redirect(url_for('public.home'))
        else:
            flash_errors(form)
    elif current_user.is_authenticated:
        flash('You are already logged in', 'info')
        return redirect(url_for('public.home'))
    return render_template("user/login.html", form=form)


@blueprint.route("/logout/")
@login_required
def logout():
    """Logout."""
    logout_user()
    flash("You are logged out.", "info")
    # TODO better goodbye page
    return redirect(url_for("public.home"))
