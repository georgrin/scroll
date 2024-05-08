import traceback
from loguru import logger
from settings import RETRY_COUNT, SCROLL_API_KEY
from utils.sleeping import sleep
from datetime import datetime
import requests
import json


def retry(func):
    async def wrapper(*args, **kwargs):
        retries = 0
        while retries <= RETRY_COUNT:
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                trace = traceback.format_exc()
                logger.error(f"Error | {e}\n{trace}")                
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
    explorers_data = {
        'zksync': {
            'url': 'https://block-explorer-api.mainnet.zksync.io/api',
        },
        'scroll': {
            'url': 'https://api.scrollscan.com/api',
            'api_key': SCROLL_API_KEY
        }
    }

    explorer_data = explorers_data.get(chain)
    if explorer_data is None:
        raise ValueError(f"Unsupported chain: {chain}")

    explorer_api_url = explorer_data.get('url')
    explorer_api_key = explorer_data.get('api_key')

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

    while True:
        try:
            response = requests.get(explorer_api_url, params=params)
            response.raise_for_status()
            data = response.json()

            if "result" not in data:
                # logger.error("No 'result' field in the response")
                raise Exception("Response does not contain 'result' field")

            if "Invalid API Key" in data["result"]:
                # logger.error("Invalid API Key")
                raise Exception(data["result"])
            if "rate limit" in data["result"]:
                # logger.error("Explorer api max rate limit reached")
                raise Exception(data["result"])

            if "error" in data:
                raise Exception(data["error"])

            return data["result"]

        except (requests.exceptions.HTTPError, json.decoder.JSONDecodeError, Exception) as e:
            logger.error(f"Error: {e}")
            await sleep(7)   

async def get_last_action_tx(address: str, dst: str, chain: str):
    tx_list = await get_account_transfer_tx_list(account_address=address, chain=chain)
    print(tx_list)
    last = None
    for tx in tx_list:
        if tx["from"].lower() == address.lower() and tx["to"].lower() == dst.lower() and tx["isError"] == "0":
            last = tx
            break

    return last


async def checkLastIteration(interval: int, account, deposit_contract_address: str, chain: str, log_prefix: str):
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
        logger.info(f"{log_prefix} previous TX not found, working")
        return True
