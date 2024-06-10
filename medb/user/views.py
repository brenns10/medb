# -*- coding: utf-8 -*-
"""Public section, including homepage and signup."""
from flask import Blueprint
from flask import abort
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

from medb.extensions import login_manager
from medb.utils import flash_errors

from .forms import LoginForm
from .forms import UserDetailsUpdateForm
from .models import User

blueprint = Blueprint(
    "user", __name__, url_prefix="/users", static_folder="../static"
)


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
            login_user(form.user, remember=form.remember.data)
            if form.remember.data:
                flash(
                    "You are logged in, and your session will be remembered.",
                    "success",
                )
            else:
                flash("You are logged in.", "success")
            # NOTE: could accept a "next" for redirect, but for simplicity
            # (and security, ish) omitted this
            return redirect(url_for("public.home"))
        else:
            flash_errors(form)
    elif current_user.is_authenticated:
        flash("You are already logged in", "info")
        return redirect(url_for("public.home"))
    return render_template("user/login.html", form=form)


@blueprint.route("/logout/")
@login_required
def logout():
    """Logout."""
    logout_user()
    flash("You are logged out.", "info")
    # TODO better goodbye page
    return redirect(url_for("public.home"))


@blueprint.route("/info/", methods=["GET", "POST"])
@login_required
def user_info():
    """User info."""
    form = UserDetailsUpdateForm(obj=current_user)
    if form.validate_on_submit():
        form.populate_obj(current_user)
        current_user.save()
        flash("Updated!", "success")
    return render_template(
        "user/info.html",
        user=current_user,
        form=form,
    )


@blueprint.route("/500/")
def error():
    abort(500)
