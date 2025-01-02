import difflib
from datetime import datetime
from dateutil import tz
from typing import List

from firefly_iii_client.models.transaction_type_property import TransactionTypeProperty


class TransactionCustom:
    def __init__(
        self,
        date: str | datetime,
        libelle: str,
        amount: float,
        found_account_number: str,
        origin_account_number: str,
        transaction_type: TransactionTypeProperty,
        destination_account_number: str = None,
    ):
        # found account number is the account number where the transaction was found
        # whereas origin account number is the account number where the transaction originated
        self.found_account_number = found_account_number
        self.origin_account_number = origin_account_number

        self.date = date
        if not isinstance(date, datetime):
            self.date = datetime.strptime(date, "%b %d, %Y, %I:%M:%S %p")
        self.date = self.date.replace(tzinfo=tz.gettz('Europe / Berlin'))
        
        self.libelle = libelle
        self.amount = abs(amount)
        self.destination_account_number = destination_account_number
        self.type = transaction_type

    def __str__(self):
        return f"Origin account: {self.origin_account_number}, Destination account: {self.destination_account_number}, Amount: {self.amount}, Date: {self.date}, Libelle {self.libelle}"

    def __hash__(self):
        return hash(
            (
                self.found_account_number,
                self.origin_account_number,
                self.destination_account_number,
                self.date,
                self.libelle,
                self.amount
            )
        )

    def __eq__(self, other: "TransactionCustom"):
        if self.__class__ != other.__class__:
            return NotImplemented

        return (
            self.origin_account_number == other.origin_account_number
            and self.destination_account_number == other.destination_account_number
            and self.date == other.date
            and self.libelle == other.libelle
            and self.amount == other.amount
            and self.type == other.type
        )

    def match(
        self,
        transaction_to_match: "TransactionCustom",
        similarity_ratio=None,
        ignore_destination_account=False,
    ):
        libelle_equal = self.libelle == transaction_to_match.libelle
        if similarity_ratio:
            libelle_equal = (
                difflib.SequenceMatcher(
                    None, self.libelle, transaction_to_match.libelle
                ).ratio()
                >= similarity_ratio
            )

        destination_account_equal = (
            self.destination_account_number == transaction_to_match.destination_account_number
        )
        if ignore_destination_account:
            destination_account_equal = True

        return (
            self.date == transaction_to_match.date
            and self.amount == transaction_to_match.amount
            and libelle_equal
            and destination_account_equal
        )

    def find_transactions_in_list(
        self,
        transactions: List["TransactionCustom"],
        similarity_ratio=None,
        ignore_destination_account=False,
    ):
        return [
            x
            for x in transactions
            if self.match(x, similarity_ratio, ignore_destination_account)
        ]

    def find_exact_transactions_in_list(self, transactions: List["TransactionCustom"]):
        return [x for x in transactions if x == self]
