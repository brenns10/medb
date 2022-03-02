# -*- coding: utf-8 -*-
"""Public forms."""
import typing as t
from datetime import date
from datetime import timedelta
from decimal import Decimal

from flask_wtf import FlaskForm
from wtforms.fields import BooleanField
from wtforms.fields import DateField
from wtforms.fields import DecimalField
from wtforms.fields import Field
from wtforms.fields import HiddenField
from wtforms.fields import RadioField
from wtforms.fields import SelectMultipleField
from wtforms.fields import StringField
from wtforms.form import Form
from wtforms.validators import DataRequired
from wtforms.validators import NumberRange
from wtforms.validators import Optional
from wtforms.validators import ValidationError

from .models import Transaction
from .models import TRANSACTION_CATEGORIES


class LinkItemForm(FlaskForm):
    """Login form."""

    public_token = HiddenField("Public Token", validators=[DataRequired()])


class LinkAccountForm(FlaskForm):
    """Link account form."""

    link = SelectMultipleField("Accounts to link")


def _date_within(td: timedelta) -> t.Callable[[Form, Field], None]:
    def __date_within(form: Form, field: Field) -> None:
        latest = date.today()
        earliest = latest - td
        if earliest <= field.data <= latest:
            return
        raise ValidationError(
            f"Date must be between {earliest:%Y-%m-%d} and {latest:%Y-%m-%d}"
        )

    return __date_within


class _deferred_str:
    def __init__(self, c: t.Callable[[], str]):
        self.c = c

    def __str__(self) -> str:
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
            "min": _deferred_str(
                lambda: str(date.today() - timedelta(days=365))
            ),
        },
    )


class TransactionReviewForm(FlaskForm):
    """Used to review the contents of a transaction, applying category and
    reimbursement."""

    reimbursement_type = RadioField(
        choices=["None", "Half", "Full", "Custom"],
        default="None",
        validators=[DataRequired()],
    )
    reimbursement_amount = DecimalField(places=2, validators=[Optional()])
    category = RadioField(
        choices=TRANSACTION_CATEGORIES, validators=[DataRequired()]
    )
    notes = StringField()

    def validate_reimbursement_amount(self, field: Field):
        if self.reimbursement_type.data == "Custom" and not field.data:
            raise ValidationError(
                "You must provide a custom reimbursement amount"
            )

    @classmethod
    def create(
        cls, txn: Transaction, formdata: t.Any
    ) -> "TransactionReviewForm":
        data = {}
        if txn.review:
            if txn.review.reimbursement_amount == txn.amount:
                data["reimbursement_type"] = "Full"
            elif txn.review.reimbursement_amount == Decimal(0):
                data["reimbursement_type"] = "None"
            elif txn.review.reimbursement_amount == txn.amount / 2:
                data["reimbursement_type"] = "Half"
            else:
                data["reimbursement_type"] = "Custom"
            data["reimbursement_amount"] = txn.review.reimbursement_amount
            data["notes"] = txn.review.notes
            data["category"] = txn.review.category
        form = cls(formdata, data=data)
        form.reimbursement_amount.validators = list(
            form.reimbursement_amount.validators
        )
        form.reimbursement_amount.validators.append(
            NumberRange(min=Decimal(0), max=txn.amount)
        )
        return form


class SubscriptionReviewForm(FlaskForm):
    """Used to update subscriptions"""

    name = StringField("Subscription Name", validators=[DataRequired()])
    is_tracked = BooleanField("Confirmed")


# NOTE: not FlaskForm since submitted via GET, no need for CSRF
class AccountReportForm(Form):

    start_date = DateField("Report Start")
    end_date = DateField("Report End")

    def validate_end_date(self, field: Field):
        if self.end_date.data < self.start_date.data:
            raise ValidationError("Start date must come before end date")


# NOTE: not FlaskForm since submitted via GET, no need for CSRF
class TransactionListForm(Form):

    start_date = DateField("Report Start")
    end_date = DateField("Report End")
    accounts = SelectMultipleField("Accounts", validators=[Optional()])
    category = SelectMultipleField(
        "Categories",
        choices=list(zip(TRANSACTION_CATEGORIES, TRANSACTION_CATEGORIES)),
        validators=[Optional()],
    )

    def validate_end_date(self, field: Field):
        if self.end_date.data < self.start_date.data:
            raise ValidationError("Start date must come before end date")


class AccountRenameForm(FlaskForm):

    name = StringField(validators=[DataRequired()])
