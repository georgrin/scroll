from loguru import logger
from settings import RETRY_COUNT
from utils.sleeping import sleep
from typing import Optional
import requests


def retry(func):
    async def wrapper(*args, **kwargs):
        retries = 0
        while retries <= RETRY_COUNT:
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                logger.error(f"Error | {e}")
                await sleep(10, 20)
                retries += 1

    return wrapper


def remove_wallet(private_key: str):
    with open("accounts.txt", "r") as file:
        lines = file.readlines()

    with open("accounts.txt", "w") as file:
        for line in lines:
            if private_key not in line:
                file.write(line)


async def get_account_transfer_tx_list(account_address: str, chain: str):
    explorer_data = {
        'zksync': {
            'url': 'https://block-explorer-api.mainnet.zksync.io/api',
        },
        'scroll': {
            'url': 'https://api.scrollscan.com/api',
            'api_key': 'ST6X93BUKMJGM126SJDHWU81NI7MFV295V'
        }
    }
    explorer_api_url = explorer_data.get(chain, None).get('url', None)
    explorer_api_key = explorer_data.get(chain, None).get('api_key', None)

    params = {
        "module": "account",
        "action": "txlist",
        "address": account_address,
        "startblock": 0,
        "endblock": 999999999,
        "sort": "desc",
    }

    if explorer_api_key:
        params['apikey'] = explorer_api_key

    response = requests.get(explorer_api_url, params=params)

    try:
        data = response.json()

        if "error" in data:
            if data["statusCode"] == 404 or data["error"] == "Not Found":
                return []
            raise ExceptionNoRetries(data["error"])

        if "result" in data:
            if "Invalid API Key" in data["result"]:
                logger.error("Invalid API Key")
                raise ExceptionNoRetries(data["result"])
            if "rate limit" in data["result"]:
                logger.error("Explorer api max rate limit reached")
                raise ExceptionWithRetries(data["result"])

        return data["result"]
    except Exception:
        await sleep(5, 5)
        await get_account_transfer_tx_list(account_address, explorer_api_url)


class ExceptionNoRetries(Exception):
    pass


class ExceptionWithRetries(Exception):
    pass


async def get_last_action_tx(address: str, dst: str, chain: str):
    tx_list = await get_account_transfer_tx_list(account_address=address, chain=chain)

    last = None
    for tx in tx_list:
        if tx["from"].lower() == address.lower() and tx["to"].lower() == dst.lower() and tx["isError"] == "0":
            # function, dic = tc.decode_function_input(tx["input"]) # это для определения конкретных методов контракта
            # if "transfer(address,uint256)" in str(function):      # пока будем юзать конкретно факт взаимодействия с адресом
                last = tx
                break

    return last


async def checkLastIteration(interval: int, account, deposit_contract_address: str, chain: str, log_prefix: str):
    from datetime import datetime
    current_datetime = datetime.now()
    last_tx = await get_last_action_tx(address=account.address, dst=deposit_contract_address, chain=chain)
    if last_tx:
        tx_time = datetime.fromtimestamp(int(last_tx["timeStamp"]))
        time_passed = current_datetime - tx_time

        if time_passed.total_seconds() < interval:
            logger.info(f"{log_prefix} already done less then {interval} seconds ago, skipping")
            return False
        else:
            logger.info(f"{log_prefix} done more then {interval} seconds ago, working")
            return True
    else:
        return True