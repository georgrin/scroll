import asyncio
import csv
from decimal import Decimal
from eth_account import Account
from modules import *

import random
import sys
import os
import signal
from typing import Union

from config import ACCOUNTS, RECIPIENTS
from settings import (
    RANDOM_WALLET,
    SLEEP_TO,
    SLEEP_FROM,
    QUANTITY_THREADS,
    THREAD_SLEEP_FROM,
    THREAD_SLEEP_TO,
    REMOVE_WALLET
)
from utils.helpers import remove_wallet
from utils.sleeping import sleep
from eth_account import Account as EthereumAccount


def retry(retries: int = 5, delay: float = 1, raise_exception: bool = False):
    def decorator(func):
        async def newfn(*args, **kwargs):
            attempt = 0
            while attempt < retries:
                try:
                    result = await func(*args, **kwargs)
                    # print(f"Успешно {func.__name__} для {[*args]}: {result}")

                    return result
                except Exception as ex:
                    attempt += 1

                    if not attempt < retries:
                        print(f"Ошибка при вызове {func.__name__} для {[*args]}: {ex}")

                        print(ex)

                        if not raise_exception:
                            return None
                        raise Exception from ex
                await asyncio.sleep(delay)
            return func(*args, **kwargs)

        return newfn

    return decorator

def get_wallets(use_recipients: bool = False):
    if use_recipients:
        account_with_recipients = dict(zip(ACCOUNTS, RECIPIENTS))

        wallets = [
            {
                "id": _id,
                "key": key,
                "recipient": account_with_recipients[key],
            } for _id, key in enumerate(account_with_recipients, start=1)
        ]
    else:
        wallets = [
            {
                "id": _id,
                "key": key,
            } for _id, key in enumerate(ACCOUNTS, start=1)
        ]

    return wallets

def get_modules():
    return [Skydrome,
    KyberSwap,
    SushiSwap,
    SyncSwap,
    OpenOcean,
    SyncSwap,
    AmbientFinance,
    Aave,
    LayerBank,
    CompoundFinance,
    GnosisSafe]

async def main():
    wallets = get_wallets()

    tasks = []
    module_cooldown = 888888888
    aggregated_results = {}
    async def _worker(module, account_id, key, recipient):
            module_instance = module(account_id, key, recipient)
            last = await module_instance.check_last_iteration(module_cooldown)

            return module_instance.address, module_instance.get_name(), not last

    for _, account in enumerate(wallets, start=1):
        for module in get_modules():
            task = asyncio.create_task(_worker(module, account.get("id"), account.get("key"), None))
            tasks.append(task)

    results = await asyncio.gather(*tasks)

    count_failed = 0
    count_success = 0

    # Сбор итоговых данных
    for result in results:
        if not result:
            count_failed += 1
            continue

        address, module_name, last = result

        if address not in aggregated_results:
            aggregated_results[address] = {}

        aggregated_results[address][module_name] = last

        count_success += 1

    print(f"Успешно сделали {count_success} запросов, не смогли получить для {count_failed}")

    # Порядок столбцов в CSV файле (добавляем название модулей
    fieldnames = ["address"]
    for module in get_modules():
        module_instance = module(wallets[0].get("id"), wallets[0].get("key"), None)
        module_name = module_instance.get_name()
        fieldnames.append(module_name)

    count_rows = 0

    # Запись результатов в CSV файл
    with open("accounts_stat.csv", "w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for address, modules_result in aggregated_results.items():
            row = {"address": address}
            for module_name, result in modules_result.items():
                row[module_name] = result
            writer.writerow(row)
            count_rows += 1

    print(f"Успешно записано {count_rows} строк")


if __name__ == "__main__":
    asyncio.run(main())
