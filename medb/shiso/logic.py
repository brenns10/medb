# -*- coding: utf-8 -*-
"""
Logic for interacting with Plaid API and the database.
"""
from functools import lru_cache

import plaid

from medb.extensions import db
from medb.settings import PLAID_CLIENT_ID
from medb.settings import PLAID_SECRET
from medb.settings import PLAID_PUBLIC_KEY
from medb.settings import PLAID_ENV
from medb.shiso.models import UserPlaidItem


@lru_cache(maxsize=1)
def plaid_client():
    return plaid.Client(
        client_id=PLAID_CLIENT_ID,
        secret=PLAID_SECRET,
        public_key=PLAID_PUBLIC_KEY,
        environment=PLAID_ENV,
        api_version='2018-05-22'
    )


def create_item(user, form):
    client = plaid_client()
    public_token = form.public_token.data
    exchange_response = client.Item.public_token.exchange(public_token)
    item = UserPlaidItem(
        user_id=user.id,
        access_token=exchange_response['access_token'],
        item_id=exchange_response['item_id'],
    )
    db.session.add(item)
    db.session.commit()
    return item


def get_item(access_token):
    client = plaid_client()
    return client.Item.get(access_token)
