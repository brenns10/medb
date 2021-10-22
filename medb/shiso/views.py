# -*- coding: utf-8 -*-
"""Public section, including homepage and signup."""
from datetime import date

from flask import abort
from flask import Blueprint
from flask import flash
from flask import redirect
from flask import render_template
from flask import request
from flask import url_for
from flask_login import current_user
from flask_login import login_required

from medb.extensions import db
from medb.settings import PLAID_ENV
from medb.settings import PLAID_PUBLIC_KEY
from medb.shiso.forms import AccountRenameForm
from medb.shiso.forms import AccountReportForm
from medb.shiso.forms import LinkAccountForm
from medb.shiso.forms import LinkItemForm
from medb.shiso.forms import SyncAccountForm
from medb.shiso.forms import TransactionListForm
from medb.shiso.forms import TransactionReviewForm
from medb.shiso.logic import compute_transaction_report
from medb.shiso.logic import create_item
from medb.shiso.logic import get_all_user_transactions
from medb.shiso.logic import get_item_summary
from medb.shiso.logic import get_linked_accounts
from medb.shiso.logic import get_next_unreviewed_transaction
from medb.shiso.logic import get_plaid_items
from medb.shiso.logic import get_transactions
from medb.shiso.logic import get_transaction
from medb.shiso.logic import get_upa_by_id
from medb.shiso.logic import initial_sync
from medb.shiso.logic import link_account
from medb.shiso.logic import review_transaction as do_review_transaction
from medb.shiso.logic import sync_account
from medb.shiso.models import Transaction
from medb.shiso.models import UserPlaidAccount
from medb.utils import flash_errors

blueprint = Blueprint(
    "shiso", __name__, url_prefix="/shiso", static_folder="../static"
)


def _view_fetch_account(account_id: int) -> UserPlaidAccount:
    account = get_upa_by_id(account_id)
    if not account or account.item.user_id != current_user.id:
        abort(404)
    return account


def _view_fetch_transaction(txn_id: int) -> Transaction:
    txn = get_transaction(txn_id)
    if not txn or txn.account.item.user_id != current_user.id:
        abort(404)
    return txn


@blueprint.route("/link/", methods=["GET", "POST"])
@login_required
def link():
    form = LinkItemForm(request.form)
    if request.method == "POST":
        if form.validate_on_submit():
            item = create_item(current_user, form)
            return redirect(url_for(".link_accounts", item_id=item.id))
        else:
            flash_errors(form)
    return render_template(
        "shiso/link.html",
        form=form,
        plaid_environment=PLAID_ENV,
        plaid_public_key=PLAID_PUBLIC_KEY,
    )


@blueprint.route("/plaid_item/<item_id>/", methods=["GET", "POST"])
@login_required
def link_accounts(item_id):
    item_summary = get_item_summary(item_id)
    if not item_summary or item_summary.user_id != current_user.id:
        abort(404)

    accounts = {a["account_id"]: a for a in item_summary.eligible_accounts}
    form = LinkAccountForm(request.form)
    form.link.choices = [
        (a["account_id"], a["name"]) for a in item_summary.eligible_accounts
    ]
    if form.validate_on_submit():
        for account_id in form.link.data:
            link_account(item_id, accounts[account_id])
        flash("Linked accounts!", "info")
        return redirect(url_for(".home"))
    return render_template(
        "shiso/plaid_item.html",
        item=item_summary,
        form=form,
        item_id=item_id,
    )


@blueprint.route("/", methods=["GET"])
@login_required
def home():
    items = get_plaid_items(current_user)
    return render_template("shiso/home.html", items=items)


@blueprint.route("/account/<int:account_id>/", methods=["GET"])
@login_required
def account_transactions(account_id):
    account = _view_fetch_account(account_id)
    txr = get_transactions(account)
    next_unreviewed = get_next_unreviewed_transaction(account)
    return render_template(
        "shiso/account_transactions.html",
        txns=txr,
        account=account,
        form=SyncAccountForm(),
        next_unreviewed=next_unreviewed,
    )


@blueprint.route("/account/<int:account_id>/rename/", methods=["GET", "POST"])
@login_required
def account_rename(account_id):
    account = _view_fetch_account(account_id)
    form = AccountRenameForm(request.form, data={"name": account.name})
    if form.validate_on_submit():
        account.name = form.name.data
        db.session.add(account)
        db.session.commit()
        return redirect(url_for(".account_transactions", account_id=account_id))
    return render_template(
        "shiso/account_rename.html", form=form, account_id=account_id
    )


@blueprint.route("/account/<int:account_id>/review/", methods=["GET"])
@login_required
def account_review(account_id):
    account = _view_fetch_account(account_id)
    txn = get_next_unreviewed_transaction(account)
    if txn:
        return redirect(url_for(".review_transaction", txn_id=txn.id))
    else:
        flash("All transactions are reviewed!")
        return redirect(url_for(".account_transactions", account_id=account.id))


@blueprint.route("/transaction/<int:txn_id>/review/", methods=["GET", "POST"])
@login_required
def review_transaction(txn_id):
    txn = _view_fetch_transaction(txn_id)
    if request.method == "GET":
        form = TransactionReviewForm.create(txn, None)
        return render_template(
            "shiso/transaction_review.html",
            form=form,
            txn=txn,
        )
    form = TransactionReviewForm.create(txn, request.form)
    if form.validate_on_submit():
        do_review_transaction(txn, form)
        next_ = get_next_unreviewed_transaction(txn.account, after=txn)
        if next_:
            flash("Success, reviewing next transaction now", "info")
            return redirect(url_for(".review_transaction", txn_id=next_.id))
        else:
            flash("Success, all transactions reviewed", "info")
            return redirect(
                url_for(".account_transactions", account_id=txn.account.id)
            )
    else:
        flash_errors(form)
        return render_template(
            "shiso/transaction_review.html",
            form=form,
            txn=txn,
        )


@blueprint.route("/account/<int:account_id>/sync/", methods=["POST"])
@login_required
def account_sync(account_id):
    account = _view_fetch_account(account_id)
    form = SyncAccountForm(request.form)
    if form.validate_on_submit():
        if not account.sync_start:
            if not form.start_date.data:
                flash("You must provide start date for initial sync")
            else:
                initial_sync(account, form.start_date.data)
                flash("Initial sync completed!", "success")
        else:
            sync_account(account)
            flash("Sync completed!", "success")
    else:
        flash_errors(form)
    return redirect(url_for(".account_transactions", account_id=account_id))


@blueprint.route("/account/<int:account_id>/report/", methods=["GET"])
@login_required
def account_report(account_id):
    account = _view_fetch_account(account_id)
    today = date.today()
    start = today.replace(day=1)
    data = {
        "start_date": start,
        "end_date": today,
    }
    form = AccountReportForm(request.args, data=data)
    if not form.validate():
        flash_errors(form)
        return render_template(
            "shiso/report.html", account=account, form=form, report=None
        )
    transactions = get_transactions(
        account, form.start_date.data, form.end_date.data
    )
    report = compute_transaction_report(transactions)
    return render_template(
        "shiso/report.html",
        account_name=account.name,
        form_url=url_for(".account_report", account_id=account.id),
        form=form,
        report=report,
        start_date=form.start_date.data,
        end_date=form.end_date.data,
        txn_args={
            "start_date": form.start_date.data,
            "end_date": form.end_date.data,
            "accounts": [account_id],
        },
    )


@blueprint.route("/transactions/", methods=["GET"])
@login_required
def all_account_transactions():
    today = date.today()
    start = today.replace(day=1)
    data = {
        "start_date": start,
        "end_date": today,
    }
    accounts = get_linked_accounts(current_user.id)
    form = TransactionListForm()
    form.accounts.choices = [(str(a.id), a.name) for a in accounts]
    form.process(request.args, data=data)
    if not form.validate():
        flash_errors(form)
        return render_template(
            "shiso/all_transactions.html",
            form=form,
            txns=[],
        )
    accounts = list(map(int, form.accounts.data))
    transactions = get_all_user_transactions(
        current_user,
        form.start_date.data,
        form.end_date.data,
        categories=form.category.data,
        accounts=accounts,
    )
    return render_template(
        "shiso/all_transactions.html",
        form=form,
        txns=transactions,
    )


@blueprint.route("/report/", methods=["GET"])
@login_required
def all_account_report():
    today = date.today()
    start = today.replace(day=1)
    data = {
        "start_date": start,
        "end_date": today,
    }
    form = AccountReportForm(request.args, data=data)
    if not form.validate():
        flash_errors(form)
        return render_template(
            "shiso/report.html",
            account_name="All Accounts",
            form_url=url_for(".all_account_report"),
            form=form,
            report=None,
        )
    transactions = get_all_user_transactions(
        current_user,
        form.start_date.data,
        form.end_date.data,
    )
    report = compute_transaction_report(transactions)
    return render_template(
        "shiso/report.html",
        account_name="All Accounts",
        form_url=url_for(".all_account_report"),
        form=form,
        report=report,
        start_date=form.start_date.data,
        end_date=form.end_date.data,
        txn_args={
            "start_date": form.start_date.data,
            "end_date": form.end_date.data,
        },
    )
