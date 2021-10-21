# -*- coding: utf-8 -*-
"""Public section, including homepage and signup."""
from flask import abort
from flask import Blueprint
from flask import flash
from flask import redirect
from flask import render_template
from flask import request
from flask import url_for
from flask_login import current_user
from flask_login import login_required

from medb.settings import PLAID_ENV
from medb.settings import PLAID_PUBLIC_KEY
from medb.shiso.forms import LinkAccountForm
from medb.shiso.forms import LinkItemForm
from medb.shiso.logic import create_item
from medb.shiso.logic import get_item_summary
from medb.shiso.logic import get_linked_accounts
from medb.shiso.logic import get_transactions
from medb.shiso.logic import get_upa_by_id
from medb.shiso.logic import link_account
from medb.shiso.logic import sync_account
from medb.user.models import User
from medb.utils import flash_errors

blueprint = Blueprint(
    "shiso", __name__, url_prefix="/shiso", static_folder="../static")


@blueprint.route("/link/", methods=["GET", "POST"])
@login_required
def link():
    form = LinkItemForm(request.form)
    if request.method == "POST":
        if form.validate_on_submit():
            item = create_item(current_user, form)
            return redirect(url_for('.link_accounts', item_id=item.id))
        else:
            flash_errors(form)
    return render_template(
        "shiso/link.html", form=form, plaid_environment=PLAID_ENV,
        plaid_public_key=PLAID_PUBLIC_KEY)


@blueprint.route("/plaid_item/<item_id>/", methods=["GET", "POST"])
@login_required
def link_accounts(item_id):
    item_summary = get_item_summary(item_id)
    if not item_summary or item_summary.user_id != current_user.id:
        abort(404)

    accounts = {a['account_id']: a for a in item_summary.eligible_accounts}
    form = LinkAccountForm(request.form)
    form.link.choices = [
        (a['account_id'], a['name']) for a in item_summary.eligible_accounts]
    if form.validate_on_submit():
        for account_id in form.link.data:
            link_account(item_id, accounts[account_id])
        flash('Linked accounts!', 'info')
        return redirect(url_for('.home'))
    return render_template(
        "shiso/plaid_item.html",
        item=item_summary,
        form=form,
        item_id=item_id,
    )


@blueprint.route("/", methods=["GET"])
@login_required
def home():
    accts = get_linked_accounts(current_user)
    return render_template("shiso/home.html", accounts=accts)


@blueprint.route("/account/<int:account_id>/transactions/", methods=["GET"])
@login_required
def account_transactions(account_id):
    account = get_upa_by_id(account_id)
    if not account or account.item.user_id != current_user.id:
        abort(404)
    txr = get_transactions(account.item.access_token, account.account_id)
    return render_template(
        "shiso/transactions.html",
        txns=list(txr.transactions),
    )


@blueprint.route("/account/<int:account_id>/", methods=["GET"])
@login_required
def account_home(account_id):
    account = get_upa_by_id(account_id)
    if not account or account.item.user_id != current_user.id:
        abort(404)
    return render_template("shiso/account.html", account=account)


#from medb.shiso.models import *
#    from datetime import date
#    from decimal import Decimal
#    from medb.extensions import db
#    user = User.query.get(1)
#    a = UserPlaidAccount.query.get(1)
#    t = Transaction(
#        account_id=a.id,
#        plaid_txn_id='abc',
#        amount=Decimal('123.56'),
#        posted=False,
#        reviewed=False,
#        name='Stephen Sample Transaction',
#        date=date(2021, 1, 1),
#        plaid_payment_channel=PaymentChannel.online,
#        plaid_payment_meta="{}",
#        plaid_merchant_name=None,
#        plaid_location="{}",
#        plaid_authorized_date=None,
#        plaid_category_id="123",
#    )
@blueprint.route('/account/<int:account_id>/sync/')
def sync():
    sync_account(get_upa_by_id(1))
    import IPython
    IPython.embed()
