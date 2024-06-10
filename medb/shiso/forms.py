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
from wtforms.fields import SelectField
from wtforms.fields import SelectMultipleField
from wtforms.fields import StringField
from wtforms.fields import SubmitField
from wtforms.form import Form
from wtforms.validators import DataRequired
from wtforms.validators import Optional
from wtforms.validators import ValidationError
from wtforms.widgets import HiddenInput

from .models import CATEGORIES_V2
from .models import LEAF_CATEGORIES_V2
from .models import Transaction


def category_choices(with_pick: bool = False, include_inner: bool = False):
    choices = []
    if with_pick:
        choices.append(("<Pick a Category>", "<Pick a Category>"))
    for parent, categories in CATEGORIES_V2.items():
        if len(categories) != 1 and include_inner:
            choices.append((parent, parent))
        for category in categories:
            if parent != category:
                choices.append((category, f"{parent}: {category}"))
            else:
                choices.append((category, category))
    return choices


def validate_category(form: Form, field: Field):
    if field.data not in LEAF_CATEGORIES_V2:
        raise ValidationError("Pick a Category")


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
    other_reimbursement = DecimalField(
        places=2, default=0, validators=[Optional()]
    )
    category = SelectField(
        choices=category_choices(True),
        validators=[DataRequired(), validate_category],
        default="<Pick a Category>",
    )
    notes = StringField()

    def validate_reimbursement_amount(self, field: Field):
        if self.reimbursement_type.data == "Custom" and field.data is None:
            raise ValidationError(
                "You must provide a custom reimbursement amount"
            )

    @classmethod
    def create(
        cls,
        txn: Transaction,
        formdata: t.Any,
        category_guess: t.Optional[str] = None,
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
        elif category_guess:
            data["category"] = category_guess
        form = cls(formdata, data=data)
        return form


class SubscriptionReviewForm(FlaskForm):
    """Used to update subscriptions"""

    name = StringField("Subscription Name", validators=[DataRequired()])
    is_tracked = BooleanField("Confirmed")


# NOTE: not FlaskForm since submitted via GET, no need for CSRF
class AccountReportForm(Form):

    start_date = DateField("Report Start", validators=[Optional()])
    end_date = DateField("Report End", validators=[Optional()])
    include_transfer = BooleanField("Include Transfers")

    def validate_end_date(self, field: Field):
        if (
            self.end_date.data
            and self.start_date.data
            and self.end_date.data < self.start_date.data
        ):
            raise ValidationError("Start date must come before end date")


# NOTE: not FlaskForm since submitted via GET, no need for CSRF
class TransactionListForm(Form):

    start_date = DateField("Report Start", validators=[Optional()])
    end_date = DateField("Report End", validators=[Optional()])
    accounts = SelectMultipleField("Accounts", validators=[Optional()])
    category = SelectMultipleField(
        "Categories",
        choices=category_choices(with_pick=False, include_inner=True),
        validators=[Optional()],
    )
    merchant = HiddenField("Merchant")
    name = HiddenField("Name")

    def validate_end_date(self, field: Field):
        if (
            self.end_date.data
            and self.start_date.data
            and self.end_date.data < self.start_date.data
        ):
            raise ValidationError("Start date must come before end date")


class AccountRenameForm(FlaskForm):

    name = StringField(validators=[DataRequired()])


class TransactionListField(Field):
    widget = HiddenInput()

    def _value(self):
        if self.data:
            return "\n".join(str(id_) for id_ in self.data)
        else:
            return ""

    def process_formdata(self, data):
        if data and data[0].strip():
            self.data = [int(s.strip()) for s in data[0].strip().split("\n")]
        else:
            self.data = []


class TransactionBulkUpdateForm(FlaskForm):

    category = SelectField(
        "Categories",
        choices=category_choices(True),
        validators=[validate_category],
        default="<Pick a Category>",
    )
    transactions = TransactionListField("Transactions")
    return_url = HiddenField()

    def validate_transactions(self, field: Field):
        if not field.data:
            raise ValidationError("No transactions selected.")


class GenericReturnForm(FlaskForm):

    return_url = HiddenField()


class AddToGroupForm(FlaskForm):

    group = SelectField(
        "Target Group",
        validators=[DataRequired()],
    )


class UserSettingsForm(FlaskForm):

    scheduled_sync = BooleanField("Enable Scheduled Sync")
    submit = SubmitField("Submit")
