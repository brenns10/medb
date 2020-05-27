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
from medb.shiso.forms import LinkItemForm
from medb.shiso.logic import create_item
from medb.shiso.logic import get_item
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


@blueprint.route("/plaid_item/<item_id>/", methods=["GET"])
@login_required
def link_accounts(item_id):
    plaid_item = UserPlaidItem.query.filter(
        UserPlaidItem.user_id==current_user.id,
        UserPlaidItem.id==item_id
    ).one_or_none()
    if not plaid_item:
        abort(404)

    item = get_item(plaid_item.access_token)
    return render_template("shiso/plaid_item.html",
        item_text=json.dumps(item, indent=2))
