# -*- coding: utf-8 -*-
"""Public forms."""
from datetime import date
from datetime import timedelta

from flask_wtf import FlaskForm
from wtforms.fields.html5 import DateField
from wtforms import HiddenField
from wtforms import SelectMultipleField
from wtforms.validators import DataRequired
from wtforms.validators import Optional
from wtforms.validators import ValidationError


class LinkItemForm(FlaskForm):
    """Login form."""

    public_token = HiddenField("Public Token", validators=[DataRequired()])


class LinkAccountForm(FlaskForm):
    """Link account form."""

    link = SelectMultipleField('Accounts to link')


def _date_within(td: timedelta):
    def __date_within(form, field):
        latest = date.today()
        earliest = latest - td
        if earliest <= field.data <= latest:
            return
        raise ValidationError(
            f"Date must be between {earliest:%Y-%m-%d} and {latest:%Y-%m-%d}")
    return __date_within


class _deferred_str:
    def __init__(self, c):
        self.c = c
    def __str__(self):
        return self.c()



class SyncAccountForm(FlaskForm):
    """Used to trigger POST /accounts/<id>/sync"""

    # wow! it's really hard to get an HTML5 date picker with min/max that is
    # server-side validated...
    start_date = DateField(
        "Start sync from",
        validators=[Optional(), _date_within(timedelta(days=365))],
        render_kw={
            "max": _deferred_str(lambda: str(date.today())),
            "min": _deferred_str(lambda: str(date.today() - timedelta(days=365))),
        },
    )
