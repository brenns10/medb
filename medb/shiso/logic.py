# -*- coding: utf-8 -*-
"""
Logic for interacting with Plaid API and the database.
"""
import dataclasses
import datetime
import enum
import json
import re
import typing as t
from collections import Counter
from dataclasses import dataclass
from dataclasses import field
from decimal import Decimal
from functools import lru_cache
from typing import Dict
from typing import List

import plaid
from plaid.api import plaid_api
from plaid.models import AccountsGetRequest
from plaid.models import CountryCode
from plaid.models import InstitutionsGetByIdRequest
from plaid.models import ItemGetRequest
from plaid.models import ItemPublicTokenExchangeRequest
from plaid.models import LinkTokenCreateRequest
from plaid.models import LinkTokenCreateRequestUser
from plaid.models import Products
from plaid.models import SandboxItemResetLoginRequest
from plaid.models import TransactionsGetRequest
from plaid.models import TransactionsGetRequestOptions
from sqlalchemy import and_
from sqlalchemy import or_
from sqlalchemy.orm import joinedload
from toolz import keyfilter

from .forms import LinkItemForm
from .forms import TransactionReviewForm
from .models import CATEGORIES_V2
from .models import CATEGORY_PARENT_V2
from .models import PaymentChannel
from .models import Subscription
from .models import Transaction
from .models import TransactionGroup
from .models import TransactionReview
from .models import UserPlaidAccount
from .models import UserPlaidItem
from medb.extensions import db
from medb.settings import PLAID_CLIENT_ID
from medb.settings import PLAID_ENV
from medb.settings import PLAID_SECRET
from medb.user.models import User


SUPPORTED_TYPES = {
    ("credit", "credit card"),
    ("depository", "checking"),
    ("depository", "savings"),
}


@dataclass
class ItemSummary(object):
    """
    Summary of data related to an "item" in Shiso
    """

    user_id: int
    institution_name: str
    item_id: str
    access_token: str
    linked_accounts: List[Dict] = field(default_factory=list)
    eligible_accounts: List[Dict] = field(default_factory=list)
    ineligible_accounts: List[Dict] = field(default_factory=list)


@dataclass
class PlaidTransaction:

    transaction_type: str
    transaction_id: str
    account_owner: t.Optional[str]
    pending_transaction_id: t.Optional[str]
    pending: bool
    payment_channel: PaymentChannel
    payment_meta: t.Dict[str, t.Optional[str]]
    name: str
    merchant_name: t.Optional[str]
    location: t.Dict[str, t.Union[None, str, float]]
    authorized_date: t.Optional[datetime.date]
    date: datetime.date
    category_id: str
    category: t.Optional[t.List[str]]
    unofficial_currency_code: t.Optional[str]
    iso_currency_code: t.Optional[str]
    amount: float
    account_id: str
    transaction_code: t.Optional[str] = None

    def to_plaid_transaction(self, acct_id: int) -> Transaction:
        return Transaction(
            account_id=acct_id,
            plaid_txn_id=self.transaction_id,
            active=True,
            amount=Decimal(str(self.amount)),
            posted=not self.pending,
            name=self.name,
            date=self.date,
            # We'll only copy this over for a newly-created transaction. For
            # updated transactions, the date field will only be copied, and thus
            # we'll preserve the original value
            original_date=self.date,
            plaid_payment_channel=self.payment_channel,
            plaid_payment_meta=json.dumps(self.payment_meta),
            plaid_merchant_name=self.merchant_name,
            plaid_location=json.dumps(self.location),
            plaid_authorized_date=self.authorized_date,
            plaid_category_id=self.category_id,
        )

    @classmethod
    def create(cls, d) -> "PlaidTransaction":
        fields = {f.name for f in dataclasses.fields(cls)}
        return cls(**keyfilter(fields.__contains__, d))


@dataclass
class PlaidBalance:

    available: t.Optional[Decimal]
    current: t.Optional[Decimal]
    limit: t.Optional[Decimal]
    iso_currency_code: t.Optional[str]
    unofficial_currency_code: t.Optional[str]

    @classmethod
    def from_json_dict(cls, json_dict):
        kwargs = json_dict.copy()

        def assign_decimal(k):
            kwargs[k] = Decimal(str(json_dict[k]))

        if json_dict.get("available") is not None:
            assign_decimal("available")
        if json_dict.get("current") is not None:
            assign_decimal("current")
        if json_dict.get("limit") is not None:
            assign_decimal("limit")
        return cls(**kwargs)


class PlaidAccountType(enum.Enum):

    investment = "investment"
    credit = "credit"
    depository = "depository"
    loan = "loan"
    other = "other"


@dataclass
class PlaidAccount:

    account_id: str
    name: str
    balances: PlaidBalance
    mask: str
    type: PlaidAccountType
    subtype: str
    official_name: t.Optional[str] = None
    verification_status: t.Optional[str] = None

    @classmethod
    def from_json_dict(cls, json_dict):
        kwargs = json_dict.copy()
        kwargs["balances"] = PlaidBalance.from_json_dict(json_dict["balances"])
        kwargs["type"] = PlaidAccountType(json_dict["type"])
        return cls(**kwargs)


@dataclass
class PlaidTransactionResponse:

    account: PlaidAccount
    transactions: t.Iterator[PlaidTransaction]


class UpdateLink(Exception):
    def __init__(self, item_id):
        self.item_id = item_id


@lru_cache(maxsize=1)
def plaid_client() -> plaid_api.PlaidApi:
    if PLAID_ENV == "sandbox":
        plaid_env = plaid.Environment.Sandbox
    elif PLAID_ENV == "development":
        plaid_env = plaid.Environment.Development
    else:
        assert False, "Plaid environment invalid"
    configuration = plaid.Configuration(
        host=plaid_env,
        api_key={
            "clientId": PLAID_CLIENT_ID,
            "secret": PLAID_SECRET,
            "plaidVersion": "2020-09-14",
        },
    )
    api_client = plaid.ApiClient(configuration)
    client = plaid_api.PlaidApi(api_client)
    return client


def get_item(access_token: str) -> t.Any:
    client = plaid_client()
    request = ItemGetRequest(access_token=access_token)
    return client.item_get(request)


def get_accounts(access_token: str) -> t.Any:
    client = plaid_client()
    request = AccountsGetRequest(access_token=access_token)
    return client.accounts_get(request)


def get_institution(ins_id: str) -> t.Any:
    client = plaid_client()
    request = InstitutionsGetByIdRequest(
        institution_id=ins_id,
        country_codes=[CountryCode("US")],
    )
    return client.institutions_get_by_id(request)


def plaid_new_item_link_token(user: User, uri: str) -> str:
    client = plaid_client()
    request = LinkTokenCreateRequest(
        products=[Products("transactions")],
        client_name="MeDB Shiso",
        country_codes=[CountryCode("US")],
        language="en",
        user=LinkTokenCreateRequestUser(
            client_user_id=str(User.id),
        ),
        redirect_uri=uri,
    )
    response = client.link_token_create(request)
    return response["link_token"]


def plaid_update_item_link_token(item_summary: ItemSummary, uri: str) -> str:
    client = plaid_client()
    request = LinkTokenCreateRequest(
        client_name="MeDB Shiso",
        country_codes=[CountryCode("US")],
        language="en",
        user=LinkTokenCreateRequestUser(
            client_user_id=str(item_summary.user_id),
        ),
        access_token=item_summary.access_token,
        redirect_uri=uri,
    )
    response = client.link_token_create(request)
    return response["link_token"]


def plaid_sandbox_reset_login(item_summary: ItemSummary):
    client = plaid_client()
    request = SandboxItemResetLoginRequest(
        access_token=item_summary.access_token,
    )
    return client.sandbox_item_reset_login(request)


def is_eligible_account(acct: t.Dict) -> bool:
    return (str(acct["type"]), str(acct["subtype"])) in SUPPORTED_TYPES


def create_item(user: User, form: LinkItemForm) -> UserPlaidItem:
    client = plaid_client()
    public_token = form.public_token.data
    request = ItemPublicTokenExchangeRequest(public_token=public_token)
    exchange_response = client.item_public_token_exchange(request)
    plaid_item = get_item(exchange_response["access_token"])
    institution = get_institution(plaid_item["item"]["institution_id"])
    item = UserPlaidItem(
        user_id=user.id,
        access_token=exchange_response["access_token"],
        item_id=exchange_response["item_id"],
        institution_name=institution["institution"]["name"],
    )
    db.session.add(item)
    db.session.commit()
    return item


def get_item_summary(item_id: int) -> t.Optional[ItemSummary]:
    item = UserPlaidItem.query.options(joinedload(UserPlaidItem.accounts)).get(
        item_id
    )
    if not item:
        return None
    linked_accounts = {acct.account_id for acct in item.accounts}

    try:
        accounts = get_accounts(item.access_token)
    except plaid.ApiException as e:
        response = json.loads(e.body)
        if response["error_code"] == "ITEM_LOGIN_REQUIRED":
            raise UpdateLink(item_id)
        else:
            raise
    summary = ItemSummary(
        user_id=item.user_id,
        institution_name=item.institution_name,
        item_id=accounts["item"]["item_id"],
        access_token=item.access_token,
    )
    for account in accounts["accounts"]:
        if is_eligible_account(account):
            if account["account_id"] in linked_accounts:
                summary.linked_accounts.append(account)
            else:
                summary.eligible_accounts.append(account)
        else:
            summary.ineligible_accounts.append(account)
    return summary


def get_plaid_items(user: User) -> t.List[UserPlaidItem]:
    return (
        UserPlaidItem.query.options(db.joinedload(UserPlaidItem.accounts))
        .filter(UserPlaidItem.user_id == user.id)
        .all()
    )


def link_account(item_id: str, account: t.Dict):
    acct = UserPlaidAccount(
        item_id=item_id,
        account_id=account["account_id"],
        name=account["name"],
        kind=str(account["subtype"]),
        sync_start=None,
    )
    db.session.add(acct)
    db.session.commit()


def get_linked_accounts(user_id: int):
    return (
        UserPlaidAccount.query.join(UserPlaidItem)
        .filter(UserPlaidItem.user_id == user_id)
        .all()
    )


def get_upi_by_id(upi_id: int):
    return UserPlaidItem.query.get(upi_id)


def get_upa_by_id(upa_id: int):
    return UserPlaidAccount.query.options(
        joinedload(UserPlaidAccount.item)
    ).get(upa_id)


def get_plaid_transactions(
    access_token: str,
    account_id: str,
    days_ago: int = 30,
) -> PlaidTransactionResponse:
    client = plaid_client()
    today = datetime.date.today()
    start = today - datetime.timedelta(days=days_ago)
    kwargs = dict(
        access_token=access_token,
        start_date=start,
        end_date=today,
    )
    opts = dict(
        account_ids=[account_id],
    )
    request = TransactionsGetRequest(
        options=TransactionsGetRequestOptions(**opts),
        **kwargs,
    )
    response = client.transactions_get(request).to_dict()

    def yield_transactions():
        offset = len(response["transactions"])
        for txn in response["transactions"]:
            yield PlaidTransaction.create(txn)
        while offset < response["total_transactions"]:
            request = TransactionsGetRequest(
                options=TransactionsGetRequestOptions(
                    offset=offset,
                    **opts,
                ),
                **kwargs,
            )
            next_response = client.transactions_get(request).to_dict()
            offset += len(next_response["transactions"])
            for txn in next_response["transactions"]:
                yield PlaidTransaction.create(txn)

    return PlaidTransactionResponse(
        PlaidAccount.from_json_dict(response["accounts"][0]),
        yield_transactions(),
    )


@dataclass
class SyncReport:

    account: UserPlaidAccount
    new: int = 0
    updated: int = 0
    rereview: int = 0
    unchanged: int = 0
    missing_pending: int = 0
    missing_list: t.List[Transaction] = field(default_factory=list)
    missing_posted: int = 0

    posted_updates: int = 0

    updated_active: int = 0
    updated_name: int = 0
    updated_date: int = 0
    updated_amount: int = 0
    updated_posted: int = 0
    updated_plaid_merchant_name: int = 0

    new_subscriptions: int = 0

    def summarize(self) -> str:
        s = (
            f"Added {self.new} new transactions, updated {self.updated}, and"
            f" saw {self.unchanged} unchanged transactions."
        )
        if self.new_subscriptions:
            s += f" Detected {self.new_subscriptions} new subscriptions."
        if self.rereview:
            s += (
                f" Of the updated transactions, {self.rereview} need re-review."
            )
        if self.posted_updates:
            s += f" {self.posted_updates} transactions posted."
        if self.updated_active:
            s += (
                f" {self.updated_active} transactions were 'resurrected' from an "
                f"inactive state to an active one, maybe due to posting."
            )
        if self.missing_pending:
            s += (
                f" {self.missing_pending} pending transactions didn't "
                f"appear on your account. You will need to review their removal."
            )
        if self.missing_posted:
            s += (
                f" WARNING: {self.missing_posted} posted transactions no longer appear "
                f"on your account. This is an error - check the DB and your statement."
            )
        return s


def initial_sync(
    acct: UserPlaidAccount, start_date: datetime.date
) -> SyncReport:
    num_txns = Transaction.query.filter(
        Transaction.account_id == acct.id
    ).count()
    if num_txns > 0:
        raise ValueError("Cannot initial sync, there are already transactions")
    today = datetime.date.today()
    days_ago = (today - start_date).days
    try:
        plaid_txns = get_plaid_transactions(
            acct.item.access_token,
            days_ago=days_ago,
            account_id=acct.account_id,
        )
    except plaid.ApiException as e:
        response = json.loads(e.body)
        if response["error_code"] == "ITEM_LOGIN_REQUIRED":
            raise UpdateLink(acct.item_id)
        else:
            raise
    report = SyncReport(account=acct)
    for pt in plaid_txns.transactions:
        db.session.add(pt.to_plaid_transaction(acct.id))
        report.new += 1
    acct.sync_start = start_date
    acct.sync_end = today
    db.session.add(acct)
    db.session.commit()
    return report


def sync_account(acct: UserPlaidAccount) -> SyncReport:
    today = datetime.date.today()
    # 14 day "grace period" for any updated transactions
    start = acct.sync_end - datetime.timedelta(days=14)
    days_ago = (today - start).days

    local_txns = Transaction.query.filter(
        (Transaction.account_id == acct.id) & (Transaction.date >= start)
    ).all()
    local_txns_by_plaid_id = {t.plaid_txn_id: t for t in local_txns}

    subs = get_subscriptions(acct.id)

    try:
        plaid_txns = get_plaid_transactions(
            acct.item.access_token,
            days_ago=days_ago,
            account_id=acct.account_id,
        )
    except plaid.ApiException as e:
        response = json.loads(e.body)
        if response["error_code"] == "ITEM_LOGIN_REQUIRED":
            raise UpdateLink(acct.item_id)
        else:
            raise

    report = SyncReport(account=acct)
    fields = [
        "name",
        "date",
        "amount",
        "posted",
        "plaid_merchant_name",
        "active",
    ]
    for pt in plaid_txns.transactions:
        stored_txn = None
        txn_id = pt.transaction_id
        prev_txn_id = pt.pending_transaction_id
        plaid_txn = pt.to_plaid_transaction(acct.id)
        if txn_id in local_txns_by_plaid_id:
            stored_txn = local_txns_by_plaid_id[txn_id]
            del local_txns_by_plaid_id[txn_id]
        elif prev_txn_id and prev_txn_id in local_txns_by_plaid_id:
            stored_txn = local_txns_by_plaid_id[prev_txn_id]
            stored_txn.plaid_txn_id = txn_id
            report.posted_updates += 1
            del local_txns_by_plaid_id[prev_txn_id]
        subscription = match_subscription(subs, plaid_txn)
        if stored_txn:
            # By Executive order of the High Stephen: subscription shall not be
            # reassigned from one non-NULL value to another. This would be
            # confusing.
            if not stored_txn.subscription:
                stored_txn.subscription = subscription
            changed_fields = []
            for fn in fields:
                if getattr(plaid_txn, fn) != getattr(stored_txn, fn):
                    changed_fields.append(fn)
                    setattr(
                        report,
                        f"updated_{fn}",
                        getattr(report, f"updated_{fn}") + 1,
                    )
            if changed_fields:
                report.updated += 1
                for fn in fields:
                    setattr(stored_txn, fn, getattr(plaid_txn, fn))
                # Situations to require re-review:
                # 1: amount changed
                # 2: somehow a "deleted" transaction becomes active again
                if "amount" in changed_fields or "active" in changed_fields:
                    stored_txn.mark_updated()
                    report.rereview += 1
                db.session.add(stored_txn)
            else:
                report.unchanged += 1
        else:
            report.new += 1
            plaid_txn.subscription = subscription
            db.session.add(plaid_txn)
    acct.sync_end = today
    db.session.add(acct)

    for plaid_id, txn in local_txns_by_plaid_id.items():
        if not txn.active:
            continue
        if txn.posted:
            report.missing_posted += 1
        else:
            report.missing_pending += 1
        txn.active = False
        txn.mark_updated()
        db.session.add(txn)
        report.missing_list.append(txn)
    db.session.commit()

    subs = subscription_search(acct)
    report.new_subscriptions = len(subs)
    return report


def get_transactions(
    acct: UserPlaidAccount,
    start_date: t.Optional[datetime.date] = None,
    end_date: t.Optional[datetime.date] = None,
    subscription_id: t.Optional[int] = None,
) -> t.List[Transaction]:
    query = Transaction.query.options(
        db.joinedload(Transaction.review),
    ).filter(
        Transaction.account_id == acct.id,
        Transaction.active,
    )
    if start_date:
        query = query.filter(Transaction.original_date >= start_date)
    if end_date:
        query = query.filter(Transaction.original_date <= end_date)
    if subscription_id is not None:
        query = query.filter(Transaction.subscription_id == subscription_id)
    return query.order_by(
        Transaction.original_date.desc(),
        Transaction.id.desc(),
    ).all()


def get_transaction(txn_id) -> t.Optional[Transaction]:
    return Transaction.query.options(
        db.joinedload(Transaction.review),
    ).get(txn_id)


def get_transactions_bulk(txn_ids: t.List[int]) -> t.List[Transaction]:
    return (
        Transaction.query.options(
            db.joinedload(Transaction.review),
        )
        .filter(Transaction.id.in_(txn_ids))
        .all()
    )


def get_next_unreviewed_transaction(
    acct: t.Optional[UserPlaidAccount] = None,
    after: t.Optional[Transaction] = None,
    user: t.Optional[User] = None,
) -> Transaction:
    """
    Return the next unreviewed transaction.

    You must either provide acct or user. So you'll either get the next
    transaction to review in this account, or across all accounts for a user.
    The "after" argument specifies where to start.

    Unlike other functions, this one could return a inactive transaction
    (because users need to review those).
    """
    assert user or acct
    assert not (user and acct)
    query = Transaction.query.options(db.joinedload(Transaction.review))
    if acct is None:
        query = query.join(UserPlaidAccount).join(UserPlaidItem)
    query = query.outerjoin(TransactionReview)
    query = query.filter(
        or_(
            TransactionReview.id.is_(None),
            TransactionReview.updated < Transaction.updated,
        )
    )

    if not acct and user:
        query = query.filter(UserPlaidItem.user_id == user.id)
    elif acct and not user:
        query = query.filter(Transaction.account_id == acct.id)
    else:
        assert False
    if after is not None:
        query = query.filter(
            and_(
                Transaction.original_date >= after.original_date,
            )
        )
    return query.order_by(
        Transaction.original_date,
        Transaction.id,
    ).first()


def review_deleted_transaction(txn: Transaction):
    """
    Review a transaction which is no longer active.
    """
    assert not txn.active
    if txn.review:
        rev = txn.review
    else:
        # insert dummy review values if it was never reviewed before
        rev = TransactionReview()
        rev.transaction_id = txn.id
        rev.reimbursement_amount = Decimal(0)
        rev.category = ""
        rev.notes = ""
    rev.reviewed_amount = txn.amount
    rev.reviewed_date = txn.date
    rev.reviewed_name = txn.name
    rev.reviewed_plaid_merchant_name = txn.plaid_merchant_name
    rev.reviewed_posted = txn.posted
    rev.mark_updated()
    db.session.add(rev)
    db.session.commit()


def review_transaction(txn: Transaction, review: TransactionReviewForm):
    other = Decimal(0)
    if review.reimbursement_type.data == "None":
        amt = Decimal(0)
    elif review.reimbursement_type.data == "Half":
        amt = txn.amount / 2
    elif review.reimbursement_type.data == "Full":
        amt = txn.amount
    else:
        amt = review.reimbursement_amount.data
        other = review.other_reimbursement.data
    if txn.review:
        rev = txn.review
    else:
        rev = TransactionReview()
    rev.transaction_id = txn.id
    rev.reimbursement_amount = amt
    rev.other_reimbursement = other
    rev.category = review.category.data
    rev.notes = review.notes.data
    rev.reviewed_amount = txn.amount
    rev.reviewed_date = txn.date
    rev.reviewed_name = txn.name
    rev.reviewed_plaid_merchant_name = txn.plaid_merchant_name
    rev.reviewed_posted = txn.posted
    rev.mark_updated()
    db.session.add(rev)
    db.session.commit()


def do_bulk_transaction_update(txn_ids: t.List[int], category: str):
    txns = get_transactions_bulk(txn_ids)
    for txn in txns:
        assert txn.review
        txn.review.category = category
        db.session.add(txn.review)
    db.session.commit()


def get_all_user_transactions(
    user: User,
    start_date: t.Optional[datetime.date] = None,
    end_date: t.Optional[datetime.date] = None,
    categories: t.Optional[t.Iterable[str]] = None,
    accounts: t.Optional[t.Container[int]] = None,
    merchant: t.Optional[str] = None,
    name: t.Optional[str] = None,
) -> t.List[Transaction]:
    query = (
        Transaction.query.options(
            db.joinedload(Transaction.review),
        )
        .join(
            Transaction.account,
        )
        .join(
            UserPlaidAccount.item,
        )
        .join(
            Transaction.review,
        )
        .filter(
            UserPlaidItem.user_id == user.id,
            Transaction.active,
        )
    )
    db_cats = set()
    if categories:
        for category in categories:
            if category in CATEGORIES_V2:
                db_cats.update(CATEGORIES_V2[category])
            else:
                db_cats.add(category)
    if start_date:
        query = query.filter(Transaction.original_date >= start_date)
    if end_date:
        query = query.filter(Transaction.original_date <= end_date)
    if categories:
        query = query.filter(TransactionReview.category.in_(db_cats))
    if accounts:
        query = query.filter(
            UserPlaidAccount.id.in_(accounts),
        )
    if merchant is not None:
        query = query.filter(
            and_(
                Transaction.plaid_merchant_name is not None,
                Transaction.plaid_merchant_name == merchant,
            )
        )
    if name is not None:
        query = query.filter(Transaction.name == name)
    return query.order_by(
        Transaction.original_date.desc(),
        Transaction.id.desc(),
    ).all()


@dataclass
class TransactionReport:

    transactions: t.List[Transaction]

    all_net: Decimal
    share_net: Decimal
    reimbursed_net: Decimal
    other_net: Decimal
    unreviewed_net: Decimal
    unreviewed_count: int

    categories: t.List[str]
    all_categorized: t.Dict[str, Decimal]
    share_categorized: t.Dict[str, Decimal]
    reimbursed_categorized: t.Dict[str, Decimal]
    other_categorized: t.Dict[str, Decimal]

    parent_categories: t.List[str]
    all_parent: t.Dict[str, Decimal]
    share_parent: t.Dict[str, Decimal]
    reimbursed_parent: t.Dict[str, Decimal]
    other_parent: t.Dict[str, Decimal]


def compute_transaction_report(
    txns: t.List[Transaction], include_transfer: bool
) -> TransactionReport:
    categories_set = set()
    txns = txns[:]
    unreviewed_net = Decimal(0)
    unreviewed_count = 0
    for i in reversed(range(len(txns))):
        if not txns[i].review:
            unreviewed_net += txns[i].amount
            unreviewed_count += 1
            del txns[i]
        else:
            categories_set.add(txns[i].review.category)

    categories = sorted(categories_set)
    all_net = Decimal(0)
    share_net = Decimal(0)
    reimbursed_net = Decimal(0)
    other_net = Decimal(0)
    all_categorized = {c: Decimal(0) for c in categories}
    share_categorized = {c: Decimal(0) for c in categories}
    reimbursed_categorized = {c: Decimal(0) for c in categories}
    other_categorized = {c: Decimal(0) for c in categories}

    for txn in txns:
        if txn.review.category == "Transfer" and not include_transfer:
            continue
        all_net += txn.amount
        share_net += (
            txn.amount
            - txn.review.reimbursement_amount
            - txn.review.other_reimbursement
        )
        reimbursed_net += txn.review.reimbursement_amount
        other_net += txn.review.other_reimbursement
        all_categorized[txn.review.category] += txn.amount
        share_categorized[txn.review.category] += (
            txn.amount
            - txn.review.reimbursement_amount
            - txn.review.other_reimbursement
        )
        reimbursed_categorized[
            txn.review.category
        ] += txn.review.reimbursement_amount
        other_categorized[txn.review.category] += txn.review.other_reimbursement

    parents = sorted({CATEGORY_PARENT_V2[cat] for cat in categories})
    all_parent = {c: Decimal(0) for c in parents}
    share_parent = {c: Decimal(0) for c in parents}
    reimbursed_parent = {c: Decimal(0) for c in parents}
    other_parent = {c: Decimal(0) for c in parents}
    for cat in categories:
        parent = CATEGORY_PARENT_V2[cat]
        all_parent[parent] += all_categorized[cat]
        share_parent[parent] += share_categorized[cat]
        reimbursed_parent[parent] += reimbursed_categorized[cat]
        other_parent[parent] += other_categorized[cat]

    return TransactionReport(
        transactions=txns,
        all_net=all_net,
        share_net=share_net,
        other_net=other_net,
        reimbursed_net=reimbursed_net,
        unreviewed_net=unreviewed_net,
        unreviewed_count=unreviewed_count,
        categories=categories,
        all_categorized=all_categorized,
        share_categorized=share_categorized,
        reimbursed_categorized=reimbursed_categorized,
        other_categorized=other_categorized,
        parent_categories=parents,
        all_parent=all_parent,
        share_parent=share_parent,
        reimbursed_parent=reimbursed_parent,
        other_parent=other_parent,
    )


class SubscriptionDetector:
    """
    Name based subscription detection

    This class implements the initial detection of subscriptions. The
    approach is to use name and date-based matching for the initial detection.
    Once a subscription is detected, we stop using this subscription matching
    mechanism.

    The trick is to avoid re-detecting the same subscriptions, and to stop
    detecting false positives once the user has annotated them as "NOT a
    subscription." Both of these can be achieved by filtering transactions
    with a subscription ID.
    """

    new: t.Dict[re.Pattern, t.Tuple[str, t.List[Transaction]]]
    singletons: t.List[Transaction]

    def __init__(self):
        self.new = dict()
        self.singletons = []

    def name_match(self, name: str, ref: str) -> bool:
        """
        The super-rough name matching system.

        The "real" matching is done later on by regular expression, so these
        funky rules only get used for initial detection. I've decided to guess
        something is a name match if it has the same number of "tokens", and
        more of those tokens match than do not match. This allows transaction
        names like the following to be similar:

            HULU *TXNID1111 HULU DIRECT PAY DATE1111
            HULU *TXNID2222 HULU DIRECT PAY DATE2222

        But others, like these, will not be matched as "similar":

            SQ *MERCHANT1111 DATE1111
            SQ *MERCHANT2222 DATE2222

        However, this is super rough, and admittedly sometimes things get lumped
        together. I should improve this later on.
        """
        if name == ref:
            return True
        name_tokens = name.split()
        ref_tokens = ref.split()
        if len(name_tokens) != len(ref_tokens):
            return False
        differ = 0
        for ntok, rtok in zip(name_tokens, ref_tokens):
            if ntok != rtok:
                differ += 1
        return len(name_tokens) - differ > differ

    def re_escape(self, string: str) -> str:
        """
        Given a string, escape its characters so that it can be used as a regex
        to match itself.
        """
        special = "\\.*+-^${}()[]|"
        return "".join([("\\" + c) if c in special else c for c in string])

    def create_expr(self, name: str, ref: str) -> t.Tuple[str, re.Pattern]:
        """
        If self.name_match() returned True, use this to create a corresponding
        regular expression. This will be used for later matches.
        """
        expr = []
        tmpl = []
        for ntok, rtok in zip(name.split(), ref.split()):
            if ntok == rtok:
                expr.append(self.re_escape(rtok))
                tmpl.append(rtok)
            else:
                expr.append("\\S+")
                tmpl.append("XXX")
        return " ".join(tmpl), re.compile("\\s+".join(expr))

    def add_transaction(self, txn: Transaction):
        """
        Helper function for adding historical transactions for detection.
        """
        if txn.subscription_id is not None:
            return
        for expr in self.new.keys():
            if expr.match(txn.name):
                self.new[expr][1].append(txn)
                return
        for i, ref_txn in enumerate(self.singletons):
            if self.name_match(txn.name, ref_txn.name):
                tmpl, expr = self.create_expr(txn.name, ref_txn.name)
                self.new[expr] = (tmpl, [ref_txn, txn])
                del self.singletons[i]
                return
        self.singletons.append(txn)

    def add_transactions(self, txns: t.List[Transaction]):
        """Add all transactions to the detector."""
        for txn in sorted(txns, key=lambda t: t.date, reverse=True):
            self.add_transaction(txn)

    def filter_infrequent(self):
        """Kick out transaction groupings which don't have at least three"""
        for key in list(self.new.keys()):
            if len(self.new[key][1]) <= 2:
                del self.new[key]

    def filter_nonmonthly(self):
        """Kick out transactions which aren't monthly."""
        for key in list(self.new.keys()):
            txns = self.new[key][1]
            prev_date = None
            filter_out = False
            for txn in txns:
                if prev_date is None:
                    if datetime.date.today() - txn.date > datetime.timedelta(
                        days=33
                    ):
                        filter_out = True
                    prev_date = txn.date
                    continue
                expected_month = (
                    12 if prev_date.month == 1 else prev_date.month - 1
                )
                if txn.date.month != expected_month:
                    filter_out = True
                    break
                prev_date = txn.date
            if filter_out:
                del self.new[key]

    def detect(
        self,
        txns: t.List[Transaction],
    ) -> t.Dict[re.Pattern, t.Tuple[str, t.List[Transaction]]]:
        self.add_transactions(txns)
        self.filter_infrequent()
        self.filter_nonmonthly()
        return self.new


def get_subscriptions(account_id: int) -> t.List[Subscription]:
    """
    Return all subscriptions for this account.
    """
    return Subscription.query.filter(
        Subscription.account_id == account_id
    ).all()


def match_subscription(
    subs: t.List[Subscription],
    txn: Transaction,
) -> t.Optional[Subscription]:
    """
    Given a list of relevant subscriptions, check if txn matches any, and if so,
    return it.
    """
    for sub in subs:
        if sub.account_id == txn.account_id and re.match(sub.regex, txn.name):
            return sub
    return None


def subscription_search(account: UserPlaidAccount) -> t.List[Subscription]:
    """
    For a given account, search for new subscriptions.
    Subscription search is done with at most 6 months data.
    """
    detector = SubscriptionDetector()
    start = datetime.date.today() - datetime.timedelta(days=31 * 6)
    txns = get_transactions(account, start_date=start)
    result = detector.detect(txns)
    if not result:
        return []
    subs = []
    for expr, (tmpl, sub_txns) in result.items():
        sub = Subscription(
            name=tmpl,
            account_id=account.id,
            regex=expr.pattern,
            is_new=True,
            is_tracked=False,
            is_active=True,
        )
        db.session.add(sub)
        subs.append(sub)
        for txn in sub_txns:
            txn.subscription = sub
            db.session.add(txn)
    db.session.commit()
    return subs


def get_next_unreviewed_subscription(user: User) -> Transaction:
    """
    Return the next unreviewed transaction.
    """
    return (
        Subscription.query.join(UserPlaidAccount)
        .join(UserPlaidItem)
        .filter(UserPlaidItem.user_id == user.id)
        .filter(Subscription.is_new)
        .order_by(Subscription.id)
        .first()
    )


def get_subscriptions_transactions(user: User) -> Subscription:
    """
    Return all subscriptions, with the transactions loaded.
    """
    return (
        Subscription.query.options(db.joinedload(Subscription.transactions))
        .options(db.joinedload(Subscription.account))
        .join(UserPlaidAccount)
        .join(UserPlaidItem)
        .filter(UserPlaidItem.user_id == user.id)
        .all()
    )


def guess_category(txn: Transaction) -> t.Optional[str]:
    """
    Based on the 5 most recent transactions matching the name or merchant,
    guess the transaction category.
    """
    query = Transaction.query.options(db.joinedload(Transaction.review))
    query = query.join(TransactionReview)
    merchant = txn.plaid_merchant_name or "NO MATCH"
    name = txn.name or "NO MATCH"
    sub_id = txn.subscription_id or -1
    similar = (
        query.filter(
            Transaction.active,
            or_(
                and_(
                    Transaction.plaid_merchant_name is not None,
                    Transaction.plaid_merchant_name == merchant,
                ),
                and_(
                    Transaction.name is not None,
                    Transaction.name == name,
                ),
                and_(
                    Transaction.subscription_id is not None,
                    Transaction.subscription_id == sub_id,
                ),
            ),
        )
        .order_by(Transaction.date.desc())
        .limit(5)
        .all()
    )
    if not similar:
        return None
    category_counter = Counter(t.review.category for t in similar)
    return category_counter.most_common(1)[0][0]


def convert_to_group(rev: TransactionReview):
    if rev.group_id:
        raise Exception("Already a part of a transaction group")
    group = TransactionGroup()
    group.leader_id = rev.id
    db.session.add(group)
    db.session.commit()
    rev.group_id = group.id
    db.session.add(group)
    db.session.commit()
    db.session.commit()
    return group


def remove_from_group(rev: TransactionReview):
    if rev.group_id:
        group = rev.group
        num_members = len(group.members)
        if group.leader_id == rev.id and num_members != 1:
            raise Exception("Please remove the other transactions first")
        rev.group_id = None
        db.session.add(rev)
        db.session.commit()
        if num_members == 1:
            db.session.delete(group)
            db.session.commit()


def get_transaction_groups(user):
    return (
        TransactionGroup.query.join(
            TransactionReview,
            TransactionGroup.leader_id == TransactionReview.id,
        )
        .join(Transaction)
        .join(UserPlaidAccount)
        .join(UserPlaidItem)
        .filter(UserPlaidItem.user_id == user.id)
        .all()
    )


def add_to_group(rev: TransactionReview, group: TransactionGroup):
    rev.group_id = group.id
    db.session.add(rev)
    db.session.commit()
