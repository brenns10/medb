# -*- coding: utf-8 -*-
"""
Logic for interacting with Plaid API and the database.
"""
import dataclasses
import datetime
import enum
import json
import typing as t
from dataclasses import dataclass
from dataclasses import field
from decimal import Decimal
from functools import lru_cache
from typing import Dict
from typing import List

import plaid
from sqlalchemy import and_
from sqlalchemy import or_
from sqlalchemy.orm import joinedload
from toolz import keyfilter

from .forms import LinkItemForm
from .forms import TransactionReviewForm
from .models import PaymentChannel
from .models import Transaction
from .models import TransactionReview
from .models import UserPlaidAccount
from .models import UserPlaidItem
from medb.extensions import db
from medb.settings import PLAID_CLIENT_ID
from medb.settings import PLAID_ENV
from medb.settings import PLAID_PUBLIC_KEY
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
    authorized_date: t.Optional[str]
    date: str
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
            date=datetime.date.fromisoformat(self.date),
            # We'll only copy this over for a newly-created transaction. For
            # updated transactions, the date field will only be copied, and thus
            # we'll preserve the original value
            original_date=datetime.date.fromisoformat(self.date),
            plaid_payment_channel=self.payment_channel,
            plaid_payment_meta=json.dumps(self.payment_meta),
            plaid_merchant_name=self.merchant_name,
            plaid_location=json.dumps(self.location),
            plaid_authorized_date=(
                None
                if self.authorized_date is None
                else datetime.date.fromisoformat(self.authorized_date)
            ),
            plaid_category_id=self.category_id,
        )

    @classmethod
    def create(cls, d) -> "PlaidTransaction":
        fields = {f.name for f in dataclasses.fields(cls)}
        return cls(**keyfilter(fields.__contains__, d))


@dataclass
class PlaidBalance:

    available: t.Optional[Decimal]
    current: Decimal
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


@lru_cache(maxsize=1)
def plaid_client() -> plaid.Client:
    return plaid.Client(
        client_id=PLAID_CLIENT_ID,
        secret=PLAID_SECRET,
        public_key=PLAID_PUBLIC_KEY,
        environment=PLAID_ENV,
        api_version="2018-05-22",
    )


def get_item(access_token: str) -> t.Any:
    client = plaid_client()
    return client.Item.get(access_token)


def get_accounts(access_token: str) -> t.Any:
    client = plaid_client()
    return client.Accounts.get(access_token)


def get_institution(ins_id: str) -> t.Any:
    client = plaid_client()
    return client.Institutions.get_by_id(ins_id)


def is_eligible_account(acct: t.Dict) -> bool:
    return (acct["type"], acct["subtype"]) in SUPPORTED_TYPES


def create_item(user: User, form: LinkItemForm) -> UserPlaidItem:
    client = plaid_client()
    public_token = form.public_token.data
    exchange_response = client.Item.public_token.exchange(public_token)
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


def get_item_summary(item_id: str) -> t.Optional[ItemSummary]:
    item = UserPlaidItem.query.options(joinedload("accounts")).get(item_id)
    if not item:
        return None
    linked_accounts = {acct.account_id for acct in item.accounts}

    accounts = get_accounts(item.access_token)
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
        kind=account["subtype"],
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


def get_upa_by_id(upa_id: int):
    return UserPlaidAccount.query.options(joinedload("item")).get(upa_id)


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
        start_date=start.isoformat(),
        end_date=today.isoformat(),
        account_ids=[account_id],
    )
    response = client.Transactions.get(**kwargs)

    def yield_transactions():
        offset = len(response["transactions"])
        for txn in response["transactions"]:
            yield PlaidTransaction.create(txn)
        while offset < response["total_transactions"]:
            next_response = client.Transactions.get(offset=offset, **kwargs)
            offset += len(next_response["transactions"])
            for txn in next_response["transactions"]:
                yield PlaidTransaction.create(txn)

    return PlaidTransactionResponse(
        PlaidAccount.from_json_dict(response["accounts"][0]),
        yield_transactions(),
    )


@dataclass
class SyncReport:

    new: int = 0
    updated: int = 0
    unchanged: int = 0
    missing_pending: int = 0
    missing_list: t.List[Transaction] = field(default_factory=list)
    missing_posted: int = 0

    posted_updates: int = 0

    updated_date: int = 0
    updated_amount: int = 0
    updated_posted: int = 0
    updated_plaid_merchant_name: int = 0

    def summarize(self) -> str:
        s = (
            f"Added {self.new} new transactions and updated {self.updated}."
            f" There were {self.unchanged} unchanged transactions."
        )
        if self.posted_updates:
            s += f" {self.posted_updates} transactions posted."
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
    plaid_txns = get_plaid_transactions(
        acct.item.access_token,
        days_ago=days_ago,
        account_id=acct.account_id,
    )
    report = SyncReport()
    for pt in plaid_txns.transactions:
        db.session.add(pt.to_plaid_transaction(acct.id))
        report.new += 1
    acct.sync_start = start_date
    acct.sync_end = today
    db.session.add(acct)
    db.session.commit()
    return report


def sync_account(acct: UserPlaidAccount) -> SyncReport:
    report = SyncReport()
    today = datetime.date.today()
    # 14 day "grace period" for any updated transactions
    start = acct.sync_end - datetime.timedelta(days=14)
    days_ago = (today - start).days

    local_txns = Transaction.query.filter(
        (Transaction.account_id == acct.id) & (Transaction.date >= start)
    ).all()
    local_txns_by_plaid_id = {t.plaid_txn_id: t for t in local_txns}

    plaid_txns = get_plaid_transactions(
        acct.item.access_token,
        days_ago=days_ago,
        account_id=acct.account_id,
    )

    report = SyncReport()
    fields = ["date", "amount", "posted", "plaid_merchant_name"]
    for pt in plaid_txns.transactions:
        stored_txn = None
        txn_id = pt.transaction_id
        prev_txn_id = pt.pending_transaction_id
        plaid_txn = pt.to_plaid_transaction(acct.id)
        print(pt.name, pt.amount, txn_id, prev_txn_id)
        if txn_id in local_txns_by_plaid_id:
            stored_txn = local_txns_by_plaid_id[txn_id]
            del local_txns_by_plaid_id[txn_id]
        elif prev_txn_id and prev_txn_id in local_txns_by_plaid_id:
            stored_txn = local_txns_by_plaid_id[prev_txn_id]
            stored_txn.plaid_txn_id = txn_id
            report.posted_updates += 1
            del local_txns_by_plaid_id[prev_txn_id]
        if stored_txn:
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
                # If the transaction just posts, we shouldn't make the user
                # re-review. However, if any other field is changed, a re-review
                # should happen.
                if changed_fields != ["posted"]:
                    stored_txn.mark_updated()
                db.session.add(stored_txn)
            else:
                report.unchanged += 1
        else:
            report.new += 1
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
    return report


def get_transactions(
    acct: UserPlaidAccount,
    start_date: t.Optional[datetime.date] = None,
    end_date: t.Optional[datetime.date] = None,
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
    return query.order_by(
        Transaction.original_date.desc(),
        Transaction.id.desc(),
    ).all()


def get_transaction(txn_id) -> t.Optional[Transaction]:
    return Transaction.query.options(
        db.joinedload(Transaction.review),
    ).get(txn_id)


def get_next_unreviewed_transaction(
    acct: UserPlaidAccount,
    after: t.Optional[Transaction] = None,
) -> Transaction:
    # Note we do not filter inactive transactions. We want to be able to review
    # those.
    query = (
        Transaction.query.options(db.joinedload(Transaction.review))
        .outerjoin(TransactionReview)
        .filter(
            and_(
                Transaction.account_id == acct.id,
                or_(
                    TransactionReview.id.is_(None),
                    TransactionReview.updated < Transaction.updated,
                ),
            )
        )
    )
    if after is not None:
        query = query.filter(
            and_(
                Transaction.original_date >= after.date,
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
    rev.mark_updated()
    db.session.add(rev)
    db.session.commit()


def review_transaction(txn: Transaction, review: TransactionReviewForm):
    if review.reimbursement_type.data == "None":
        amt = Decimal(0)
    elif review.reimbursement_type.data == "Half":
        amt = txn.amount / 2
    elif review.reimbursement_type.data == "Full":
        amt = txn.amount
    else:
        amt = review.reimbursement_amount.data
        assert Decimal(0) <= amt <= txn.amount
    if txn.review:
        rev = txn.review
    else:
        rev = TransactionReview()
    rev.transaction_id = txn.id
    rev.reimbursement_amount = amt
    rev.category = review.category.data
    rev.notes = review.notes.data
    rev.mark_updated()
    db.session.add(rev)
    db.session.commit()


def get_all_user_transactions(
    user: User,
    start_date: t.Optional[datetime.date] = None,
    end_date: t.Optional[datetime.date] = None,
    categories: t.Optional[t.Container[str]] = None,
    accounts: t.Optional[t.Container[int]] = None,
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
    if start_date:
        query = query.filter(Transaction.original_date >= start_date)
    if end_date:
        query = query.filter(Transaction.original_date <= end_date)
    if categories:
        query = query.filter(TransactionReview.category.in_(categories))
    if accounts:
        query = query.filter(
            UserPlaidAccount.id.in_(accounts),
        )
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
    unreviewed_net: Decimal
    unreviewed_count: int

    categories: t.List[str]
    all_categorized: t.Dict[str, Decimal]
    share_categorized: t.Dict[str, Decimal]
    reimbursed_categorized: t.Dict[str, Decimal]


def compute_transaction_report(txns: t.List[Transaction]) -> TransactionReport:
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
    all_categorized = {c: Decimal(0) for c in categories}
    share_categorized = {c: Decimal(0) for c in categories}
    reimbursed_categorized = {c: Decimal(0) for c in categories}

    for txn in txns:
        all_net += txn.amount
        share_net += txn.amount - txn.review.reimbursement_amount
        reimbursed_net += txn.review.reimbursement_amount
        all_categorized[txn.review.category] += txn.amount
        share_categorized[txn.review.category] += (
            txn.amount - txn.review.reimbursement_amount
        )
        reimbursed_categorized[
            txn.review.category
        ] += txn.review.reimbursement_amount

    return TransactionReport(
        transactions=txns,
        all_net=all_net,
        share_net=share_net,
        reimbursed_net=reimbursed_net,
        unreviewed_net=unreviewed_net,
        unreviewed_count=unreviewed_count,
        categories=categories,
        all_categorized=all_categorized,
        share_categorized=share_categorized,
        reimbursed_categorized=reimbursed_categorized,
    )
