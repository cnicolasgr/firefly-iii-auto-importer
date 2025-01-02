import logging
from datetime import datetime, timedelta
from typing import List

import firefly_iii_client
from firefly_iii_client import AccountRead, ApiException, TransactionArray
from firefly_iii_client.configuration import Configuration as Firefly_configuration
from firefly_iii_client.models.transaction_type_property import TransactionTypeProperty


from Util.Transactions.Transaction_custom import TransactionCustom


class FireflyConnector:
    def __init__(self, configuration: Firefly_configuration):
        self.configuration = configuration
        self.logger = logging.getLogger(__name__)

    def get_firefly_accounts(self):
        # List all accounts
        with firefly_iii_client.ApiClient(self.configuration) as api_client:
            api_instance = firefly_iii_client.AccountsApi(api_client)
            try:
                api_response = api_instance.list_account()
                accounts = []
                for a in api_response.data:
                    if (
                        a.attributes.type.value
                        == firefly_iii_client.AccountTypeFilter.ASSET
                        or a.attributes.type.value
                        == firefly_iii_client.AccountTypeFilter.CASH
                    ):
                        accounts.append(a)
                logging.info(
                    "Listing of Firefly-III accounts: %s"
                    % [a.attributes.name for a in accounts]
                )
                return accounts
            except ApiException as e:
                logging.error(
                    "Exception when calling AccountsApi->list_account: %s\n" % e
                )

    def get_firefly_transactions(self, accounts: List[AccountRead], period_days: int):
        """
        Retrieve transactions from Firefly III for the specified accounts and period.

        Args:
            accounts (List[AccountRead]): A list of account objects to retrieve transactions for.
            period_days (int): The number of days in the past to retrieve transactions for. If None, retrieves all transactions.

        Returns:
            List[TransactionArray]: A list of transaction arrays for the specified accounts and period.

        Raises:
            ApiException: If there is an error when retrieving transactions from the Firefly III API.

        Note:
            Accounts of type 'CASH' are excluded from the retrieval to avoid duplicates.
        """

        if period_days is not None:
            date_start = (datetime.now() - timedelta(days=period_days)).strftime(
                "%Y-%m-%d"
            )
            date_stop = datetime.now().strftime("%Y-%m-%d")
            accounts = [
                a
                for a in accounts
                if a.attributes.type.value != firefly_iii_client.AccountTypeFilter.CASH
            ]

        with firefly_iii_client.ApiClient(self.configuration) as api_client:
            api_instance = firefly_iii_client.AccountsApi(api_client)
            try:
                all_transactions: List[TransactionArray] = []
                for a in accounts:
                    all_transactions.append(
                        api_instance.list_transaction_by_account(
                            id=a.id, start=date_start, end=date_stop
                        )
                    )
                return all_transactions
            except ApiException as e:
                raise ("Exception when retrieving transactions%s\n" % e)

    def create_firefly_transactions(
        self, transaction: List[firefly_iii_client.TransactionSplitStore]
    ):
        for t in transaction:
            self.create_firefly_transaction(t)

    def create_firefly_transaction(
        self, transaction: firefly_iii_client.TransactionSplitStore
    ):
        with firefly_iii_client.ApiClient(self.configuration) as api_client:
            api_instance = firefly_iii_client.TransactionsApi(api_client)
            transaction_store = firefly_iii_client.TransactionStore(
                transactions=[transaction]
            )
            try:
                # Store a new transaction
                api_instance.store_transaction(transaction_store)
                self.logger.info("Stored new transaction: %s" % transaction)
            except Exception as e:
                self.logger.error(
                    "Exception when calling TransactionsApi->store_transaction: %s\n"
                    % e
                )

    def convert_to_custom_transactions(
        self,
        firefly_transactions: list[TransactionArray],
        firefly_accounts: List[AccountRead],
    ):
        all_operations: List[TransactionCustom] = []

        for f in firefly_transactions:
            for data in f.data:
                for t in data.attributes.transactions:
                    source_account = FireflyConnector.find_account(
                        firefly_accounts, account_name=t.source_name
                    )
                    if not source_account:
                        raise Exception(f"Source account not found for transaction {t}")

                    destination_account = FireflyConnector.find_account(
                        firefly_accounts, account_name=t.destination_name
                    )
                    if not destination_account:
                        continue

                    # by convention: convert the amount is negative if this is a withdrawal, positive if it is a deposit
                    custom_operation = TransactionCustom(
                        found_account_number=source_account.attributes.account_number,
                        origin_account_number=source_account.attributes.account_number,
                        destination_account_number=destination_account.attributes.account_number,
                        transaction_type=t.type,
                        date=t.var_date,
                        amount=float(t.amount),
                        libelle=t.description,
                    )
                    all_operations.append(custom_operation)
        return all_operations

    def convert_to_firefly_transactions(
        self, transactions: List[TransactionCustom], firefly_accounts: List[AccountRead]
    ) -> List[firefly_iii_client.TransactionSplitStore]:
        firefly_transactions: List[firefly_iii_client.TransactionSplitStore] = []
        for t in transactions:
            source_account = FireflyConnector.find_account(
                firefly_accounts, account_number=t.origin_account_number
            )

            destination_account = FireflyConnector.find_account(
                firefly_accounts, account_number=t.destination_account_number
            )

            # Ensure source and destination accounts are different
            if (
                source_account
                and destination_account
                and source_account.id == destination_account.id
            ):
                if t.amount < 0:
                    destination_account = None
                else:
                    source_account = None

            firefly_transaction = firefly_iii_client.TransactionSplitStore(
                type=t.type,
                var_date=t.date,
                amount=str(abs(t.amount)),
                description=t.libelle,
                source_id=source_account.id if source_account else None,
                destination_id=destination_account.id if destination_account else None,
            )
            firefly_transactions.append(firefly_transaction)
        return firefly_transactions

    @staticmethod
    def find_account(
        firefly_accounts: List[AccountRead],
        account_name: str = None,
        account_number: str = None,
        account_type: str = None,
        iban: str = None,
    ) -> AccountRead | None:
        # At least one of the parameters must be provided
        if account_name is None and account_number is None and iban is None:
            return None

        for a in firefly_accounts:
            if (
                (account_name is None or a.attributes.name == account_name)
                and (
                    account_number is None
                    or a.attributes.account_number == account_number
                )
                and (
                    account_type is None
                    or a.attributes.type.value == account_type.value
                )
                and (iban is None or a.attributes.iban == iban)
            ):
                return a
        return None
