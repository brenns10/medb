# -*- coding: utf-8 -*-
"""Public section, including homepage and signup."""
from flask import Blueprint

from me_db.extensions import login_manager
from me_db.user.models import User

blueprint = Blueprint("user", __name__, url_prefix="/users", static_folder="../static")


@login_manager.user_loader
def load_user(user_id):
    """Load user by ID."""
    return User.query.get(int(user_id))
