import logging
import os
from firefly_iii_client.configuration import Configuration as Firefly_configuration


from Util.Transactions.Transaction_custom import TransactionCustom
import banks_clients
from banks_clients.configuration import Configuration as Bank_configuration
from firefly_connector import FireflyConnector
from firefly_iii_client.models.transaction_type_property import TransactionTypeProperty

logger = logging.getLogger(__name__)


def check_transfers(transactions: list[TransactionCustom]):
    """Detect transfer operations from a list of operations.
    Add the destination account to detected transfers
    """
    for t in transactions:
        t_other_account = [
            a for a in transactions if a.found_account_number != t.found_account_number
        ]
        similar_transactions = t.find_transactions_in_list(
            t_other_account, 0.9, True
        )

        if len(similar_transactions) > 0:
            similar_transaction = similar_transactions[0]

            if len(similar_transactions) > 1:
                # either there is a false positive, or the same transaction was done twice
                logger.info(
                    "Found multiple potential transactions for transfer. \n Original: %s \n Similar Transactions: [%s]",
                    t,
                    ", ".join(map(str, similar_transactions)),
                )

                # check if the same transaction was done twice
                t_same_account = [
                    a for a in transactions if a.found_account_number == t.found_account_number
                ]
                if len(
                    t.find_transactions_in_list(t_same_account, 0.9, True)
                ) == len(similar_transactions):
                    pass
                else:
                    raise Exception(
                        "Found multiple potential transactions for transfer. See logs for more details"
                    )

            if (t.origin_account_number and similar_transaction.origin_account_number) or (t.destination_account_number and similar_transaction.destination_account_number):
                raise Exception(
                    "Error in transfer detection: %s and %s",
                    t,
                    similar_transaction
                )
            
            origin_account = (
                t.origin_account_number if t.origin_account_number else similar_transaction.origin_account_number
            )
            destination_account_number = (
                t.destination_account_number if t.destination_account_number else similar_transaction.destination_account_number
            )
            logger.info(
                "Found transfer: %s. %s -> %s",
                t,
                origin_account,
                destination_account_number,
            )

            t.origin_account_number = origin_account
            t.destination_account_number = destination_account_number
            t.amount = abs(t.amount)
            t.type = TransactionTypeProperty.TRANSFER
            # remove duplicate from transactions list
            temp_transactions = transactions.copy()
            temp_transactions.remove(similar_transaction)
            transactions[:] = temp_transactions


def check_duplicates(
    transactions_1: list[TransactionCustom], transactions_2: list[TransactionCustom]
):
    """Check for duplicates between two lists of transactions and remove them from the second list"""
    for t in transactions_1:
        similar_transactions = t.find_exact_transactions_in_list(transactions_2)
        if len(similar_transactions) > 0:
            logger.info(
                "Found duplicate: %s. Removing it from the list of transactions to add.",
                t,
            )
            transactions_2.remove(similar_transactions[0])
    return


def main():
    logging.basicConfig(
        filename="logging.log",
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s: %(message)s",
    )

    logger.critical(
        "\n\n*****************************\nStarting new import process\n*****************************\n"
    )
    firefly_configuration = Firefly_configuration(
        host=os.environ["FIREFLY_III_URL"],
        access_token=os.environ["FIREFLY_PERSONAL_ACCESS_TOKEN"],
    )
    firefly_connector = FireflyConnector(firefly_configuration)
    firefly_accounts = firefly_connector.get_firefly_accounts()
    firefly_transactions = firefly_connector.get_firefly_transactions(
        firefly_accounts, int(os.environ["GET_TRANSACTIONS_PERIOD_DAYS"])
    )
    firefly_transactions_custom = firefly_connector.convert_to_custom_transactions(
        firefly_transactions, firefly_accounts
    )

    credit_agricole_configuration = Bank_configuration(
        department=os.environ["CREDIT_AGRICOLE_DEPARTMENT"],
        username=os.environ["CREDIT_AGRICOLE_USERNAME"],
        password=os.environ["CREDIT_AGRICOLE_PASSWORD"],
    )
    with banks_clients.CreditAgricole(credit_agricole_configuration) as ca_client:
        accounts = ca_client.list_account(firefly_accounts)
        all_bank_transactions = ca_client.list_transactions(accounts, int(os.environ["GET_TRANSACTIONS_PERIOD_DAYS"]))

    check_transfers(all_bank_transactions)
    check_duplicates(firefly_transactions_custom, all_bank_transactions)

    # convert transactions back to firefly transactions
    all_bank_transactions = firefly_connector.convert_to_firefly_transactions(
        all_bank_transactions, firefly_accounts
    )
    firefly_connector.create_firefly_transactions(all_bank_transactions)


if __name__ == "__main__":
    main()
