# -*- coding: utf-8 -*-
"""Public forms."""
from flask_wtf import FlaskForm
from wtforms import HiddenField
from wtforms.validators import DataRequired

from medb.user.models import User


class LinkItemForm(FlaskForm):
    """Login form."""

    public_token = HiddenField("Public Token", validators=[DataRequired()])
