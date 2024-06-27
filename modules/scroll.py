import random
from datetime import datetime

import aiohttp

from loguru import logger
from eth_account.messages import encode_defunct
from aiohttp_socks import ProxyType, ProxyConnector, ChainProxyConnector

from settings import PROXIES
from utils.gas_checker import check_gas
from utils.helpers import retry
from .account import Account

from config import (
    BRIDGE_CONTRACTS,
    DEPOSIT_ABI,
    DEPOSIT_ECONOMY_ABI,
    WITHDRAW_ABI,
    ORACLE_ABI,
    SCROLL_TOKENS,
    WETH_ABI
)


def get_random_proxy():
    if PROXIES is None or len(PROXIES) == 0:
        return None
    else:
        return ProxyConnector.from_url(random.choice(PROXIES))


class Scroll(Account):
    def __init__(self, account_id: int, private_key: str, chain: str, recipient) -> None:
        super().__init__(account_id=account_id, private_key=private_key, chain=chain, recipient=recipient)
        self.connector = None

    @retry
    @check_gas
    async def deposit(
            self,
            min_amount: float,
            max_amount: float,
            decimal: int,
            all_amount: bool,
            min_percent: int,
            max_percent: int
    ):
        amount_wei, amount, balance = await self.get_amount(
            "ETH",
            min_amount,
            max_amount,
            decimal,
            all_amount,
            min_percent,
            max_percent
        )

        logger.info(f"[{self.account_id}][{self.address}] Bridge to Scroll | {amount} ETH")

        contract = self.get_contract(BRIDGE_CONTRACTS["deposit"], DEPOSIT_ABI)
        contract_oracle = self.get_contract(BRIDGE_CONTRACTS["oracle"], ORACLE_ABI)

        fee = await contract_oracle.functions.estimateCrossDomainMessageFee(168000).call()

        tx_data = await self.get_tx_data(amount_wei + fee, False)

        transaction = await contract.functions.sendMessage(
            self.address,
            amount_wei,
            "0x",
            168000,
        ).build_transaction(tx_data)

        signed_txn = await self.sign(transaction)

        txn_hash = await self.send_raw_transaction(signed_txn)

        await self.wait_until_tx_finished(txn_hash.hex())

    @retry
    @check_gas
    async def deposit_economy(
            self,
            min_amount: float,
            max_amount: float,
            decimal: int,
            all_amount: bool,
            min_percent: int,
            max_percent: int
    ):
        amount_wei, amount, balance = await self.get_amount(
            "ETH",
            min_amount,
            max_amount,
            decimal,
            all_amount,
            min_percent,
            max_percent
        )

        logger.info(f"[{self.account_id}][{self.address}] Bridge to Scroll | {amount} ETH")

        # TODO: добавить проверку, что мы отправляем не меньше, чем 0.01 ETH

        # You can only use "Economy" for deposit more than 0.01 ETH
        if amount_wei < 10000000000000000:
            raise ValueError(f"You can only use 'Economy' for deposit more than 0.01 ETH, try to send: {amount}")

        contract = self.get_contract(BRIDGE_CONTRACTS["deposit_economy"], DEPOSIT_ECONOMY_ABI)
        contract_oracle = self.get_contract(BRIDGE_CONTRACTS["oracle"], ORACLE_ABI)

        # Тут скорее всего неправильно считается комса для экономного депозита
        fee = await contract_oracle.functions.estimateCrossDomainMessageFee(168000).call()

        tx_data = await self.get_tx_data(amount_wei + fee, False)

        transaction = await contract.functions.depositETH().build_transaction(tx_data)

        signed_txn = await self.sign(transaction)

        txn_hash = await self.send_raw_transaction(signed_txn)

        await self.wait_until_tx_finished(txn_hash.hex())

    @retry
    @check_gas
    async def withdraw(
            self,
            min_amount: float,
            max_amount: float,
            decimal: int,
            all_amount: bool,
            min_percent: int,
            max_percent: int
    ):
        amount_wei, amount, balance = await self.get_amount(
            "ETH",
            min_amount,
            max_amount,
            decimal,
            all_amount,
            min_percent,
            max_percent
        )

        logger.info(f"[{self.account_id}][{self.address}] Bridge from Scroll | {amount} ETH")

        contract = self.get_contract(BRIDGE_CONTRACTS["withdraw"], WITHDRAW_ABI)

        tx_data = await self.get_tx_data(amount_wei)

        transaction = await contract.functions.withdrawETH(
            amount_wei,
            0
        ).build_transaction(tx_data)

        signed_txn = await self.sign(transaction)

        txn_hash = await self.send_raw_transaction(signed_txn)

        await self.wait_until_tx_finished(txn_hash.hex())

    @retry
    @check_gas
    async def wrap_eth(
            self,
            min_amount: float,
            max_amount: float,
            decimal: int,
            all_amount: bool,
            min_percent: int,
            max_percent: int
    ):
        amount_wei, amount, balance = await self.get_amount(
            "ETH",
            min_amount,
            max_amount,
            decimal,
            all_amount,
            min_percent,
            max_percent
        )

        weth_contract = self.get_contract(SCROLL_TOKENS["WETH"], WETH_ABI)

        logger.info(f"[{self.account_id}][{self.address}] Wrap {amount} ETH")

        tx_data = await self.get_tx_data(amount_wei)

        transaction = await weth_contract.functions.deposit().build_transaction(tx_data)

        signed_txn = await self.sign(transaction)

        txn_hash = await self.send_raw_transaction(signed_txn)

        await self.wait_until_tx_finished(txn_hash.hex())

    @retry
    @check_gas
    async def unwrap_eth(
            self,
            min_amount: float,
            max_amount: float,
            decimal: int,
            all_amount: bool,
            min_percent: int,
            max_percent: int
    ):
        amount_wei, amount, balance = await self.get_amount(
            "WETH",
            min_amount,
            max_amount,
            decimal,
            all_amount,
            min_percent,
            max_percent
        )

        weth_contract = self.get_contract(SCROLL_TOKENS["WETH"], WETH_ABI)

        logger.info(f"[{self.account_id}][{self.address}] Unwrap {amount} ETH")

        tx_data = await self.get_tx_data()

        transaction = await weth_contract.functions.withdraw(amount_wei).build_transaction(tx_data)

        signed_txn = await self.sign(transaction)

        txn_hash = await self.send_raw_transaction(signed_txn)

        await self.wait_until_tx_finished(txn_hash.hex())

    async def _check_signed_terms_of_use(self, connector) -> bool:
        url = "https://venus.scroll.io/v1/signature/address"

        params = {
            "address": self.address,
        }

        async with aiohttp.ClientSession(connector=connector) as session:
            response = await session.get(url=url, params=params)

            if response.status == 200:
                status = await response.json()

                if status["data"] and int(status["errcode"]) == 0:
                    return True
                else:
                    return False
            else:
                logger.error(f"[{self.account_id}][{self.address}][{self.chain}] Bad Scroll request")

                raise Exception(f"Bad Scroll request: {response.status}")

    async def _sign_terms_of_use(self, connector) -> bool:
        url = "https://venus.scroll.io/v1/signature/sign"

        message = "By signing this message, you acknowledge that you have read and understood the Scroll Sessions Terms of Use, Scroll Terms of Service and Privacy Policy, and agree to abide by all of the terms and conditions contained therein."

        message = encode_defunct(text=message)
        signed_message = self.w3.eth.account.sign_message(message, private_key=self.private_key)

        body = {
            "address": self.address,
            "signature": signed_message.signature.hex(),
            "timestamp": int(datetime.now().timestamp() * 1000)
        }

        async with aiohttp.ClientSession(connector=connector) as session:
            response = await session.post(url=url, json=body)

            if response.status == 200:
                status = await response.json()

                if int(status["errcode"]) == 0:
                    logger.info(
                        f"[{self.account_id}][{self.address}][{self.chain}] Scroll Terms of Use successfully signed: {status}")

                    return True
                else:
                    return False
            else:
                logger.error(f"[{self.account_id}][{self.address}][{self.chain}] Bad Scroll sign terms of use request")

                raise Exception(f"Bad Scroll sign terms of use request: {response.status}")

    @retry
    @check_gas
    async def sign_terms_of_use(self):
        connector = get_random_proxy()
        signed = await self._check_signed_terms_of_use(connector)

        if signed:
            logger.info(f"[{self.account_id}][{self.address}][{self.chain}] Scroll Terms of Use already signed")
            return False

        logger.info(f"[{self.account_id}][{self.address}][{self.chain}] Scroll Terms of Use haven't signed yet")

        return await self._sign_terms_of_use(connector)
