# -*- coding: utf-8 -*-
"""Public section, including homepage and signup."""
import json

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
from medb.shiso.logic import link_account
from medb.shiso.models import UserPlaidItem
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
    if not item_summary:
        abort(404)

    #import pdb; pdb.set_trace()
    accounts = {a['account_id']: a for a in item_summary.eligible_accounts}
    form = LinkAccountForm(request.form)
    form.link.choices = [
        (a['account_id'], a['name']) for a in item_summary.eligible_accounts]
    if form.validate_on_submit():
        for account_id in form.link.data:
            link_account(current_user, item_id, accounts[account_id])
        flash('Linked accounts!', 'info')
        return redirect(url_for('.home'))
    return render_template("shiso/plaid_item.html", item=item_summary,
        form=form, item_id=item_id)


@blueprint.route("/", methods=["GET"])
@login_required
def home():
    accts = get_linked_accounts(current_user)
    return render_template("shiso/home.html", accounts=accts)
