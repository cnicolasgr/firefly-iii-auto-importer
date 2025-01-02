from datetime import datetime, timedelta
from typing import List

from creditagricole_particuliers import Authenticator
from creditagricole_particuliers.accounts import Account, Accounts
from firefly_iii_client import AccountRead

from Util.Transactions.Transaction_custom import TransactionCustom
from banks_clients.configuration import Configuration
from firefly_iii_client.models.transaction_type_property import TransactionTypeProperty


class CreditAgricole:
    """This class contains the client and useful functions for the Credit Agricole bank.

    :param configuration: A bank configuration object.
    """

    def __init__(self, configuration: Configuration):
        self.session = Authenticator(
            configuration.username, configuration.password, configuration.department
        )

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.session = None

    def list_account(self, reference_accounts: List[AccountRead] = None):
        """Get the accounts of the bank.
        If a reference list is provided, fetch only the accounts matching the accounts in the provided slist

        :param reference_accounts: TThe list of reference accounts to match
        :return: A list of matching accounts
        """
        accounts: List[Account] = Accounts(session=self.session)
        matching_accounts: List[Account] = []

        if reference_accounts is None:
            return accounts

        for acc in accounts:
            if any(
                e.attributes.account_number == acc.numeroCompte
                for e in reference_accounts
            ):
                matching_accounts.append(acc)
        return matching_accounts

    def list_transactions(
        self, accounts: List[Account], period_days=None
    ):
        if period_days is not None:
            date_start = (datetime.now() - timedelta(days=period_days)).strftime(
                "%Y-%m-%d"
            )
            date_stop = datetime.now().strftime("%Y-%m-%d")

        all_operations: List[TransactionCustom] = []
        for acc in accounts:
            operations_for_account = acc.get_operations(
                date_start=date_start, date_stop=date_stop
            )
            custom_operations_for_account = [
                TransactionCustom(
                    found_account_number=acc.numeroCompte,
                    origin_account_number=acc.numeroCompte if t.montantOp < 0 else None,
                    destination_account_number=None if t.montantOp < 0 else acc.numeroCompte,
                    transaction_type=TransactionTypeProperty.WITHDRAWAL
                    if t.montantOp < 0
                    else TransactionTypeProperty.DEPOSIT,
                    date=t.dateOp,
                    amount=t.montantOp,
                    libelle=t.libelleOp,
                )
                for t in operations_for_account.list_operations
            ]
            all_operations.extend(custom_operations_for_account)
        return all_operations
