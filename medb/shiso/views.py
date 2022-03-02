# -*- coding: utf-8 -*-
"""Public section, including homepage and signup."""
import typing as t
from datetime import date
from decimal import Decimal

import click
from flask import abort
from flask import Blueprint
from flask import flash
from flask import redirect
from flask import render_template
from flask import request
from flask import session
from flask import url_for
from flask_login import current_user
from flask_login import login_required
from markupsafe import Markup

from .forms import AccountRenameForm
from .forms import AccountReportForm
from .forms import LinkAccountForm
from .forms import LinkItemForm
from .forms import SubscriptionReviewForm
from .forms import SyncAccountForm
from .forms import TransactionListForm
from .forms import TransactionReviewForm
from .logic import compute_transaction_report
from .logic import create_item
from .logic import get_all_user_transactions
from .logic import get_item_summary
from .logic import get_linked_accounts
from .logic import get_next_unreviewed_transaction
from .logic import get_plaid_items
from .logic import get_subscriptions
from .logic import get_transaction
from .logic import get_transactions
from .logic import get_upa_by_id
from .logic import get_upi_by_id
from .logic import initial_sync
from .logic import ItemSummary
from .logic import link_account
from .logic import plaid_new_item_link_token
from .logic import plaid_sandbox_reset_login
from .logic import plaid_update_item_link_token
from .logic import review_deleted_transaction
from .logic import review_transaction as do_review_transaction
from .logic import sync_account
from .logic import UpdateLink
from .models import Subscription
from .models import Transaction
from .models import UserPlaidAccount
from medb.extensions import db
from medb.utils import flash_errors

blueprint = Blueprint(
    "shiso", __name__, url_prefix="/shiso", static_folder="../static"
)


def _view_fetch_upi(item_id: int) -> ItemSummary:
    item = get_upi_by_id(item_id)
    if not item or item.user_id != current_user.id:
        abort(404)
    return item


def _view_fetch_item_summary(item_id: int) -> ItemSummary:
    item = get_item_summary(item_id)
    if not item or item.user_id != current_user.id:
        abort(404)
    return item


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


def _view_fetch_subscription(sub_id: int) -> Subscription:
    sub = Subscription.query.get(sub_id)
    if not sub:
        abort(404)
    return sub


def all_accounts() -> t.Iterator[UserPlaidAccount]:
    for item in get_plaid_items(current_user):
        for account in item.accounts:
            yield account


@blueprint.route("/link/", methods=["GET", "POST"])
@login_required
def link():
    link_token = plaid_new_item_link_token(current_user)
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
        link_token=link_token,
        update=None,
        post_url=url_for(".link"),
    )


@blueprint.route("/plaid_item/<item_id>/update/", methods=["GET", "POST"])
@login_required
def update_link(item_id):
    item = _view_fetch_upi(item_id)
    form = LinkItemForm(request.form)
    if request.method == "POST" and form.validate_on_submit():
        flash("Item re-authenticated!", "success")
        return redirect(url_for(".home"))
    link_token = plaid_update_item_link_token(item)
    return render_template(
        "shiso/link.html",
        form=form,
        link_token=link_token,
        update=item,
        post_url=url_for(".update_link", item_id=item_id),
    )


@blueprint.route("/plaid_item/<item_id>/", methods=["GET", "POST"])
@login_required
def link_accounts(item_id: int):
    try:
        item_summary = _view_fetch_item_summary(item_id)
    except UpdateLink as e:
        return redirect(url_for(".update_link", item_id=e.item_id))
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
    next_unreviewed = get_next_unreviewed_transaction(user=current_user)
    return render_template(
        "shiso/home.html",
        items=items,
        next_unreviewed=next_unreviewed,
        form=SyncAccountForm(),
    )


@blueprint.route("/account/<int:account_id>/", methods=["GET"])
@login_required
def account_transactions(account_id: int):
    account = _view_fetch_account(account_id)
    txr = get_transactions(account)
    next_unreviewed = get_next_unreviewed_transaction(account)
    return render_template(
        "shiso/account_transactions.html",
        txns=txr,
        account=account,
        form=SyncAccountForm(),
        next_unreviewed=next_unreviewed,
        review_dest=".account_review_transaction",
    )


@blueprint.route("/account/<int:account_id>/rename/", methods=["GET", "POST"])
@login_required
def account_rename(account_id: int):
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
def account_review(account_id: int):
    account = _view_fetch_account(account_id)
    txn = get_next_unreviewed_transaction(account)
    if txn:
        return redirect(url_for(".account_review_transaction", txn_id=txn.id))
    else:
        flash("All transactions are reviewed!", "success")
        return redirect(url_for(".account_transactions", account_id=account.id))


@blueprint.route("/review/", methods=["GET"])
@login_required
def global_review():
    txn = get_next_unreviewed_transaction(user=current_user)
    if txn:
        return redirect(url_for(".global_review_transaction", txn_id=txn.id))
    else:
        flash("All transactions are reviewed!", "success")
        return redirect(url_for(".home"))


def review_transaction(txn_id: int, acct: bool):
    txn = _view_fetch_transaction(txn_id)
    if request.method == "GET":
        form = TransactionReviewForm.create(txn, None)
        dest = (
            ".account_review_transaction"
            if acct
            else ".global_review_transaction"
        )
        return render_template(
            "shiso/transaction_review.html",
            form=form,
            txn=txn,
            dest=dest,
        )
    if not txn.active:
        # Inactive transactions don't have the full form rendered or used. Don't
        # try to validate it, just go ahead and use it.
        review_deleted_transaction(txn)
    else:
        form = TransactionReviewForm.create(txn, request.form)
        if not form.validate_on_submit():
            flash_errors(form)
            return render_template(
                "shiso/transaction_review.html",
                form=form,
                txn=txn,
            )
        do_review_transaction(txn, form)
    if acct:
        next_ = get_next_unreviewed_transaction(acct=txn.account, after=txn)
    else:
        next_ = get_next_unreviewed_transaction(after=txn, user=current_user)
    if next_:
        flash("Success, reviewing next transaction now", "info")
        dest = (
            ".account_review_transaction"
            if acct
            else ".global_review_transaction"
        )
        return redirect(url_for(dest, txn_id=next_.id))
    else:
        flash("Success, all transactions reviewed", "info")
        dest = ".account_transactions" if acct else ".home"
        return redirect(
            url_for(".account_transactions", account_id=txn.account.id)
        )


@blueprint.route(
    "/transaction/<int:txn_id>/account-review/", methods=["GET", "POST"]
)
@login_required
def account_review_transaction(txn_id: int):
    return review_transaction(txn_id, True)


@blueprint.route(
    "/transaction/<int:txn_id>/global-review/", methods=["GET", "POST"]
)
@login_required
def global_review_transaction(txn_id: int):
    return review_transaction(txn_id, False)


@blueprint.route("/account/<int:account_id>/sync/", methods=["POST"])
@login_required
def account_sync(account_id: int):
    account = _view_fetch_account(account_id)
    form = SyncAccountForm(request.form)
    if form.validate_on_submit():
        try:
            if not account.sync_start:
                if not form.start_date.data:
                    flash("You must provide start date for initial sync")
                else:
                    s = initial_sync(account, form.start_date.data)
                    flash(f"Initial sync completed! {s.summarize()}", "success")
            else:
                s = sync_account(account)
                flash(f"Sync completed! {s.summarize()}", "success")
        except UpdateLink as e:
            return redirect(url_for(".update_link", item_id=e.item_id))
    else:
        flash_errors(form)
    return redirect(url_for(".account_transactions", account_id=account_id))


@blueprint.route("/account/sync/", methods=["POST"])
@login_required
def global_sync():
    form = SyncAccountForm(request.form)
    results = []
    if form.validate_on_submit():
        items = get_plaid_items(current_user)
        try:
            for item in items:
                for account in item.accounts:
                    if account.sync_start:
                        results.append(sync_account(account))
        except UpdateLink as e:
            return redirect(url_for(".update_link", item_id=e.item_id))
    else:
        flash_errors(form)
    return render_template("shiso/global_sync_result.html", results=results)


@blueprint.route("/account/<int:account_id>/report/", methods=["GET"])
@login_required
def account_report(account_id: int):
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
        review_dest=".global_review_transaction",
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


@blueprint.route("/privacy/toggle/", methods=["GET"])
@login_required
def privacy_toggle():
    session["privacy"] = not session.get("privacy", False)
    return redirect(url_for(".home"))


@blueprint.route("/subscription/<int:sub_id>/", methods=["GET", "POST"])
@login_required
def subscription_show(sub_id):
    sub = _view_fetch_subscription(sub_id)
    sub_txns = get_transactions(sub.account, subscription_id=sub_id)
    if request.method == "POST":
        form = SubscriptionReviewForm(request.form)
        if form.validate_on_submit():
            form.populate_obj(sub)
            sub.is_new = False
            db.session.commit()
        else:
            flash_errors(form)
    else:
        form = SubscriptionReviewForm(obj=sub)
    return render_template(
        "shiso/subscription_show.html",
        sub=sub,
        txns=sub_txns,
        form=form,
    )


@blueprint.route("/subscription/", methods=["GET"])
@login_required
def subscription_list():
    subs = []
    for account in all_accounts():
        subs.extend(get_subscriptions(account.id))
    return render_template(
        "shiso/subscription_list.html",
        subs=subs,
    )


@blueprint.cli.command("reset-item-login")
@click.argument("item_id", type=int)
def reset_item_login(item_id):
    item = get_upi_by_id(item_id)
    assert item
    plaid_sandbox_reset_login(item)


@blueprint.app_template_filter("usd")
def usd(text):
    if session.get("privacy"):
        return Markup("$&mdash;.&mdash;")
    value = Decimal(text)
    return f"${value:.2f}"


@blueprint.app_template_filter("yesno")
def yesno(value):
    if value:
        return "Yes"
    return "No"
