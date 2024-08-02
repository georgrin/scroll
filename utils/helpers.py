import asyncio
import random
import time
import traceback
from decimal import Decimal, ROUND_DOWN

import requests
import json

from itertools import chain as itertools_chain
from typing import Tuple, Type
from concurrent import futures
from inspect import iscoroutinefunction
from functools import wraps
from threading import Thread
from onecache import AsyncCacheDecorator
from loguru import logger
from datetime import datetime

from settings import RETRY_COUNT, SCROLL_API_KEY, EXPLORER_CACHE_MS, ETHEREUM_API_KEY
from utils.sleeping import sleep


def retry_sync(times: int, exceptions: Tuple[Type[Exception]] = Exception, sleep_from: int = 10, sleep_to: int = 20):
    """
    Retry Decorator
    Retries the wrapped function/method `times` times if the exceptions listed
    in ``exceptions`` are thrown
    :param times: The number of times to repeat the wrapped function/method
    :param exceptions: Lists of exceptions that trigger a retry attempt
    """

    def decorator(func):
        def newfn(*args, **kwargs):
            attempt = 0
            while attempt < times:
                try:
                    return func(*args, **kwargs)
                except exceptions as ex:
                    delay = random.randint(sleep_from, sleep_to)

                    logger.debug(
                        'Exception thrown when attempting to run %s, attempt '
                        '%d of %d, wait %i second before new attempt'
                        ', error: %s' % (str(func).split()[1], attempt + 1, times, delay, ex)
                    )
                    attempt += 1
                    time.sleep(delay)
                    return func(*args, **kwargs)

        return newfn

    return decorator


def retry(func, sleep_from: int = 10, sleep_to: int = 20):
    async def wrapper(*args, **kwargs):
        retries = 0
        while retries <= RETRY_COUNT:
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                trace = traceback.format_exc()
                logger.error(f"Error | {e}\n{trace}")
                await sleep(sleep_from, sleep_to)
                retries += 1

    return wrapper


def remove_wallet(private_key: str):
    with open("accounts.txt", "r") as file:
        lines = file.readlines()

    with open("accounts.txt", "w") as file:
        for line in lines:
            if private_key not in line:
                file.write(line)


@AsyncCacheDecorator(ttl=EXPLORER_CACHE_MS)
async def get_eth_usd_price(chain: str):
    explorers_data = {
        "scroll": {
            "url": "https://api.scrollscan.com/api",
            "api_key": SCROLL_API_KEY
        }
    }

    explorer_data = explorers_data.get(chain)
    if explorer_data is None:
        raise ValueError(f"Unsupported chain: {chain}")

    explorer_api_url = explorer_data.get("url")
    explorer_api_key = explorer_data.get("api_key")

    params = {
        "module": "stats",
        "action": "ethprice",
    }

    if explorer_api_key:
        params["apikey"] = explorer_api_key

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

            return float(data["result"]["ethusd"])
        except (requests.exceptions.HTTPError, json.decoder.JSONDecodeError, Exception) as e:
            logger.error(f"Error get_eth_usd_price: {e}")
            await sleep(10)


@AsyncCacheDecorator(ttl=EXPLORER_CACHE_MS)
async def get_account_transfer_tx_list(account_address: str, chain: str):
    explorers_data = {
        'zksync': {
            'url': 'https://block-explorer-api.mainnet.zksync.io/api',
        },
        'scroll': {
            'url': 'https://api.scrollscan.com/api',
            'api_key': SCROLL_API_KEY
        },
        'ethereum': {
            'url': 'https://api.etherscan.io/api',
            'api_key': ETHEREUM_API_KEY
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

            if data["result"]:
                last_tx = data["result"][0]
                logger.info(f"Last known tx for address in block {last_tx['blockNumber']}, hash: {last_tx['hash']}")
                # await sleep(3)

            return data["result"]

        except (requests.exceptions.HTTPError, json.decoder.JSONDecodeError, Exception) as e:
            logger.error(f"Error get_account_transfer_tx_list: {e}")
            await sleep(7)


async def get_last_action(address: str, dst: str, chain: str):
    tx_list = await get_account_transfer_tx_list(account_address=address, chain=chain)
    last = None

    for tx in tx_list:
        print(tx)
        if tx["from"].lower() == address.lower() and tx["to"].lower() == dst.lower() and tx["isError"] == "0":
            last = tx
            break
    return last


async def get_action_tx_count(address: str, dst: str, chain: str):
    tx_list = await get_account_transfer_tx_list(account_address=address, chain=chain)
    action_tx_list = []
    for tx in tx_list:
        if tx["from"].lower() == address.lower() and tx["to"].lower() == dst.lower() and tx["isError"] == "0":
            action_tx_list.append(tx)

    return len(action_tx_list)


async def get_last_tx(address: str, chain: str):
    tx_list = await get_account_transfer_tx_list(account_address=address, chain=chain)
    return tx_list[0] if len(tx_list) > 1 else None


async def get_last_action_tx(address: str, dst: str, chain: str):
    tx_list = await get_account_transfer_tx_list(account_address=address, chain=chain)
    last = None
    for tx in tx_list:
        if tx["from"].lower() == address.lower() and tx["to"].lower() == dst.lower() and tx["isError"] == "0":
            last = tx
            break

    return last


async def checkLastIteration(interval: int,
                             account,
                             deposit_contract_address: str,
                             chain: str,
                             log_prefix: str,
                             log: bool = True):
    current_datetime = datetime.now()
    last_tx = await get_last_action_tx(address=account.address, dst=deposit_contract_address, chain=chain)
    if last_tx:
        tx_time = datetime.fromtimestamp(int(last_tx["timeStamp"]))
        time_passed = current_datetime - tx_time

        if time_passed.total_seconds() < interval or interval < 0:
            if log:
                logger.info(f"{log_prefix} already done less then {interval} seconds ago, skipping")
            return False
        else:
            if log:
                logger.info(f"{log_prefix} done more then {interval} seconds ago, working")
            return True
    else:
        if log:
            logger.info(f"{log_prefix} previous TX not found, working")
        return True


def floor(value: Decimal, places=6) -> Decimal:
    return value.quantize(Decimal(10) ** -places, rounding=ROUND_DOWN)


def float_floor(value: Decimal, places=6):
    return float(floor(Decimal(value), places=places))


def find_duplicate_in_dict(dict):
    # finding duplicate values
    # from dictionary using set
    rev_dict = {}
    for key, value in dict.items():
        rev_dict.setdefault(value, set()).add(key)

    return set(itertools_chain.from_iterable(
        values for key, values in rev_dict.items()
        if len(values) > 1))


def timeout(
        timeout_duration: float = None, exception_to_raise: Type[Exception] = TimeoutError,
        error_msg="Timeout reached"
):
    """
    Wraps a function to raise the specified exception if execution time
    is greater than the specified timeout.

    Works with both synchronous and asynchronous callables, but with synchronous ones will introduce
    some overhead due to the backend use of threads and asyncio.

        :param float timeout_duration: Timeout duration in seconds. If none callable won't time out.
        :param Type[Exception] exception_to_raise: Exception to raise when the callable times out.
            Defaults to TimeoutError.
        :return: The decorated function.
        :rtype: callable
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            async def async_func():
                return func(*args, **kwargs)

            thread = _LoopWrapper()
            thread.start()
            future = asyncio.run_coroutine_threadsafe(async_func(), thread.loop)
            try:
                result = future.result(timeout=timeout_duration)
            except futures.TimeoutError:
                thread.stop_loop()
                raise exception_to_raise(error_msg)
            thread.stop_loop()
            return result

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                value = await asyncio.wait_for(
                    func(*args, **kwargs), timeout=timeout_duration
                )
                return value
            except asyncio.TimeoutError:
                raise exception_to_raise(error_msg)

        if iscoroutinefunction(func):
            return async_wrapper
        return wrapper

    return decorator


class _LoopWrapper(Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.loop = asyncio.new_event_loop()

    def run(self) -> None:
        self.loop.run_forever()
        self.loop.call_soon_threadsafe(self.loop.close)

    def stop_loop(self):
        for task in asyncio.all_tasks(self.loop):
            task.cancel()
        self.loop.call_soon_threadsafe(self.loop.stop)
