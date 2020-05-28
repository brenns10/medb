# -*- coding: utf-8 -*-
"""
Logic for interacting with Plaid API and the database.
"""
import datetime
from dataclasses import dataclass
from dataclasses import field
from functools import lru_cache
from typing import Dict
from typing import List

import plaid
from sqlalchemy.orm import joinedload

from medb.extensions import db
from medb.settings import PLAID_CLIENT_ID
from medb.settings import PLAID_SECRET
from medb.settings import PLAID_PUBLIC_KEY
from medb.settings import PLAID_ENV
from medb.shiso.models import UserPlaidAccount
from medb.shiso.models import UserPlaidItem


SUPPORTED_TYPES = {
    ('credit', 'credit card'),
    ('depository', 'checking'),
    ('depository', 'savings'),
}


@dataclass
class ItemSummary(object):
    """
    Summary of data related to an "item" in Shiso
    """

    institution_id: str
    institution_name: str
    item_id: str
    access_token: str
    linked_accounts: List[Dict] = field(default_factory=list)
    eligible_accounts: List[Dict] = field(default_factory=list)
    ineligible_accounts: List[Dict] = field(default_factory=list)


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


def get_accounts(access_token):
    client = plaid_client()
    return client.Accounts.get(access_token)


def get_institution(ins_id):
    client = plaid_client()
    return client.Institutions.get_by_id(ins_id)


def is_eligible_account(acct):
    return (acct['type'], acct['subtype']) in SUPPORTED_TYPES


def get_item_summary(item_id):
    item = UserPlaidItem.query.options(joinedload('accounts')).get(item_id)
    if not item:
        return None
    linked_accounts = {acct.account_id for acct in item.accounts}

    accounts = get_accounts(item.access_token)
    institution = get_institution(accounts['item']['institution_id'])
    summary = ItemSummary(
        institution_id=accounts['item']['institution_id'],
        institution_name=institution['institution']['name'],
        item_id=accounts['item']['item_id'],
        access_token=item.access_token,
    )
    for account in accounts['accounts']:
        if is_eligible_account(account):
            if account['account_id'] in linked_accounts:
                summary.linked_accounts.append(account)
            else:
                summary.eligible_accounts.append(account)
        else:
            summary.ineligible_accounts.append(account)
    return summary

def link_account(user, item_id, account):
    acct = UserPlaidAccount(
        item_id=item_id,
        account_id=account['account_id'],
        name=account['name'],
        kind=account['subtype'],
    )
    db.session.add(acct)
    db.session.commit()


def get_linked_accounts(user):
    user_items = UserPlaidItem.query.filter(
        UserPlaidItem.user_id == user.id
    ).all()
    user_accounts = UserPlaidAccount.query.filter(
        UserPlaidAccount.item_id.in_([it.id for it in user_items])
    ).all()
    return user_accounts


def get_upa_by_id(upa_id):
    return UserPlaidAccount.query.options(
        joinedload('account')
    ).get(upa_id)


def get_transactions(access_token, account_ids, days_ago=30):
    client = plaid_client()
    today = datetime.date.today()
    start = today - datetime.timedelta(days=days_ago)
    kwargs = dict(
        access_token=access_token, start_date=start.isoformat(),
        end_date=today.isoformat(), account_ids=account_ids,
    )
    response = client.Transactions.get(**kwargs)
    offset = len(response['transactions'])
    yield from response['transactions']
    while offset < response['total_transactions']:
        response = client.Transactions.get(offset=offset, **kwargs)
        offset += len(response['transactions'])
        yield from response['transactions']
