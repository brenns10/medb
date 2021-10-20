# -*- coding: utf-8 -*-
"""Public forms."""
from flask_wtf import FlaskForm
from wtforms import HiddenField
from wtforms import SelectMultipleField
from wtforms.validators import DataRequired


class LinkItemForm(FlaskForm):
    """Login form."""

    public_token = HiddenField("Public Token", validators=[DataRequired()])


class LinkAccountForm(FlaskForm):
    """Link account form."""

    link = SelectMultipleField('Accounts to link')
